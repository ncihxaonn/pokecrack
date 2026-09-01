from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ROOT = REPOSITORY_ROOT / "deploy"


def load_retention_module():
    module_path = DEPLOY_ROOT / "lib" / "prune_backups.py"
    spec = importlib.util.spec_from_file_location("prune_backups", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_database_url_module():
    module_path = DEPLOY_ROOT / "lib" / "run_with_database_url.py"
    spec = importlib.util.spec_from_file_location("run_with_database_url", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_nostr_preflight_module():
    database_url_module = load_database_url_module()
    sys.modules["run_with_database_url"] = database_url_module
    module_path = DEPLOY_ROOT / "lib" / "verify_nostr_release.py"
    spec = importlib.util.spec_from_file_location("verify_nostr_release", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class ShellPortabilityTests(unittest.TestCase):
    def test_bash_3_compatible_helpers_report_bsd_or_gnu_metadata(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            fixture = Path(temporary) / "fixture"
            fixture.write_bytes(b"fixture")
            fixture.chmod(0o600)
            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    'source "$1"; pokecrack_stat_mode "$2"; '
                    'pokecrack_stat_uid "$2"; pokecrack_stat_size "$2"; '
                    'pokecrack_lowercase "Bash-BSD-GNU"',
                    "bash",
                    str(DEPLOY_ROOT / "lib" / "shell_portability.sh"),
                    str(fixture),
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.splitlines(),
                ["600", str(os.geteuid()), "7", "bash-bsd-gnu"],
            )

            fake_bin = Path(temporary) / "bin"
            fake_bin.mkdir()
            digest = "a" * 64
            write_executable(
                fake_bin / "shasum",
                f"""#!/bin/bash
[[ $1 == -a && $2 == 256 ]]
printf '%s  %s\n' '{digest}' "$3"
""",
            )
            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    'source "$1"; pokecrack_sha256_file "$2"',
                    "bash",
                    str(DEPLOY_ROOT / "lib" / "shell_portability.sh"),
                    str(fixture),
                ],
                check=False,
                text=True,
                capture_output=True,
                env={"PATH": str(fake_bin)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), digest)

    def test_shell_entrypoints_do_not_use_known_gnu_or_bash_4_only_forms(self) -> None:
        scripts = list(DEPLOY_ROOT.glob("*.sh"))
        scripts.extend((DEPLOY_ROOT / "scripts").glob("*.sh"))
        source = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
        for forbidden in (
            "${value,,}",
            "${2,,}",
            "readlink --",
            "mv -Tf --",
            "chmod 0600 --",
            "chmod 0700 --",
            "gzip --test --",
            'wait -n "${pids[@]}"',
            "timeout 10s opencli doctor",
        ):
            self.assertNotIn(forbidden, source)


class WorkflowSecurityPolicyTests(unittest.TestCase):
    def test_ci_audits_both_python_lockfiles_with_a_pinned_auditor(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertGreaterEqual(workflow.count("pip-audit==2.10.1"), 2)
        self.assertIn("pokecrack-worker-audit.txt", workflow)
        self.assertIn("pokecrack-browser-audit.txt", workflow)

    def test_worker_deploy_workflow_forwards_only_explicit_reviewed_service_sets(
        self,
    ) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "deploy-worker.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("service_set:", workflow)
        self.assertIn("- tcgdex", workflow)
        self.assertIn("- tcgdex-nostr", workflow)
        self.assertIn("retire_nostr:", workflow)
        self.assertIn("REQUESTED_SHA: ${{ inputs.confirm_sha }}", workflow)
        self.assertIn("REQUESTED_SERVICE_SET: ${{ inputs.service_set }}", workflow)
        self.assertIn("REQUESTED_RETIRE_NOSTR: ${{ inputs.retire_nostr }}", workflow)
        self.assertIn('[[ "$REQUESTED_SHA" == "$GITHUB_SHA" ]]', workflow)
        self.assertIn("tcgdex|tcgdex-nostr", workflow)
        self.assertIn("VPS_NOSTR_ENV_FILE:", workflow)
        self.assertIn('--nostr-env-file "$nostr_env_file"', workflow)
        self.assertIn("deploy_args+=(--retire-nostr)", workflow)
        self.assertIn('--service-set "$service_set"', workflow)
        self.assertNotIn('[[ "${{ inputs.confirm_sha }}"', workflow)
        self.assertNotIn('[[ "${{ inputs.service_set }}"', workflow)
        self.assertNotIn('[[ "${{ inputs.retire_nostr }}"', workflow)
        checkout = workflow.index('git -C "$repository" checkout --detach "$sha"')
        deploy = workflow.index('"$repository/deploy/scripts/deploy.sh" "$sha"')
        self.assertLess(checkout, deploy)
        self.assertNotIn("- full", workflow)

    def test_database_migration_workflow_never_interpolates_dispatch_inputs_in_shell(
        self,
    ) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "migrate-database.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("CONFIRM_SHA: ${{ inputs.confirm_sha }}", workflow)
        self.assertIn("BACKUP_REFERENCE: ${{ inputs.backup_reference }}", workflow)
        self.assertIn('[[ "$CONFIRM_SHA" == "$GITHUB_SHA" ]]', workflow)
        self.assertIn('[[ "$CONFIRM_SHA" =~ ^[0-9a-f]{40}$ ]]', workflow)
        self.assertIn(
            '[[ "$BACKUP_REFERENCE" =~ ^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$ ]]',
            workflow,
        )
        self.assertNotIn('[[ "${{ inputs.confirm_sha }}"', workflow)
        self.assertNotIn('[[ -n "${{ inputs.backup_reference }}"', workflow)

    def test_database_migration_workflow_uses_only_the_scoped_management_api_token(
        self,
    ) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "migrate-database.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("SUPABASE_DB_URL", workflow)
        self.assertIn("SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}", workflow)
        self.assertIn("SUPABASE_PROJECT_REF: ${{ vars.SUPABASE_PROJECT_REF }}", workflow)
        self.assertIn("scripts/run_supabase_migrations.py list", workflow)
        self.assertIn("scripts/run_supabase_migrations.py preview", workflow)
        self.assertIn("scripts/run_supabase_migrations.py apply", workflow)
        self.assertIn("scripts/run_supabase_migrations.py verify", workflow)
        self.assertNotIn("db push", workflow)
        self.assertNotIn("--db-url", workflow)


class BackupRetentionTests(unittest.TestCase):
    def test_keeps_seven_daily_and_four_weekly_representatives(self) -> None:
        retention = load_retention_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary)
            names = [
                "pokecrack-20260720T010000Z.sql.gz",
                "pokecrack-20260721T010000Z.sql.gz",
                "pokecrack-20260722T010000Z.sql.gz",
                "pokecrack-20260723T010000Z.sql.gz",
                "pokecrack-20260724T010000Z.sql.gz",
                "pokecrack-20260725T010000Z.sql.gz",
                "pokecrack-20260726T010000Z.sql.gz",
                "pokecrack-20260727T010000Z.sql.gz",
                "pokecrack-20260728T010000Z.sql.gz",
                "pokecrack-20260729T010000Z.sql.gz",
                "pokecrack-20260729T020000Z.sql.gz",
            ]
            paths = []
            for name in names:
                path = root / name
                path.write_bytes(b"backup")
                paths.append(path)
            unrelated = root / "do-not-touch.sql.gz"
            unrelated.write_bytes(b"unrelated")

            selected = retention.select_backups_to_delete(
                paths + [unrelated], daily=7, weekly=4
            )
            selected_names = {path.name for path in selected}

            parsed = [(path, retention.parse_backup_timestamp(path)) for path in paths]
            daily_dates = sorted(
                {timestamp.date() for _, timestamp in parsed}, reverse=True
            )[:7]
            expected_keep = {
                max(
                    (item for item in parsed if item[1].date() == day),
                    key=lambda item: item[1],
                )[0].name
                for day in daily_dates
            }
            weekly_keys = []
            for _, timestamp in sorted(parsed, key=lambda item: item[1], reverse=True):
                iso = timestamp.isocalendar()
                key = (iso.year, iso.week)
                if key not in weekly_keys:
                    weekly_keys.append(key)
                if len(weekly_keys) == 4:
                    break
            expected_keep.update(
                max(
                    (
                        item
                        for item in parsed
                        if (item[1].isocalendar().year, item[1].isocalendar().week)
                        == key
                    ),
                    key=lambda item: item[1],
                )[0].name
                for key in weekly_keys
            )
            self.assertEqual(selected_names, set(names) - expected_keep)
            self.assertNotIn(unrelated.name, selected_names)

    def test_rejects_invalid_retention_values(self) -> None:
        retention = load_retention_module()
        with self.assertRaises(ValueError):
            retention.select_backups_to_delete([], daily=-1, weekly=4)
        with self.assertRaises(ValueError):
            retention.select_backups_to_delete([], daily=7, weekly=-1)


class OpenCliInstallerTests(unittest.TestCase):
    def make_archive(self, directory: Path, version: str) -> Path:
        archive = directory / f"browser-bridge-{version}.zip"
        manifest = {
            "manifest_version": 3,
            "name": "Pinned Browser Bridge fixture",
            "version": version,
        }
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("browser-bridge/manifest.json", json.dumps(manifest))
            bundle.writestr("browser-bridge/service-worker.js", "void 0;\n")
        return archive

    def install(
        self,
        *,
        version: str,
        archive: Path,
        install_root: Path,
        fake_bin: Path,
    ) -> subprocess.CompletedProcess[str]:
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["FAKE_DOWNLOAD"] = str(archive)
        return subprocess.run(
            [
                str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                "install",
                "--version",
                version,
                "--sha256",
                digest,
                "--url",
                f"https://downloads.example.invalid/browser-bridge-{version}.zip",
                "--install-root",
                str(install_root),
            ],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )

    def test_install_switch_and_rollback_preserve_two_valid_releases(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = base / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "curl",
                """#!/usr/bin/env bash
set -Eeuo pipefail
output=''
while (($#)); do
  if [[ $1 == '-o' || $1 == '--output' ]]; then
    output=$2
    shift 2
  else
    shift
  fi
done
[[ -n $output ]]
cp "$FAKE_DOWNLOAD" "$output"
""",
            )
            install_root = base / "extension"
            first = self.make_archive(base, "1.2.3")
            second = self.make_archive(base, "1.2.4")

            result = self.install(
                version="1.2.3",
                archive=first,
                install_root=install_root,
                fake_bin=fake_bin,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install_root / "current").resolve().name, "1.2.3")
            self.assertFalse((install_root / "previous").exists())

            result = self.install(
                version="1.2.4",
                archive=second,
                install_root=install_root,
                fake_bin=fake_bin,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install_root / "current").resolve().name, "1.2.4")
            self.assertEqual((install_root / "previous").resolve().name, "1.2.3")

            result = subprocess.run(
                [
                    str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                    "rollback",
                    "--install-root",
                    str(install_root),
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install_root / "current").resolve().name, "1.2.3")
            self.assertEqual((install_root / "previous").resolve().name, "1.2.4")
            self.assertTrue((install_root / "releases" / "1.2.3").is_dir())
            self.assertTrue((install_root / "releases" / "1.2.4").is_dir())

    def test_installer_rejects_query_and_fragment_before_download(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = base / "bin"
            fake_bin.mkdir()
            marker = base / "curl-invoked"
            write_executable(
                fake_bin / "curl", f"#!/usr/bin/env bash\ntouch {marker!s}\nexit 99\n"
            )
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            for suffix in ("?token=must-not-log", "#fragment"):
                result = subprocess.run(
                    [
                        str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                        "install",
                        "--version",
                        "1.2.3",
                        "--sha256",
                        "0" * 64,
                        "--url",
                        f"https://downloads.example.invalid/bridge.zip{suffix}",
                        "--install-root",
                        str(base / "extension"),
                    ],
                    check=False,
                    text=True,
                    capture_output=True,
                    env=environment,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("query or fragment", result.stderr)
                self.assertFalse(marker.exists())

    def test_extension_download_has_size_time_and_low_speed_limits(self) -> None:
        script = (DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh").read_text(
            encoding="utf-8"
        )
        for flag in (
            "--max-filesize",
            "--connect-timeout",
            "--max-time",
            "--speed-limit",
            "--speed-time",
        ):
            self.assertIn(flag, script)

    def test_download_failure_cleans_up_without_masking_the_original_status(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = base / "bin"
            fake_bin.mkdir()
            write_executable(fake_bin / "curl", "#!/usr/bin/env bash\nexit 37\n")
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            result = subprocess.run(
                [
                    str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                    "install",
                    "--version",
                    "1.2.3",
                    "--sha256",
                    "0" * 64,
                    "--url",
                    "https://downloads.example.invalid/bridge.zip",
                    "--install-root",
                    str(base / "extension"),
                ],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 37)
            self.assertNotIn("unbound variable", result.stderr)
            self.assertFalse((base / "extension" / "current").exists())

    def test_latest_and_bad_checksum_fail_without_changing_current(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            install_root = base / "extension"
            latest = subprocess.run(
                [
                    str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                    "install",
                    "--version",
                    "latest",
                    "--sha256",
                    "0" * 64,
                    "--url",
                    "https://downloads.example.invalid/latest/bridge.zip",
                    "--install-root",
                    str(install_root),
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(latest.returncode, 0)
            self.assertFalse((install_root / "current").exists())

            fake_bin = base / "bin"
            fake_bin.mkdir()
            write_executable(
                fake_bin / "curl",
                """#!/usr/bin/env bash
set -Eeuo pipefail
output=''
while (($#)); do
  if [[ $1 == '-o' || $1 == '--output' ]]; then output=$2; shift 2; else shift; fi
done
cp "$FAKE_DOWNLOAD" "$output"
""",
            )
            archive = self.make_archive(base, "1.2.3")
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_DOWNLOAD"] = str(archive)
            bad = subprocess.run(
                [
                    str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                    "install",
                    "--version",
                    "1.2.3",
                    "--sha256",
                    "f" * 64,
                    "--url",
                    "https://downloads.example.invalid/bridge-1.2.3.zip",
                    "--install-root",
                    str(install_root),
                ],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse((install_root / "current").exists())


class DatabaseURLRunnerTests(unittest.TestCase):
    def test_url_maps_to_libpq_environment_without_retaining_the_url(self) -> None:
        runner = load_database_url_module()
        database_url = (
            "postgresql://backup%2Duser:p%40ssword@db.example.invalid:6543/"
            "pokecrack?sslmode=require&connect_timeout=7&"
            "application_name=backup%2520literal"
        )

        environment = runner.libpq_environment(database_url)

        self.assertEqual(
            environment,
            {
                "PGAPPNAME": "backup%20literal",
                "PGCONNECT_TIMEOUT": "7",
                "PGDATABASE": "pokecrack",
                "PGHOST": "db.example.invalid",
                "PGPASSWORD": "p@ssword",
                "PGPORT": "6543",
                "PGSSLMODE": "require",
                "PGUSER": "backup-user",
            },
        )
        self.assertNotIn(database_url, environment.values())

    def test_url_rejects_ambiguous_or_unsupported_shapes_without_echoing_secret(
        self,
    ) -> None:
        runner = load_database_url_module()
        invalid = (
            "postgresql://user:fixture-secret@example.invalid/db",
            "postgresql://user:fixture-secret@example.invalid/db?sslmode=disable",
            "postgresql://user:fixture-secret@example.invalid/db?sslmode=allow",
            "postgresql://user:fixture-secret@example.invalid/db?sslmode=prefer",
            "postgresql://user:fixture-secret@example.invalid/db?sslmode=require&sslmode=disable",
            "postgresql://user:fixture-secret@example.invalid/db?unknown=value",
            "postgresql://user:fixture-secret@example.invalid/too/many",
            "postgresql://user:fixture-secret@example.invalid/db#fragment",
            "postgresql://user:fixture-secret@example.invalid/db\n",
        )

        for database_url in invalid:
            with self.subTest(database_url=database_url):
                with self.assertRaises(
                    (runner.DatabaseURLConfigurationError, ValueError)
                ):
                    runner.libpq_environment(database_url)

    def test_child_environment_removes_every_inherited_pg_variable(self) -> None:
        runner = load_database_url_module()
        parsed = runner.libpq_environment(
            "postgresql://backup:fixture-secret@example.invalid/db?sslmode=verify-full"
        )

        environment = runner.child_environment(
            parsed,
            parent_environment={
                "PATH": "/fixture/bin",
                "PGSSLCERTMODE": "disable",
                "PGLOADBALANCEHOSTS": "random",
                "PGTCPUSERTO": "1",
                "PGPASSWORD": "hostile-parent-secret",
            },
        )

        self.assertEqual(environment["PATH"], "/fixture/bin")
        self.assertEqual(environment["PGPASSWORD"], "fixture-secret")
        self.assertEqual(environment["PGSSLMODE"], "verify-full")
        self.assertFalse(
            {"PGSSLCERTMODE", "PGLOADBALANCEHOSTS", "PGTCPUSERTO"} & environment.keys()
        )


class NostrPreflightTests(unittest.TestCase):
    def test_disabled_nostr_is_a_successful_noop_without_psql(self) -> None:
        preflight = load_nostr_preflight_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "production.env"
            env_file.write_text(
                "DATA_MODE=live\nNOSTR_COLLECTION_ENABLED=false\n", encoding="utf-8"
            )
            env_file.chmod(0o600)
            self.assertEqual(
                preflight.run(type("Arguments", (), {"env_file": env_file})()), 0
            )
            with self.assertRaisesRegex(
                preflight.NostrPreflightError,
                "requires NOSTR_COLLECTION_ENABLED=true",
            ):
                preflight.run(
                    type(
                        "Arguments",
                        (),
                        {"env_file": env_file, "require_enabled": True},
                    )()
                )

    def test_enabled_nostr_requires_a_separate_attestor_preflight_url(self) -> None:
        preflight = load_nostr_preflight_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "production.env"
            env_file.write_text(
                "DATA_MODE=live\nNOSTR_COLLECTION_ENABLED=true\n", encoding="utf-8"
            )
            env_file.chmod(0o600)
            with self.assertRaises(preflight.NostrPreflightError):
                preflight.run(type("Arguments", (), {"env_file": env_file})())

    def test_enabled_nostr_environment_rejects_every_unreviewed_variable(self) -> None:
        preflight = load_nostr_preflight_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "nostr.env"
            env_file.write_text(
                "DATA_MODE=live\n"
                "NOSTR_COLLECTION_ENABLED=true\n"
                "NOSTR_SUPABASE_DB_URL=postgresql://worker:secret@db.example.invalid/db?sslmode=require\n"
                "SUPABASE_NOSTR_PREFLIGHT_DB_URL=postgresql://attestor:secret@db.example.invalid/db?sslmode=require\n"
                "DEPLOY_SHA=unreviewed-override\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            with self.assertRaisesRegex(
                preflight.NostrPreflightError, "only the exact release variables"
            ):
                preflight.run(type("Arguments", (), {"env_file": env_file})())

    def test_enabled_nostr_rejects_reusing_the_worker_database_url(self) -> None:
        preflight = load_nostr_preflight_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "production.env"
            database_url = "postgresql://worker:fixture-secret@example.invalid/db?sslmode=require"
            env_file.write_text(
                "DATA_MODE=live\n"
                "NOSTR_COLLECTION_ENABLED=true\n"
                f"NOSTR_SUPABASE_DB_URL={database_url}\n"
                f"SUPABASE_NOSTR_PREFLIGHT_DB_URL={database_url}\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            with self.assertRaises(preflight.NostrPreflightError):
                preflight.run(type("Arguments", (), {"env_file": env_file})())

    def test_enabled_nostr_does_not_print_database_url_or_token(self) -> None:
        preflight = load_nostr_preflight_module()
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "production.env"
            secret = "fixture-not-in-output"
            env_file.write_text(
                "DATA_MODE=live\n"
                "NOSTR_COLLECTION_ENABLED=true\n"
                f"SUPABASE_NOSTR_PREFLIGHT_DB_URL=postgresql://pokecrack_nostr_attestor_login:{secret}@db.example.invalid/db?sslmode=require\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            original_which = preflight.shutil.which
            preflight.shutil.which = lambda name: sys.executable if name == "psql" else None
            try:
                with self.assertRaises(preflight.NostrPreflightError):
                    preflight.run(type("Arguments", (), {"env_file": env_file})())
            finally:
                preflight.shutil.which = original_which
            self.assertNotIn(secret, preflight.CONTRACT_QUERY)
            self.assertIn("ingest.verify_nostr_release_v2", preflight.CONTRACT_QUERY)
            self.assertNotIn("source_request_gates", preflight.CONTRACT_QUERY)
            self.assertNotIn("schema_migrations", preflight.CONTRACT_QUERY)

    def test_attestor_url_requires_the_exact_fixed_set_role_option(self) -> None:
        preflight = load_nostr_preflight_module()
        base = (
            "postgresql://pokecrack_nostr_attestor_login:fixture-secret@"
            "db.example.invalid/db?sslmode=require"
        )
        for suffix in (
            "",
            "&options=-c%20role%3Dservice_role",
            "&options=-c%20role%3Dpokecrack_nostr_attestor%20-c%20statement_timeout%3D0",
        ):
            with self.subTest(suffix=suffix), self.assertRaises(
                preflight.NostrPreflightError
            ):
                preflight._psql_contract(base + suffix, psql_path="/fixture/psql")

    def test_attestor_contract_uses_fixed_role_and_returns_only_boolean_shape(self) -> None:
        preflight = load_nostr_preflight_module()
        database_url = (
            "postgresql://pokecrack_nostr_attestor_login:fixture-secret@"
            "db.example.invalid/db?sslmode=require&"
            "options=-c%20role%3Dpokecrack_nostr_attestor"
        )
        expected = {key: True for key in preflight.REQUIRED_CONTRACT_KEYS}
        captured: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object):
            captured["command"] = command
            captured["environment"] = kwargs["env"]
            return type(
                "Result",
                (),
                {"returncode": 0, "stdout": json.dumps(expected) + "\n"},
            )()

        original_run = preflight.subprocess.run
        inherited_worker = os.environ.get("NOSTR_SUPABASE_DB_URL")
        inherited_attestor = os.environ.get("SUPABASE_NOSTR_PREFLIGHT_DB_URL")
        os.environ["NOSTR_SUPABASE_DB_URL"] = "must-not-reach-psql"
        os.environ["SUPABASE_NOSTR_PREFLIGHT_DB_URL"] = "must-not-reach-psql"
        preflight.subprocess.run = fake_run
        try:
            self.assertEqual(
                preflight._psql_contract(database_url, psql_path="/fixture/psql"),
                expected,
            )
        finally:
            preflight.subprocess.run = original_run
            if inherited_worker is None:
                os.environ.pop("NOSTR_SUPABASE_DB_URL", None)
            else:
                os.environ["NOSTR_SUPABASE_DB_URL"] = inherited_worker
            if inherited_attestor is None:
                os.environ.pop("SUPABASE_NOSTR_PREFLIGHT_DB_URL", None)
            else:
                os.environ["SUPABASE_NOSTR_PREFLIGHT_DB_URL"] = inherited_attestor

        environment = captured["environment"]
        self.assertIsInstance(environment, dict)
        self.assertEqual(
            environment["PGOPTIONS"], preflight.ATTESTOR_ROLE_OPTION
        )
        self.assertEqual(environment["PGUSER"], "pokecrack_nostr_attestor_login")
        self.assertNotIn("NOSTR_SUPABASE_DB_URL", environment)
        self.assertNotIn("SUPABASE_NOSTR_PREFLIGHT_DB_URL", environment)
        self.assertNotIn("fixture-secret", preflight.CONTRACT_QUERY)
        self.assertIn("session_user = 'pokecrack_nostr_attestor_login'", preflight.CONTRACT_QUERY)
        self.assertIn("current_user = 'pokecrack_nostr_attestor'", preflight.CONTRACT_QUERY)

    def test_preflight_and_worker_must_target_the_same_database_with_distinct_roles(self) -> None:
        preflight = load_nostr_preflight_module()
        attestor = (
            "postgresql://pokecrack_nostr_attestor_login:attestor-secret@"
            "db-a.example.invalid/db?sslmode=require&"
            "options=-c%20role%3Dpokecrack_nostr_attestor"
        )
        worker = (
            "postgresql://pokecrack_nostr_worker_login:worker-secret@"
            "db-b.example.invalid/db?sslmode=require&"
            "options=-c%20role%3Dpokecrack_nostr_worker"
        )
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            env_file = Path(temporary) / "nostr.env"
            env_file.write_text(
                "DATA_MODE=live\n"
                "NOSTR_COLLECTION_ENABLED=true\n"
                f"SUPABASE_NOSTR_PREFLIGHT_DB_URL={attestor}\n"
                f"NOSTR_SUPABASE_DB_URL={worker}\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            with self.assertRaises(preflight.NostrPreflightError):
                preflight.run(type("Arguments", (), {"env_file": env_file})())


class BackupScriptTests(unittest.TestCase):
    def test_pg_dump_scope_is_exactly_the_application_schemas_and_ledger(
        self,
    ) -> None:
        script = (DEPLOY_ROOT / "scripts" / "backup.sh").read_text(
            encoding="utf-8"
        )
        invocation = script.split("if ! run_database_command pg_dump \\\n", 1)[1]
        invocation = invocation.split("  | python3 ", 1)[0]

        self.assertNotIn("--role=service_role", invocation)
        self.assertIn("--strict-names", invocation)
        self.assertEqual(
            re.findall(r"--schema=([a-z_]+)", invocation),
            ["catalog", "ingest", "analytics", "public", "supabase_migrations"],
        )
        for provider_schema in ("auth", "storage", "realtime", "extensions"):
            self.assertNotIn(f"--schema={provider_schema}", invocation)

    @staticmethod
    def gate_schema_dump(*, youtube: bool = True) -> bytes:
        source_constraint = (
            b"CONSTRAINT source_request_gates_source_check CHECK "
            b"((source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'::text))"
            if youtube
            else b"CONSTRAINT source_request_gates_source_check CHECK "
            b"((source_key = 'tcgdex_catalog'::text))"
        )
        return (
            b"""CREATE TABLE ingest.source_request_gates (
    source_key text NOT NULL,
    owner_job_id uuid,
    owner_lease_generation bigint,
    acquired_at timestamp with time zone,
    active_until timestamp with time zone,
    CONSTRAINT source_request_gates_owner_check CHECK ((((owner_job_id IS NULL) AND (owner_lease_generation IS NULL) AND (acquired_at IS NULL) AND (active_until IS NULL)) OR ((owner_job_id IS NOT NULL) AND (owner_lease_generation >= 1) AND (acquired_at IS NOT NULL) AND (active_until > acquired_at)))),
    """
            + source_constraint
            + b"""
);
ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;
ALTER TABLE ONLY ingest.source_request_gates
    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);
ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;
"""
        )

    @staticmethod
    def canonical_gate_seed(
        *,
        youtube: bool,
        public_studies: bool = False,
        bluesky: bool = False,
        nostr: bool = False,
        mastodon: bool = False,
    ) -> bytes:
        youtube_row = b"youtube_discovery\n" if youtube else b""
        bluesky_row = b"bluesky_jetstream\n" if bluesky else b""
        nostr_rows = (
            b"nostr_relay_primal\n"
            b"nostr_relay_nos_lol\n"
            b"nostr_relay_nostr_net\n"
            if nostr
            else b""
        )
        mastodon_row = b"mastodon_social\n" if mastodon else b""
        public_rows = (
            b"public_study_comicbook_us_55\n"
            b"public_study_wargamer_gb_17\n"
            b"public_study_cardchill_gb_90\n"
            b"public_study_bleedingcool_us_36\n"
            b"public_study_tcgtalk_sg_54\n"
            if public_studies
            else b""
        )
        return (
            b"\n-- Canonical idle request gates; live lease ownership is not retained.\n"
            b"COPY ingest.source_request_gates (source_key) FROM stdin;\n"
            b"tcgdex_catalog\n"
            + youtube_row
            + bluesky_row
            + nostr_rows
            + mastodon_row
            + public_rows
            + b"\\.\n\n"
        )

    @classmethod
    def with_canonical_gate_seed(cls, dump: bytes, *, youtube: bool) -> bytes:
        enable = b"ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;\n"
        return dump.replace(enable, cls.canonical_gate_seed(youtube=youtube) + enable)

    @classmethod
    def pre_youtube_dump(cls) -> bytes:
        return (
            b"""-- PostgreSQL database dump fixture
CREATE TABLE ingest.source_policies (
);
"""
            + cls.gate_schema_dump(youtube=False)
            + b"""COPY ingest.source_policies (source_key, id) FROM stdin;
tcgdex_catalog\t33333333-3333-4333-8333-333333333333
other\t22222222-2222-4222-8222-222222222222
\\.
"""
        )

    @classmethod
    def post_youtube_dump(cls) -> bytes:
        return (
            cls.gate_schema_dump(youtube=True)
            + b"""CREATE UNLOGGED TABLE ingest.youtube_discoveries (
);
COPY ingest.source_policies (id, source_key) FROM stdin;
11111111-1111-4111-8111-111111111111\tyoutube_discovery
33333333-3333-4333-8333-333333333333\ttcgdex_catalog
\\.
COPY ingest.youtube_discoveries (video_id, source_policy_id) FROM stdin;
\\.
"""
        )

    @classmethod
    def post_public_study_dump(cls) -> bytes:
        return (
            cls.gate_schema_dump(youtube=True)
            + b"""CREATE UNLOGGED TABLE ingest.youtube_discoveries (
);
CREATE TABLE ingest.public_study_observations (
    study_key text NOT NULL,
    source_policy_id uuid NOT NULL,
    source_item_id uuid NOT NULL,
    extraction_run_id uuid NOT NULL,
    opening_id uuid NOT NULL,
    country_code text NOT NULL,
    country_name text NOT NULL,
    geography_basis text NOT NULL,
    geography_confidence text NOT NULL,
    source_observed_at timestamp with time zone NOT NULL,
    pack_count integer NOT NULL,
    qualifying_hit_pack_count integer NOT NULL,
    set_external_id text NOT NULL,
    product_scope text NOT NULL,
    metric_key text NOT NULL,
    metric_version text NOT NULL,
    collector_version text NOT NULL,
    parser_version text NOT NULL,
    source_policy_version text NOT NULL,
    evidence_sha256 text NOT NULL,
    first_verified_at timestamp with time zone NOT NULL,
    last_verified_at timestamp with time zone NOT NULL,
    is_demo boolean DEFAULT false NOT NULL,
    CONSTRAINT public_study_observations_country_name_check CHECK (((btrim(country_name) <> ''::text) AND (char_length(country_name) <= 160))),
    CONSTRAINT public_study_observations_counts_check CHECK ((((pack_count >= 1) AND (pack_count <= 100000)) AND ((qualifying_hit_pack_count >= 0) AND (qualifying_hit_pack_count <= pack_count)))),
    CONSTRAINT public_study_observations_geography_check CHECK (((geography_basis = ANY (ARRAY['publisher_country'::text, 'author_public_residence'::text])) AND (geography_confidence = 'tier_b'::text))),
    CONSTRAINT public_study_observations_hash_check CHECK ((evidence_sha256 ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT public_study_observations_key_check CHECK ((study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'::text)),
    CONSTRAINT public_study_observations_live_only_check CHECK ((NOT is_demo)),
    CONSTRAINT public_study_observations_metric_check CHECK (((metric_key = 'qualifying_hit_pack_rate'::text) AND (metric_version = 'global-sir-v1'::text))),
    CONSTRAINT public_study_observations_product_check CHECK ((product_scope = ANY (ARRAY['all'::text, 'booster_box'::text, 'etb'::text, 'booster_bundle'::text]))),
    CONSTRAINT public_study_observations_set_check CHECK (((btrim(set_external_id) <> ''::text) AND (char_length(set_external_id) <= 160))),
    CONSTRAINT public_study_observations_time_check CHECK ((last_verified_at >= first_verified_at)),
    CONSTRAINT public_study_observations_version_check CHECK (((btrim(collector_version) <> ''::text) AND (char_length(collector_version) <= 120) AND (btrim(parser_version) <> ''::text) AND (char_length(parser_version) <= 120) AND (btrim(source_policy_version) <> ''::text) AND (char_length(source_policy_version) <= 120)))
);
COPY ingest.source_policies (id, source_key) FROM stdin;
11111111-1111-4111-8111-111111111111\tyoutube_discovery
33333333-3333-4333-8333-333333333333\ttcgdex_catalog
44444444-4444-4444-8444-444444444444\tpublic_study_comicbook_us_55
55555555-5555-4555-8555-555555555555\tpublic_study_wargamer_gb_17
99999999-9999-4999-8999-999999999990\tpublic_study_cardchill_gb_90
aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0\tpublic_study_bleedingcool_us_36
bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb0\tpublic_study_tcgtalk_sg_54
\\.
COPY ingest.youtube_discoveries (video_id, source_policy_id) FROM stdin;
\\.
COPY ingest.public_study_observations (study_key, source_policy_id, source_item_id, extraction_run_id, opening_id, country_code, country_name, geography_basis, geography_confidence, source_observed_at, pack_count, qualifying_hit_pack_count, set_external_id, product_scope, metric_key, metric_version, collector_version, parser_version, source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo) FROM stdin;
comicbook-perfect-order-us-55-v1\t44444444-4444-4444-8444-444444444444\t66666666-6666-4666-8666-666666666666\t77777777-7777-4777-8777-777777777777\t88888888-8888-4888-8888-888888888888\tUS\tUnited States\tpublisher_country\ttier_b\t2026-03-19 21:00:00+00\t55\t1\tme03\tall\tqualifying_hit_pack_rate\tglobal-sir-v1\tpublic-study-comicbook-perfect-order-v1\tcomicbook-perfect-order-evidence-v1\tpublic-study-comicbook-perfect-order-v1\taaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\t2026-08-29 01:02:03+00\t2026-08-29 01:02:03+00\tf
\\.
"""
        )

    @classmethod
    def post_bluesky_dump(cls) -> bytes:
        bluesky_policy = b"cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        base = cls.post_public_study_dump()
        policy_end = (
            b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb0\tpublic_study_tcgtalk_sg_54\n"
        )
        checkpoint = (
            b"COPY ingest.bluesky_jetstream_checkpoints (source_policy_id, endpoint, protocol, collection, last_cursor, last_collected_at, events_seen_total, bytes_seen_total, candidates_seen_total, deletions_seen_total, is_demo, created_at, updated_at) FROM stdin;\n"
            + bluesky_policy
            + b"\twss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents\txrpc.v1.json\tapp.bsky.feed.post\t123\t2026-08-30 00:00:00+00\t10\t2048\t2\t1\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n\\.\n"
        )
        return (
            base.replace(
                policy_end,
                policy_end + bluesky_policy + b"\tbluesky_jetstream\n",
                1,
            )
            + checkpoint
        )

    @classmethod
    def post_nostr_dump(cls) -> bytes:
        nostr_policies = (
            b"11111111-1111-4111-8111-111111111111\tnostr_relay_primal\n"
            b"22222222-2222-4222-8222-222222222222\tnostr_relay_nos_lol\n"
            b"33333333-3333-4333-8333-333333333333\tnostr_relay_nostr_net\n"
        )
        checkpoint_columns = (
            b"source_policy_id, relay_key, endpoint, nip11_url, protocol, "
            b"approved_tags, last_checkpoint, events_seen_total, bytes_seen_total, "
            b"candidates_seen_total, deletions_seen_total, is_demo, created_at, "
            b"updated_at"
        )
        approved_tags = (
            b"{pokemontcg,PokemonTCG,pokemoncards,PokemonCards,"
            b"\xe3\x83\x9d\xe3\x82\xb1\xe3\x82\xab,"
            b"\xe3\x83\x9d\xe3\x82\xb1\xe3\x83\xa2\xe3\x83\xb3\xe3\x82\xab\xe3\x83\xbc\xe3\x83\x89,"
            b"\xed\x8f\xac\xec\xbc\x93\xeb\xaa\xac\xec\xb9\xb4\xeb\x93\x9c,"
            b"\xe5\xae\x9d\xe5\x8f\xaf\xe6\xa2\xa6\xe5\x8d\xa1\xe7\x89\x8c,"
            b"\xe5\xaf\xb6\xe5\x8f\xaf\xe5\xa4\xa2\xe5\x8d\xa1\xe7\x89\x8c}"
        )
        checkpoint_rows = (
            b"11111111-1111-4111-8111-111111111111\tprimal\t"
            b"wss://relay.primal.net/\thttps://relay.primal.net/\tnip01\t"
            + approved_tags
            + b"\t\\N\t10\t1024\t2\t1\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n"
            b"22222222-2222-4222-8222-222222222222\tnos_lol\t"
            b"wss://nos.lol/\thttps://nos.lol/\tnip01\t"
            + approved_tags
            + b"\t\\N\t10\t1024\t2\t1\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n"
            b"33333333-3333-4333-8333-333333333333\tnostr_net\t"
            b"wss://relay.nostr.net/\thttps://relay.nostr.net/\tnip01\t"
            + approved_tags
            + b"\t\\N\t10\t1024\t2\t1\tf\t2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n"
        )
        base = cls.post_public_study_dump()
        policy_end = (
            b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb0\tpublic_study_tcgtalk_sg_54\n"
        )
        nostr_dump = (
            b"CREATE TABLE ingest.nostr_relay_candidates (\n);\n"
            b"CREATE TABLE ingest.nostr_relay_observations (\n);\n"
            b"CREATE TABLE ingest.nostr_relay_checkpoints (\n);\n"
            b"COPY ingest.nostr_relay_checkpoints ("
            + checkpoint_columns
            + b") FROM stdin;\n"
            + checkpoint_rows
            + b"\\.\n"
        )
        return (
            base.replace(policy_end, policy_end + nostr_policies, 1)
            + nostr_dump
        )

    @classmethod
    def post_mastodon_dump(cls) -> bytes:
        mastodon_policy = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        base = cls.post_public_study_dump()
        policy_end = (
            b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb0\tpublic_study_tcgtalk_sg_54\n"
        )
        policy_row = mastodon_policy.encode() + b"\tmastodon_social\n"
        tags = (
            "pokemontcg",
            "pokemoncards",
            "pokeca_ja",
            "pokemon_card_ja",
            "pokemon_card_ko",
            "pokemon_card_zh_hans",
            "pokemon_card_zh_hant",
        )
        checkpoint_rows = b"".join(
            (
                f"{mastodon_policy}\tmastodon_social\t{tag}\topaque-001\t"
                "2026-08-30 00:00:00+00\tf\t1\t2\t2048\t1\tf\t"
                "2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n"
            ).encode()
            for tag in tags
        )
        mastodon_dump = (
            b"CREATE TABLE ingest.mastodon_public_hashtag_candidates (\n);\n"
            b"CREATE TABLE ingest.mastodon_public_hashtag_observations (\n);\n"
            b"CREATE TABLE ingest.mastodon_public_hashtag_checkpoints (\n);\n"
            b"COPY ingest.mastodon_public_hashtag_checkpoints ("
            b"source_policy_id, instance_key, tag_key, last_status_id, "
            b"last_collected_at, incomplete, requests_seen_total, statuses_seen_total, "
            b"bytes_seen_total, candidates_seen_total, is_demo, created_at, updated_at"
            b") FROM stdin;\n"
            + checkpoint_rows
            + b"\\.\n"
            b"CREATE TABLE ingest.mastodon_rate_cooldowns (\n);\n"
            b"COPY ingest.mastodon_rate_cooldowns (source_policy_id, instance_key, "
            b"cooldown_until, is_demo, created_at, updated_at) FROM stdin;\n"
            + mastodon_policy.encode()
            + b"\tmastodon_social\t2000-01-01 00:00:00+00\tf\t"
            b"2026-08-29 00:00:00+00\t2026-08-30 00:00:00+00\n\\.\n"
        )
        return base.replace(policy_end, policy_end + policy_row, 1) + mastodon_dump

    def make_fake_commands(self, base: Path) -> Path:
        fake_bin = base / "bin"
        fake_bin.mkdir()
        write_executable(
            fake_bin / "date",
            """#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} == '-u' ]]
printf '%s\n' "$FAKE_UTC"
""",
        )
        write_executable(
            fake_bin / "pg_dump",
            """#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${PGDATABASE:-} == 'pokecrack' ]]
[[ ${PGHOST:-} == 'example.invalid' ]]
[[ ${PGPASSWORD:-} == 'very-secret' ]]
[[ ${PGPORT:-} == '6543' ]]
[[ ${PGUSER:-} == 'backup-user' ]]
[[ ${PGSSLMODE:-} == 'require' ]]
[[ ${PGCONNECT_TIMEOUT:-} == '7' ]]
[[ ${PGAPPNAME:-} == 'pokecrack-backup' ]]
role_argument_count=0
strict_names_count=0
schema_argument_count=0
catalog_schema_count=0
ingest_schema_count=0
analytics_schema_count=0
public_schema_count=0
migration_schema_count=0
provider_schema_count=0
gate_exclusion_count=0
bluesky_candidate_exclusion_count=0
bluesky_observation_exclusion_count=0
nostr_candidate_exclusion_count=0
nostr_observation_exclusion_count=0
mastodon_candidate_exclusion_count=0
mastodon_observation_exclusion_count=0
for argument in "$@"; do
  [[ $argument != *'very-secret'* ]]
  if [[ $argument == '--role=service_role' ]]; then
    role_argument_count=$((role_argument_count + 1))
  fi
  if [[ $argument == '--strict-names' ]]; then
    strict_names_count=$((strict_names_count + 1))
  fi
  if [[ $argument == --schema=* ]]; then
    schema_argument_count=$((schema_argument_count + 1))
    case "$argument" in
      --schema=catalog) catalog_schema_count=$((catalog_schema_count + 1)) ;;
      --schema=ingest) ingest_schema_count=$((ingest_schema_count + 1)) ;;
      --schema=analytics) analytics_schema_count=$((analytics_schema_count + 1)) ;;
      --schema=public) public_schema_count=$((public_schema_count + 1)) ;;
      --schema=supabase_migrations) migration_schema_count=$((migration_schema_count + 1)) ;;
      --schema=auth|--schema=storage|--schema=realtime|--schema=extensions)
        provider_schema_count=$((provider_schema_count + 1))
        ;;
    esac
  fi
  if [[ $argument == '--exclude-table-data=ingest.source_request_gates' ]]; then
    gate_exclusion_count=$((gate_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.bluesky_jetstream_candidates' ]]; then
    bluesky_candidate_exclusion_count=$((bluesky_candidate_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.bluesky_jetstream_observations' ]]; then
    bluesky_observation_exclusion_count=$((bluesky_observation_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.nostr_relay_candidates' ]]; then
    nostr_candidate_exclusion_count=$((nostr_candidate_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.nostr_relay_observations' ]]; then
    nostr_observation_exclusion_count=$((nostr_observation_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.mastodon_public_hashtag_candidates' ]]; then
    mastodon_candidate_exclusion_count=$((mastodon_candidate_exclusion_count + 1))
  fi
  if [[ $argument == '--exclude-table-data=ingest.mastodon_public_hashtag_observations' ]]; then
    mastodon_observation_exclusion_count=$((mastodon_observation_exclusion_count + 1))
  fi
done
[[ $role_argument_count == 0 ]]
[[ $strict_names_count == 1 ]]
[[ $schema_argument_count == 5 ]]
[[ $catalog_schema_count == 1 ]]
[[ $ingest_schema_count == 1 ]]
[[ $analytics_schema_count == 1 ]]
[[ $public_schema_count == 1 ]]
[[ $migration_schema_count == 1 ]]
[[ $provider_schema_count == 0 ]]
[[ $gate_exclusion_count == 1 ]]
[[ $bluesky_candidate_exclusion_count == 1 ]]
[[ $bluesky_observation_exclusion_count == 1 ]]
[[ $nostr_candidate_exclusion_count == 1 ]]
[[ $nostr_observation_exclusion_count == 1 ]]
[[ $mastodon_candidate_exclusion_count == 1 ]]
[[ $mastodon_observation_exclusion_count == 1 ]]
if [[ ${FAKE_EMPTY_DUMP:-0} == 1 ]]; then
  exit 0
fi
if [[ -n ${FAKE_DUMP_FILE:-} ]]; then
  /bin/cat "$FAKE_DUMP_FILE"
  exit 0
fi
exit 18
""",
        )
        write_executable(
            fake_bin / "psql",
            """#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${PGDATABASE:-} == 'pokecrack' ]]
[[ ${PGHOST:-} == 'example.invalid' ]]
[[ ${PGPASSWORD:-} == 'very-secret' ]]
[[ ${PGPORT:-} == '6543' ]]
[[ ${PGUSER:-} == 'backup-user' ]]
[[ ${PGSSLMODE:-} == 'require' ]]
[[ ${PGCONNECT_TIMEOUT:-} == '7' ]]
[[ ${PGAPPNAME:-} == 'pokecrack-backup' ]]
for argument in "$@"; do
  [[ $argument != *'very-secret'* ]]
done
set_role_count=0
for argument in "$@"; do
  if [[ $argument == 'set role service_role;'$'\n''select '* ]]; then
    set_role_count=$((set_role_count + 1))
  fi
done
[[ $set_role_count == 1 ]]
if [[ ${FAKE_PSQL_FAIL:-0} == 1 ]]; then
  printf '%s\n' 'fixture connection failure' >&2
  exit 17
fi
arguments="$*"
if [[ $arguments == *mastodon_public_hashtag_candidates* && $arguments == *has_table_privilege* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'table-state:set-role' >> "$FAKE_PSQL_LOG"
  printf '%b\n' "${FAKE_TABLE_STATE:-rp\\tru\\trp\\t0\\t0\\t0\\t0\\t0\\t0\\t0\\t0\\t0\\t0\\t0\\ttrue}"
elif [[ $arguments == *to_regclass* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'table-state:set-role' >> "$FAKE_PSQL_LOG"
  printf '%b\n' "${FAKE_TABLE_STATE:-rp\\tru\\trp\\t0\\t0\\t0\\t0\\ttrue}"
elif [[ $arguments == *bluesky_jetstream* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'bluesky-policy-lookup:set-role' >> "$FAKE_PSQL_LOG"
  if [[ -n ${FAKE_BLUESKY_POLICY_OUTPUT:-} ]]; then
    printf '%s\n' "$FAKE_BLUESKY_POLICY_OUTPUT"
  fi
elif [[ $arguments == *nostr_relay_primal* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'nostr-policy-lookup:set-role' >> "$FAKE_PSQL_LOG"
  if [[ -n ${FAKE_NOSTR_POLICY_OUTPUT:-} ]]; then
    printf '%s\n' "$FAKE_NOSTR_POLICY_OUTPUT"
  fi
elif [[ $arguments == *mastodon_social* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'mastodon-policy-lookup:set-role' >> "$FAKE_PSQL_LOG"
  if [[ -n ${FAKE_MASTODON_POLICY_OUTPUT:-} ]]; then
    printf '%s\n' "$FAKE_MASTODON_POLICY_OUTPUT"
  fi
elif [[ $arguments == *youtube_discovery* ]]; then
  [[ -z ${FAKE_PSQL_LOG:-} ]] || printf '%s\n' 'policy-lookup:set-role' >> "$FAKE_PSQL_LOG"
  if [[ -n ${FAKE_POLICY_OUTPUT:-} ]]; then
    printf '%s\n' "$FAKE_POLICY_OUTPUT"
  fi
else
  exit 19
fi
""",
        )
        return fake_bin

    def run_backup(
        self,
        *,
        fake_bin: Path,
        backup_dir: Path,
        timestamp: str,
        empty: bool = False,
        dump: bytes | None = None,
        table_state: str = "rp\tru\trp\t0\t0\t0\t0\ttrue",
        policy_output: str = "11111111-1111-4111-8111-111111111111",
        bluesky_policy_output: str = "",
        nostr_policy_output: str = "",
        mastodon_policy_output: str = "",
        psql_fail: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["FAKE_UTC"] = timestamp
        environment["SUPABASE_DB_URL"] = (
            "postgresql://backup-user:very-secret@example.invalid:6543/"
            "pokecrack?sslmode=require&connect_timeout=7&application_name=pokecrack-backup"
        )
        environment["BACKUP_DIR"] = str(backup_dir)
        environment["BACKUP_RETENTION_DAILY"] = "7"
        environment["BACKUP_RETENTION_WEEKLY"] = "4"
        environment["FAKE_TABLE_STATE"] = table_state
        environment["FAKE_POLICY_OUTPUT"] = policy_output
        environment["FAKE_BLUESKY_POLICY_OUTPUT"] = bluesky_policy_output
        environment["FAKE_NOSTR_POLICY_OUTPUT"] = nostr_policy_output
        environment["FAKE_MASTODON_POLICY_OUTPUT"] = mastodon_policy_output
        environment["FAKE_PSQL_LOG"] = str(fake_bin.parent / "psql-preflight.log")
        if empty:
            environment["FAKE_EMPTY_DUMP"] = "1"
        effective_dump = (
            self.post_youtube_dump() if dump is None and not empty else dump
        )
        if effective_dump is not None:
            dump_file = fake_bin.parent / "fixture-dump.sql"
            dump_file.write_bytes(effective_dump)
            environment["FAKE_DUMP_FILE"] = str(dump_file)
        if psql_fail:
            environment["FAKE_PSQL_FAIL"] = "1"
        return subprocess.run(
            [str(DEPLOY_ROOT / "scripts" / "backup.sh")],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )

    def test_both_preflights_set_service_role_in_their_psql_session(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=base / "backups",
                timestamp="20260729T020000Z",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            self.assertEqual(
                (base / "psql-preflight.log").read_text(encoding="utf-8").splitlines(),
                [
                    "table-state:set-role",
                    "policy-lookup:set-role",
                    "bluesky-policy-lookup:set-role",
                    "nostr-policy-lookup:set-role",
                ],
            )

    def test_coherent_pre_youtube_schema_is_backed_up_without_policy_id(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            dump = self.pre_youtube_dump()
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=dump,
                table_state="rp\t0\trp\t0\t0\t0\t0\ttrue",
                policy_output="",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                self.assertEqual(
                    stream.read(),
                    self.with_canonical_gate_seed(dump, youtube=False),
                )
            self.assertEqual(
                (backup_dir / ".last-successful-backup")
                .read_text(encoding="utf-8")
                .splitlines(),
                [backup.name, "completed_at=20260729T020000Z"],
            )

    def test_partial_youtube_migration_states_fail_atomically(self) -> None:
        policy = "11111111-1111-4111-8111-111111111111"
        cases = {
            "table-without-policy": {
                "table_state": "rp\tru\trp\t0\t0\t0\t0\ttrue",
                "policy_output": "",
            },
            "policy-without-table": {
                "table_state": "rp\t0\trp\t0\t0\t0\t0\ttrue",
                "policy_output": policy,
            },
            "old-preflight-with-new-dump": {
                "table_state": "rp\t0\trp\t0\t0\t0\t0\ttrue",
                "policy_output": "",
            },
            "new-preflight-with-old-dump": {
                "table_state": "rp\tru\trp\t0\t0\t0\t0\ttrue",
                "policy_output": policy,
                "dump": self.pre_youtube_dump(),
            },
        }
        for name, values in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    table_state=values["table_state"],
                    policy_output=values["policy_output"],
                    dump=values.get("dump"),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_database_url_file_must_be_owner_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            credential_file = base / "database-url"
            credential_file.write_text(
                "postgresql://backup-user:fixture@example.invalid/pokecrack\n",
                encoding="utf-8",
            )
            credential_file.chmod(0o644)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["SUPABASE_DB_URL_FILE"] = str(credential_file)
            environment.pop("SUPABASE_DB_URL", None)
            environment["BACKUP_DIR"] = str(base / "backups")
            result = subprocess.run(
                [str(DEPLOY_ROOT / "scripts" / "backup.sh")],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("owner-only", result.stderr)
            self.assertNotIn("fixture", result.stderr)

    def test_dump_is_validated_marked_and_retained_without_secret_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            timestamps = [
                "20260720T010000Z",
                "20260721T010000Z",
                "20260722T010000Z",
                "20260723T010000Z",
                "20260724T010000Z",
                "20260725T010000Z",
                "20260726T010000Z",
                "20260727T010000Z",
                "20260728T010000Z",
                "20260729T010000Z",
                "20260729T020000Z",
            ]
            for timestamp in timestamps:
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp=timestamp,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("very-secret", result.stdout + result.stderr)

            retention = load_retention_module()
            all_paths = [
                backup_dir / f"pokecrack-{timestamp}.sql.gz" for timestamp in timestamps
            ]
            expected_deleted = {
                path.name
                for path in retention.select_backups_to_delete(
                    all_paths, daily=7, weekly=4
                )
            }
            actual_names = {path.name for path in backup_dir.glob("pokecrack-*.sql.gz")}
            self.assertEqual(
                actual_names, {path.name for path in all_paths} - expected_deleted
            )
            latest = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            self.assertTrue(latest.is_file())
            with gzip.open(latest, "rt", encoding="utf-8") as stream:
                self.assertIn("CREATE TABLE ingest.source_request_gates", stream.read())
            marker_lines = (
                (backup_dir / ".last-successful-backup")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            self.assertEqual(marker_lines[0], latest.name)
            self.assertEqual(marker_lines[1], "completed_at=20260729T020000Z")

    def test_empty_dump_fails_and_does_not_advance_marker(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                empty=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            self.assertFalse((backup_dir / ".last-successful-backup").exists())
            self.assertEqual(list(backup_dir.glob("pokecrack-*.sql.gz")), [])

    def test_non_regular_success_marker_fails_before_creating_a_backup(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            backup_dir.mkdir()
            (backup_dir / ".last-successful-backup").mkdir()

            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("success marker must be a regular", result.stderr)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            self.assertEqual(list(backup_dir.glob("pokecrack-*.sql.gz")), [])

    def test_backup_removes_only_dedicated_youtube_discovery_rows(self) -> None:
        youtube_policy = "11111111-1111-4111-8111-111111111111"
        other_policy = "22222222-2222-4222-8222-222222222222"
        youtube_item = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        rebound_item = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        other_item = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        first_video = "AbCdEfGhI_1"
        second_video = "ZyXwVuTsR-2"
        dump = (
            self.gate_schema_dump(youtube=True)
            + f"""-- PostgreSQL database dump fixture
CREATE UNLOGGED TABLE ingest.youtube_discoveries (
);
COPY ingest.source_policies (source_key, id) FROM stdin;
youtube_discovery\t{youtube_policy}
tcgdex_catalog\t33333333-3333-4333-8333-333333333333
other\t{other_policy}
\\.
COPY ingest.source_items (note, id, source_policy_id) FROM stdin;
youtube\\trow\t{youtube_item}\t{youtube_policy}
rebound\\nrow\t{rebound_item}\t{other_policy}
keep\t{other_item}\t{other_policy}
\\.
COPY ingest.source_discoveries (note, source_item_id) FROM stdin;
query-a\t{youtube_item}
query-b\t{rebound_item}
\\.
COPY ingest.youtube_discoveries (title, source_policy_id, video_id) FROM stdin;
cache-first\t{youtube_policy}\t{first_video}
cache-second\t{youtube_policy}\t{second_video}
\\.
""".encode()
        )

        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=dump,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                sanitized = stream.read()
            self.assertNotIn(first_video.encode(), sanitized)
            self.assertNotIn(second_video.encode(), sanitized)
            self.assertIn(youtube_item.encode(), sanitized)
            self.assertIn(rebound_item.encode(), sanitized)
            self.assertIn(other_item.encode(), sanitized)
            self.assertIn(
                b"COPY ingest.source_discoveries (note, source_item_id) FROM stdin;\nquery-a\t",
                sanitized,
            )
            self.assertIn(
                b"COPY ingest.youtube_discoveries (title, source_policy_id, video_id) FROM stdin;\n\\.\n",
                sanitized,
            )
            self.assertIn(self.canonical_gate_seed(youtube=True), sanitized)
            self.assertLess(
                sanitized.index(self.canonical_gate_seed(youtube=True)),
                sanitized.index(
                    b"ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;"
                ),
            )

    def test_backup_retains_public_study_ledger_and_reseeds_all_idle_gates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=self.post_public_study_dump(),
                table_state="rp\tru\trp\trp\t0\t0\t0\ttrue",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                sanitized = stream.read()
            self.assertIn(b"comicbook-perfect-order-us-55-v1", sanitized)
            self.assertIn(
                self.canonical_gate_seed(youtube=True, public_studies=True),
                sanitized,
            )

    def test_backup_retains_bluesky_checkpoint_but_no_private_activity(self) -> None:
        bluesky_policy = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=self.post_bluesky_dump(),
                table_state="rp\tru\trp\trp\trp\trp\trp\ttrue",
                bluesky_policy_output=bluesky_policy,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                sanitized = stream.read()
            self.assertIn(b"bluesky_jetstream_checkpoints", sanitized)
            self.assertIn(
                self.canonical_gate_seed(
                    youtube=True,
                    public_studies=True,
                    bluesky=True,
                ),
                sanitized,
            )
            self.assertNotIn(b"bluesky_jetstream_candidates (", sanitized)
            self.assertNotIn(b"bluesky_jetstream_observations (", sanitized)

    def test_backup_retains_nostr_checkpoints_but_no_private_activity(self) -> None:
        nostr_policy_output = (
            "nostr_relay_primal\t11111111-1111-4111-8111-111111111111\n"
            "nostr_relay_nos_lol\t22222222-2222-4222-8222-222222222222\n"
            "nostr_relay_nostr_net\t33333333-3333-4333-8333-333333333333"
        )
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=self.post_nostr_dump(),
                table_state="rp\tru\trp\trp\t0\t0\t0\trp\trp\trp\ttrue",
                nostr_policy_output=nostr_policy_output,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                sanitized = stream.read()
            self.assertIn(b"nostr_relay_checkpoints", sanitized)
            self.assertIn(
                self.canonical_gate_seed(
                    youtube=True,
                    public_studies=True,
                    nostr=True,
                ),
                sanitized,
            )
            self.assertNotIn(b"COPY ingest.nostr_relay_candidates (", sanitized)
            self.assertNotIn(b"COPY ingest.nostr_relay_observations (", sanitized)

    def test_backup_retains_mastodon_checkpoints_but_no_private_activity(self) -> None:
        mastodon_policy_output = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                dump=self.post_mastodon_dump(),
                table_state=(
                    "rp\tru\trp\trp\t0\t0\t0\t0\t0\t0\t"
                    "rp\trp\trp\trp\ttrue"
                ),
                mastodon_policy_output=mastodon_policy_output,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            backup = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            with gzip.open(backup, "rb") as stream:
                sanitized = stream.read()
            self.assertIn(b"mastodon_public_hashtag_checkpoints", sanitized)
            self.assertIn(b"mastodon_rate_cooldowns", sanitized)
            self.assertIn(
                self.canonical_gate_seed(
                    youtube=True,
                    public_studies=True,
                    mastodon=True,
                ),
                sanitized,
            )
            self.assertNotIn(
                b"COPY ingest.mastodon_public_hashtag_candidates (", sanitized
            )
            self.assertNotIn(
                b"COPY ingest.mastodon_public_hashtag_observations (", sanitized
            )

    def test_mastodon_policy_preflight_is_exact_and_atomic(self) -> None:
        valid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        table_state = (
            "rp\tru\trp\trp\t0\t0\t0\t0\t0\t0\t"
            "rp\trp\trp\trp\ttrue"
        )
        cases = {
            "missing": "",
            "ambiguous": valid + "\neeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            "malformed": "not-a-uuid",
        }
        for name, policy_output in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    dump=self.post_mastodon_dump(),
                    table_state=table_state,
                    mastodon_policy_output=policy_output,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_nostr_policy_rows_without_private_tables_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                nostr_policy_output=(
                    "nostr_relay_primal\t11111111-1111-4111-8111-111111111111"
                ),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Nostr retention policy exists", result.stderr)
            self.assertEqual(list(backup_dir.iterdir()), [])

    def test_nostr_policy_lookup_requires_exact_source_key_order(self) -> None:
        cases = {
            "missing-source-key": "11111111-1111-4111-8111-111111111111",
            "wrong-source-key": (
                "nostr_relay_nos_lol\t11111111-1111-4111-8111-111111111111"
            ),
            "wrong-order": (
                "nostr_relay_nos_lol\t22222222-2222-4222-8222-222222222222\n"
                "nostr_relay_primal\t11111111-1111-4111-8111-111111111111\n"
                "nostr_relay_nostr_net\t33333333-3333-4333-8333-333333333333"
            ),
        }
        for name, policy_output in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    dump=self.post_nostr_dump(),
                    table_state="rp\tru\trp\trp\t0\t0\t0\trp\trp\trp\ttrue",
                    nostr_policy_output=policy_output,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Nostr retention policy lookup", result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_psql_failure_is_atomic_and_does_not_expose_database_url(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            backup_dir = base / "backups"
            result = self.run_backup(
                fake_bin=fake_bin,
                backup_dir=backup_dir,
                timestamp="20260729T020000Z",
                psql_fail=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("very-secret", result.stdout + result.stderr)
            self.assertTrue(backup_dir.is_dir())
            self.assertEqual(list(backup_dir.iterdir()), [])

    def test_missing_ambiguous_and_malformed_policy_preflight_is_atomic(self) -> None:
        valid = "11111111-1111-4111-8111-111111111111"
        cases = {
            "missing": "",
            "ambiguous": valid + "\n22222222-2222-4222-8222-222222222222",
            "malformed": "not-a-uuid",
        }
        for name, policy_output in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    policy_output=policy_output,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_bluesky_policy_preflight_is_exact_and_atomic(self) -> None:
        valid = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        cases = {
            "missing": "",
            "ambiguous": valid + "\ndddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "malformed": "not-a-uuid",
        }
        for name, policy_output in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    dump=self.post_bluesky_dump(),
                    table_state="rp\tru\trp\trp\trp\trp\trp\ttrue",
                    bluesky_policy_output=policy_output,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_malformed_or_inconsistent_table_preflight_is_atomic(self) -> None:
        cases = {
            "malformed": "unexpected",
            "missing-policies": "0\tru\trp\t0\t0\t0\t0\ttrue",
            "unlogged-policies": "ru\tru\trp\t0\t0\t0\t0\ttrue",
            "missing-youtube-table": "rp\t0\trp\t0\t0\t0\t0\ttrue",
            "logged-youtube-table": "rp\trp\trp\t0\t0\t0\t0\ttrue",
            "temporary-youtube-table": "rp\trt\trp\t0\t0\t0\t0\ttrue",
            "youtube-view": "rp\tvp\trp\t0\t0\t0\t0\ttrue",
            "missing-request-gate": "rp\tru\t0\t0\t0\t0\t0\tfalse",
            "unlogged-request-gate": "rp\tru\tru\t0\t0\t0\t0\ttrue",
            "request-gate-without-maintain": "rp\tru\trp\t0\t0\t0\t0\tfalse",
            "unlogged-public-ledger": "rp\tru\trp\tru\t0\t0\t0\ttrue",
            "public-ledger-without-youtube": "rp\t0\trp\trp\t0\t0\t0\ttrue",
            "partial-bluesky-tables": "rp\tru\trp\trp\trp\t0\t0\ttrue",
            "unlogged-bluesky-checkpoint": "rp\tru\trp\trp\trp\trp\tru\ttrue",
            "partial-mastodon-tables": (
                "rp\tru\trp\trp\t0\t0\t0\t0\t0\t0\t"
                "rp\t0\trp\trp\ttrue"
            ),
            "unlogged-mastodon-checkpoint": (
                "rp\tru\trp\trp\t0\t0\t0\t0\t0\t0\t"
                "rp\trp\tru\trp\ttrue"
            ),
        }
        for name, table_state in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    table_state=table_state,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])

    def test_dump_snapshot_mismatches_are_atomic_and_do_not_advance_marker(
        self,
    ) -> None:
        policy = "11111111-1111-4111-8111-111111111111"
        wrong_policy = "33333333-3333-4333-8333-333333333333"
        policy_row = f"{policy}\tyoutube_discovery\n".encode()
        gate_ddl = self.gate_schema_dump(youtube=True)
        cache_ddl = b"CREATE UNLOGGED TABLE ingest.youtube_discoveries (\n);\n"
        cache_block = f"""COPY ingest.youtube_discoveries (video_id, source_policy_id) FROM stdin;
AbCdEfGhI_1\t{policy}
\\.
""".encode()
        valid_dump = (
            gate_ddl
            + cache_ddl
            + (
                f"""COPY ingest.source_policies (id, source_key) FROM stdin;
{policy}\tyoutube_discovery
33333333-3333-4333-8333-333333333333\ttcgdex_catalog
\\.
""".encode()
                + cache_block
            )
        )
        cases = {
            "missing-policy-row": valid_dump.replace(policy_row, b""),
            "duplicate-policy-row": valid_dump.replace(
                policy_row, policy_row + policy_row
            ),
            "missing-cache-copy": valid_dump.replace(cache_block, b""),
            "malformed-cache-copy": valid_dump.replace(
                b"video_id, source_policy_id",
                b"video_id, wrong_policy_column",
            ),
            "cache-policy-mismatch": valid_dump.replace(
                f"AbCdEfGhI_1\t{policy}".encode(),
                f"AbCdEfGhI_1\t{wrong_policy}".encode(),
            ),
            "logged-cache-create-race": valid_dump.replace(
                cache_ddl,
                b"CREATE TABLE ingest.youtube_discoveries (\n);\n",
            ),
            "missing-cache-create": valid_dump.replace(cache_ddl, b""),
            "duplicate-cache-create": valid_dump.replace(
                cache_ddl,
                cache_ddl + cache_ddl,
            ),
            "missing-request-gate-create": valid_dump.replace(gate_ddl, b""),
            "duplicate-request-gate-create": valid_dump.replace(
                gate_ddl,
                gate_ddl + gate_ddl,
            ),
            "unlogged-request-gate-create": valid_dump.replace(
                b"CREATE TABLE ingest.source_request_gates",
                b"CREATE UNLOGGED TABLE ingest.source_request_gates",
            ),
            "request-gate-schema-drift": valid_dump.replace(
                b"owner_job_id uuid", b"owner_job_id text"
            ),
            "request-gate-missing-force-rls": valid_dump.replace(
                b"ALTER TABLE ONLY ingest.source_request_gates FORCE ROW LEVEL SECURITY;\n",
                b"",
            ),
            "request-gate-missing-primary-key": valid_dump.replace(
                b"ALTER TABLE ONLY ingest.source_request_gates\n"
                b"    ADD CONSTRAINT source_request_gates_pkey PRIMARY KEY (source_key);\n",
                b"",
            ),
            "request-gate-missing-enable-rls": valid_dump.replace(
                b"ALTER TABLE ingest.source_request_gates ENABLE ROW LEVEL SECURITY;\n",
                b"",
            ),
            "request-gate-copy-data": valid_dump
            + b"COPY ingest.source_request_gates (source_key, owner_job_id) FROM stdin;\n"
            + b"tcgdex_catalog\taaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n\\.\n",
            "quoted-request-gate-copy-data": valid_dump
            + b'COPY "ingest"."source_request_gates" ("source_key") FROM stdin;\n'
            + b"tcgdex_catalog\n\\.\n",
            "request-gate-insert-data": valid_dump
            + b"INSERT INTO ingest.source_request_gates (source_key) VALUES ('tcgdex_catalog');\n",
        }
        for name, dump in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                fake_bin = self.make_fake_commands(base)
                backup_dir = base / "backups"
                result = self.run_backup(
                    fake_bin=fake_bin,
                    backup_dir=backup_dir,
                    timestamp="20260729T020000Z",
                    dump=dump,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("very-secret", result.stdout + result.stderr)
                self.assertEqual(list(backup_dir.iterdir()), [])


class DeployAndRollbackScriptTests(unittest.TestCase):
    @staticmethod
    def deployment_manifest(sha: str, *, nostr: bool = False) -> str:
        service_set = "tcgdex-nostr" if nostr else "tcgdex"
        services = (
            "collector,scheduler,watchdog,nostr-collector"
            if nostr
            else "collector,scheduler,watchdog"
        )
        return (
            "version=1\n"
            f"sha={sha}\n"
            f"service_set={service_set}\n"
            f"services={services}\n"
        )

    @staticmethod
    def write_nostr_env(path: Path) -> None:
        path.write_text(
            "DATA_MODE=live\n"
            "NOSTR_COLLECTION_ENABLED=true\n"
            "NOSTR_SUPABASE_DB_URL="
            "postgresql://pokecrack_nostr_worker_login:worker-secret@"
            "db.example.invalid/pokecrack?sslmode=require&"
            "options=-c%20role%3Dpokecrack_nostr_worker\n"
            "SUPABASE_NOSTR_PREFLIGHT_DB_URL="
            "postgresql://pokecrack_nostr_attestor_login:attestor-secret@"
            "db.example.invalid/pokecrack?sslmode=require&"
            "options=-c%20role%3Dpokecrack_nostr_attestor\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    def setUpRepository(self, base: Path) -> tuple[Path, str]:
        repository = base / "repository"
        deploy = repository / "deploy"
        scripts = deploy / "scripts"
        library = deploy / "lib"
        scripts.mkdir(parents=True)
        library.mkdir()
        shutil.copy2(DEPLOY_ROOT / "compose.prod.yml", deploy / "compose.prod.yml")
        shutil.copy2(
            DEPLOY_ROOT / "lib" / "shell_portability.sh",
            library / "shell_portability.sh",
        )
        for name in ("run_with_database_url.py", "verify_nostr_release.py"):
            shutil.copy2(DEPLOY_ROOT / "lib" / name, library / name)
        for name in ("deploy.sh", "rollback.sh"):
            shutil.copy2(DEPLOY_ROOT / "scripts" / name, scripts / name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=repository,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Deploy test"], cwd=repository, check=True
        )
        (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture"], cwd=repository, check=True
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        return repository, sha

    def make_fake_docker(self, base: Path) -> Path:
        fake_bin = base / "bin"
        fake_bin.mkdir()
        write_executable(
            fake_bin / "docker",
            """#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ ${1:-} == 'compose' ]]; then
  if [[ " $* " == *' ps -q '* ]]; then
    printf 'container-%s\n' "${*: -1}"
  fi
  exit 0
fi
if [[ ${1:-} == 'ps' ]]; then
  if [[ -n ${FAKE_PROJECT_ROWS:-} ]]; then
    printf '%s\n' "$FAKE_PROJECT_ROWS"
  fi
  exit 0
fi
if [[ ${1:-} == 'inspect' ]]; then
  if [[ ${FAKE_UNHEALTHY:-0} == 1 ]]; then
    printf '%s\n' 'running unhealthy'
  else
    printf '%s\n' 'running healthy'
  fi
  exit 0
fi
printf '%s\n' 'unexpected docker invocation' >&2
exit 97
""",
        )
        return fake_bin

    def environment(
        self, base: Path, fake_bin: Path
    ) -> tuple[dict[str, str], Path, Path]:
        docker_log = base / "docker.log"
        env_file = base / "production.env"
        env_file.write_text("DATA_MODE=demo\nAI_PROVIDER=fixture\n", encoding="utf-8")
        env_file.chmod(0o600)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["FAKE_DOCKER_LOG"] = str(docker_log)
        return environment, env_file, docker_log

    def test_deploy_checks_out_exact_sha_builds_starts_and_marks_health(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            state_dir = base / "state"
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(state_dir),
                    "--health-timeout",
                    "2",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            deployed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            self.assertEqual(deployed, sha)
            self.assertEqual(
                (state_dir / "last-successful-deployment").read_text(),
                self.deployment_manifest(sha),
            )
            self.assertEqual(
                stat.S_IMODE((state_dir / "last-successful-deployment").stat().st_mode),
                0o600,
            )
            invocations = docker_log.read_text(encoding="utf-8").splitlines()
            config_index = next(
                i
                for i, line in enumerate(invocations)
                if " config --quiet" in f" {line}"
            )
            build_index = next(
                i for i, line in enumerate(invocations) if " build " in f" {line} "
            )
            up_index = next(
                i for i, line in enumerate(invocations) if " up " in f" {line} "
            )
            inspect_index = next(
                i for i, line in enumerate(invocations) if line.startswith("inspect ")
            )
            self.assertLess(config_index, build_index)
            self.assertLess(build_index, up_index)
            self.assertLess(up_index, inspect_index)
            build = invocations[build_index]
            up = invocations[up_index]
            self.assertIn("build --pull collector scheduler watchdog", build)
            self.assertIn("up --detach collector scheduler watchdog", up)
            self.assertNotIn("--remove-orphans", up)
            self.assertNotIn("auth-browser", build + up)
            self.assertNotIn("ai-worker", build + up)
            self.assertNotIn("aggregator", build + up)
            self.assertIn(
                f"Deployment healthy at exact SHA {sha} for service set tcgdex ",
                result.stdout,
            )

    def test_nostr_service_set_uses_two_env_files_and_marks_four_healthy_services(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            nostr_env_file = base / "nostr.env"
            self.write_nostr_env(nostr_env_file)
            contract = json.dumps(
                {
                    key: True
                    for key in load_nostr_preflight_module().REQUIRED_CONTRACT_KEYS
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            write_executable(
                fake_bin / "psql",
                "#!/usr/bin/env bash\n" + f"printf '%s\\n' '{contract}'\n",
            )
            state_dir = base / "state"
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--nostr-env-file",
                    str(nostr_env_file),
                    "--state-dir",
                    str(state_dir),
                    "--health-timeout",
                    "2",
                    "--service-set",
                    "tcgdex-nostr",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (state_dir / "last-successful-deployment").read_text(),
                self.deployment_manifest(sha, nostr=True),
            )
            invocations = docker_log.read_text(encoding="utf-8").splitlines()
            build = next(line for line in invocations if " build " in f" {line} ")
            up = next(line for line in invocations if " up " in f" {line} ")
            self.assertIn("--profile nostr", build)
            self.assertIn(
                "build --pull collector scheduler watchdog nostr-collector", build
            )
            self.assertIn(
                "up --detach collector scheduler watchdog nostr-collector", up
            )
            self.assertNotIn("worker-secret", result.stdout + result.stderr)
            self.assertNotIn("attestor-secret", result.stdout + result.stderr)

    def test_failed_health_does_not_write_success_marker(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, _ = self.environment(base, fake_bin)
            environment["FAKE_UNHEALTHY"] = "1"
            state_dir = base / "state"
            state_dir.mkdir()
            previous = "1" * 40
            previous_marker = state_dir / "last-successful-deployment"
            previous_marker.write_text(self.deployment_manifest(previous))
            previous_marker.chmod(0o600)
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(state_dir),
                    "--health-timeout",
                    "1",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                (state_dir / "last-successful-deployment").read_text(),
                self.deployment_manifest(previous),
            )
            self.assertIn(f"Rollback commit: {previous}", result.stderr)

    def test_nostr_contract_failure_happens_before_any_service_replacement(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            nostr_env_file = base / "nostr.env"
            self.write_nostr_env(nostr_env_file)
            write_executable(fake_bin / "psql", "#!/usr/bin/env bash\nexit 17\n")
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--nostr-env-file",
                    str(nostr_env_file),
                    "--service-set",
                    "tcgdex-nostr",
                    "--state-dir",
                    str(base / "state"),
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("existing services were left unchanged", result.stderr)
            self.assertNotIn("worker-secret", result.stdout + result.stderr)
            self.assertNotIn("attestor-secret", result.stdout + result.stderr)
            self.assertFalse((base / "state" / "last-successful-deployment").exists())
            if docker_log.exists():
                invocations = docker_log.read_text(encoding="utf-8")
                self.assertNotIn(" build ", f" {invocations} ")
                self.assertNotIn(" up ", f" {invocations} ")

    def test_nostr_service_set_cannot_bypass_preflight_with_a_disabled_flag(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            nostr_env_file = base / "nostr.env"
            nostr_env_file.write_text(
                "DATA_MODE=live\nNOSTR_COLLECTION_ENABLED=false\n",
                encoding="utf-8",
            )
            nostr_env_file.chmod(0o600)
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--nostr-env-file",
                    str(nostr_env_file),
                    "--service-set",
                    "tcgdex-nostr",
                    "--state-dir",
                    str(base / "state"),
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("existing services were left unchanged", result.stderr)
            if docker_log.exists():
                invocations = docker_log.read_text(encoding="utf-8")
                self.assertNotIn(" build ", f" {invocations} ")
                self.assertNotIn(" up ", f" {invocations} ")

    def test_legacy_sha_only_marker_is_not_treated_as_a_service_set_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, _ = self.environment(base, fake_bin)
            environment["FAKE_UNHEALTHY"] = "1"
            state_dir = base / "state"
            state_dir.mkdir()
            (state_dir / "last-successful-sha").write_text("1" * 40 + "\n")
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(state_dir),
                    "--health-timeout",
                    "1",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Rollback commit:", result.stderr)

    def test_deploy_rejects_full_and_unknown_service_sets_before_docker(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            for service_set in ("full", "collector"):
                with self.subTest(service_set=service_set):
                    result = subprocess.run(
                        [
                            str(repository / "deploy" / "scripts" / "deploy.sh"),
                            sha,
                            "--env-file",
                            str(env_file),
                            "--state-dir",
                            str(base / f"state-{service_set}"),
                            "--service-set",
                            service_set,
                        ],
                        cwd=repository,
                        check=False,
                        text=True,
                        capture_output=True,
                        env=environment,
                    )
                    self.assertNotEqual(result.returncode, 0)
            self.assertFalse(docker_log.exists())

    def test_retiring_nostr_requires_the_explicit_flag_and_removes_only_that_service(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, docker_log = self.environment(base, fake_bin)
            environment["FAKE_PROJECT_ROWS"] = "container-nostr|nostr-collector"

            denied = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(base / "denied-state"),
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("explicit --retire-nostr", denied.stderr)

            docker_log.unlink(missing_ok=True)
            allowed = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "deploy.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(base / "allowed-state"),
                    "--retire-nostr",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            invocations = docker_log.read_text(encoding="utf-8")
            self.assertIn(" stop nostr-collector", f" {invocations}")
            self.assertIn(" rm --force --stop nostr-collector", f" {invocations}")
            self.assertNotIn("rm --force --stop collector", invocations)

    def test_existing_non_tcgdex_container_blocks_without_removing_it(self) -> None:
        cases = {
            "auth-browser": (
                "container-auth|auth-browser",
                "unapproved service container exists: auth-browser",
            ),
            "retired-worker": (
                "container-retired|retired-worker",
                "unapproved service container exists: retired-worker",
            ),
            "missing-label": (
                "container-unknown|",
                "Pokecrack project container is missing a valid Compose service label",
            ),
        }
        for name, (project_row, expected_error) in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                repository, sha = self.setUpRepository(base)
                fake_bin = self.make_fake_docker(base)
                environment, env_file, docker_log = self.environment(base, fake_bin)
                environment["FAKE_PROJECT_ROWS"] = project_row
                state_dir = base / "state"
                result = subprocess.run(
                    [
                        str(repository / "deploy" / "scripts" / "deploy.sh"),
                        sha,
                        "--env-file",
                        str(env_file),
                        "--state-dir",
                        str(state_dir),
                    ],
                    cwd=repository,
                    check=False,
                    text=True,
                    capture_output=True,
                    env=environment,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)
                self.assertFalse((state_dir / "last-successful-deployment").exists())
                invocations = docker_log.read_text(encoding="utf-8")
                self.assertNotIn(" stop ", f" {invocations} ")
                self.assertNotIn(" rm ", f" {invocations} ")
                self.assertNotIn(" up ", f" {invocations} ")

    def test_invalid_success_manifest_destination_fails_closed(self) -> None:
        for destination_kind in ("directory", "symlink"):
            with (
                self.subTest(destination_kind=destination_kind),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                repository, sha = self.setUpRepository(base)
                fake_bin = self.make_fake_docker(base)
                environment, env_file, docker_log = self.environment(base, fake_bin)
                state_dir = base / "state"
                state_dir.mkdir()
                manifest = state_dir / "last-successful-deployment"
                if destination_kind == "directory":
                    manifest.mkdir()
                else:
                    target = base / "outside-manifest"
                    target.write_text("must remain unchanged\n", encoding="utf-8")
                    manifest.symlink_to(target)

                result = subprocess.run(
                    [
                        str(repository / "deploy" / "scripts" / "deploy.sh"),
                        sha,
                        "--env-file",
                        str(env_file),
                        "--state-dir",
                        str(state_dir),
                        "--health-timeout",
                        "2",
                    ],
                    cwd=repository,
                    check=False,
                    text=True,
                    capture_output=True,
                    env=environment,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "success manifest path must be a regular, non-symlink file",
                    result.stderr,
                )
                if destination_kind == "directory":
                    self.assertTrue(manifest.is_dir())
                    self.assertEqual(list(manifest.iterdir()), [])
                else:
                    self.assertTrue(manifest.is_symlink())
                    self.assertEqual(target.read_text(), "must remain unchanged\n")
                self.assertEqual(
                    list(state_dir.glob(".last-successful-deployment.*")), []
                )
                self.assertFalse(docker_log.exists())

    def test_corrupt_success_manifests_are_not_reported_as_rollback(self) -> None:
        previous = "1" * 40
        canonical = self.deployment_manifest(previous)
        cases = {
            "missing-final-newline": canonical.rstrip("\n"),
            "extra-blank-line": canonical + "\n",
            "unterminated-trailing-bytes": canonical + "trailing",
        }
        for name, contents in cases.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary,
            ):
                base = Path(temporary)
                repository, sha = self.setUpRepository(base)
                fake_bin = self.make_fake_docker(base)
                environment, env_file, _ = self.environment(base, fake_bin)
                environment["FAKE_UNHEALTHY"] = "1"
                state_dir = base / "state"
                state_dir.mkdir()
                marker = state_dir / "last-successful-deployment"
                marker.write_text(contents, encoding="utf-8")
                marker.chmod(0o600)

                result = subprocess.run(
                    [
                        str(repository / "deploy" / "scripts" / "deploy.sh"),
                        sha,
                        "--env-file",
                        str(env_file),
                        "--state-dir",
                        str(state_dir),
                        "--health-timeout",
                        "1",
                    ],
                    cwd=repository,
                    check=False,
                    text=True,
                    capture_output=True,
                    env=environment,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Rollback commit:", result.stderr)
                self.assertEqual(marker.read_text(encoding="utf-8"), contents)

    def test_rollback_requires_and_forwards_an_explicit_commit(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            repository, sha = self.setUpRepository(base)
            fake_bin = self.make_fake_docker(base)
            environment, env_file, _ = self.environment(base, fake_bin)
            state_dir = base / "state"
            missing = subprocess.run(
                [str(repository / "deploy" / "scripts" / "rollback.sh")],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertNotEqual(missing.returncode, 0)
            result = subprocess.run(
                [
                    str(repository / "deploy" / "scripts" / "rollback.sh"),
                    sha,
                    "--env-file",
                    str(env_file),
                    "--state-dir",
                    str(state_dir),
                    "--health-timeout",
                    "2",
                ],
                cwd=repository,
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f"Rollback target {sha} is healthy for the selected deterministic service set",
                result.stdout,
            )


class CleanupScriptTests(unittest.TestCase):
    def test_cleanup_only_removes_stopped_project_containers_and_unused_labeled_images(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = base / "bin"
            fake_bin.mkdir()
            log = base / "docker.log"
            write_executable(
                fake_bin / "docker",
                """#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$FAKE_DOCKER_LOG"
exit 0
""",
            )
            env_file = base / "production.env"
            env_file.write_text(
                "DATA_MODE=demo\nAI_PROVIDER=fixture\n", encoding="utf-8"
            )
            env_file.chmod(0o600)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            environment["FAKE_DOCKER_LOG"] = str(log)
            result = subprocess.run(
                [
                    str(DEPLOY_ROOT / "scripts" / "cleanup.sh"),
                    "--env-file",
                    str(env_file),
                    "--image-retention-hours",
                    "48",
                ],
                check=False,
                text=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            invocations = log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any(" rm --force" in f" {line}" for line in invocations))
            self.assertTrue(
                any(
                    "label=com.pokecrack.runtime=worker" in line and "until=48h" in line
                    for line in invocations
                )
            )
            self.assertTrue(
                any(
                    "label=com.pokecrack.runtime=auth-browser" in line
                    and "until=48h" in line
                    for line in invocations
                )
            )
            combined = "\n".join(invocations)
            self.assertNotIn(" down", combined)
            self.assertNotIn("--stop", combined)


class ComposeSecurityPolicyTests(unittest.TestCase):
    def render(
        self, *, include_unready: bool = True, enable_nostr: bool = False
    ) -> dict[str, object]:
        if shutil.which("docker") is None:
            self.skipTest(
                "Docker CLI is unavailable; CI performs the Compose render contract"
            )
        environment = os.environ.copy()
        environment.update(
            {
                "DEPLOY_SHA": "0123456789abcdef0123456789abcdef01234567",
                "CHROMIUM_PROFILE_ROOT_HOST": "/tmp/pokecrack-test-profiles",
                "BACKUP_DIR": "/tmp/pokecrack-test-backups",
                "OPENCLI_EXTENSION_DIR": "/tmp/pokecrack-test-extension",
                "NOVNC_PASSWORD_FILE": "/tmp/pokecrack-test-novnc-password",
            }
        )
        if include_unready:
            environment["COMPOSE_PROFILES"] = "unready-full,nostr"
        else:
            environment.pop("COMPOSE_PROFILES", None)
        command = [
            "docker",
            "compose",
            "--env-file",
            str(DEPLOY_ROOT / "env" / "production.env.example"),
        ]
        if enable_nostr:
            command.extend(
                ["--env-file", str(DEPLOY_ROOT / "env" / "nostr.env.example")]
            )
        command.extend(
            ["-f", str(DEPLOY_ROOT / "compose.prod.yml"), "config", "--format", "json"]
        )
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            env=environment,
            cwd=REPOSITORY_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_services_have_health_hardening_limits_and_private_egress(self) -> None:
        document = self.render()
        services = document["services"]
        expected = {
            "collector",
            "nostr-collector",
            "auth-browser",
            "ai-worker",
            "aggregator",
            "scheduler",
            "watchdog",
        }
        self.assertEqual(set(services), expected)
        self.assertTrue(document["networks"]["internal"]["internal"])
        self.assertFalse(document["networks"]["egress"].get("internal", False))
        nostr_egress = document["networks"]["nostr-egress"]
        self.assertFalse(nostr_egress.get("internal", False))
        self.assertTrue(nostr_egress["enable_ipv6"])
        self.assertEqual(
            nostr_egress["ipam"]["config"], [{"subnet": "fd12:706f:6b65::/64"}]
        )
        for name, service in services.items():
            self.assertEqual(service["restart"], "unless-stopped", name)
            self.assertTrue(service["read_only"], name)
            self.assertIn("healthcheck", service, name)
            self.assertIn("/tmp", " ".join(service["tmpfs"]), name)
            expected_networks = (
                {"internal", "nostr-egress"}
                if name == "nostr-collector"
                else {"internal", "egress"}
            )
            self.assertEqual(set(service["networks"]), expected_networks, name)
            self.assertGreater(float(service["cpus"]), 0, name)
            self.assertGreater(int(service["mem_limit"]), 0, name)
            self.assertEqual(service["logging"]["driver"], "local", name)
            self.assertEqual(service["logging"]["options"]["max-size"], "10m", name)
            self.assertEqual(service["logging"]["options"]["max-file"], "5", name)
        worker_images = {
            services[name]["image"] for name in expected - {"auth-browser"}
        }
        self.assertEqual(len(worker_images), 1)

    def test_default_compose_profile_contains_only_tcgdex_core_services(self) -> None:
        services = self.render(include_unready=False)["services"]
        self.assertEqual(set(services), {"collector", "scheduler", "watchdog"})

    def test_nostr_profile_has_one_dedicated_database_capability(self) -> None:
        document = self.render(enable_nostr=True)
        services = document["services"]
        nostr = services["nostr-collector"]
        environment = nostr["environment"]
        self.assertEqual(nostr["profiles"], ["nostr"])
        self.assertEqual(nostr["command"], ["nostr-collector"])
        self.assertEqual(environment["WORKER_ROLE"], "nostr-collector")
        self.assertEqual(environment["WORKER_ID"], "nostr-collector-1")
        self.assertEqual(environment["NOSTR_COLLECTION_ENABLED"], "true")
        self.assertEqual(environment["WORKER_MAX_CONCURRENCY"], "1")
        self.assertEqual(set(nostr["networks"]), {"internal", "nostr-egress"})
        self.assertNotIn("egress", nostr["networks"])
        self.assertIn("NOSTR_SUPABASE_DB_URL", environment)
        self.assertNotIn("SUPABASE_DB_URL", environment)
        self.assertNotIn("SUPABASE_NOSTR_PREFLIGHT_DB_URL", environment)
        self.assertNotIn("YOUTUBE_API_KEY", environment)
        self.assertEqual(
            services["collector"]["environment"]["NOSTR_COLLECTION_ENABLED"],
            "false",
        )
        self.assertEqual(
            services["scheduler"]["environment"]["NOSTR_COLLECTION_ENABLED"],
            "false",
        )
        self.assertNotIn(
            "NOSTR_SUPABASE_DB_URL", services["scheduler"]["environment"]
        )
        rendered = json.dumps(document)
        self.assertNotIn("SUPABASE_NOSTR_PREFLIGHT_DB_URL", rendered)

        nostr_template = DEPLOY_ROOT / "env" / "nostr.env.example"
        assignments = {
            line.split("=", 1)[0]
            for line in nostr_template.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        }
        self.assertEqual(
            assignments,
            {
                "DATA_MODE",
                "NOSTR_COLLECTION_ENABLED",
                "NOSTR_SUPABASE_DB_URL",
                "SUPABASE_NOSTR_PREFLIGHT_DB_URL",
            },
        )

    def test_worker_services_do_not_receive_unused_supabase_service_role_secret(
        self,
    ) -> None:
        services = self.render()["services"]
        for name, service in services.items():
            self.assertNotIn(
                "SUPABASE_SECRET_KEY", service.get("environment", {}), name
            )
        production_env = (DEPLOY_ROOT / "env" / "production.env.example").read_text()
        self.assertNotIn("SUPABASE_SECRET_KEY", production_env)
        root_env = (REPOSITORY_ROOT / ".env.example").read_text()
        self.assertNotIn("SUPABASE_SECRET_KEY", root_env)

    def test_root_example_environment_defaults_to_network_free_fixture_mode(
        self,
    ) -> None:
        root_env = (REPOSITORY_ROOT / ".env.example").read_text()
        self.assertIn("DATA_MODE=demo", root_env)
        self.assertIn("AI_PROVIDER=fixture", root_env)
        self.assertIn("SCRAPLING_DYNAMIC_ENABLED=false", root_env)
        self.assertIn("OPENCLI_ENABLED=false", root_env)

    def test_only_loopback_novnc_is_published_and_sensitive_volumes_are_declared(
        self,
    ) -> None:
        document = self.render()
        services = document["services"]
        for name, service in services.items():
            ports = service.get("ports", [])
            if name == "auth-browser":
                self.assertEqual(len(ports), 1)
                self.assertEqual(ports[0]["host_ip"], "127.0.0.1")
                self.assertEqual(ports[0]["published"], "6080")
                self.assertEqual(ports[0]["target"], 6080)
            else:
                self.assertEqual(ports, [], name)
        self.assertEqual(set(document["volumes"]), {"browser_profiles", "backups"})
        rendered = json.dumps(document)
        self.assertNotIn("/var/run/docker.sock", rendered)
        self.assertNotRegex(rendered, r'"published"\s*:\s*"?(9222|5900|19825)')

    def test_ai_worker_receives_explicit_cost_rates_for_fail_closed_budgeting(
        self,
    ) -> None:
        environment = self.render()["services"]["ai-worker"]["environment"]
        self.assertIn("AI_INPUT_PER_MILLION_AUD", environment)
        self.assertIn("AI_OUTPUT_PER_MILLION_AUD", environment)
        self.assertEqual(environment["AI_MAX_OUTPUT_TOKENS"], "4096")

    def test_youtube_collection_flag_reaches_scheduler_without_sharing_the_api_key(
        self,
    ) -> None:
        compose = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        collector = compose[
            compose.index("  collector:") : compose.index("  nostr-collector:")
        ]
        scheduler = compose[
            compose.index("  scheduler:") : compose.index("  watchdog:")
        ]
        expected_flag = (
            'YOUTUBE_COLLECTION_ENABLED: "${YOUTUBE_COLLECTION_ENABLED:-false}"'
        )
        self.assertIn(expected_flag, collector)
        self.assertIn(expected_flag, scheduler)
        self.assertIn("YOUTUBE_API_KEY:", collector)
        self.assertIn("MATON_API_KEY:", collector)
        self.assertIn("YOUTUBE_MATON_CONNECTION_ID:", collector)
        self.assertNotIn("YOUTUBE_API_KEY:", scheduler)
        self.assertNotIn("MATON_API_KEY:", scheduler)
        self.assertNotIn("YOUTUBE_MATON_CONNECTION_ID:", scheduler)

    def test_nostr_enablement_is_pinned_to_the_isolated_collector(self) -> None:
        compose = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        collector = compose[
            compose.index("  collector:") : compose.index("  nostr-collector:")
        ]
        nostr = compose[
            compose.index("  nostr-collector:") : compose.index("  auth-browser:")
        ]
        scheduler = compose[
            compose.index("  scheduler:") : compose.index("  watchdog:")
        ]
        self.assertIn('NOSTR_COLLECTION_ENABLED: "false"', collector)
        self.assertIn('NOSTR_COLLECTION_ENABLED: "true"', nostr)
        self.assertIn('NOSTR_COLLECTION_ENABLED: "false"', scheduler)
        self.assertNotIn("${NOSTR_COLLECTION_ENABLED", collector)
        self.assertNotIn("${NOSTR_COLLECTION_ENABLED", scheduler)
        self.assertNotIn("SCHEDULE_NOSTR_COLLECTION", scheduler)
        self.assertIn("NOSTR_SUPABASE_DB_URL:", nostr)
        self.assertNotIn("NOSTR_SUPABASE_DB_URL:", scheduler)

    def test_public_study_schedule_matches_the_fail_closed_worker_contract(
        self,
    ) -> None:
        compose = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        collector = compose[
            compose.index("  collector:") : compose.index("  nostr-collector:")
        ]
        scheduler = compose[
            compose.index("  scheduler:") : compose.index("  watchdog:")
        ]
        expected_flag = (
            "PUBLIC_STUDY_COLLECTION_ENABLED: "
            '"${PUBLIC_STUDY_COLLECTION_ENABLED:-false}"'
        )

        self.assertIn(expected_flag, collector)
        self.assertIn(expected_flag, scheduler)
        self.assertIn(
            'SCHEDULE_PUBLIC_COLLECTION: "${SCHEDULE_PUBLIC_COLLECTION:-15 4 * * *}"',
            scheduler,
        )
        self.assertIn(
            "SCHEDULE_PUBLIC_COLLECTION=15 4 * * *",
            (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8"),
        )

    def test_worker_image_installs_the_bounded_youtube_transport(self) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.worker").read_text(encoding="utf-8")
        self.assertIn(
            "apt-get install --yes --no-install-recommends ca-certificates curl",
            dockerfile,
        )
        self.assertIn("rm -rf /var/lib/apt/lists/*", dockerfile)

    def test_worker_base_image_is_pinned_by_digest_in_build_and_compose_defaults(self) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.worker").read_text(encoding="utf-8")
        match = re.search(
            r"^ARG PYTHON_IMAGE=(python:3\.13\.5-slim-bookworm@sha256:[0-9a-f]{64})$",
            dockerfile,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(match)
        image = match.group(1) if match is not None else ""
        compose = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn(f"PYTHON_IMAGE:-{image}", compose)
        self.assertNotIn("PYTHON_IMAGE:-python:3.13.5-slim-bookworm}", compose)

    def test_auth_browser_pins_opencli_and_starts_its_loopback_daemon(self) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(
            encoding="utf-8"
        )
        entrypoint = (DEPLOY_ROOT / "auth-browser-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        document = self.render()
        build_args = document["services"]["auth-browser"]["build"]["args"]
        self.assertIn("OPENCLI_VERSION", build_args)
        self.assertIn("@jackwener/opencli@${OPENCLI_VERSION}", dockerfile)
        self.assertNotIn("@jackwener/opencli@latest", dockerfile)
        self.assertIn(
            "/usr/local/lib/node_modules/@jackwener/opencli/dist/src/main.js",
            dockerfile,
        )
        self.assertNotIn(
            "/usr/local/lib/node_modules/@jackwener/opencli/dist/main.js",
            dockerfile,
        )
        self.assertIn("opencli daemon restart", entrypoint)
        self.assertIn("pokecrack_browser.container_browser", entrypoint)

    def test_auth_browser_runtime_dependencies_and_startup_order_are_health_compatible(
        self,
    ) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(
            encoding="utf-8"
        )
        entrypoint = (DEPLOY_ROOT / "auth-browser-entrypoint.sh").read_text(
            encoding="utf-8"
        )
        healthcheck = (DEPLOY_ROOT / "auth-browser-healthcheck.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("services/auth-browser/pyproject.toml", dockerfile)
        self.assertIn(
            "pip install --no-cache-dir /opt/pokecrack/auth-browser", dockerfile
        )
        self.assertIn("pokecrack-browser --version", dockerfile)
        self.assertNotIn("PYTHONPATH=", dockerfile)
        manager_start = entrypoint.index("pokecrack_browser.container_browser")
        cdp_probe = entrypoint.index("/json/version")
        daemon_start = entrypoint.index("opencli daemon restart")
        self.assertLess(manager_start, cdp_probe)
        self.assertLess(cdp_probe, daemon_start)
        self.assertNotIn('chromium "${chromium_arguments[@]}"', entrypoint)
        self.assertIn("browser-supervisor.pid", entrypoint)
        self.assertIn("browser-supervisor", healthcheck)
        self.assertIn("process_matches_identity", healthcheck)
        self.assertIn("opencli doctor", healthcheck)
        self.assertIn("run_bounded_process", healthcheck)
        self.assertIn("if [[ ${OPENCLI_ENABLED:-false} == true ]]; then", healthcheck)
        self.assertIn("/json/version", healthcheck)

    def test_auth_browser_uses_canonical_extension_path(self) -> None:
        document = self.render()
        service = document["services"]["auth-browser"]
        self.assertEqual(
            service["environment"]["POKECRACK_BRIDGE_EXTENSION_PATH"],
            "/opt/pokecrack/opencli-extension/current",
        )
        secret = service["secrets"][0]
        self.assertEqual(secret["source"], "novnc_password")
        self.assertEqual(secret["uid"], "10001")
        self.assertEqual(secret["gid"], "10001")
        self.assertEqual(secret["mode"], "0400")
        extension_mount = next(
            mount
            for mount in service["volumes"]
            if mount["target"] == "/opt/pokecrack/opencli-extension"
        )
        self.assertEqual(extension_mount["type"], "bind")
        self.assertEqual(extension_mount["source"], "/tmp/pokecrack-test-extension")
        self.assertTrue(extension_mount["read_only"])
        compose_source = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn(
            "${OPENCLI_EXTENSION_DIR:-/opt/pokecrack/opencli-extension}", compose_source
        )
        self.assertIn("create_host_path: false", compose_source)
        self.assertFalse(extension_mount.get("bind", {}).get("create_host_path", False))
        self.assertTrue(
            any(
                "uid=10001" in item and "gid=10001" in item for item in service["tmpfs"]
            )
        )
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(
            encoding="utf-8"
        )
        self.assertIn("/profiles", dockerfile)
        self.assertIn("install -d -o 10001 -g 10001 -m 0700", dockerfile)

    def test_worker_service_roles_delegate_live_readiness_to_the_worker_composition(
        self,
    ) -> None:
        entrypoint = (DEPLOY_ROOT / "worker-service-entrypoint.sh").read_text()
        self.assertNotIn('if [[ "${DATA_MODE:-demo}" != "demo" ]]', entrypoint)
        self.assertIn("collector|nostr-collector|ai-worker|watchdog)", entrypoint)
        self.assertIn("command=(pokecrack-worker worker --forever)", entrypoint)
        self.assertIn("command=(pokecrack-worker scheduler)", entrypoint)
        self.assertIn("command=(pokecrack-worker aggregate all)", entrypoint)

        expected_commands = {
            "collector": "worker --forever",
            "nostr-collector": "worker --forever",
            "ai-worker": "worker --forever",
            "watchdog": "worker --forever",
            "aggregator": "aggregate all",
            "scheduler": "scheduler",
        }
        for role, expected in expected_commands.items():
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                executable = root / "pokecrack-worker"
                invocation = root / "invocation.txt"
                executable.write_text(
                    '#!/usr/bin/env bash\nprintf "%s\\n" "$*" > "$POKECRACK_TEST_INVOCATION"\nexit 78\n',
                    encoding="utf-8",
                )
                executable.chmod(0o755)
                environment = os.environ.copy()
                environment.update(
                    {
                        "DATA_MODE": "live",
                        "PATH": f"{root}:{environment['PATH']}",
                        "POKECRACK_TEST_INVOCATION": str(invocation),
                    }
                )
                result = subprocess.run(
                    [str(DEPLOY_ROOT / "worker-service-entrypoint.sh"), role],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    env=environment,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(
                    invocation.read_text(encoding="utf-8").strip(), expected
                )
                self.assertNotIn("production database-backed", result.stderr)

    def test_live_worker_concurrency_defaults_to_supported_single_process_mode(
        self,
    ) -> None:
        source = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn('WORKER_MAX_CONCURRENCY: "${WORKER_MAX_CONCURRENCY:-1}"', source)
        root_example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
        production_example = (DEPLOY_ROOT / "env" / "production.env.example").read_text(
            encoding="utf-8"
        )
        self.assertIn("WORKER_MAX_CONCURRENCY=1", root_example)
        self.assertIn("WORKER_MAX_CONCURRENCY=1", production_example)
        self.assertIn(
            "CHROMIUM_PROFILE_ROOT_HOST=/opt/pokecrack/browser-profiles", root_example
        )
        self.assertIn(
            "CHROMIUM_PROFILE_ROOT_HOST=/opt/pokecrack/browser-profiles",
            production_example,
        )
        for stale_name in (
            "POKECRACK_PROFILE_ROOT=",
            "POKECRACK_EXTENSION_ROOT=",
            "POKECRACK_BACKUP_ROOT=",
        ):
            self.assertNotIn(stale_name, root_example)
            self.assertNotIn(stale_name, production_example)

    def test_required_operator_entrypoints_are_executable(self) -> None:
        required = {
            "deploy.sh",
            "rollback.sh",
            "backup.sh",
            "cleanup.sh",
            "install-opencli-extension.sh",
        }
        scripts = DEPLOY_ROOT / "scripts"
        self.assertEqual({path.name for path in scripts.glob("*.sh")}, required)
        for name in required:
            self.assertTrue(os.access(scripts / name, os.X_OK), name)


if __name__ == "__main__":
    unittest.main()
