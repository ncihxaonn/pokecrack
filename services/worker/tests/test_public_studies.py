from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from pokecrack_worker.collectors.base import (
    PUBLIC_COLLECTOR_USER_AGENT,
    CollectorError,
    FetchResponse,
)
from pokecrack_worker.collectors.scrapling.adapters.public_studies import (
    RobotsTxtChecker,
    comicbook_perfect_order_adapter,
    wargamer_chaos_rising_adapter,
)
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
COMICBOOK_SOURCE_URL = PUBLIC_STUDIES[0].source_url
COMICBOOK_FETCH_URL = PUBLIC_STUDIES[0].fetch_url
WARGAMER_SOURCE_URL = PUBLIC_STUDIES[1].source_url
WARGAMER_FETCH_URL = PUBLIC_STUDIES[1].fetch_url


class FixtureHTTPClient:
    def __init__(self, responses: Mapping[str, FetchResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, *, timeout_seconds: float) -> FetchResponse:
        self.calls.append((url, timeout_seconds))
        return self.responses[url]


def _html(url: str, body: str) -> FetchResponse:
    return FetchResponse(
        status_code=200,
        url=url,
        headers={"content-type": "text/html; charset=utf-8"},
        body=body.encode(),
    )


@pytest.mark.parametrize(
    (
        "fetch_url",
        "source_url",
        "domain",
        "adapter_factory",
        "body",
        "expected_lines",
    ),
    (
        (
            COMICBOOK_FETCH_URL,
            COMICBOOK_SOURCE_URL,
            "comicbook.com",
            comicbook_perfect_order_adapter,
            """
            <html><head><style>hidden</style></head><body><main><article>
              <h1>I Opened 55 Packs from Pokémon TCG's Perfect Order — Pull Rates</h1>
              <p>In total, I opened 55 boosters from the upcoming Perfect Order lineup.</p>
              <ul><li>1 Special Illustration Rare</li></ul>
              <script>invented 999 packs</script>
            </article></main></body></html>
            """,
            (
                "In total, I opened 55 boosters from the upcoming Perfect Order lineup.",
                "1 Special Illustration Rare",
            ),
        ),
        (
            WARGAMER_FETCH_URL,
            WARGAMER_SOURCE_URL,
            "www.wargamer.com",
            wargamer_chaos_rising_adapter,
            """
            <html><body><main><article>
              <h1>I opened Pokémon Chaos Rising packs early – it was a blessing and a curse</h1>
              <p>after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release,
              my opinion remains positive on those fronts.</p>
              <p>I was missing out on any SIR mega hits.</p>
            </article></main></body></html>
            """,
            (
                "after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.",
                "missing out on any SIR mega hits.",
            ),
        ),
    ),
)
def test_reviewed_public_study_parsers_emit_only_bounded_provenance(
    fetch_url: str,
    source_url: str,
    domain: str,
    adapter_factory: object,
    body: str,
    expected_lines: tuple[str, str],
) -> None:
    client = FixtureHTTPClient({fetch_url: _html(fetch_url, body)})
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(fetch_url)
    adapter = adapter_factory(client=client)  # type: ignore[operator]

    candidates = adapter.collect(fetch_url, policy)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source_domain == domain
    assert candidate.source_url == source_url
    assert candidate.external_id == policy.config["study_key"]
    assert candidate.text == "\n".join(expected_lines)
    assert "<html" not in candidate.text
    assert "invented 999 packs" not in candidate.text
    assert candidate.media_urls == ()
    assert candidate.content_sha256 is not None
    assert len(candidate.content_sha256) == 64
    assert candidate.metadata == {
        "study_key": policy.config["study_key"],
        "parser_version": policy.config["parser_version"],
    }


def test_public_study_adapter_rejects_policy_or_evidence_drift() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        COMICBOOK_FETCH_URL
    )
    missing_evidence = _html(
        COMICBOOK_FETCH_URL,
        "<article><h1>I Opened 55 Packs from Perfect Order — Pull Rates</h1>"
        "<p>55 packs.</p></article>",
    )
    adapter = comicbook_perfect_order_adapter(
        client=FixtureHTTPClient({COMICBOOK_FETCH_URL: missing_evidence})
    )

    with pytest.raises(CollectorError, match="evidence"):
        adapter.collect(COMICBOOK_FETCH_URL, policy)
    with pytest.raises(CollectorError, match="policy"):
        adapter.collect(
            COMICBOOK_FETCH_URL,
            policy.model_copy(update={"statistics_eligible_default": False}),
        )
    with pytest.raises(CollectorError, match="exact reviewed URL"):
        adapter.collect(f"{COMICBOOK_FETCH_URL}?page=2", policy)
    with pytest.raises(CollectorError, match="exact reviewed URL"):
        adapter.collect(COMICBOOK_SOURCE_URL, policy)


