#!/usr/bin/env python3
"""Verify non-secret evidence before an approved PokeCrack release mutation.

This command is intentionally read-only. It verifies that a clean checkout is
the exact current ``origin/main`` commit, that the canonical CI evidence covers
every stage, and that an operator-supplied evidence record binds the same SHA
to the approved Supabase/VPS targets, a fresh encrypted backup, an isolated
restore drill, and least-privilege/approval attestations. It never calls a
provider, opens SSH, applies migrations, or deploys a worker.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import math
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


REPOSITORY = "ncihxaonn/pokecrack"
ORIGIN = "https://github.com/ncihxaonn/pokecrack.git"
ORIGIN_PATTERN = re.compile(r"https://github\.com/ncihxaonn/pokecrack(?:\.git)?\Z")
PROJECT_REF = "wohnphsxlquhhknuthrj"
VPS_DEPLOY_PATH = "/home/codex/pokecrack"
POSTGRES_META_IMAGE = "ghcr.io/supabase/postgres-meta@sha256:cef71ba901751dcc242cc685cf13786935ea8926820fb342f23bb0fbef77de5a"
GITLEAKS_TOOL = "docker-image:ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
SERVICE_SETS = frozenset({"tcgdex", "tcgdex-nostr", "tcgdex-bluesky"})
CI_STAGES = (
    "web",
    "worker",
    "auth-browser",
    "database",
    "container-worker",
    "repository-policy",
    "deployment-contracts",
)
RELEASE_SHA = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}\Z")
HOST_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/=]{20,100}\Z")
UTC_TIMESTAMP = re.compile(r"[0-9]{8}T[0-9]{6}Z\Z")


class PreflightError(ValueError):
    """A required release evidence contract was not satisfied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)


def _safe_absolute(path: Path, label: str) -> Path:
    _require(path.is_absolute(), f"{label} must be an absolute path")
    _require(".." not in path.parts, f"{label} must not contain ..")
    return path


def _outside_checkout(path: Path, checkout: Path, label: str) -> None:
    resolved_path = path.resolve(strict=False)
    resolved_checkout = checkout.resolve()
    _require(
        resolved_path != resolved_checkout and resolved_checkout not in resolved_path.parents,
        f"{label} must be outside the checkout",
    )


def _private_file(path: Path, label: str, *, nonempty: bool = False) -> Path:
    _safe_absolute(path, label)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PreflightError(f"{label} is unavailable") from exc
    _require(not stat.S_ISLNK(metadata.st_mode), f"{label} must not be a symlink")
    _require(stat.S_ISREG(metadata.st_mode), f"{label} must be a regular file")
    _require(metadata.st_uid == os.geteuid(), f"{label} must be owned by this user")
    _require(
        stat.S_IMODE(metadata.st_mode) & 0o077 == 0,
        f"{label} must be inaccessible to group and other users",
    )
    if nonempty:
        _require(metadata.st_size > 0, f"{label} must not be empty")
    return path


def _read_json(path: Path, checkout: Path, label: str) -> tuple[dict[str, Any], Path]:
    _outside_checkout(path, checkout, label)
    private_path = _private_file(path, label)
    try:
        payload = json.loads(private_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"{label} is not valid UTF-8 JSON") from exc
    _require(isinstance(payload, dict), f"{label} must contain a JSON object")
    return payload, private_path


def _sha256_file(path: Path, label: str) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise PreflightError(f"could not hash {label}") from exc
    return digest.hexdigest()


