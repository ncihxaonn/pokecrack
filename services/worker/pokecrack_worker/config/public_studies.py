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
    PublicStudyIdentity(
        study_key="pontocom-herois-excelsos-br-48-v1",
        source_url=(
            "https://pontocomdesenvolvimento.net/postagem/1028/"
            "herois-excelsos-vale-a-pena-abrir-uma-case-lacrada"
        ),
        fetch_url=(
            "https://pontocomdesenvolvimento.net/postagem/1028/"
            "herois-excelsos-vale-a-pena-abrir-uma-case-lacrada"
        ),
        domain="pontocomdesenvolvimento.net",
        adapter="pontocom_herois_excelsos_study",
        collector_version="public-study-pontocom-herois-excelsos-v1",
        parser_version="pontocom-herois-excelsos-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="richards-bricks-charizard-upc-pr-18-v1",
        source_url="https://www.youtube.com/watch?v=OON-ICjlrd4",
        fetch_url="https://www.youtube.com/watch?v=OON-ICjlrd4",
        domain="www.youtube.com",
        adapter="richards_bricks_charizard_upc_study",
        collector_version="public-study-richards-bricks-youtube-v1",
        parser_version="richards-bricks-charizard-upc-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="richards-bricks-mega-evolution-box-pr-36-v1",
        source_url="https://m.youtube.com/watch?v=p_8k9ZkHV_0",
        fetch_url="https://m.youtube.com/watch?v=p_8k9ZkHV_0",
        domain="m.youtube.com",
        adapter="richards_bricks_mega_evolution_box_study",
        collector_version="public-study-richards-bricks-youtube-v1",
        parser_version="richards-bricks-mega-evolution-box-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="indigo-geek-megaevolucion-mx-50-v1",
        source_url="https://www.youtube.com/watch?v=KNCSNJNcjJ8",
        fetch_url="https://www.youtube.com/watch?v=KNCSNJNcjJ8",
        domain="www.youtube.com",
        adapter="indigo_geek_megaevolucion_study",
        collector_version="public-study-indigo-geek-megaevolucion-youtube-v1",
        parser_version="indigo-geek-megaevolucion-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="pokehanna-ascended-heroes-ca-9-v1",
        source_url="https://www.youtube.com/watch?v=Jj0IxqUYat8",
        fetch_url="https://www.youtube.com/watch?v=Jj0IxqUYat8",
        domain="www.youtube.com",
        adapter="pokehanna_ascended_heroes_study",
        collector_version="public-study-pokehanna-ascended-heroes-youtube-v1",
        parser_version="pokehanna-ascended-heroes-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="tcg-market-chaos-rising-pa-6-v1",
        source_url="https://www.youtube.com/watch?v=fHQpNECg4y4",
        fetch_url="https://www.youtube.com/watch?v=fHQpNECg4y4",
        domain="www.youtube.com",
        adapter="tcg_market_panama_chaos_rising_study",
        collector_version="public-study-tcg-market-panama-chaos-rising-youtube-v1",
        parser_version="tcg-market-panama-chaos-rising-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="tcg-market-pitch-black-pa-4-v1",
        source_url="https://www.youtube.com/watch?v=6kb1MvcnMJE",
        fetch_url="https://www.youtube.com/watch?v=6kb1MvcnMJE",
        domain="www.youtube.com",
        adapter="tcg_market_panama_pitch_black_study",
        collector_version="public-study-tcg-market-panama-pitch-black-youtube-v1",
        parser_version="tcg-market-panama-pitch-black-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="pokeshow-mega-evolution-gt-3-v1",
        source_url="https://www.youtube.com/watch?v=DWRdhUuIUvI",
        fetch_url="https://www.youtube.com/watch?v=DWRdhUuIUvI",
        domain="www.youtube.com",
        adapter="pokeshow_guatemala_megaevolution_study",
        collector_version="public-study-pokeshow-guatemala-megaevolution-youtube-v1",
        parser_version="pokeshow-guatemala-megaevolution-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="cartas-pokemon-argentina-pitch-black-ar-36-v1",
        source_url="https://www.youtube.com/watch?v=HcsWjycR1L0",
        fetch_url="https://www.youtube.com/watch?v=HcsWjycR1L0",
        domain="www.youtube.com",
        adapter="cartas_pokemon_argentina_pitch_black_study",
        collector_version="public-study-cartas-pokemon-argentina-pitch-black-youtube-v1",
        parser_version="cartas-pokemon-argentina-pitch-black-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
        source_url="https://www.youtube.com/watch?v=Meg4AO9CqHE",
        fetch_url="https://www.youtube.com/watch?v=Meg4AO9CqHE",
        domain="www.youtube.com",
        adapter="pokemaniaco_lucas_phantasmal_flames_study",
        collector_version="public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1",
        parser_version="pokemaniaco-lucas-phantasmal-flames-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="cofre-lab-chilling-reign-cr-4-v1",
        source_url="https://www.youtube.com/watch?v=15eGmqByP0I",
        fetch_url="https://www.youtube.com/watch?v=15eGmqByP0I",
        domain="www.youtube.com",
        adapter="cofre_lab_chilling_reign_study",
        collector_version="public-study-cofre-lab-chilling-reign-youtube-v1",
        parser_version="cofre-lab-chilling-reign-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="pokeyabros-perfect-order-co-2-v1",
        source_url="https://www.youtube.com/watch?v=n_PdWg27x-o",
        fetch_url="https://www.youtube.com/watch?v=n_PdWg27x-o",
        domain="www.youtube.com",
        adapter="pokeyabros_perfect_order_study",
        collector_version="public-study-pokeyabros-perfect-order-youtube-v1",
        parser_version="pokeyabros-perfect-order-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="andree-insane-cards-cosmic-eclipse-ec-20-v1",
        source_url="https://www.youtube.com/watch?v=wDDCbJKFTCw",
        fetch_url="https://www.youtube.com/watch?v=wDDCbJKFTCw",
        domain="www.youtube.com",
        adapter="andree_insane_cards_cosmic_eclipse_study",
        collector_version="public-study-andree-insane-cards-cosmic-eclipse-youtube-v1",
        parser_version="andree-insane-cards-cosmic-eclipse-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="thekeiplay-lost-origin-pe-36-v1",
        source_url="https://www.youtube.com/watch?v=YKHGiYIhsQU",
        fetch_url="https://www.youtube.com/watch?v=YKHGiYIhsQU",
        domain="www.youtube.com",
        adapter="thekeiplay_lost_origin_study",
        collector_version="public-study-thekeiplay-lost-origin-youtube-v1",
        parser_version="thekeiplay-lost-origin-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="gringo-gameplays-silver-tempest-uy-36-v1",
        source_url="https://www.youtube.com/watch?v=lYzM0jtPLKw",
        fetch_url="https://www.youtube.com/watch?v=lYzM0jtPLKw",
        domain="www.youtube.com",
        adapter="gringo_gameplays_silver_tempest_study",
        collector_version="public-study-gringo-gameplays-silver-tempest-youtube-v1",
        parser_version="gringo-gameplays-silver-tempest-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="garbage-rips-gem-vol2-cn-1-v1",
        source_url=(
            "https://garbagerips.com/rip/"
            "only-garbage-rips-chinese-gem-pack-vol-2-eeveelutions-8jKHh-P7P7M.html"
        ),
        fetch_url=(
            "https://garbagerips.com/rip/"
            "only-garbage-rips-chinese-gem-pack-vol-2-eeveelutions-8jKHh-P7P7M.html"
        ),
        domain="garbagerips.com",
        adapter="garbage_rips_gem_vol2_study",
        collector_version="public-study-garbage-rips-gem-vol2-v1",
        parser_version="garbage-rips-gem-vol2-evidence-v1",
    ),
    PublicStudyIdentity(
        study_key="bikuhime-hantaman-pertama-a-id-20-v1",
        source_url=(
            "https://bikuhime.wordpress.com/2020/05/17/"
            "yang-perlu-diketahui-sebelum-beli-booster-box-pokemon-tcg-bag-1/"
        ),
        fetch_url=(
            "https://bikuhime.wordpress.com/2020/05/17/"
            "yang-perlu-diketahui-sebelum-beli-booster-box-pokemon-tcg-bag-1/"
        ),
        domain="bikuhime.wordpress.com",
        adapter="bikuhime_hantaman_pertama_a_study",
        collector_version="public-study-bikuhime-hantaman-pertama-a-v1",
        parser_version="bikuhime-hantaman-pertama-a-evidence-v1",
    ),
)

