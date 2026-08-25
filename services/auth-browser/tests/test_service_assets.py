from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_service_has_installable_cli_and_locked_local_environment(self) -> None:
        pyproject = tomllib.loads((SERVICE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(
            pyproject["project"]["scripts"]["pokecrack-browser"],
            "pokecrack_browser.cli:main",
        )
        self.assertEqual(pyproject["project"]["dependencies"], ["playwright==1.55.0"])
        self.assertTrue((SERVICE_ROOT / "uv.lock").is_file())


class ContainerAssetTests(unittest.TestCase):
    def test_container_has_no_public_api_or_exposed_ports_and_no_floating_bridge_download(
        self,
    ) -> None:
        dockerfile = (SERVICE_ROOT / "Dockerfile").read_text(encoding="utf-8")
        lowered = dockerfile.lower()
        self.assertIn("mcr.microsoft.com/playwright/python:v1.55.0-noble", dockerfile)
        self.assertNotIn("expose ", lowered)
        self.assertNotIn("curl", lowered)
        self.assertNotIn("wget", lowered)
        self.assertNotIn("latest", lowered)
        self.assertIn("/opt/pokecrack/opencli-extension", dockerfile)

    def test_supervisor_binds_vnc_novnc_daemon_and_x11_safely(self) -> None:
        supervisor = (SERVICE_ROOT / "container" / "supervisord.conf").read_text(encoding="utf-8")
        self.assertIn("Xvfb :99", supervisor)
        self.assertIn("-nolisten tcp", supervisor)
        self.assertIn("x11vnc", supervisor)
        self.assertIn("-listen 127.0.0.1", supervisor)
        self.assertIn("-rfbport 5900", supervisor)
        self.assertIn("127.0.0.1:6080", supervisor)
        self.assertIn("127.0.0.1:5900", supervisor)
        self.assertIn("run_bridge_daemon.py", supervisor)
        self.assertIn("startretries=3", supervisor)

    def test_host_network_example_keeps_all_four_ports_on_host_loopback(self) -> None:
        compose = (SERVICE_ROOT / "compose.example.yaml").read_text(encoding="utf-8")
        self.assertIn("network_mode: host", compose)
        self.assertNotIn("ports:", compose)
        for port in (5900, 6080, 9222, 19825):
            self.assertIn(f"127.0.0.1:{port}", compose)

    def test_entrypoint_requires_private_profile_and_vnc_secret_without_backups(self) -> None:
        entrypoint = (SERVICE_ROOT / "container" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("container_init", entrypoint)
        self.assertIn("supervisord", entrypoint)
        self.assertNotIn("tar ", entrypoint)
        self.assertNotIn("upload", entrypoint.lower())
        self.assertTrue((SERVICE_ROOT / "container" / "run_bridge_daemon.py").is_file())


if __name__ == "__main__":
    unittest.main()
