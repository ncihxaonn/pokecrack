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
    PublicStudyIdentity(
        study_key="tcgtalk-perfect-order-sg-54-v1",
        source_url=(
            "https://tcgtalk.com/blog/"
            "perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232"
        ),
        fetch_url=(
            "https://tcgtalk.com/blog/"
            "perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232"
        ),
        domain="tcgtalk.com",
        adapter="tcgtalk_perfect_order_study",
        collector_version="public-study-tcgtalk-perfect-order-v1",
        parser_version="tcgtalk-perfect-order-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="pokesup-abyss-eye-jp-30-v1",
        source_url="https://pokesup.com/blog/unboxing-m5/",
        fetch_url="https://pokesup.com/blog/unboxing-m5/",
        domain="pokesup.com",
        adapter="pokesup_abyss_eye_study",
        collector_version="public-study-pokesup-abyss-eye-v1",
        parser_version="pokesup-abyss-eye-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="limitsend-inferno-x-kr-30-v1",
        source_url=(
            "https://limitsend.tistory.com/entry/"
            "%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-"
            "%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-"
            "%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-"
            "%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-"
            "%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88"
        ),
        fetch_url=(
            "https://limitsend.tistory.com/entry/"
            "%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-"
            "%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-"
            "%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-"
            "%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-"
            "%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88"
        ),
        domain="limitsend.tistory.com",
        adapter="limitsend_inferno_x_study",
        collector_version="public-study-limitsend-inferno-x-v1",
        parser_version="limitsend-inferno-x-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="buyfunlife-ninja-spinner-tw-40-v1",
        source_url="https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/",
        fetch_url="https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/",
        domain="buyfunlife.com",
        adapter="buyfunlife_ninja_spinner_study",
        collector_version="public-study-buyfunlife-ninja-spinner-v1",
        parser_version="buyfunlife-ninja-spinner-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="allonline-mega-dream-ex-th-10-v1",
        source_url=(
            "https://blog.allonline.7eleven.co.th/collectibles-zone/"
            "pokemon-card-review-dream-evolution-ex-all-online/"
        ),
        fetch_url=(
            "https://blog.allonline.7eleven.co.th/collectibles-zone/"
            "pokemon-card-review-dream-evolution-ex-all-online/"
        ),
        domain="blog.allonline.7eleven.co.th",
        adapter="allonline_mega_dream_ex_study",
        collector_version="public-study-allonline-mega-dream-ex-v1",
        parser_version="allonline-mega-dream-ex-evidence-v1",
    ),
)

PUBLIC_STUDIES_BY_KEY = {study.study_key: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_URL = {study.source_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_FETCH_URL = {study.fetch_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDY_COVERAGE_KEYS = frozenset(
    {
        "cardchill-ascended-heroes-gb-90-v1",
        "bleedingcool-phantasmal-flames-us-36-v1",
        "tcgtalk-perfect-order-sg-54-v1",
        "pokesup-abyss-eye-jp-30-v1",
        "limitsend-inferno-x-kr-30-v1",
        "buyfunlife-ninja-spinner-tw-40-v1",
        "allonline-mega-dream-ex-th-10-v1",
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