PUBLIC_STUDIES += (
    PublicStudyIdentity(
        study_key="nanjakorya-star-birth-jp-100-v1",
        source_url="https://nanjakorya.com/1123",
        fetch_url="https://nanjakorya.com/1123",
        domain="nanjakorya.com",
        adapter="nanjakorya_star_birth_study",
        collector_version="public-study-nanjakorya-star-birth-v1",
        parser_version="nanjakorya-star-birth-evidence-v1",
    ),
)

PUBLIC_STUDIES += (
    PublicStudyIdentity(
        study_key="nanjakorya-paradigm-jp-100-v1",
        source_url="https://nanjakorya.com/1823",
        fetch_url="https://nanjakorya.com/1823",
        domain="nanjakorya.com",
        adapter="nanjakorya_paradigm_trigger_study",
        collector_version="public-study-nanjakorya-paradigm-v1",
        parser_version="nanjakorya-paradigm-evidence-v1",
    ),
)

PUBLIC_STUDIES += (
    PublicStudyIdentity(
        study_key="bokunotebook-vstar-universe-th-1-v1",
        source_url="https://bokunotebook.com/archives/13725",
        fetch_url="https://bokunotebook.com/archives/13725",
        domain="bokunotebook.com",
        adapter="bokunotebook_vstar_universe_study",
        collector_version="public-study-bokunotebook-vstar-universe-v1",
        parser_version="bokunotebook-vstar-universe-evidence-v1",
    ),
)