def _git(checkout: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        command = " ".join(arguments)
        raise PreflightError(f"git {command} failed")
    return result.stdout.strip()


def validate_checkout(checkout: Path, sha: str) -> Path:
    checkout = checkout.resolve()
    _require(RELEASE_SHA.fullmatch(sha) is not None, "--sha must be a 40-character lowercase SHA")
    _require((checkout / ".git").exists(), "checkout does not contain a Git repository")
    _require(not (checkout / ".git").is_symlink(), "checkout .git entry must not be a symlink")
    _require(ORIGIN_PATTERN.fullmatch(_git(checkout, "remote", "get-url", "origin")) is not None, "unexpected repository origin")
    _require(_git(checkout, "rev-parse", "--verify", "HEAD^{commit}") == sha, "HEAD does not match --sha")
    _require(
        _git(checkout, "rev-parse", "--verify", "refs/remotes/origin/main") == sha,
        "origin/main does not match --sha",
    )
    _require(_git(checkout, "status", "--porcelain", "--untracked-files=all") == "", "checkout is not clean")
    return checkout


def validate_ci_manifest(path: Path, checkout: Path, sha: str) -> tuple[dict[str, Any], str, Path]:
    payload, manifest_path = _read_json(path, checkout, "CI manifest")
    _require(payload.get("schema_version") == 1, "CI manifest schema_version must be 1")
    _require(payload.get("status") == "passed", "CI manifest status is not passed")
    _require(payload.get("exit_code") == 0, "CI manifest exit_code is not zero")
    _require(payload.get("expected_sha") == sha, "CI manifest expected_sha does not match release SHA")
    _require(payload.get("actual_sha") == sha, "CI manifest actual_sha does not match release SHA")
    _require(payload.get("repository") == REPOSITORY, "CI manifest repository is not PokeCrack")
    _require(isinstance(payload.get("runner_version"), int), "CI manifest runner_version is missing")

    stages = payload.get("stages")
    _require(isinstance(stages, list), "CI manifest stages must be a list")
    stage_names = [entry.get("name") for entry in stages if isinstance(entry, dict)]
    _require(stage_names == list(CI_STAGES), "CI manifest must contain every canonical stage in order")
    manifest_directory = manifest_path.parent.resolve()
    for entry in stages:
        _require(isinstance(entry, dict), "CI manifest contains a malformed stage")
        _require(entry.get("exit_code") == 0, f"CI stage failed: {entry.get('name')}")
        log_name = entry.get("log")
        _require(
            isinstance(log_name, str)
            and Path(log_name).name == log_name
            and log_name.endswith(".log"),
            f"CI stage log is not a safe filename: {entry.get('name')}",
        )
        log_path = manifest_directory / log_name
        _private_file(log_path, f"CI stage log {entry.get('name')}", nonempty=True)
        _outside_checkout(log_path, checkout, "CI stage log")

    image_evidence = {
        "database": ("postgres-meta-image.txt", POSTGRES_META_IMAGE),
        "repository-policy": ("gitleaks-image.txt", GITLEAKS_TOOL.removeprefix("docker-image:")),
    }
    for stage_name, (filename, expected) in image_evidence.items():
        image_path = manifest_directory / filename
        _private_file(image_path, f"{stage_name} image evidence", nonempty=True)
        _outside_checkout(image_path, checkout, f"{stage_name} image evidence")
        _require(image_path.read_text(encoding="utf-8").strip() == expected, f"{stage_name} image evidence is not pinned")

    tools = payload.get("tools")
    _require(isinstance(tools, dict), "CI manifest tools must be an object")
    required_tools = {"bash", "git", "python3", "node", "pnpm", "npx", "uv", "docker", "shellcheck", "gitleaks"}
    _require(required_tools <= tools.keys(), "CI manifest is missing tool versions")
    _require(all(isinstance(tools[name], str) and tools[name] != "unavailable" for name in required_tools), "CI manifest has unavailable tools")
    _require(tools["gitleaks"] == GITLEAKS_TOOL, "CI manifest does not prove the approved Gitleaks image")
    return payload, _sha256_file(manifest_path, "CI manifest"), manifest_path


def _require_true(mapping: dict[str, Any], key: str, label: str) -> None:
    _require(mapping.get(key) is True, f"{label}.{key} must be true")


def _parse_backup_time(value: Any) -> datetime:
    _require(isinstance(value, str) and UTC_TIMESTAMP.fullmatch(value) is not None, "backup.created_at must be YYYYMMDDTHHMMSSZ")
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PreflightError("backup.created_at is not a real UTC timestamp") from exc


def validate_release_evidence(
    path: Path,
    checkout: Path,
    sha: str,
    manifest_sha256: str,
    project_ref: str,
    service_set: str,
    vps_host_key_fingerprint: str,
    vps_deploy_path: str,
    max_backup_age_hours: float,
) -> dict[str, Any]:
    payload, evidence_path = _read_json(path, checkout, "release evidence")
    _require(payload.get("schema_version") == 1, "release evidence schema_version must be 1")
    _require(payload.get("repository") == REPOSITORY, "release evidence repository is not PokeCrack")
    _require(payload.get("release_sha") == sha, "release evidence release_sha does not match --sha")
    _require(payload.get("ci_manifest_sha256") == manifest_sha256, "release evidence is not bound to the CI manifest")

    target = payload.get("target")
    _require(isinstance(target, dict), "release evidence target must be an object")
    _require(target.get("supabase_project_ref") == project_ref == PROJECT_REF, "Supabase project target is not the approved project")
    _require(target.get("service_set") == service_set and service_set in SERVICE_SETS, "worker service set is not approved")
    _require(target.get("vps_host_key_fingerprint") == vps_host_key_fingerprint, "VPS host fingerprint does not match the supplied target")
    _require(HOST_FINGERPRINT.fullmatch(vps_host_key_fingerprint) is not None, "VPS host fingerprint is malformed")
    _require(target.get("vps_deploy_path") == vps_deploy_path == VPS_DEPLOY_PATH, "VPS deploy path is not the approved target")

    approval = payload.get("approval")
    _require(isinstance(approval, dict), "release evidence approval must be an object")
    _require_true(approval, "recorded", "approval")
    approval_reference = approval.get("reference")
    _require(isinstance(approval_reference, str) and REFERENCE.fullmatch(approval_reference) is not None, "approval.reference is malformed")

    backup = payload.get("backup")
    _require(isinstance(backup, dict), "release evidence backup must be an object")
    backup_reference = backup.get("reference")
    _require(isinstance(backup_reference, str) and REFERENCE.fullmatch(backup_reference) is not None, "backup.reference is malformed")
    _require_true(backup, "encrypted", "backup")
    _require_true(backup, "isolated_restore_verified", "backup")
    _require_true(backup, "retention_verified", "backup")
    created_at = _parse_backup_time(backup.get("created_at"))
    _require(max_backup_age_hours > 0, "--max-backup-age-hours must be positive")
    _require(math.isfinite(max_backup_age_hours), "--max-backup-age-hours must be finite")
    age = datetime.now(timezone.utc) - created_at
    _require(age >= timedelta(seconds=-300), "backup.created_at is in the future")
    _require(age <= timedelta(hours=max_backup_age_hours), "backup is older than the permitted release window")

    artifact_sha256 = backup.get("artifact_sha256")
    restore_sha256 = backup.get("restore_evidence_sha256")
    _require(isinstance(artifact_sha256, str) and SHA256.fullmatch(artifact_sha256) is not None, "backup.artifact_sha256 is malformed")
    _require(isinstance(restore_sha256, str) and SHA256.fullmatch(restore_sha256) is not None, "backup.restore_evidence_sha256 is malformed")
    artifact_path = Path(backup.get("artifact_path", ""))
    restore_path = Path(backup.get("restore_evidence_path", ""))
    for candidate, label, expected in (
        (artifact_path, "backup artifact", artifact_sha256),
        (restore_path, "restore evidence", restore_sha256),
    ):
        _outside_checkout(candidate, checkout, label)
        _private_file(candidate, label, nonempty=True)
        _require(_sha256_file(candidate, label) == expected, f"{label} checksum does not match release evidence")

    permissions = payload.get("permissions")
    _require(isinstance(permissions, dict), "release evidence permissions must be an object")
    for key in (
        "runner_has_no_production_credentials",
        "backup_credential_is_separate",
        "worker_credential_is_separate",
        "backup_role_noinherit",
        "backup_role_cannot_read_gate_rows",
        "production_mutation_requires_owner_approval",
    ):
        _require_true(permissions, key, "permissions")

    return {
        "manifest_path": str(evidence_path),
        "backup_reference": backup_reference,
        "backup_created_at": backup.get("created_at"),
        "approval_reference": approval_reference,
        "target": {
            "supabase_project_ref": project_ref,
            "service_set": service_set,
            "vps_host_key_fingerprint": vps_host_key_fingerprint,
            "vps_deploy_path": vps_deploy_path,
        },
    }


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    _require(RELEASE_SHA.fullmatch(arguments.sha) is not None, "--sha must be a 40-character lowercase SHA")
    _require(arguments.project_ref == PROJECT_REF, "--project-ref is not the approved PokeCrack project")
    _require(arguments.service_set in SERVICE_SETS, "--service-set is not approved")
    _require(arguments.vps_deploy_path == VPS_DEPLOY_PATH, "--vps-deploy-path is not the approved target")
    checkout = validate_checkout(arguments.checkout, arguments.sha)
    manifest, manifest_sha256, manifest_path = validate_ci_manifest(arguments.ci_manifest, checkout, arguments.sha)
    release = validate_release_evidence(
        arguments.release_evidence,
        checkout,
        arguments.sha,
        manifest_sha256,
        arguments.project_ref,
        arguments.service_set,
        arguments.vps_host_key_fingerprint,
        arguments.vps_deploy_path,
        arguments.max_backup_age_hours,
    )
    return {
        "ok": True,
        "repository": REPOSITORY,
        "release_sha": arguments.sha,
        "checkout": str(checkout),
        "ci_manifest": {"path": str(manifest_path), "sha256": manifest_sha256, "stages": len(manifest["stages"])},
        "target": release["target"],
        "backup": {
            "reference": release["backup_reference"],
            "created_at": release["backup_created_at"],
            "encrypted": True,
            "isolated_restore_verified": True,
        },
        "approval_reference": release["approval_reference"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True, help="exact 40-character main commit SHA")
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--ci-manifest", type=Path, required=True)
    parser.add_argument("--release-evidence", type=Path, required=True)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--service-set", required=True)
    parser.add_argument("--vps-host-key-fingerprint", required=True)
    parser.add_argument("--vps-deploy-path", required=True)
    parser.add_argument("--max-backup-age-hours", type=float, default=24.0)
    arguments = parser.parse_args()
    try:
        print(json.dumps(run(arguments), ensure_ascii=False, indent=2))
    except (OSError, PreflightError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