def test_public_study_evidence_must_be_inside_the_article() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        COMICBOOK_FETCH_URL
    )
    sidebar_only = _html(
        COMICBOOK_FETCH_URL,
        """
        <h1>I Opened 55 Packs from Pokémon TCG's Perfect Order — Pull Rates</h1>
        <aside>
          In total, I opened 55 boosters from the upcoming Perfect Order lineup.
          1 Special Illustration Rare
        </aside>
        <article><h2>Unrelated article body</h2></article>
        """,
    )

    with pytest.raises(CollectorError, match="title"):
        comicbook_perfect_order_adapter(
            client=FixtureHTTPClient({COMICBOOK_FETCH_URL: sidebar_only})
        ).collect(COMICBOOK_FETCH_URL, policy)


def test_robots_checker_is_same_origin_bounded_and_delays_before_followup() -> None:
    robots_url = "https://comicbook.com/robots.txt"
    client = FixtureHTTPClient(
        {
            robots_url: FetchResponse(
                status_code=200,
                url=robots_url,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                body=b"User-agent: *\nDisallow:\n",
            )
        }
    )
    sleeps: list[float] = []
    checker = RobotsTxtChecker(client=client, sleeper=sleeps.append)

    assert checker.allowed(COMICBOOK_FETCH_URL, user_agent=PUBLIC_COLLECTOR_USER_AGENT)
    assert client.calls == [(robots_url, 30.0)]
    assert sleeps == [30.0]


def test_robots_checker_uses_the_exact_fetch_path_and_collector_user_agent() -> None:
    robots_url = "https://comicbook.com/robots.txt"
    path = "/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates/"
    client = FixtureHTTPClient(
        {
            robots_url: FetchResponse(
                status_code=200,
                url=robots_url,
                headers={"content-type": "text/plain"},
                body=(
                    f"User-agent: PokecrackMetadataCollector\nDisallow: {path}\n"
                    "User-agent: *\nDisallow:\n"
                ).encode(),
            )
        }
    )
    checker = RobotsTxtChecker(client=client, followup_delay_seconds=0)

    assert not checker.allowed(
        COMICBOOK_FETCH_URL,
        user_agent=PUBLIC_COLLECTOR_USER_AGENT,
    )
    assert checker.allowed(COMICBOOK_SOURCE_URL, user_agent=PUBLIC_COLLECTOR_USER_AGENT)


def test_robots_checker_fails_closed_on_redirect_or_non_plaintext() -> None:
    robots_url = "https://comicbook.com/robots.txt"
    redirected = FixtureHTTPClient(
        {
            robots_url: FetchResponse(
                status_code=200,
                url="https://www.comicbook.com/robots.txt",
                headers={"content-type": "text/plain"},
                body=b"User-agent: *\nAllow: /\n",
            )
        }
    )
    html = FixtureHTTPClient(
        {
            robots_url: FetchResponse(
                status_code=200,
                url=robots_url,
                headers={"content-type": "text/html"},
                body=b"User-agent: *\nAllow: /\n",
            )
        }
    )

    assert not RobotsTxtChecker(client=redirected).allowed(
        COMICBOOK_FETCH_URL, user_agent=PUBLIC_COLLECTOR_USER_AGENT
    )
    assert not RobotsTxtChecker(client=html).allowed(
        COMICBOOK_FETCH_URL, user_agent=PUBLIC_COLLECTOR_USER_AGENT
    )
