from __future__ import annotations

import unittest
from pathlib import Path

from test_nanjakorya_study import document

from pokecrack_worker.collectors.base import CollectorError, FetchResponse
from pokecrack_worker.collectors.scrapling.adapters.nanjakorya_coverage import (
    EVIDENCE_EXCERPT,
    EVIDENCE_SHA256,
    IDENTITY,
    POLICY_CONFIG,
    nanjakorya_star_birth_adapter,
)
from pokecrack_worker.config.public_studies import PUBLIC_STUDY_COVERAGE_KEYS
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


class FixtureClient:
    def __init__(self, body: str) -> None:
        self.body = body
        self.calls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append(url)
        return FetchResponse(
            status_code=200,
            url=url,
            headers={"content-type": "text/html"},
            body=self.body.encode(),
        )


class NanjakoryaCoverageTests(unittest.TestCase):
    def test_exact_cohort_is_coverage_not_rate(self) -> None:
        policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
            IDENTITY.fetch_url
        )
        client = FixtureClient(document())
        item = nanjakorya_star_birth_adapter(client=client).collect(IDENTITY.fetch_url, policy)[0]
        self.assertEqual(policy.config, POLICY_CONFIG)
        self.assertIn(IDENTITY.study_key, PUBLIC_STUDY_COVERAGE_KEYS)
        self.assertEqual(policy.config["pack_count"], 100)
        self.assertIsNone(policy.config["opening_country"])
        self.assertIsNone(policy.config["opened_at"])
        self.assertNotIn("qualifying_hit_pack_count", policy.config)
        self.assertEqual(item.text, EVIDENCE_EXCERPT)
        self.assertEqual(item.content_sha256, EVIDENCE_SHA256)
        self.assertEqual(item.media_urls, ())
        self.assertEqual(client.calls, [IDENTITY.fetch_url])

    def test_changed_counts_rejected_even_with_same_title(self) -> None:
        policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
            IDENTITY.fetch_url
        )
        client = FixtureClient(document().replace("RR：2枚", "RR：3枚", 1))
        with self.assertRaises(CollectorError):
            nanjakorya_star_birth_adapter(client=client).collect(IDENTITY.fetch_url, policy)

    def test_policy_and_url_drift_fail_before_network(self) -> None:
        policy = SourcePolicyRegistry.from_yaml(ROOT / "config/sources.yaml").resolve(
            IDENTITY.fetch_url
        )
        client = FixtureClient(document())
        adapter = nanjakorya_star_birth_adapter(client=client)
        with self.assertRaises(CollectorError):
            adapter.collect(IDENTITY.fetch_url + "?page=2", policy)
        drifted = policy.model_copy(update={"config": {**POLICY_CONFIG, "pack_count": 200}})
        with self.assertRaises(CollectorError):
            adapter.collect(IDENTITY.fetch_url, drifted)
        self.assertEqual(client.calls, [])
