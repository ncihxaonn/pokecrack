from __future__ import annotations

import unittest
from pathlib import Path

from pokecrack_browser.adapters import (
    DEFAULT_ADAPTER_ROOT,
    AdapterConfigError,
    AdapterSpec,
    load_adapter,
)


class AdapterDescriptorTests(unittest.TestCase):
    def test_fixture_descriptor_has_complete_pinned_contract(self) -> None:
        adapter = load_adapter("fixture", DEFAULT_ADAPTER_ROOT)

        self.assertEqual(adapter.name, "fixture")
        self.assertEqual(adapter.profile, "research-general")
        self.assertTrue(adapter.version)
        self.assertGreaterEqual(len(adapter.argv), 2)
        self.assertGreaterEqual(len(adapter.auth_health_argv), 2)
        self.assertGreaterEqual(len(adapter.version_argv), 2)
        self.assertIsInstance(adapter.json_schema, dict)
        self.assertGreater(adapter.timeout_seconds, 0)
        self.assertGreater(adapter.max_results, 0)
        self.assertGreaterEqual(adapter.min_interval_seconds, 0)
        self.assertFalse(adapter.requires_browser)
        self.assertEqual(adapter.allowed_source_hosts, frozenset({"research.example.invalid"}))
        self.assertTrue((DEFAULT_ADAPTER_ROOT / "fixture-output.json").is_file())

    def test_untrusted_query_is_one_argv_token_and_never_a_shell_fragment(self) -> None:
        adapter = load_adapter("fixture", DEFAULT_ADAPTER_ROOT)
        query = "cards; touch /tmp/never-created && $(id)"

        argv = adapter.render_argv(query=query, max_results=3)

        self.assertIn(query, argv)
        self.assertEqual(argv.count(query), 1)
        self.assertNotIn("-c", argv[:3])
        self.assertNotIn("shell=True", argv)

    def test_shell_wrappers_control_characters_and_embedded_placeholders_are_rejected(self) -> None:
        base = {
            "name": "unsafe",
            "version": "1.0.0",
            "argv": ["opencli", "{query}"],
            "profile": "research-general",
            "allowed_source_hosts": ["research.example.invalid"],
            "query": {"required": False, "max_length": 100},
            "json_schema": {"type": "object"},
            "timeout_seconds": 5,
            "max_results": 5,
            "min_interval_seconds": 0,
            "auth_health_argv": ["opencli", "auth-health"],
            "version_argv": ["opencli", "--version"],
        }
        for bad_argv in (
            ["sh", "-c", "opencli {query}"],
            ["opencli", "--query={query}"],
            ["opencli", "bad\nargument"],
        ):
            with self.subTest(argv=bad_argv), self.assertRaises(AdapterConfigError):
                AdapterSpec.from_mapping({**base, "argv": bad_argv}, source=Path("unsafe.json"))

    def test_adapter_output_host_allowlist_rejects_missing_and_unsafe_hosts(self) -> None:
        base = {
            "name": "unsafe",
            "version": "1.0.0",
            "argv": ["opencli", "{query}"],
            "profile": "research-general",
            "query": {"required": False, "max_length": 100},
            "json_schema": {"type": "object"},
            "timeout_seconds": 5,
            "max_results": 5,
            "min_interval_seconds": 0,
            "auth_health_argv": ["opencli", "auth-health"],
            "version_argv": ["opencli", "--version"],
        }
        for hosts in (None, [], ["localhost"], ["127.0.0.1"], ["*.example.com"]):
            value = dict(base)
            if hosts is not None:
                value["allowed_source_hosts"] = hosts
            with self.subTest(hosts=hosts), self.assertRaises(AdapterConfigError):
                AdapterSpec.from_mapping(value, source=Path("unsafe.json"))

    def test_adapter_name_cannot_escape_adapter_root(self) -> None:
        with self.assertRaises(AdapterConfigError):
            load_adapter("../fixture", DEFAULT_ADAPTER_ROOT)


if __name__ == "__main__":
    unittest.main()
