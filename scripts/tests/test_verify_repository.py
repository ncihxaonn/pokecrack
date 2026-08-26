import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_repository import (
    find_client_secret_exposure,
    find_forbidden_artifacts,
    find_forbidden_dependencies,
    find_large_files,
    find_missing_gitleaks_pr_permissions,
    find_probable_secrets,
    find_unpinned_actions,
)


class RepositoryGuardTests(unittest.TestCase):
    def test_forbidden_artifacts_flags_env_profile_backup_and_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                ".env",
                "browser-profiles/social-western/Cookies",
                "backups/live.sql.gz",
                "evidence/source.mp4",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            findings = find_forbidden_artifacts(root)

            self.assertEqual(4, len(findings))

    def test_examples_and_gitkeep_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = (
                ".env.example",
                "deploy/env/production.example",
                "services/auth-browser/profiles/.gitkeep",
                "data/examples/opencli.example.json",
            )
            for relative in allowed:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture", encoding="utf-8")

            self.assertEqual([], find_forbidden_artifacts(root))

    def test_client_secret_environment_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "apps/web/src/config/env.ts"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("process.env.NEXT_PUBLIC_SUPABASE_SECRET_KEY", encoding="utf-8")

            findings = find_client_secret_exposure(root)

            self.assertEqual(1, len(findings))

    def test_paid_dependencies_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "apps/web/package.json"
            package.parent.mkdir(parents=True, exist_ok=True)
            package.write_text(json.dumps({"dependencies": {"stripe": "1.0.0"}}), encoding="utf-8")

            findings = find_forbidden_dependencies(root)

            self.assertEqual(1, len(findings))

    def test_github_actions_must_use_full_commit_shas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                "steps:\n  - uses: actions/checkout@v4\n  - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4\n",
                encoding="utf-8",
            )
            self.assertEqual([".github/workflows/ci.yml:2:actions/checkout@v4"], find_unpinned_actions(root))

    def test_gitleaks_pr_workflow_requires_pull_request_read_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                "\n".join(
                    (
                        "on:",
                        "  pull_request:",
                        "permissions:",
                        "  contents: read",
                        "jobs:",
                        "  scan:",
                        "    steps:",
                        "      - uses: gitleaks/gitleaks-action@" + "a" * 40,
                    )
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                [".github/workflows/ci.yml"],
                find_missing_gitleaks_pr_permissions(root),
            )

            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "  contents: read",
                    "  contents: read\n  pull-requests: read",
                ),
                encoding="utf-8",
            )
            self.assertEqual([], find_missing_gitleaks_pr_permissions(root))

    def test_large_files_are_rejected_at_configured_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "assets/large.bin"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"x" * 32)

            self.assertEqual(["assets/large.bin"], find_large_files(root, max_bytes=16))

    def test_probable_literal_secret_is_rejected_but_placeholder_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "service/config.py"
            bad.parent.mkdir(parents=True, exist_ok=True)
            bad.write_text('api_key = "live-super-secret-value"', encoding="utf-8")
            example = root / ".env.example"
            example.write_text("AI_API_KEY=", encoding="utf-8")

            findings = find_probable_secrets(root)

            self.assertEqual(1, len(findings))

    def test_high_confidence_tokens_use_regex_word_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "service/config.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "\n".join(
                    (
                        "github = 'ghp_" + "a" * 36 + "'",
                        "aws = 'AKIA" + "B" * 16 + "'",
                        "slack = 'xoxb-" + "c" * 24 + "'",
                        "openai = 'sk-" + "d" * 24 + "'",
                    )
                ),
                encoding="utf-8",
            )

            findings = find_probable_secrets(root)

            self.assertEqual(
                ["service/config.py:high-confidence-token"],
                findings,
            )

    def test_high_confidence_token_prefixes_inside_words_are_not_matched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "service/config.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("notaghp_" + "a" * 36, encoding="utf-8")

            self.assertEqual([], find_probable_secrets(root))


if __name__ == "__main__":
    unittest.main()
