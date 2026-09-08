from __future__ import annotations

import unittest
from pathlib import Path

from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    InMemoryPolicyAuditSink,
    PolicyDeniedError,
    SourcePolicyRegistry,
)

ROOT = Path(__file__).resolve().parents[3]


class RestrictedSourceInventoryTests(unittest.TestCase):
    def test_registered_restriction_has_no_collection_route(self) -> None:
        registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
        policy = registry.resolve(
            "https://cardshoplive.com/pages/hit-rates-for-pokemon-tcg-scarlet-and-violet"
        )
        self.assertEqual(policy.name, "Card Shop Live")
        self.assertFalse(policy.enabled)
        self.assertFalse(policy.statistics_eligible_default)
        self.assertEqual(policy.routes, frozenset())
        self.assertEqual(policy.config["security_finding_status"], "not_established")
        self.assertEqual(policy.retention_days, 0)

    def test_every_route_and_subdomain_is_denied_without_network(self) -> None:
        # Policy authorization is local; no HTTP client is constructed or called.
        audit = InMemoryPolicyAuditSink()
        registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml", audit_sink=audit)
        for host in (
            "cardshoplive.com",
            "www.cardshoplive.com",
            "digitaltq.com",
            "www.digitaltq.com",
            "api.digitaltq.com",
        ):
            for route in CollectorRoute:
                with self.subTest(host=host, route=route), self.assertRaises(PolicyDeniedError):
                    registry.require(f"https://{host}/pages/pull-rates", route)
        self.assertEqual(len(audit.events), 5 * len(CollectorRoute))

    def test_digitaltq_has_no_retention_or_statistical_admission(self) -> None:
        registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
        policy = registry.resolve("https://www.digitaltq.com/pokemon-151-pull-rates-pokemon-tcg")
        self.assertEqual(policy.name, "DigitalTQ")
        self.assertFalse(policy.enabled)
        self.assertFalse(policy.statistics_eligible_default)
        self.assertEqual(policy.routes, frozenset())
        self.assertEqual(policy.retention_days, 0)
        self.assertEqual(policy.config["security_finding_status"], "not_established")
