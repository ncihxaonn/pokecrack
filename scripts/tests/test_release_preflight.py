from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "verify_release_preflight.py"
SPEC = importlib.util.spec_from_file_location("verify_release_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.evidence_dir = self.root / "evidence"
        self.evidence_dir.mkdir(mode=0o700)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.artifact = self.evidence_dir / "backup.sql.gz.age"
        self.restore = self.evidence_dir / "restore-report.json"
        self.artifact.write_bytes(b"encrypted backup")
        self.restore.write_text("sanitized restore evidence\n", encoding="utf-8")
        for path in (self.artifact, self.restore):
            path.chmod(0o600)
        self.sha = "a" * 40
        self.fingerprint = "SHA256:" + ("A" * 43)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def digest(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def manifest(self) -> tuple[Path, str]:
        manifest_dir = self.evidence_dir / "ci"
        manifest_dir.mkdir(mode=0o700)
        stages = []
        for stage in MODULE.CI_STAGES:
            log = manifest_dir / f"{stage}.log"
            log.write_text(f"{stage} passed\n", encoding="utf-8")
            log.chmod(0o600)
            stages.append({"name": stage, "exit_code": 0, "log": log.name})
        for name, value in (
            ("postgres-meta-image.txt", MODULE.POSTGRES_META_IMAGE),
            ("gitleaks-image.txt", MODULE.GITLEAKS_TOOL.removeprefix("docker-image:")),
        ):
            image = manifest_dir / name
            image.write_text(f"{value}\n", encoding="utf-8")
            image.chmod(0o600)
        payload = {
            "schema_version": 1,
            "runner_version": 1,
            "status": "passed",
            "exit_code": 0,
            "expected_sha": self.sha,
            "actual_sha": self.sha,
            "repository": MODULE.REPOSITORY,
            "stages": stages,
            "tools": {
                **{
                    name: "available"
                    for name in (
                        "bash",
                        "git",
                        "python3",
                        "node",
                        "pnpm",
                        "npx",
                        "uv",
                        "docker",
                        "shellcheck",
                    )
                },
                "gitleaks": MODULE.GITLEAKS_TOOL,
            },
        }
        path = manifest_dir / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)
        return path, self.digest(path)

    def release_evidence(self, manifest_sha: str) -> Path:
        created = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload = {
            "schema_version": 1,
            "repository": MODULE.REPOSITORY,
            "release_sha": self.sha,
            "ci_manifest_sha256": manifest_sha,
            "target": {
                "supabase_project_ref": MODULE.PROJECT_REF,
                "service_set": "tcgdex",
                "vps_host_key_fingerprint": self.fingerprint,
                "vps_deploy_path": MODULE.VPS_DEPLOY_PATH,
            },
            "approval": {"recorded": True, "reference": "protected-environment-approval"},
            "backup": {
                "reference": "encrypted-backup-reference",
                "encrypted": True,
                "isolated_restore_verified": True,
                "retention_verified": True,
                "created_at": created,
                "artifact_path": str(self.artifact),
                "artifact_sha256": self.digest(self.artifact),
                "restore_evidence_path": str(self.restore),
                "restore_evidence_sha256": self.digest(self.restore),
            },
            "permissions": {
                "runner_has_no_production_credentials": True,
                "backup_credential_is_separate": True,
                "worker_credential_is_separate": True,
                "backup_role_noinherit": True,
                "backup_role_cannot_read_gate_rows": True,
                "production_mutation_requires_owner_approval": True,
            },
        }
        path = self.evidence_dir / "release-evidence.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_manifest_and_release_evidence_are_bound(self) -> None:
        manifest, manifest_sha = self.manifest()
        evidence = self.release_evidence(manifest_sha)
        payload = MODULE.validate_release_evidence(
            evidence,
            self.checkout,
            self.sha,
            manifest_sha,
            MODULE.PROJECT_REF,
            "tcgdex",
            self.fingerprint,
            MODULE.VPS_DEPLOY_PATH,
            24.0,
        )
        self.assertEqual(payload["backup_reference"], "encrypted-backup-reference")
        MODULE.validate_ci_manifest(manifest, self.checkout, self.sha)

    def test_manifest_rejects_a_failed_stage(self) -> None:
        manifest, manifest_sha = self.manifest()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["stages"][2]["exit_code"] = 1
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        manifest.chmod(0o600)
        with self.assertRaises(MODULE.PreflightError):
            MODULE.validate_ci_manifest(manifest, self.checkout, self.sha)

    def test_release_evidence_rejects_unencrypted_backup(self) -> None:
        manifest, manifest_sha = self.manifest()
        evidence = self.release_evidence(manifest_sha)
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        payload["backup"]["encrypted"] = False
        evidence.write_text(json.dumps(payload), encoding="utf-8")
        evidence.chmod(0o600)
        with self.assertRaises(MODULE.PreflightError):
            MODULE.validate_release_evidence(
                evidence,
                self.checkout,
                self.sha,
                manifest_sha,
                MODULE.PROJECT_REF,
                "tcgdex",
                self.fingerprint,
                MODULE.VPS_DEPLOY_PATH,
                24.0,
            )

    def test_release_evidence_rejects_checksum_drift(self) -> None:
        _, manifest_sha = self.manifest()
        evidence = self.release_evidence(manifest_sha)
        self.artifact.write_bytes(b"changed backup")
        self.artifact.chmod(0o600)
        with self.assertRaises(MODULE.PreflightError):
            MODULE.validate_release_evidence(
                evidence,
                self.checkout,
                self.sha,
                manifest_sha,
                MODULE.PROJECT_REF,
                "tcgdex",
                self.fingerprint,
                MODULE.VPS_DEPLOY_PATH,
                24.0,
            )

    def test_preflight_has_no_production_mutation_entrypoint(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "SUPABASE_ACCESS_TOKEN",
            "run_supabase_migrations.py apply",
            "deploy.sh",
            "ssh ",
            "vercel --prod",
        ):
            self.assertNotIn(forbidden, source)

    def test_release_gate_requires_the_approved_scanner_digest(self) -> None:
        source = (ROOT / "scripts" / "run_ci_checks.sh").read_text(encoding="utf-8")
        self.assertIn(MODULE.GITLEAKS_TOOL.removeprefix("docker-image:"), source)
        self.assertNotIn("POKECRACK_GITLEAKS_IMAGE", source)

    def test_origin_pattern_accepts_github_checkout_variants_only(self) -> None:
        for origin in (
            "https://github.com/ncihxaonn/pokecrack",
            "https://github.com/ncihxaonn/pokecrack.git",
        ):
            with self.subTest(origin=origin):
                self.assertIsNotNone(MODULE.ORIGIN_PATTERN.fullmatch(origin))
        for origin in (
            "http://github.com/ncihxaonn/pokecrack",
            "https://github.com/other-owner/pokecrack",
            "https://user:token@github.com/ncihxaonn/pokecrack",
        ):
            with self.subTest(origin=origin):
                self.assertIsNone(MODULE.ORIGIN_PATTERN.fullmatch(origin))


if __name__ == "__main__":
    unittest.main()
