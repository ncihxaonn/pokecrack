"""Separate, explicit source adapters for Scrapling transports."""

from .dynamic_fixture import DynamicFixtureAdapter
from .example_public import ExamplePublicAdapter
from .public_studies import (
    ReviewedPublicStudyAdapter,
    RobotsTxtChecker,
    bleedingcool_phantasmal_flames_adapter,
    cardchill_ascended_heroes_adapter,
    cartas_pokemon_argentina_pitch_black_adapter,
    comicbook_perfect_order_adapter,
    indigo_geek_megaevolucion_adapter,
    pokehanna_ascended_heroes_adapter,
    pokemaniaco_lucas_phantasmal_flames_adapter,
    pokeshow_guatemala_megaevolution_adapter,
    pokesup_abyss_eye_adapter,
    pontocom_herois_excelsos_adapter,
    tcg_market_panama_chaos_rising_adapter,
    tcg_market_panama_pitch_black_adapter,
    tcgtalk_perfect_order_adapter,
    wargamer_chaos_rising_adapter,
)

__all__ = [
    "DynamicFixtureAdapter",
    "ExamplePublicAdapter",
    "ReviewedPublicStudyAdapter",
    "RobotsTxtChecker",
    "bleedingcool_phantasmal_flames_adapter",
    "cardchill_ascended_heroes_adapter",
    "cartas_pokemon_argentina_pitch_black_adapter",
    "comicbook_perfect_order_adapter",
    "indigo_geek_megaevolucion_adapter",
    "pokesup_abyss_eye_adapter",
    "pokehanna_ascended_heroes_adapter",
    "pokeshow_guatemala_megaevolution_adapter",
    "pokemaniaco_lucas_phantasmal_flames_adapter",
    "pontocom_herois_excelsos_adapter",
    "tcg_market_panama_chaos_rising_adapter",
    "tcg_market_panama_pitch_black_adapter",
    "tcgtalk_perfect_order_adapter",
    "wargamer_chaos_rising_adapter",
]
