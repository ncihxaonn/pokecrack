import pytest
from pydantic import ValidationError

from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    InMemoryPolicyAuditSink,
    PolicyDeniedError,
    SourcePolicy,
    SourcePolicyDocument,
    SourcePolicyRegistry,
)


def _exact_youtube_policy(fetch_url: str) -> dict[str, object]:
    return {
        "enabled": True,
        "collector": "scrapling_http",
        "routes": ["static"],
        "config": {"fetch_url": fetch_url},
    }


def _youtube_policy_document(*policies: tuple[str, dict[str, object]]) -> dict[str, object]:
    sources: dict[str, object] = {
        "youtube.com": {
            "enabled": False,
            "collector": "disabled",
            "include_subdomains": True,
        }
    }
    sources.update(dict(policies))
    return {"version": 1, "sources": sources}


def test_unknown_domains_are_disabled_by_default() -> None:
    registry = SourcePolicyRegistry(
        [
            SourcePolicy(
                domain="youtube.com",
                enabled=True,
                routes={CollectorRoute.YOUTUBE},
            )
        ]
    )

    policy = registry.resolve("https://not-configured.example/item/1")

    assert policy.enabled is False
    assert policy.domain == "not-configured.example"
    assert registry.allows("https://not-configured.example/item/1", CollectorRoute.YOUTUBE) is False


def test_policy_document_rejects_stealth_captcha_and_proxy_controls() -> None:
    for prohibited_key in ("stealth", "solve_captcha", "proxy"):
        source = {
            "domain": "retailer.example",
            "enabled": True,
            "routes": ["static"],
            prohibited_key: True,
        }

        with pytest.raises(ValidationError):
            SourcePolicyRegistry.from_mapping({"version": 1, "sources": [source]})


def test_yaml_registry_only_allows_explicit_collector_routes(tmp_path) -> None:
    policy_file = tmp_path / "sources.yaml"
    policy_file.write_text(
        """
version: 1
sources:
  - domain: youtube.com
    include_subdomains: true
    enabled: true
    routes: [youtube]
""".strip(),
        encoding="utf-8",
    )

    registry = SourcePolicyRegistry.from_yaml(policy_file)

    assert registry.allows("https://www.youtube.com/watch?v=abc", "youtube")
    assert not registry.allows("https://www.youtube.com/watch?v=abc", "dynamic")


def test_labeled_mapping_keys_allow_same_domain_exact_fetch_policies() -> None:
    first_url = "https://www.youtube.com/watch?v=first"
    second_url = "https://www.youtube.com/watch?v=second"
    registry = SourcePolicyRegistry.from_mapping(
        _youtube_policy_document(
            ("www.youtube.com#first", _exact_youtube_policy(first_url)),
            ("www.youtube.com#second", _exact_youtube_policy(second_url)),
        )
    )

    assert registry.resolve(first_url).config["fetch_url"] == first_url
    assert registry.resolve(second_url).config["fetch_url"] == second_url
    assert registry.allows(first_url, "static")
    assert registry.allows(second_url, "static")


def test_unknown_same_domain_url_falls_back_to_disabled_parent_policy() -> None:
    first_url = "https://www.youtube.com/watch?v=first"
    second_url = "https://www.youtube.com/watch?v=second"
    unknown_url = "https://www.youtube.com/watch?v=unreviewed&token=secret"
    audit = InMemoryPolicyAuditSink()
    registry = SourcePolicyRegistry.from_mapping(
        _youtube_policy_document(
            ("www.youtube.com#first", _exact_youtube_policy(first_url)),
            ("www.youtube.com#second", _exact_youtube_policy(second_url)),
        ),
        audit_sink=audit,
    )

    resolved = registry.resolve(unknown_url)

    assert resolved.domain == "youtube.com"
    assert resolved.enabled is False
    assert not registry.allows(unknown_url, "static")
    assert audit.events[-1].policy_domain == "youtube.com"
    assert audit.events[-1].source == "https://www.youtube.com/watch"
    assert "secret" not in audit.events[-1].model_dump_json()


def test_duplicate_domains_without_fetch_urls_are_rejected() -> None:
    with pytest.raises(ValidationError, match="require config.fetch_url"):
        SourcePolicyDocument.model_validate(
            {
                "version": 1,
                "sources": {
                    "www.youtube.com#first": {
                        "enabled": True,
                        "collector": "scrapling_http",
                        "routes": ["static"],
                    },
                    "www.youtube.com#second": {
                        "enabled": True,
                        "collector": "scrapling_http",
                        "routes": ["static"],
                    },
                },
            }
        )


