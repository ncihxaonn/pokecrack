import pytest
from pydantic import ValidationError

from pokecrack_worker.config.source_policy import (
    CollectorRoute,
    InMemoryPolicyAuditSink,
    PolicyDeniedError,
    SourcePolicy,
    SourcePolicyRegistry,
)


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
