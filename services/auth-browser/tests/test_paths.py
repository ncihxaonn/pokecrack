from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from pokecrack_browser.paths import (
    ALLOWED_PROFILES,
    PathValidationError,
    prepare_profile_directory,
    validate_extension_path,
    validate_profile_name,
)


class ProfileNameTests(unittest.TestCase):
    def test_profile_name_is_restricted_to_initial_allowlist(self) -> None:
        self.assertEqual(
            ALLOWED_PROFILES,
            frozenset({"social-western", "social-chinese", "research-general"}),
        )
        for name in ALLOWED_PROFILES:
            self.assertEqual(validate_profile_name(name), name)
        for name in ("../social-western", "default", "", "social-western/other"):
            with self.subTest(name=name), self.assertRaises(PathValidationError):
                validate_profile_name(name)


class ProfileDirectoryTests(unittest.TestCase):
    def test_new_root_and_profile_are_created_with_mode_0700(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "profiles"
            profile = prepare_profile_directory(root, "social-western", create=True)

            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(profile.stat().st_mode), 0o700)
            self.assertEqual(profile, root / "social-western")

    def test_existing_root_and_profile_must_have_mode_0700(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "profiles"
            profile = root / "social-western"
            profile.mkdir(parents=True)
            os.chmod(root, 0o700)
            os.chmod(profile, 0o755)

            with self.assertRaisesRegex(PathValidationError, "0700"):
                prepare_profile_directory(root, "social-western")

            os.chmod(profile, 0o700)
            os.chmod(root, 0o750)
            with self.assertRaisesRegex(PathValidationError, "0700"):
                prepare_profile_directory(root, "social-western")

    def test_root_and_profile_must_be_absolute_real_directories(self) -> None:
        with self.assertRaisesRegex(PathValidationError, "absolute"):
            prepare_profile_directory(Path("profiles"), "social-western")

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            real_root = base / "real"
            real_profile = real_root / "social-western"
            real_profile.mkdir(parents=True)
            os.chmod(real_root, 0o700)
            os.chmod(real_profile, 0o700)

            root_link = base / "profiles"
            root_link.symlink_to(real_root, target_is_directory=True)
            with self.assertRaisesRegex(PathValidationError, "symbolic link"):
                prepare_profile_directory(root_link, "social-western")

            root = base / "clean"
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            (root / "social-western").symlink_to(real_profile, target_is_directory=True)
            with self.assertRaisesRegex(PathValidationError, "symbolic link"):
                prepare_profile_directory(root, "social-western")


class ExtensionPathTests(unittest.TestCase):
    def test_valid_extension_is_an_absolute_pinned_unpacked_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            extension = Path(temporary).resolve() / "opencli-extension"
            extension.mkdir(mode=0o755)
            manifest = {
                "manifest_version": 3,
                "name": "OpenCLI",
                "version": "1.0.23",
                "background": {"service_worker": "dist/background.js"},
            }
            (extension / "manifest.json").write_text(json.dumps(manifest))

            validated = validate_extension_path(extension, expected_version="1.0.23")

            self.assertEqual(validated, extension)

    def test_managed_current_symlink_to_pinned_in_root_release_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            install_root = Path(temporary).resolve() / "opencli-extension"
            release = install_root / "releases" / "1.2.3"
            release.mkdir(parents=True)
            (release / "manifest.json").write_text(
                json.dumps(
                    {
                        "manifest_version": 3,
                        "name": "Browser Bridge",
                        "version": "1.2.3",
                    }
                ),
                encoding="utf-8",
            )
            current = install_root / "current"
            current.symlink_to(Path("releases") / "1.2.3", target_is_directory=True)

            validated = validate_extension_path(current, expected_version="1.2.3")

            self.assertEqual(validated, release.resolve())

    def test_managed_current_symlink_outside_install_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            install_root = base / "opencli-extension"
            (install_root / "releases" / "1.2.3").mkdir(parents=True)
            outside = base / "outside" / "1.2.3"
            outside.mkdir(parents=True)
            (outside / "manifest.json").write_text(
                json.dumps(
                    {
                        "manifest_version": 3,
                        "name": "Browser Bridge",
                        "version": "1.2.3",
                    }
                ),
                encoding="utf-8",
            )
            current = install_root / "current"
            current.symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(PathValidationError, "outside|managed release"):
                validate_extension_path(current, expected_version="1.2.3")


if __name__ == "__main__":
    unittest.main()
