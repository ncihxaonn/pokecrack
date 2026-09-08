"""Explicit, source-specific Scrapling adapter registries."""

from __future__ import annotations

from pokecrack_worker.collectors.base import (
    DynamicAdapterRegistry,
    HTTPAdapterRegistry,
    HTTPClient,
)

from .adapters.asia_coverage import garbage_rips_gem_vol2_adapter
from .adapters.dynamic_fixture import DynamicFixtureAdapter
from .adapters.example_public import ExamplePublicAdapter
from .adapters.indonesia_coverage import bikuhime_hantaman_pertama_a_adapter
from .adapters.nanjakorya_coverage import nanjakorya_star_birth_adapter
from .adapters.paradigm_trigger_coverage import nanjakorya_paradigm_trigger_adapter
from .adapters.public_studies import (
    allonline_mega_dream_ex_adapter,
    andree_insane_cards_cosmic_eclipse_adapter,
    bleedingcool_phantasmal_flames_adapter,
    buyfunlife_ninja_spinner_adapter,
    cardchill_ascended_heroes_adapter,
    cartas_pokemon_argentina_pitch_black_adapter,
    cofre_lab_chilling_reign_adapter,
    comicbook_perfect_order_adapter,
    gringo_gameplays_silver_tempest_adapter,
    indigo_geek_megaevolucion_adapter,
    limitsend_inferno_x_adapter,
    pokehanna_ascended_heroes_adapter,
    pokemaniaco_lucas_phantasmal_flames_adapter,
    pokeshow_guatemala_megaevolution_adapter,
    pokesup_abyss_eye_adapter,
    pokeyabros_perfect_order_adapter,
    pontocom_herois_excelsos_adapter,
    richards_bricks_charizard_upc_adapter,
    richards_bricks_mega_evolution_box_adapter,
    tcg_market_panama_chaos_rising_adapter,
    tcg_market_panama_pitch_black_adapter,
    tcgtalk_perfect_order_adapter,
    thekeiplay_lost_origin_adapter,
    wargamer_chaos_rising_adapter,
)


def build_fixture_registries(
    *, http_client: HTTPClient, dynamic_client: HTTPClient
) -> tuple[HTTPAdapterRegistry, DynamicAdapterRegistry]:
    """Build only the two bounded synthetic adapters; there is no catch-all."""

    static_registry = HTTPAdapterRegistry()
    static_registry.register("example_public", ExamplePublicAdapter(client=http_client))
    dynamic_registry = DynamicAdapterRegistry()
    dynamic_registry.register("dynamic_fixture", DynamicFixtureAdapter(client=dynamic_client))
    return static_registry, dynamic_registry


def build_live_static_registry(*, http_client: HTTPClient) -> HTTPAdapterRegistry:
    """Build only explicitly reviewed live static adapters; there is no catch-all."""

    static_registry = HTTPAdapterRegistry()
    static_registry.register(
        "nanjakorya_paradigm_trigger_study",
        nanjakorya_paradigm_trigger_adapter(client=http_client),
    )
    static_registry.register(
        "nanjakorya_star_birth_study",
        nanjakorya_star_birth_adapter(client=http_client),
    )
    static_registry.register(
        "bikuhime_hantaman_pertama_a_study",
        bikuhime_hantaman_pertama_a_adapter(client=http_client),
    )
    static_registry.register(
        "garbage_rips_gem_vol2_study",
        garbage_rips_gem_vol2_adapter(client=http_client),
    )
    static_registry.register(
        "comicbook_perfect_order_study",
        comicbook_perfect_order_adapter(client=http_client),
    )
    static_registry.register(
        "wargamer_chaos_rising_study",
        wargamer_chaos_rising_adapter(client=http_client),
    )
    static_registry.register(
        "cardchill_ascended_heroes_study",
        cardchill_ascended_heroes_adapter(client=http_client),
    )
    static_registry.register(
        "bleedingcool_phantasmal_flames_study",
        bleedingcool_phantasmal_flames_adapter(client=http_client),
    )
    static_registry.register(
        "tcgtalk_perfect_order_study",
        tcgtalk_perfect_order_adapter(client=http_client),
    )
    static_registry.register(
        "pokesup_abyss_eye_study",
        pokesup_abyss_eye_adapter(client=http_client),
    )
    static_registry.register(
        "limitsend_inferno_x_study",
        limitsend_inferno_x_adapter(client=http_client),
    )
    static_registry.register(
        "buyfunlife_ninja_spinner_study",
        buyfunlife_ninja_spinner_adapter(client=http_client),
    )
    static_registry.register(
        "allonline_mega_dream_ex_study",
        allonline_mega_dream_ex_adapter(client=http_client),
    )
    static_registry.register(
        "pontocom_herois_excelsos_study",
        pontocom_herois_excelsos_adapter(client=http_client),
    )
    static_registry.register(
        "richards_bricks_charizard_upc_study",
        richards_bricks_charizard_upc_adapter(client=http_client),
    )
    static_registry.register(
        "richards_bricks_mega_evolution_box_study",
        richards_bricks_mega_evolution_box_adapter(client=http_client),
    )
    static_registry.register(
        "indigo_geek_megaevolucion_study",
        indigo_geek_megaevolucion_adapter(client=http_client),
    )
    static_registry.register(
        "pokehanna_ascended_heroes_study",
        pokehanna_ascended_heroes_adapter(client=http_client),
    )
    static_registry.register(
        "tcg_market_panama_chaos_rising_study",
        tcg_market_panama_chaos_rising_adapter(client=http_client),
    )
    static_registry.register(
        "tcg_market_panama_pitch_black_study",
        tcg_market_panama_pitch_black_adapter(client=http_client),
    )
    static_registry.register(
        "pokeshow_guatemala_megaevolution_study",
        pokeshow_guatemala_megaevolution_adapter(client=http_client),
    )
    static_registry.register(
        "cartas_pokemon_argentina_pitch_black_study",
        cartas_pokemon_argentina_pitch_black_adapter(client=http_client),
    )
    static_registry.register(
        "pokemaniaco_lucas_phantasmal_flames_study",
        pokemaniaco_lucas_phantasmal_flames_adapter(client=http_client),
    )
    static_registry.register(
        "cofre_lab_chilling_reign_study",
        cofre_lab_chilling_reign_adapter(client=http_client),
    )
    static_registry.register(
        "pokeyabros_perfect_order_study",
        pokeyabros_perfect_order_adapter(client=http_client),
    )
    static_registry.register(
        "andree_insane_cards_cosmic_eclipse_study",
        andree_insane_cards_cosmic_eclipse_adapter(client=http_client),
    )
    static_registry.register(
        "thekeiplay_lost_origin_study",
        thekeiplay_lost_origin_adapter(client=http_client),
    )
    static_registry.register(
        "gringo_gameplays_silver_tempest_study",
        gringo_gameplays_silver_tempest_adapter(client=http_client),
    )
    return static_registry


__all__ = [
    "DynamicAdapterRegistry",
    "HTTPAdapterRegistry",
    "build_fixture_registries",
    "build_live_static_registry",
]
