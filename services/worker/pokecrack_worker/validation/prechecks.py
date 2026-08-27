from __future__ import annotations

from dataclasses import dataclass

from pokecrack_worker.extraction.models import EvidenceTier, ExtractorOutput, ProductType


@dataclass(frozen=True, slots=True)
class PrecheckIssue:
    code: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class PrecheckResult:
    issues: tuple[PrecheckIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def is_valid_country_code(value: str) -> bool:
    """Return whether value is an exact two-letter uppercase ASCII country code."""

    return len(value) == 2 and all("A" <= character <= "Z" for character in value)


def run_prechecks(output: ExtractorOutput, *, max_pack_count: int = 10_000) -> PrecheckResult:
    """Run cheap, deterministic checks before spending on validation AI."""

    issues: list[PrecheckIssue] = []
    is_eligible_tier = output.evidence_tier in (EvidenceTier.A, EvidenceTier.B)
    if is_eligible_tier and (output.set_name is None or not output.set_name.strip()):
        issues.append(PrecheckIssue("missing_set", "set_name", "tier A/B requires a set"))
    if is_eligible_tier and (output.pack_count is None or output.pack_count <= 0):
        issues.append(
            PrecheckIssue(
                "invalid_pack_count", "pack_count", "tier A/B requires a positive pack count"
            )
        )
    elif output.pack_count is not None and output.pack_count > max_pack_count:
        issues.append(
            PrecheckIssue(
                "pack_count_too_large",
                "pack_count",
                f"pack count exceeds deterministic cap of {max_pack_count}",
            )
        )
    if is_eligible_tier and not output.evidence:
        issues.append(
            PrecheckIssue("missing_evidence", "evidence", "tier A/B requires field evidence")
        )
    if output.hits and (output.pack_count is None or output.pack_count <= 0):
        issues.append(
            PrecheckIssue(
                "hits_without_packs", "hits", "reported hits require a positive pack count"
            )
        )
    if output.country_code is not None:
        if not is_valid_country_code(output.country_code):
            issues.append(
                PrecheckIssue(
                    "invalid_country_code",
                    "country_code",
                    "country code must be exactly two uppercase ASCII letters",
                )
            )
    if output.product_type not in (
        ProductType.BOOSTER_BOX,
        ProductType.ETB,
        ProductType.BOOSTER_BUNDLE,
    ):
        issues.append(
            PrecheckIssue(
                "outside_scope_product",
                "product_type",
                "product must be booster_box, etb, or booster_bundle",
            )
        )
    if output.batch_code is not None and len(output.batch_code) > 128:
        issues.append(
            PrecheckIssue("batch_code_too_long", "batch_code", "batch code exceeds 128 chars")
        )

    seen_hits: set[tuple[str, str | None]] = set()
    for hit in output.hits:
        key = (hit.card_name.casefold().strip(), hit.collector_number)
        if key in seen_hits:
            issues.append(
                PrecheckIssue(
                    "duplicate_hit", "hits", "duplicate hit rows must be combined by quantity"
                )
            )
            break
        seen_hits.add(key)
    return PrecheckResult(tuple(issues))
