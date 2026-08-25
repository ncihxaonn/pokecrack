from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from pokecrack_browser.browser_process import run_persistent_context
from pokecrack_browser.launcher import BrowserLaunchConfig, playwright_launch_options
from pokecrack_browser.paths import PathValidationError, validate_extension_path


class ExtensionValidationTests(unittest.TestCase):
    def _extension(self, root: Path, *, version: str = "1.2.3") -> Path:
        extension = root / "bridge-extension"
        extension.mkdir()
        (extension / "manifest.json").write_text(
            json.dumps(
                {
                    "manifest_version": 3,
                    "name": "Browser Bridge",
                    "version": version,
                    "background": {"service_worker": "background.js"},
                }
            ),
            encoding="utf-8",
        )
        (extension / "background.js").write_text("// fixture", encoding="utf-8")
        return extension

    def test_extension_path_and_version_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            extension = self._extension(Path(temporary))
            with self.assertRaisesRegex(PathValidationError, "version"):
                validate_extension_path(extension, expected_version="9.9.9")
            with self.assertRaisesRegex(PathValidationError, "absolute"):
                validate_extension_path(Path("bridge-extension"), expected_version="1.2.3")

    def test_symlinked_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extension = self._extension(root)
            link = root / "bridge-link"
            link.symlink_to(extension, target_is_directory=True)
            with self.assertRaisesRegex(PathValidationError, "symbolic link|traversal"):
                validate_extension_path(link, expected_version="1.2.3")


class LauncherArgumentTests(unittest.TestCase):
    def test_persistent_context_is_headed_with_pinned_extension_and_loopback_cdp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / "profile"
            extension = root / "bridge-extension"
            profile.mkdir()
            extension.mkdir()
            config = BrowserLaunchConfig(
                profile_dir=profile,
                extension_dir=extension,
                cdp_host="127.0.0.1",
                cdp_port=9222,
            )

            options = playwright_launch_options(config)

            self.assertEqual(options["user_data_dir"], str(profile))
            self.assertIs(options["headless"], False)
            self.assertIn(f"--disable-extensions-except={extension}", options["args"])
            self.assertIn(f"--load-extension={extension}", options["args"])
            self.assertIn("--remote-debugging-address=127.0.0.1", options["args"])
            self.assertIn("--remote-debugging-port=9222", options["args"])
            self.assertNotIn("--remote-allow-origins=*", options["args"])
            self.assertNotIn("ws_endpoint", options)

    def test_non_loopback_cdp_and_invalid_port_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for host, port in (
                ("0.0.0.0", 9222),
                ("::", 9222),
                ("127.0.0.1", 0),
                ("127.0.0.1", 70000),
            ):
                with self.subTest(host=host, port=port), self.assertRaises(ValueError):
                    BrowserLaunchConfig(root / "profile", root / "extension", host, port)


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.options: dict[str, object] | None = None

    def launch_persistent_context(self, **options: object) -> _FakeContext:
        self.options = options
        return self.context


class _FakePlaywrightManager:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium

    def __enter__(self) -> _FakePlaywrightManager:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class PersistentContextTests(unittest.TestCase):
    def test_worker_uses_playwright_context_and_closes_it_on_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = BrowserLaunchConfig(root / "profile", root / "extension")
            context = _FakeContext()
            chromium = _FakeChromium(context)
            stop = threading.Event()
            stop.set()

            run_persistent_context(
                config,
                stop_event=stop,
                playwright_factory=lambda: _FakePlaywrightManager(chromium),
            )

            assert chromium.options is not None
            self.assertEqual(chromium.options["user_data_dir"], str(config.profile_dir))
            self.assertIs(chromium.options["headless"], False)
            self.assertTrue(context.closed)


if __name__ == "__main__":
    unittest.main()
