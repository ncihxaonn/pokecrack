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
    TCGTALK_EVIDENCE_EXCERPT,
    TCGTALK_EVIDENCE_SHA256,
    RobotsTxtChecker,
    bleedingcool_phantasmal_flames_adapter,
    cardchill_ascended_heroes_adapter,
    comicbook_perfect_order_adapter,
    tcgtalk_perfect_order_adapter,
    wargamer_chaos_rising_adapter,
)
from pokecrack_worker.config.public_studies import PUBLIC_STUDIES
from pokecrack_worker.config.source_policy import SourcePolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
COMICBOOK_SOURCE_URL = PUBLIC_STUDIES[0].source_url
COMICBOOK_FETCH_URL = PUBLIC_STUDIES[0].fetch_url
WARGAMER_SOURCE_URL = PUBLIC_STUDIES[1].source_url
WARGAMER_FETCH_URL = PUBLIC_STUDIES[1].fetch_url
CARDCHILL_SOURCE_URL = PUBLIC_STUDIES[2].source_url
CARDCHILL_FETCH_URL = PUBLIC_STUDIES[2].fetch_url
BLEEDINGCOOL_SOURCE_URL = PUBLIC_STUDIES[3].source_url
BLEEDINGCOOL_FETCH_URL = PUBLIC_STUDIES[3].fetch_url
TCGTALK_SOURCE_URL = PUBLIC_STUDIES[4].source_url
TCGTALK_FETCH_URL = PUBLIC_STUDIES[4].fetch_url


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
        (
            CARDCHILL_FETCH_URL,
            CARDCHILL_SOURCE_URL,
            "cardchill.com",
            cardchill_ascended_heroes_adapter,
            """
            <html><body><main><article>
              <h1>Ripping 10 Ascended Heroes ETBs: Is the “Mega Attack” Pull Rate Real?</h1>
              <p>I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes.</p>
              <p>Out of 90 packs, I pulled 19 Double Rare (ex) cards.</p>
              <p>Across 10 ETBs, I pulled exactly one SIR.</p>
            </article></main></body></html>
            """,
            (
                "I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes.",
                "Out of 90 packs, I pulled 19 Double Rare (ex) cards.",
                "Across 10 ETBs, I pulled exactly one SIR.",
            ),
        ),
        (
            BLEEDINGCOOL_FETCH_URL,
            BLEEDINGCOOL_SOURCE_URL,
            "bleedingcool.com",
            bleedingcool_phantasmal_flames_adapter,
            """
            <html><body><main><article>
              <h1>Opening Pokémon TCG: Mega Evolution – Phantasmal Flames Products</h1>
              <p>Now, the meat and potatoes: the booster box.</p>
              <p>A booster box contains 36 packs, which essentially guarantees some fire.</p>
              <p>My Secret Rare count here is a whopping eight, made up of five Illustration
              Rares, two Full Art Trainer Supporters, and, the biggest hit, a Special
              Illustration Rare ex.</p>
            </article></main></body></html>
            """,
            (
                "Now, the meat and potatoes: the booster box.",
                "A booster box contains 36 packs, which essentially guarantees some fire.",
                "My Secret Rare count here is a whopping eight, made up of five Illustration Rares, two Full Art Trainer Supporters, and, the biggest hit, a Special Illustration Rare ex.",
            ),
        ),
        (
            TCGTALK_FETCH_URL,
            TCGTALK_SOURCE_URL,
            "tcgtalk.com",
            tcgtalk_perfect_order_adapter,
            """
            <html><body><main><article>
              <h1>Perfect Order Pull Rates: What Singapore Collectors Can Expect</h1>
              <p>By Marcus Tan</p>
              <p>Based on community opening of 9 booster bundles (54 packs total) plus
              pre-release stream data from 420+ packs.</p>
              <p>Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per
              54 packs in this particular opening, with the Meowth EX SIR being the pull.</p>
              <script>invented 999 packs</script>
            </article></main></body></html>
            """,
            (
                "Based on community opening of 9 booster bundles (54 packs total)",
                "Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs in this particular opening, with the Meowth EX SIR being the pull.",
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
    expected_lines: tuple[str, ...],
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
    if domain == "tcgtalk.com":
        assert candidate.content_sha256 == TCGTALK_EVIDENCE_SHA256
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


def test_tcgtalk_hash_pin_is_strict_without_binding_bleedingcool() -> None:
    tcgtalk_policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        TCGTALK_FETCH_URL
    )
    tcgtalk_body = _html(
        TCGTALK_FETCH_URL,
        "<article><h1>Perfect Order Pull Rates: What Singapore Collectors Can Expect</h1>"
        "<p>Based on community opening of 9 booster bundles (54 packs total) plus unrelated text.</p>"
        "<p>Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs "
        "in this particular opening, with the Meowth EX SIR being the pull.</p></article>",
    )
    adapter = tcgtalk_perfect_order_adapter(
        client=FixtureHTTPClient({TCGTALK_FETCH_URL: tcgtalk_body})
    )
    candidate = adapter.collect(TCGTALK_FETCH_URL, tcgtalk_policy)[0]
    assert candidate.content_sha256 == TCGTALK_EVIDENCE_SHA256
    assert candidate.text == TCGTALK_EVIDENCE_EXCERPT

    adapter.expected_evidence_sha256 = "0" * 64
    with pytest.raises(CollectorError, match="hash"):
        adapter.collect(TCGTALK_FETCH_URL, tcgtalk_policy)

    bleedingcool_policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        BLEEDINGCOOL_FETCH_URL
    )
    bleedingcool = bleedingcool_phantasmal_flames_adapter(
        client=FixtureHTTPClient(
            {
                BLEEDINGCOOL_FETCH_URL: _html(
                    BLEEDINGCOOL_FETCH_URL,
                    "<article><h1>Opening Pokémon TCG: Mega Evolution – Phantasmal Flames Products</h1>"
                    "<p>Now, the meat and potatoes: the booster box.</p>"
                    "<p>A booster box contains 36 packs, which essentially guarantees some fire.</p>"
                    "<p>My Secret Rare count here is a whopping eight, made up of five Illustration Rares, "
                    "two Full Art Trainer Supporters, and, the biggest hit, a Special Illustration Rare ex.</p>"
                    "</article>",
                )
            }
        )
    )
    assert bleedingcool.expected_evidence_sha256 is None
    assert bleedingcool.collect(BLEEDINGCOOL_FETCH_URL, bleedingcool_policy)


