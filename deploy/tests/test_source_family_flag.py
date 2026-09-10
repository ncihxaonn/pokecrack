import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "lib/update_source_family_flag.py"


class SourceFamilyFlagTests(unittest.TestCase):
    def run_helper(
        self, path: Path, value: str = "true", family: str = "pokesup"
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(HELPER), "--env-file", str(path), "--value", value, "--family", family],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_numbered_opt_in_and_parent_dependency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pokecrack-numbered-flag-") as tmp:
            path = Path(tmp) / "runtime.env"
            original = "PUBLIC_STUDY_COLLECTION_ENABLED=true\nSOURCE_FAMILY_COLLECTION_ENABLED=true\nOTHER=untouched\n"
            path.write_text(original)
            path.chmod(0o600)
            result = self.run_helper(path, family="numbered")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text(), original + "NUMBERED_FAMILY_COLLECTION_ENABLED=true\n")
            self.assertNotEqual(self.run_helper(path, "false").returncode, 0)
            self.assertEqual(self.run_helper(path, "false", "numbered").returncode, 0)
            self.assertEqual(self.run_helper(path, "false").returncode, 0)
            self.assertNotEqual(self.run_helper(path, "true", "numbered").returncode, 0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_only_flag_changes_and_disable_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pokecrack-family-flag-") as tmp:
            path = Path(tmp) / "runtime.env"
            original = (
                "PUBLIC_STUDY_COLLECTION_ENABLED=true\nUNRELATED=private-test-value\n"
            )
            path.write_text(original)
            path.chmod(0o600)
            first = self.run_helper(path)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(
                path.read_text(), original + "SOURCE_FAMILY_COLLECTION_ENABLED=true\n"
            )
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("private-test-value", first.stdout + first.stderr)
            for _ in range(2):
                self.assertEqual(self.run_helper(path, "false").returncode, 0)
                self.assertEqual(
                    path.read_text(),
                    original + "SOURCE_FAMILY_COLLECTION_ENABLED=false\n",
                )

    def test_symlink_loose_permissions_duplicates_and_prerequisites_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="pokecrack-family-flag-") as tmp:
            directory = Path(tmp)
            path = directory / "runtime.env"
            base = "PUBLIC_STUDY_COLLECTION_ENABLED=true\n"
            for bad in [
                "OTHER=x\n",
                base
                + "SOURCE_FAMILY_COLLECTION_ENABLED=true\nSOURCE_FAMILY_COLLECTION_ENABLED=false\n",
                base + "export SOURCE_FAMILY_COLLECTION_ENABLED=true\n",
                base.rstrip("\n"),
            ]:
                path.write_text(bad)
                path.chmod(0o600)
                self.assertNotEqual(self.run_helper(path).returncode, 0)
                self.assertEqual(path.read_text(), bad)
            path.write_text(base)
            path.chmod(0o644)
            self.assertNotEqual(self.run_helper(path).returncode, 0)
            path.chmod(0o600)
            link = directory / "linked.env"
            link.symlink_to(path)
            self.assertNotEqual(self.run_helper(link).returncode, 0)
            os.chmod(directory, 0o777)
            self.assertNotEqual(self.run_helper(path).returncode, 0)
            os.chmod(directory, 0o700)
