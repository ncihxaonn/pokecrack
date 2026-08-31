"""Separate, explicit source adapters for Scrapling transports."""

from .dynamic_fixture import DynamicFixtureAdapter
from .example_public import ExamplePublicAdapter
from .public_studies import (
    ReviewedPublicStudyAdapter,
    RobotsTxtChecker,
    bleedingcool_phantasmal_flames_adapter,
    cardchill_ascended_heroes_adapter,
    comicbook_perfect_order_adapter,
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
    "comicbook_perfect_order_adapter",
    "tcgtalk_perfect_order_adapter",
    "wargamer_chaos_rising_adapter",
]
