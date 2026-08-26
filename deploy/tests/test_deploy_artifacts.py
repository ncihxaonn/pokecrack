from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import tempfile
import unittest
import zipfile


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

            selected = retention.select_backups_to_delete(paths + [unrelated], daily=7, weekly=4)
            selected_names = {path.name for path in selected}

            parsed = [(path, retention.parse_backup_timestamp(path)) for path in paths]
            daily_dates = sorted({timestamp.date() for _, timestamp in parsed}, reverse=True)[:7]
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
                        if (item[1].isocalendar().year, item[1].isocalendar().week) == key
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

            result = self.install(version="1.2.3", archive=first, install_root=install_root, fake_bin=fake_bin)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install_root / "current").resolve().name, "1.2.3")
            self.assertFalse((install_root / "previous").exists())

            result = self.install(version="1.2.4", archive=second, install_root=install_root, fake_bin=fake_bin)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((install_root / "current").resolve().name, "1.2.4")
            self.assertEqual((install_root / "previous").resolve().name, "1.2.3")

            result = subprocess.run(
                [str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"), "rollback", "--install-root", str(install_root)],
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
            write_executable(fake_bin / "curl", f"#!/usr/bin/env bash\ntouch {marker!s}\nexit 99\n")
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            for suffix in ("?token=must-not-log", "#fragment"):
                result = subprocess.run(
                    [
                        str(DEPLOY_ROOT / "scripts" / "install-opencli-extension.sh"),
                        "install",
                        "--version", "1.2.3",
                        "--sha256", "0" * 64,
                        "--url", f"https://downloads.example.invalid/bridge.zip{suffix}",
                        "--install-root", str(base / "extension"),
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

    def test_download_failure_cleans_up_without_masking_the_original_status(self) -> None:
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
                    "--version", "1.2.3",
                    "--sha256", "0" * 64,
                    "--url", "https://downloads.example.invalid/bridge.zip",
                    "--install-root", str(base / "extension"),
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


class BackupScriptTests(unittest.TestCase):
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
[[ ${PGDATABASE:-} == 'postgresql://backup-user:very-secret@example.invalid/pokecrack' ]]
for argument in "$@"; do
  [[ $argument != *'very-secret'* ]]
done
if [[ ${FAKE_EMPTY_DUMP:-0} == 1 ]]; then
  exit 0
fi
printf '%s\n' '-- PostgreSQL database dump fixture' 'CREATE TABLE fixture (id integer);'
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
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
        environment["FAKE_UTC"] = timestamp
        environment["SUPABASE_DB_URL"] = (
            "postgresql://backup-user:very-secret@example.invalid/pokecrack"
        )
        environment["BACKUP_DIR"] = str(backup_dir)
        environment["BACKUP_RETENTION_DAILY"] = "7"
        environment["BACKUP_RETENTION_WEEKLY"] = "4"
        if empty:
            environment["FAKE_EMPTY_DUMP"] = "1"
        return subprocess.run(
            [str(DEPLOY_ROOT / "scripts" / "backup.sh")],
            check=False,
            text=True,
            capture_output=True,
            env=environment,
        )

    def test_database_url_file_must_be_owner_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=DEPLOY_ROOT / "tests") as temporary:
            base = Path(temporary)
            fake_bin = self.make_fake_commands(base)
            credential_file = base / "database-url"
            credential_file.write_text("postgresql://backup-user:fixture@example.invalid/pokecrack\n", encoding="utf-8")
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
            all_paths = [backup_dir / f"pokecrack-{timestamp}.sql.gz" for timestamp in timestamps]
            expected_deleted = {
                path.name
                for path in retention.select_backups_to_delete(all_paths, daily=7, weekly=4)
            }
            actual_names = {path.name for path in backup_dir.glob("pokecrack-*.sql.gz")}
            self.assertEqual(actual_names, {path.name for path in all_paths} - expected_deleted)
            latest = backup_dir / "pokecrack-20260729T020000Z.sql.gz"
            self.assertTrue(latest.is_file())
            with gzip.open(latest, "rt", encoding="utf-8") as stream:
                self.assertIn("CREATE TABLE fixture", stream.read())
            marker_lines = (backup_dir / ".last-successful-backup").read_text(
                encoding="utf-8"
            ).splitlines()
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


class DeployAndRollbackScriptTests(unittest.TestCase):
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
        for name in ("deploy.sh", "rollback.sh"):
            shutil.copy2(DEPLOY_ROOT / "scripts" / name, scripts / name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.name", "Deploy test"], cwd=repository, check=True)
        (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repository, check=True)
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

    def environment(self, base: Path, fake_bin: Path) -> tuple[dict[str, str], Path, Path]:
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
            self.assertEqual((state_dir / "last-successful-sha").read_text().strip(), sha)
            invocations = docker_log.read_text(encoding="utf-8").splitlines()
            config_index = next(i for i, line in enumerate(invocations) if " config --quiet" in f" {line}")
            build_index = next(i for i, line in enumerate(invocations) if " build " in f" {line} ")
            up_index = next(i for i, line in enumerate(invocations) if " up " in f" {line} ")
            inspect_index = next(i for i, line in enumerate(invocations) if line.startswith("inspect "))
            self.assertLess(config_index, build_index)
            self.assertLess(build_index, up_index)
            self.assertLess(up_index, inspect_index)
            self.assertIn(f"Deployment healthy at exact SHA {sha}", result.stdout)

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
            (state_dir / "last-successful-sha").write_text(previous + "\n")
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
            self.assertEqual((state_dir / "last-successful-sha").read_text().strip(), previous)
            self.assertIn(f"Rollback commit: {previous}", result.stderr)

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
            self.assertIn(f"Rollback target {sha} is healthy", result.stdout)


class CleanupScriptTests(unittest.TestCase):
    def test_cleanup_only_removes_stopped_project_containers_and_unused_labeled_images(self) -> None:
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
            env_file.write_text("DATA_MODE=demo\nAI_PROVIDER=fixture\n", encoding="utf-8")
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
                any("label=com.pokecrack.runtime=worker" in line and "until=48h" in line for line in invocations)
            )
            self.assertTrue(
                any("label=com.pokecrack.runtime=auth-browser" in line and "until=48h" in line for line in invocations)
            )
            combined = "\n".join(invocations)
            self.assertNotIn(" down", combined)
            self.assertNotIn("--stop", combined)


class ComposeSecurityPolicyTests(unittest.TestCase):
    def render(self) -> dict[str, object]:
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
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(DEPLOY_ROOT / "env" / "production.env.example"),
                "-f",
                str(DEPLOY_ROOT / "compose.prod.yml"),
                "config",
                "--format",
                "json",
            ],
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
        expected = {"collector", "auth-browser", "ai-worker", "aggregator", "scheduler", "watchdog"}
        self.assertEqual(set(services), expected)
        self.assertTrue(document["networks"]["internal"]["internal"])
        self.assertFalse(document["networks"]["egress"].get("internal", False))
        for name, service in services.items():
            self.assertEqual(service["restart"], "unless-stopped", name)
            self.assertTrue(service["read_only"], name)
            self.assertIn("healthcheck", service, name)
            self.assertIn("/tmp", " ".join(service["tmpfs"]), name)
            self.assertEqual(set(service["networks"]), {"internal", "egress"}, name)
            self.assertGreater(float(service["cpus"]), 0, name)
            self.assertGreater(int(service["mem_limit"]), 0, name)
        worker_images = {
            services[name]["image"]
            for name in expected - {"auth-browser"}
        }
        self.assertEqual(len(worker_images), 1)

    def test_worker_services_do_not_receive_unused_supabase_service_role_secret(self) -> None:
        services = self.render()["services"]
        for name, service in services.items():
            self.assertNotIn("SUPABASE_SECRET_KEY", service.get("environment", {}), name)
        production_env = (DEPLOY_ROOT / "env" / "production.env.example").read_text()
        self.assertNotIn("SUPABASE_SECRET_KEY", production_env)
        root_env = (REPOSITORY_ROOT / ".env.example").read_text()
        self.assertNotIn("SUPABASE_SECRET_KEY", root_env)

    def test_root_example_environment_defaults_to_network_free_fixture_mode(self) -> None:
        root_env = (REPOSITORY_ROOT / ".env.example").read_text()
        self.assertIn("DATA_MODE=demo", root_env)
        self.assertIn("AI_PROVIDER=fixture", root_env)
        self.assertIn("SCRAPLING_DYNAMIC_ENABLED=false", root_env)
        self.assertIn("OPENCLI_ENABLED=false", root_env)

    def test_only_loopback_novnc_is_published_and_sensitive_volumes_are_declared(self) -> None:
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

    def test_ai_worker_receives_explicit_cost_rates_for_fail_closed_budgeting(self) -> None:
        environment = self.render()["services"]["ai-worker"]["environment"]
        self.assertIn("AI_INPUT_PER_MILLION_AUD", environment)
        self.assertIn("AI_OUTPUT_PER_MILLION_AUD", environment)
        self.assertEqual(environment["AI_MAX_OUTPUT_TOKENS"], "4096")

    def test_auth_browser_pins_opencli_and_starts_its_loopback_daemon(self) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(encoding="utf-8")
        entrypoint = (DEPLOY_ROOT / "auth-browser-entrypoint.sh").read_text(encoding="utf-8")
        document = self.render()
        build_args = document["services"]["auth-browser"]["build"]["args"]
        self.assertIn("OPENCLI_VERSION", build_args)
        self.assertIn("@jackwener/opencli@${OPENCLI_VERSION}", dockerfile)
        self.assertNotIn("@jackwener/opencli@latest", dockerfile)
        self.assertIn("opencli daemon restart", entrypoint)
        self.assertIn("pokecrack_browser.container_browser", entrypoint)

    def test_auth_browser_runtime_dependencies_and_startup_order_are_health_compatible(self) -> None:
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(encoding="utf-8")
        entrypoint = (DEPLOY_ROOT / "auth-browser-entrypoint.sh").read_text(encoding="utf-8")
        healthcheck = (DEPLOY_ROOT / "auth-browser-healthcheck.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("services/auth-browser/pyproject.toml", dockerfile)
        self.assertIn("pip install --no-cache-dir /opt/pokecrack/auth-browser", dockerfile)
        self.assertIn("pokecrack-browser --version", dockerfile)
        self.assertNotIn("PYTHONPATH=", dockerfile)
        manager_start = entrypoint.index("pokecrack_browser.container_browser")
        cdp_probe = entrypoint.index('/json/version')
        daemon_start = entrypoint.index('opencli daemon restart')
        self.assertLess(manager_start, cdp_probe)
        self.assertLess(cdp_probe, daemon_start)
        self.assertNotIn('chromium "${chromium_arguments[@]}"', entrypoint)
        self.assertIn("browser-supervisor.pid", entrypoint)
        self.assertIn("browser-supervisor", healthcheck)
        self.assertIn("process_matches_identity", healthcheck)
        self.assertIn("opencli doctor", healthcheck)
        self.assertIn("run_bounded_process", healthcheck)
        self.assertIn('if [[ ${OPENCLI_ENABLED:-false} == true ]]; then', healthcheck)
        self.assertIn('/json/version', healthcheck)

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
            mount for mount in service["volumes"]
            if mount["target"] == "/opt/pokecrack/opencli-extension"
        )
        self.assertEqual(extension_mount["type"], "bind")
        self.assertEqual(extension_mount["source"], "/tmp/pokecrack-test-extension")
        self.assertTrue(extension_mount["read_only"])
        compose_source = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn("${OPENCLI_EXTENSION_DIR:-/opt/pokecrack/opencli-extension}", compose_source)
        self.assertFalse(extension_mount["bind"]["create_host_path"])
        self.assertTrue(any("uid=10001" in item and "gid=10001" in item for item in service["tmpfs"]))
        dockerfile = (DEPLOY_ROOT / "Dockerfile.auth-browser").read_text(encoding="utf-8")
        self.assertIn("/profiles", dockerfile)
        self.assertIn("install -d -o 10001 -g 10001 -m 0700", dockerfile)

    def test_worker_service_roles_delegate_live_readiness_to_the_worker_composition(self) -> None:
        entrypoint = (DEPLOY_ROOT / "worker-service-entrypoint.sh").read_text()
        self.assertNotIn('if [[ "${DATA_MODE:-demo}" != "demo" ]]', entrypoint)
        self.assertIn("collector|ai-worker|watchdog)", entrypoint)
        self.assertIn("command=(pokecrack-worker worker --forever)", entrypoint)
        self.assertIn("command=(pokecrack-worker scheduler)", entrypoint)
        self.assertIn("command=(pokecrack-worker aggregate all)", entrypoint)

        expected_commands = {
            "collector": "worker --forever",
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
                self.assertEqual(invocation.read_text(encoding="utf-8").strip(), expected)
                self.assertNotIn("production database-backed", result.stderr)

    def test_live_worker_concurrency_defaults_to_supported_single_process_mode(self) -> None:
        source = (DEPLOY_ROOT / "compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn('WORKER_MAX_CONCURRENCY: "${WORKER_MAX_CONCURRENCY:-1}"', source)
        root_example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
        production_example = (DEPLOY_ROOT / "env" / "production.env.example").read_text(
            encoding="utf-8"
        )
        self.assertIn("WORKER_MAX_CONCURRENCY=1", root_example)
        self.assertIn("WORKER_MAX_CONCURRENCY=1", production_example)
        self.assertIn("CHROMIUM_PROFILE_ROOT_HOST=/opt/pokecrack/browser-profiles", root_example)
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
