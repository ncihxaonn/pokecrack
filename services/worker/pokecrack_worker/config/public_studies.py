"""Immutable identities for the small reviewed public-study allowlist."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicStudyIdentity:
    study_key: str
    source_url: str
    fetch_url: str
    domain: str
    adapter: str
    collector_version: str
    parser_version: str


PUBLIC_STUDIES: tuple[PublicStudyIdentity, ...] = (
    PublicStudyIdentity(
        study_key="comicbook-perfect-order-us-55-v1",
        source_url=(
            "https://comicbook.com/gaming/feature/"
            "pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates"
        ),
        fetch_url=(
            "https://comicbook.com/gaming/feature/"
            "pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates/"
        ),
        domain="comicbook.com",
        adapter="comicbook_perfect_order_study",
        collector_version="public-study-comicbook-perfect-order-v1",
        parser_version="comicbook-perfect-order-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="wargamer-chaos-rising-gb-17-v1",
        source_url="https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
        fetch_url="https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
        domain="www.wargamer.com",
        adapter="wargamer_chaos_rising_study",
        collector_version="public-study-wargamer-chaos-rising-v1",
        parser_version="wargamer-chaos-rising-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="cardchill-ascended-heroes-gb-90-v1",
        source_url=(
            "https://cardchill.com/article/"
            "ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real"
        ),
        fetch_url=(
            "https://cardchill.com/article/"
            "ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real"
        ),
        domain="cardchill.com",
        adapter="cardchill_ascended_heroes_study",
        collector_version="public-study-cardchill-ascended-heroes-v1",
        parser_version="cardchill-ascended-heroes-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="bleedingcool-phantasmal-flames-us-36-v1",
        source_url=(
            "https://bleedingcool.com/games/"
            "opening-pokemon-tcg-mega-evolution-phantasmal-flames-products"
        ),
        fetch_url=(
            "https://bleedingcool.com/games/"
            "opening-pokemon-tcg-mega-evolution-phantasmal-flames-products/"
        ),
        domain="bleedingcool.com",
        adapter="bleedingcool_phantasmal_flames_study",
        collector_version="public-study-bleedingcool-phantasmal-flames-v1",
        parser_version="bleedingcool-phantasmal-flames-evidence-v1",
    ),
)

PUBLIC_STUDIES_BY_KEY = {study.study_key: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_URL = {study.source_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_FETCH_URL = {study.fetch_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDY_COVERAGE_KEYS = frozenset(
    {
        "cardchill-ascended-heroes-gb-90-v1",
        "bleedingcool-phantasmal-flames-us-36-v1",
    }
)

if len(PUBLIC_STUDIES_BY_KEY) != len(PUBLIC_STUDIES):
    raise RuntimeError("public study keys must be unique")
if len(PUBLIC_STUDIES_BY_URL) != len(PUBLIC_STUDIES):
    raise RuntimeError("public study URLs must be unique")
if len(PUBLIC_STUDIES_BY_FETCH_URL) != len(PUBLIC_STUDIES):
    raise RuntimeError("public study fetch URLs must be unique")


__all__ = [
    "PUBLIC_STUDIES",
    "PUBLIC_STUDIES_BY_KEY",
    "PUBLIC_STUDIES_BY_FETCH_URL",
    "PUBLIC_STUDIES_BY_URL",
    "PUBLIC_STUDY_COVERAGE_KEYS",
    "PublicStudyIdentity",
]
