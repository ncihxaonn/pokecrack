from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from pokecrack_worker.config.settings import Settings
from pokecrack_worker.config.source_policy import SourcePolicy, SourcePolicyRegistry
from pokecrack_worker.models import CollectorType

EXACT_COLLECTORS = (
    "official_api",
    "bluesky_jetstream",
    "scrapling_http",
    "scrapling_dynamic",
    "opencli_authenticated",
    "manual_import",
    "disabled",
)


def test_collector_vocabulary_is_exact_and_registry_has_no_force_bypass() -> None:
    assert tuple(item.value for item in CollectorType) == EXACT_COLLECTORS
    assert "force" not in inspect.signature(SourcePolicyRegistry.require).parameters
    assert "force" not in inspect.signature(SourcePolicyRegistry.allows).parameters


def test_policy_rejects_nested_proxy_stealth_and_captcha_controls() -> None:
    for prohibited in ("proxy_url", "stealth_mode", "captcha_solver"):
        with pytest.raises(ValidationError, match="prohibited collection control"):
            SourcePolicy(
                domain="example.com",
                enabled=True,
                collector="scrapling_http",
                routes={"static"},
                config={"transport": {prohibited: "configured"}},
            )


def test_policy_and_settings_collection_limits_have_hard_upper_bounds() -> None:
    with pytest.raises(ValidationError):
        SourcePolicy(domain="example.com", min_delay_seconds=86_401)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, scrapling_http_concurrency=33)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, scrapling_request_timeout_seconds=121)


def test_credential_url_error_never_repeats_userinfo_or_query_secret() -> None:
    secret = "never-log-this"
    registry = SourcePolicyRegistry()

    with pytest.raises(ValueError) as caught:
        registry.require(
            f"https://collector:{secret}@unknown.example/item?token={secret}", "static"
        )

    assert secret not in str(caught.value)
