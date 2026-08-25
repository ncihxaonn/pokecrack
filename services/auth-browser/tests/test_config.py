from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pokecrack_browser.config import ServiceSettings


class ServiceSettingsTests(unittest.TestCase):
    def test_default_extension_path_uses_deploy_managed_current_link(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = ServiceSettings.from_env()
        self.assertEqual(
            settings.extension_dir,
            Path("/opt/pokecrack/opencli-extension/current"),
        )

    def test_network_services_reject_non_loopback_hosts(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            ServiceSettings(cdp_host="0.0.0.0")
        with self.assertRaisesRegex(ValueError, "loopback"):
            ServiceSettings(daemon_host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