PUBLIC_STUDIES += (
    PublicStudyIdentity(
        study_key="auckland-show-mighty-ape-nz-105-v1",
        source_url="https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap",
        fetch_url="https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap",
        domain="www.aucklandcardshow.com",
        adapter="auckland_show_mighty_ape_study",
        collector_version="public-study-auckland-show-v1",
        parser_version="auckland-show-105-evidence-v1",
    ),
)

PUBLIC_STUDIES_BY_KEY = {study.study_key: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_URL = {study.source_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDIES_BY_FETCH_URL = {study.fetch_url: study for study in PUBLIC_STUDIES}
PUBLIC_STUDY_COVERAGE_KEYS = frozenset(
    {
        "auckland-show-mighty-ape-nz-105-v1",
        "bokunotebook-vstar-universe-th-1-v1",
        "nanjakorya-paradigm-jp-100-v1",
        "nanjakorya-star-birth-jp-100-v1",
        "bikuhime-hantaman-pertama-a-id-20-v1",
        "garbage-rips-gem-vol2-cn-1-v1",
        "cardchill-ascended-heroes-gb-90-v1",
        "bleedingcool-phantasmal-flames-us-36-v1",
        "tcgtalk-perfect-order-sg-54-v1",
        "pokesup-abyss-eye-jp-30-v1",
        "limitsend-inferno-x-kr-30-v1",
        "buyfunlife-ninja-spinner-tw-40-v1",
        "allonline-mega-dream-ex-th-10-v1",
        "richards-bricks-charizard-upc-pr-18-v1",
        "richards-bricks-mega-evolution-box-pr-36-v1",
        "indigo-geek-megaevolucion-mx-50-v1",
        "pokehanna-ascended-heroes-ca-9-v1",
        "tcg-market-chaos-rising-pa-6-v1",
        "tcg-market-pitch-black-pa-4-v1",
        "pokeshow-mega-evolution-gt-3-v1",
        "cartas-pokemon-argentina-pitch-black-ar-36-v1",
        "pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
        "cofre-lab-chilling-reign-cr-4-v1",
        "pokeyabros-perfect-order-co-2-v1",
        "andree-insane-cards-cosmic-eclipse-ec-20-v1",
        "thekeiplay-lost-origin-pe-36-v1",
        "gringo-gameplays-silver-tempest-uy-36-v1",
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