def test_tcgtalk_accepts_reviewed_document_title_when_article_heading_is_absent() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        TCGTALK_FETCH_URL
    )
    body = _html(
        TCGTALK_FETCH_URL,
        "<html><head><title>Perfect Order Pull Rates: What Singapore Collectors Can Expect | "
        "tcgTalk</title></head><body><h1>tcgTalk</h1><article>"
        "<p>Based on community opening of 9 booster bundles (54 packs total)</p>"
        "<p>Out of 54 packs opened, the community pull rate held roughly true: 1 SIR per "
        "54 packs in this particular opening, with the Meowth EX SIR being the pull.</p>"
        "</article></body></html>",
    )

    candidate = tcgtalk_perfect_order_adapter(
        client=FixtureHTTPClient({TCGTALK_FETCH_URL: body})
    ).collect(TCGTALK_FETCH_URL, policy)[0]

    assert candidate.title == (
        "Perfect Order Pull Rates: What Singapore Collectors Can Expect | tcgTalk"
    )
    assert candidate.text == TCGTALK_EVIDENCE_EXCERPT
    assert candidate.content_sha256 == TCGTALK_EVIDENCE_SHA256


def test_document_title_fallback_remains_disabled_for_other_studies() -> None:
    policy = SourcePolicyRegistry.from_yaml(ROOT / "config" / "sources.yaml").resolve(
        COMICBOOK_FETCH_URL
    )
    body = _html(
        COMICBOOK_FETCH_URL,
        "<html><head><title>I Opened 55 Packs from Pokémon TCG's Perfect Order — Pull Rates"
        "</title></head><body><article>"
        "<p>In total, I opened 55 boosters from the upcoming Perfect Order lineup.</p>"
        "<p>1 Special Illustration Rare</p>"
        "</article></body></html>",
    )

    with pytest.raises(CollectorError, match="title"):
        comicbook_perfect_order_adapter(
            client=FixtureHTTPClient({COMICBOOK_FETCH_URL: body})
        ).collect(COMICBOOK_FETCH_URL, policy)


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
