from __future__ import annotations

import unittest
from pathlib import Path

from test_nanjakorya_coverage import FixtureClient
from test_paradigm_trigger_study import document

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.paradigm_trigger_coverage import (
    EVIDENCE_EXCERPT,
    EVIDENCE_SHA256,
    IDENTITY,
    POLICY_CONFIG,
    nanjakorya_paradigm_trigger_adapter,
)
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


class ParadigmTriggerCoverageTests(unittest.TestCase):
    def test_exact_document_is_minimal_coverage_evidence(self) -> None:
        registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
        policy = registry.resolve(IDENTITY.fetch_url)
        self.assertEqual(policy.config, POLICY_CONFIG)
        client = FixtureClient(document())
        item = nanjakorya_paradigm_trigger_adapter(client=client).collect(
            IDENTITY.fetch_url, policy
        )[0]
        self.assertEqual(item.text, EVIDENCE_EXCERPT)
        self.assertEqual(item.content_sha256, EVIDENCE_SHA256)
        self.assertEqual(item.media_urls, ())
        self.assertEqual(client.calls, [IDENTITY.fetch_url])

    def test_reports_on_same_domain_do_not_cross_route(self) -> None:
        registry = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml")
        old = registry.resolve("https://nanjakorya.com/1123")
        self.assertEqual(old.config["study_key"], "nanjakorya-star-birth-jp-100-v1")
        client = FixtureClient(document())
        adapter = nanjakorya_paradigm_trigger_adapter(client=client)
        with self.assertRaises(CollectorError):
            adapter.collect(IDENTITY.fetch_url, old)
        policy = registry.resolve(IDENTITY.fetch_url)
        with self.assertRaises(CollectorError):
            adapter.collect("https://nanjakorya.com/1123", policy)
        self.assertEqual(client.calls, [])
        for url in [
            IDENTITY.fetch_url + "?page=2",
            "https://nanjakorya.com/unknown",
            "https://nanjakorya.com/1823/",
            "https://nanjakorya.com",
        ]:
            with self.subTest(url=url):
                self.assertFalse(registry.allows(url, "static"))

    def test_policy_and_complete_evidence_drift_rejected(self) -> None:
        policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
            IDENTITY.fetch_url
        )
        client = FixtureClient(document())
        adapter = nanjakorya_paradigm_trigger_adapter(client=client)
        with self.assertRaises(CollectorError):
            adapter.collect(
                IDENTITY.fetch_url,
                policy.model_copy(update={"config": {**POLICY_CONFIG, "pack_count": 101}}),
            )
        self.assertEqual(client.calls, [])
        client.body = document().replace("<td>100</td>", "<td>101</td>")
        with self.assertRaises(CollectorError):
            adapter.collect(IDENTITY.fetch_url, policy)
