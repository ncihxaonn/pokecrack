from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from pokecrack_worker.collectors.base import (
    CollectionService,
    CollectorError,
    FetchResponse,
)
from pokecrack_worker.collectors.scrapling.adapters.public_studies import (
    ALLONLINE_EVIDENCE_EXCERPT,
    ALLONLINE_EVIDENCE_SHA256,
    ALLONLINE_POLICY_CONFIG,
    BUYFUNLIFE_EVIDENCE_EXCERPT,
    BUYFUNLIFE_EVIDENCE_SHA256,
    BUYFUNLIFE_POLICY_CONFIG,
    LIMITSEND_EVIDENCE_EXCERPT,
    LIMITSEND_EVIDENCE_SHA256,
    LIMITSEND_POLICY_CONFIG,
    RobotsTxtChecker,
    allonline_mega_dream_ex_adapter,
    buyfunlife_ninja_spinner_adapter,
    limitsend_inferno_x_adapter,
)
from pokecrack_worker.collectors.scrapling.registry import build_live_static_registry
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES_BY_KEY
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]


class FixtureHTTPClient:
    def __init__(self, responses: Mapping[str, FetchResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append((url, timeout_seconds))
        return self.responses[url]


def _response(url: str, body: str, content_type: str) -> FetchResponse:
    return FetchResponse(
        status_code=200,
        url=url,
        headers={"content-type": content_type},
        body=body.encode(),
    )


ASIA_STUDIES = (
    (
        "limitsend-inferno-x-kr-30-v1",
        limitsend_inferno_x_adapter,
        LIMITSEND_POLICY_CONFIG,
        ROOT / "services" / "worker" / "fixtures" / "limitsend_inferno_x.html",
        LIMITSEND_EVIDENCE_EXCERPT,
        LIMITSEND_EVIDENCE_SHA256,
        "ko",
        "M2",
        30,
    ),
    (
        "buyfunlife-ninja-spinner-tw-40-v1",
        buyfunlife_ninja_spinner_adapter,
        BUYFUNLIFE_POLICY_CONFIG,
        ROOT / "services" / "worker" / "fixtures" / "buyfunlife_ninja_spinner.html",
        BUYFUNLIFE_EVIDENCE_EXCERPT,
        BUYFUNLIFE_EVIDENCE_SHA256,
        "zh-TW",
        "M4",
        40,
    ),
    (
        "allonline-mega-dream-ex-th-10-v1",
        allonline_mega_dream_ex_adapter,
        ALLONLINE_POLICY_CONFIG,
        ROOT / "services" / "worker" / "fixtures" / "allonline_mega_dream_ex.html",
        ALLONLINE_EVIDENCE_EXCERPT,
        ALLONLINE_EVIDENCE_SHA256,
        "th",
        "MA3",
        10,
    ),
)


@pytest.mark.parametrize(
    (
        "study_key",
        "adapter_factory",
        "expected_config",
        "fixture_path",
        "expected_excerpt",
        "expected_sha256",
        "set_language",
        "set_external_id",
        "pack_count",
    ),
    ASIA_STUDIES,
)
def test_asia_coverage_adapters_emit_only_hash_pinned_facts(
    study_key: str,
    adapter_factory: object,
    expected_config: Mapping[str, object],
    fixture_path: Path,
    expected_excerpt: str,
    expected_sha256: str,
    set_language: str,
    set_external_id: str,
    pack_count: int,
) -> None:
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8")
    client = FixtureHTTPClient(
        {identity.fetch_url: _response(identity.fetch_url, body, "text/html; charset=utf-8")}
    )
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )

    candidate = adapter_factory(client=client).collect(identity.fetch_url, policy)[0]  # type: ignore[operator]

    assert policy.config == expected_config
    assert policy.config["set_language"] == set_language
    assert policy.config["set_external_id"] == set_external_id
    assert policy.config["pack_count"] == pack_count
    assert policy.config["denominator_complete"] is True
    assert (
        not {
            "qualifying_hit_pack_count",
            "qualifying_metric",
            "metric_version",
        }
        & policy.config.keys()
    )
    assert candidate.source_url == identity.source_url
    assert candidate.text == expected_excerpt
    assert candidate.content_sha256 == expected_sha256
    assert candidate.media_urls == ()
    assert candidate.metadata == {
        "study_key": study_key,
        "parser_version": identity.parser_version,
    }


@pytest.mark.parametrize(
    (
        "study_key",
        "adapter_factory",
        "expected_config",
        "fixture_path",
        "expected_excerpt",
        "expected_sha256",
        "set_language",
        "set_external_id",
        "pack_count",
    ),
    ASIA_STUDIES,
)
def test_asia_coverage_adapters_fail_closed_on_evidence_drift(
    study_key: str,
    adapter_factory: object,
    expected_config: Mapping[str, object],
    fixture_path: Path,
    expected_excerpt: str,
    expected_sha256: str,
    set_language: str,
    set_external_id: str,
    pack_count: int,
) -> None:
    del (
        expected_config,
        expected_excerpt,
        expected_sha256,
        set_language,
        set_external_id,
        pack_count,
    )
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    body = fixture_path.read_text(encoding="utf-8").replace(
        str(PUBLIC_STUDIES_BY_KEY[study_key].study_key.split("-")[-2]),
        "999",
    )
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        identity.fetch_url
    )
    adapter = adapter_factory(  # type: ignore[operator]
        client=FixtureHTTPClient(
            {identity.fetch_url: _response(identity.fetch_url, body, "text/html")}
        )
    )

    with pytest.raises(CollectorError, match="evidence"):
        adapter.collect(identity.fetch_url, policy)


@pytest.mark.parametrize(
    (
        "study_key",
        "adapter_factory",
        "expected_config",
        "fixture_path",
        "expected_excerpt",
        "expected_sha256",
        "set_language",
        "set_external_id",
        "pack_count",
    ),
    ASIA_STUDIES,
)
def test_asia_coverage_collection_requests_only_robots_and_article(
    study_key: str,
    adapter_factory: object,
    expected_config: Mapping[str, object],
    fixture_path: Path,
    expected_excerpt: str,
    expected_sha256: str,
    set_language: str,
    set_external_id: str,
    pack_count: int,
) -> None:
    del (
        adapter_factory,
        expected_config,
        expected_excerpt,
        expected_sha256,
        set_language,
        set_external_id,
        pack_count,
    )
    identity = PUBLIC_STUDIES_BY_KEY[study_key]
    robots_url = str(
        SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml")
        .resolve(identity.fetch_url)
        .config["robots_url"]
    )
    client = FixtureHTTPClient(
        {
            robots_url: _response(
                robots_url,
                "User-agent: *\nAllow: /\n",
                "text/plain; charset=utf-8",
            ),
            identity.fetch_url: _response(
                identity.fetch_url,
                fixture_path.read_text(encoding="utf-8"),
                "text/html; charset=utf-8",
            ),
        }
    )
    service = CollectionService(
        policies=SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml"),
        http_adapters=build_live_static_registry(http_client=client),
        robots=RobotsTxtChecker(client=client, followup_delay_seconds=0),
    )

    candidates = service.collect_url(identity.fetch_url, route="static")

    assert len(candidates) == 1
    assert client.calls == [(robots_url, 30.0), (identity.fetch_url, 30.0)]
