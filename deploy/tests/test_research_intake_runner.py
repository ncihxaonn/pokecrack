"""No runtime intake against a different checkout, image or collector."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy/scripts/import-research-intake.sh"
REVISION = "a" * 40
CONTAINER = "b" * 12
IMAGE = "sha256:" + "c" * 64


class ResearchIntakeRunnerTests(unittest.TestCase):
    def test_real_script_rejects_nonproduction_checkout_without_docker(self):
        result = subprocess.run(["bash", str(SCRIPT)], input=b"{}", capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"unapproved_runtime_path", result.stderr)

    def run_mock(self, args=(REVISION,), **overrides):
        with tempfile.TemporaryDirectory(prefix="pokecrack-intake-runner-") as temp:
            root = Path(temp)
            script = root / "deploy/scripts/import-research-intake.sh"
            script.parent.mkdir(parents=True)
            # Only the explicit approved root is replaced in this isolated fixture.
            script.write_text(SCRIPT.read_text().replace("/home/codex/pokecrack", str(root)))
            binaries = root / "bin"
            binaries.mkdir()
            programs = {
                "git": '#!/bin/sh\nprintf "%s\\n" "$TEST_REVISION"\n',
                "timeout": '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do case "$1" in --*) shift;; [0-9]*) shift;; *) break;; esac; done\nexec "$@"\n',
                "docker": '''#!/bin/sh
case "$1 $2" in
  'ps -q') printf '%s\\n' "$TEST_CONTAINER";;
  'inspect --format') printf '%s\\n' "$TEST_IMAGE";;
  'image inspect') printf '%s\\n' "$TEST_IMAGE_REVISION";;
  'exec -i') printf '%s\\n' "$*" > "$TEST_EXEC_LOG"; cat;;
  *) exit 99;;
esac
''',
            }
            for name, body in programs.items():
                target = binaries / name
                target.write_text(body)
                target.chmod(0o700)
            log = root / "exec.log"
            env = {**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}",
                   "TEST_REVISION": REVISION, "TEST_CONTAINER": CONTAINER,
                   "TEST_IMAGE": IMAGE, "TEST_IMAGE_REVISION": REVISION,
                   "TEST_EXEC_LOG": str(log), **overrides}
            result = subprocess.run(["bash", str(script), *args], input=b'{"references":[]}',
                                    capture_output=True, env=env)
            return result, log.read_text() if log.exists() else None

    def test_matching_release_forwards_stdin_once_without_credentials(self):
        result, log = self.run_mock()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'{"references":[]}')
        self.assertEqual(log, f"exec -i {CONTAINER} pokecrack-worker intake-research\n")

    def test_mismatched_missing_or_multiple_runtime_never_executes(self):
        for overrides in (
            {"TEST_IMAGE_REVISION": "d" * 40},
            {"TEST_CONTAINER": ""},
            {"TEST_CONTAINER": CONTAINER + "\n" + "e" * 12},
            {"TEST_IMAGE": "not-an-image"},
            {"TEST_REVISION": "not-a-commit"},
        ):
            with self.subTest(overrides=overrides):
                result, log = self.run_mock(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(log)

    def test_manifest_workflow_revision_must_match_runtime_checkout(self):
        for args in ((), ("d" * 40,), ("invalid",), (REVISION, "extra")):
            with self.subTest(args=args):
                result, log = self.run_mock(args=args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(log)


if __name__ == "__main__":
    unittest.main()
