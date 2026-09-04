from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEPLOY_ROOT = Path(__file__).resolve().parents[1]
RUNNER = DEPLOY_ROOT / "lib" / "run_backup_from_env.py"


class BackupEnvironmentRunnerTests(unittest.TestCase):
    def write_environment(self, root: Path, body: str, *, mode: int = 0o600) -> Path:
        path = root / "production.env"
        path.write_text(body, encoding="utf-8")
        path.chmod(mode)
        return path

    def write_fake_backup(self, root: Path) -> Path:
        path = root / "fake-backup.py"
        path.write_text(
            """#!/usr/bin/env python3
import gzip
import json
import os
from pathlib import Path

backup_dir = Path(os.environ["BACKUP_DIR"])
backup_dir.mkdir(mode=0o700)
filename = "pokecrack-20260904T101112Z.sql.gz"
with gzip.open(backup_dir / filename, "wb") as stream:
    stream.write(b"reviewed backup fixture")
(backup_dir / filename).chmod(0o600)
(backup_dir / ".last-successful-backup").write_text(
    filename + "\\ncompleted_at=20260904T101112Z\\n",
    encoding="utf-8",
)
(backup_dir / ".last-successful-backup").chmod(0o600)
(backup_dir / "child-environment.json").write_text(
    json.dumps(sorted(os.environ)),
    encoding="utf-8",
)
""",
            encoding="utf-8",
        )
        path.chmod(0o700)
        return path

    def run_runner(
        self,
        *,
        env_file: Path,
        backup_script: Path,
        default_db_url_file: Path,
        dedicated_db_url_file: Path | None = None,
        postgres_client_directory: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(RUNNER),
            "--env-file",
            str(env_file),
            "--backup-script",
            str(backup_script),
            "--default-db-url-file",
            str(default_db_url_file),
        ]
        if postgres_client_directory is not None:
            command.extend(
                ["--postgres-client-directory", str(postgres_client_directory)]
            )
        if dedicated_db_url_file is not None:
            command.extend(
                ["--dedicated-db-url-file", str(dedicated_db_url_file)]
            )
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )

    def write_postgres_clients(self, root: Path, *, mode: int = 0o500) -> Path:
        directory = root / "postgres-client"
        directory.mkdir(mode=0o700)
        for command in ("pg_dump", "psql"):
            path = directory / command
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(mode)
        return directory

    def test_runs_with_allowlisted_dotenv_projection_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            backup_dir = root / "backups"
            injection_marker = root / "injected"
            env_file = self.write_environment(
                root,
                "\n".join(
                    (
                        f"BACKUP_DIR={backup_dir}",
                        "BACKUP_RETENTION_DAILY=7",
                        "BACKUP_RETENTION_WEEKLY=4",
                        "BACKUP_PREFLIGHT_ROLE=postgres",
                        "SUPABASE_DB_URL='postgresql://fixture.invalid/db?sslmode=require&connect_timeout=5'",
                        "AI_API_KEY=must-not-reach-child",
                        "SCHEDULE_CATALOG_SYNC=0 2,14 * * *",
                        f"UNRELATED_COMMAND=$(touch {injection_marker})",
                    )
                )
                + "\n",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "pokecrack-20260904T101112Z.sql.gz\n")
            self.assertFalse(injection_marker.exists())
            child_keys = json.loads(
                (backup_dir / "child-environment.json").read_text(encoding="utf-8")
            )
            self.assertIn("SUPABASE_DB_URL", child_keys)
            self.assertIn("BACKUP_PREFLIGHT_ROLE", child_keys)
            self.assertNotIn("AI_API_KEY", child_keys)
            self.assertNotIn("SCHEDULE_CATALOG_SYNC", child_keys)
            self.assertNotIn("UNRELATED_COMMAND", child_keys)

    def test_accepts_private_reviewed_postgres_clients(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            backup_dir = root / "backups"
            env_file = self.write_environment(
                root,
                f"BACKUP_DIR={backup_dir}\nSUPABASE_DB_URL=postgresql://fixture.invalid/db?sslmode=require\n",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
                postgres_client_directory=self.write_postgres_clients(root),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_group_accessible_postgres_clients(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            env_file = self.write_environment(
                root,
                f"BACKUP_DIR={root / 'backups'}\nSUPABASE_DB_URL=secret-value\n",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
                postgres_client_directory=self.write_postgres_clients(
                    root, mode=0o550
                ),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_rejects_postgres_client_path_separator_injection(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            env_file = self.write_environment(
                root,
                f"BACKUP_DIR={root / 'backups'}\nSUPABASE_DB_URL=secret-value\n",
            )
            client_directory = self.write_postgres_clients(root)
            injected_directory = root / "postgres-client:unreviewed"
            client_directory.rename(injected_directory)
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
                postgres_client_directory=injected_directory,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_rejects_group_readable_environment_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            env_file = self.write_environment(
                root,
                f"BACKUP_DIR={root / 'backups'}\nSUPABASE_DB_URL=secret-value\n",
                mode=0o640,
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_rejects_symlinked_environment_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            target = self.write_environment(
                root,
                f"BACKUP_DIR={root / 'backups'}\nSUPABASE_DB_URL=secret-value\n",
            )
            env_file = root / "production-link.env"
            env_file.symlink_to(target)
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_rejects_environment_below_group_writable_parent(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            unsafe_parent = root / "group-writable"
            unsafe_parent.mkdir(mode=0o770)
            unsafe_parent.chmod(0o770)
            env_file = self.write_environment(
                unsafe_parent,
                f"BACKUP_DIR={root / 'backups'}\nSUPABASE_DB_URL=secret-value\n",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_rejects_duplicate_allowlisted_assignment(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            env_file = self.write_environment(
                root,
                "\n".join(
                    (
                        f"BACKUP_DIR={root / 'first'}",
                        f"BACKUP_DIR={root / 'second'}",
                        "SUPABASE_DB_URL=secret-value",
                    )
                )
                + "\n",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=root / "unused-db-url",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("secret-value", result.stderr)

    def test_reads_default_database_url_file_without_forwarding_its_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            backup_dir = root / "backups"
            env_file = self.write_environment(root, f"BACKUP_DIR={backup_dir}\n")
            database_url_file = root / "supabase-db-url"
            database_url_file.write_text(
                "postgresql://fixture.invalid/db?sslmode=require&connect_timeout=5\n",
                encoding="utf-8",
            )
            database_url_file.chmod(0o600)
            result = self.run_runner(
                env_file=env_file,
                backup_script=self.write_fake_backup(root),
                default_db_url_file=database_url_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            child_keys = json.loads(
                (backup_dir / "child-environment.json").read_text(encoding="utf-8")
            )
            self.assertIn("SUPABASE_DB_URL", child_keys)
            self.assertNotIn("SUPABASE_DB_URL_FILE", child_keys)

    def test_dedicated_database_url_file_overrides_inline_worker_url(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            root = Path(temporary).resolve()
            backup_dir = root / "backups"
            env_file = self.write_environment(
                root,
                f"BACKUP_DIR={backup_dir}\nSUPABASE_DB_URL=postgresql://worker.invalid/db?sslmode=require\n",
            )
            database_url_file = root / "supabase-db-url"
            dedicated_url = (
                "postgresql://backup.invalid/db?sslmode=require&connect_timeout=5"
            )
            database_url_file.write_text(dedicated_url + "\n", encoding="utf-8")
            database_url_file.chmod(0o600)
            backup_script = self.write_fake_backup(root)
            backup_script.write_text(
                backup_script.read_text(encoding="utf-8")
                + "\nassert os.environ['SUPABASE_DB_URL'] == "
                + repr(dedicated_url)
                + "\n",
                encoding="utf-8",
            )
            result = self.run_runner(
                env_file=env_file,
                backup_script=backup_script,
                default_db_url_file=root / "unused-db-url",
                dedicated_db_url_file=database_url_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