def test_labeled_mapping_domain_must_match_key_hostname() -> None:
    with pytest.raises(ValidationError, match="domain key mismatch"):
        SourcePolicyDocument.model_validate(
            {
                "version": 1,
                "sources": {
                    "www.youtube.com#indigo-geek": {
                        "domain": "youtube.com",
                        "enabled": True,
                        "collector": "scrapling_http",
                        "routes": ["static"],
                        "config": {
                            "fetch_url": "https://www.youtube.com/watch?v=video",
                        },
                    }
                },
            }
        )


def test_duplicate_fetch_urls_are_rejected() -> None:
    fetch_url = "https://www.youtube.com/watch?v=duplicate"
    with pytest.raises(ValidationError, match="config.fetch_url values must be unique"):
        SourcePolicyRegistry.from_mapping(
            _youtube_policy_document(
                ("www.youtube.com#first", _exact_youtube_policy(fetch_url)),
                ("www.youtube.com#second", _exact_youtube_policy(fetch_url)),
            )
        )


def test_legacy_single_domain_exact_urls_remain_compatible() -> None:
    fetch_url = "https://www.youtube.com/watch?v=legacy"
    registry = SourcePolicyRegistry.from_mapping(
        {
            "version": 1,
            "sources": {
                "www.youtube.com": {
                    "enabled": True,
                    "collector": "scrapling_http",
                    "routes": ["static"],
                    "exact_urls": [fetch_url],
                }
            },
        }
    )

    assert registry.allows(fetch_url, "static")
    assert not registry.allows("https://www.youtube.com/watch?v=other", "static")


def test_fetch_url_must_be_credential_free_https_and_match_domain() -> None:
    with pytest.raises(ValidationError, match="credential-free HTTPS"):
        SourcePolicy(
            domain="www.youtube.com",
            enabled=True,
            collector="scrapling_http",
            routes={"static"},
            config={"fetch_url": "https://user:password@www.youtube.com/watch?v=secret"},
        )

    with pytest.raises(ValidationError, match="match policy domain"):
        SourcePolicy(
            domain="www.youtube.com",
            enabled=True,
            collector="scrapling_http",
            routes={"static"},
            config={"fetch_url": "https://example.com/watch?v=wrong-domain"},
        )


@pytest.mark.parametrize(
    "second_urls",
    [["https://example.com/one"], ["https://example.com/two", "https://example.com/three"]],
)
def test_same_domain_exact_url_duplicates_and_ambiguity_are_rejected(second_urls) -> None:
    with pytest.raises(ValidationError):
        SourcePolicyRegistry.from_mapping(
            {
                "version": 1,
                "sources": {
                    "example.com#first": {"exact_urls": ["https://example.com/one"]},
                    "example.com#second": {"exact_urls": second_urls},
                },
            }
        )


def test_same_domain_single_exact_urls_route_without_config_mutation() -> None:
    registry = SourcePolicyRegistry.from_mapping(
        {
            "version": 1,
            "sources": {
                "example.com#first": {
                    "enabled": True,
                    "routes": ["static"],
                    "exact_urls": ["https://example.com/one"],
                },
                "example.com#second": {
                    "enabled": True,
                    "routes": ["static"],
                    "exact_urls": ["https://example.com/two"],
                },
            },
        }
    )
    for url in ("https://example.com/one", "https://example.com/two"):
        assert registry.allows(url, "static")
        assert registry.resolve(url).config == {}
    assert not registry.allows("https://example.com/three", "static")


def test_url_credentials_are_rejected_before_any_audit_event_can_capture_them() -> None:
    audit = InMemoryPolicyAuditSink()
    registry = SourcePolicyRegistry(audit_sink=audit)

    with pytest.raises(ValueError, match="credentials"):
        registry.require(
            "https://audit-user:audit-password@unknown.example/item?api_key=secret",
            "static",
        )

    assert audit.events == []


def test_plaintext_http_is_rejected_before_source_policy_authorization() -> None:
    audit = InMemoryPolicyAuditSink()
    registry = SourcePolicyRegistry(
        [
            SourcePolicy(
                domain="youtube.com",
                enabled=True,
                routes={CollectorRoute.YOUTUBE},
            )
        ],
        audit_sink=audit,
    )

    with pytest.raises(ValueError, match="HTTPS"):
        registry.require("http://youtube.com/watch?v=plaintext", CollectorRoute.YOUTUBE)

    assert audit.events == []


def test_policy_audit_source_is_rebuilt_from_safe_host_port_and_path_only() -> None:
    audit = InMemoryPolicyAuditSink()
    registry = SourcePolicyRegistry(audit_sink=audit)

    with pytest.raises(PolicyDeniedError):
        registry.require("HTTPS://UNKNOWN.Example:8443/item?api_key=secret#fragment", "static")

    assert audit.events[0].source == "https://unknown.example:8443/item"
    assert "secret" not in audit.events[0].model_dump_json()
