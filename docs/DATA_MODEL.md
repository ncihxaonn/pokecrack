# Data model

The SQL migrations are authoritative. They currently establish private `catalog` and `ingest` schemas with default-deny privileges/RLS; browser access must be through explicitly granted public-safe relations. Never infer a deployed schema from these files alone.

## Catalog

- `catalog.sets`: set code/name/series/language/release date and aliases.
- `catalog.products`: sealed product type and pack count, linked to a set.
- `catalog.cards`: catalog identity, collector number, rarity and hit flag.
- `catalog.regions`: country/region/timezone reference.
- `catalog.retailers` and `catalog.stores`: normalized retailer/location reference.
- `catalog.iso_alpha2_codes`: reviewed 249-code ISO 3166-1 alpha-2 allowlist used
  by the independent global public v2 country dimension.

Catalog rows carry `is_demo`; synthetic and live rows must not be conflated.

## Private ingest and control plane

- `ingest.source_policies`: exact domain, source kind, enabled routes, limits and freshness.
- `ingest.source_items`: canonical discovery identity, bounded private excerpt/payload, hashes and retention.
- `ingest.youtube_discoveries`: dedicated `UNLOGGED`, forced-RLS cache containing only exact YouTube video identity, canonical URL, title, publication time, source-policy reference, first/last seen and per-row expiry. The fenced finalizer validates exact collector/policy versions but does not retain those version strings. The cache has no query/rank, channel, description, hash, inferred classification, product/batch hint, geography, evidence, or generic-source relationship.
- `ingest.public_study_observations`: immutable, forced-RLS ledger for the
  exact reviewed public studies. It links one bounded source item,
  deterministic extraction, and complete opening while retaining the
  policy-owned country, denominator, private qualifying numerator, evidence
  hash, and version identities. `service_role` can read but cannot mutate it
  directly.
- `ingest.public_study_coverage_observations`: immutable, forced-RLS
  denominator-only ledger for reviewed public studies that are not yet part of
  the statistical ledger. It retains bounded provenance and pack coverage but
  no qualifying-hit numerator or inference fields.
- `ingest.extraction_runs`: model/prompt versions, structured outputs, confidence, status and errors.
- `ingest.openings`: normalized observed opening and the statistical eligibility decision.
- `ingest.opening_hits`: card/rarity quantities within an opening.
- `ingest.batch_sightings`: bounded batch-code activity, optionally tied to an opening/product/region.
- `ingest.jobs`: idempotent queued work, monotonic per-claim lease generations, retries and terminal states.
- `ingest.worker_heartbeats`: worker version/status/current job and bounded metrics.
- `ingest.browser_sessions`: session metadata/opaque secret-manager reference only; never cookies or tokens.
- `ingest.ai_usage_daily`: request/token/estimated-cost budget ledger.
- `ingest.admin_audit_log`: hashed actor/network identifiers and bounded action details.

## Important invariants

An opening can be `statistics_eligible=true` only when it has a set and positive pack count, is complete, nonduplicate, tier A/B, and not rejected. The current application policy additionally requires `country_code=AU` for public v1 aggregation. Activity-only evidence never contributes a denominator. Duplicate links cannot self-reference. Queue lease fields must agree with state. Raw payloads and AI output are private and retention-bounded. Browser cookies remain outside PostgreSQL.

## Exact state and evidence rules

| Field | Allowed values |
| --- | --- |
| `source_items.status` | `discovered`, `queued`, `collected`, `extracted`, `validated`, `accepted`, `activity_only`, `rejected`, `failed`, `excluded` |
| `source_items.usage_classification` | `statistics`, `activity_only`, `catalog`, `operations`, `excluded` |
| `extraction_runs.stage` | `extract`, `validate`, `escalate` |
| `extraction_runs.decision` | `accepted`, `activity_only`, `rejected`, `failed` (or null while incomplete) |
| `openings.validation_status` | `accepted`, `activity_only`, `rejected`, `excluded` |
| `openings.public_status` | `provisional`, `verified`, `rejected` |
| `jobs.status` | `pending`, `running`, `completed`, `failed`, `dead`, `cancelled` |
| Public signal | `insufficient_sample`, `no_significant_signal`, `watch`, `possible_anomaly` |

The SQL eligibility constraint permits `eligible_for_statistics=true` only with non-null set and positive pack count, complete opening, tier A/B, accepted validation, no `duplicate_of`, and no duplicate suspicion. Application policy must additionally require an approved source, catalog/methodology version, and matching live/demo mode. Tier C is activity-only auxiliary evidence; tier D is discovery/activity-only and never a denominator. Rejected records are not public observations.

A running job must carry worker/start/expiry fields and an expiry after lease start; only terminal jobs carry `completed_at`. Lease authority is the exact `(locked_by, lease_generation)` pair while `lock_expires_at` is still in the future according to the database clock. Every claim increments the generation, so reusing a stable worker ID cannot revive an older attempt. Canonical URL and platform/external identity are unique within live/demo mode, active queue dedupe keys are unique, and self-duplicate links are forbidden. The separate YouTube discovery cache has no content hash or route into this generic identity graph; its typed finalizer still rejects video/URL identity collisions and enforces the exact minimal result contract.

The forward migration makes `service_role` a read-only table principal across `catalog`, `ingest`, `analytics`, and `public`; `ingest.source_request_gates` is not directly readable or row-mutable. Its only direct exception is PostgreSQL 17 `MAINTAIN`, required for the logical backup's schema lock while gate data is excluded. Worker mutations go through narrow `SECURITY DEFINER` RPCs that validate the exact job family, payload, live lease generation, retry window, heartbeat metadata, policy gate, and typed finalizer. Inheriting `service_role` does not confer direct `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, or `TRIGGER` rights on application tables after that migration is applied. Dedicated worker and backup credentials must replace the shared broad role before collection is enabled.

The Admin RPC implementations live in `ingest` with no non-owner execution. Their public compatibility wrappers require `session_user=authenticator` plus a `service_role` JWT claim, so a direct database worker cannot turn inherited role membership or a forged request GUC into Admin access.

## Public contract

Public DTOs contain aggregate labels, rates/intervals, sample sizes, freshness and demo provenance. They must exclude source URLs when unsafe, raw payloads, author identifiers/hashes, exact account/profile/session data, job payloads, AI prompts/output, service health internals and credentials. Public relations require explicit grants and tests; adding a table does not make it public.

Public v1 remains the frozen Australia-only regional contract. The independent
v2 contract reads only three narrow forced-RLS projections:

- `public.tcgdex_set_index`: safe current set identity/release metadata;
- `public.tcgdex_catalog_status`: catalog revision, count and freshness without
  hashes, ETags, job IDs or raw payloads;
- `public.country_period_map_cells`: one explicit country/time-window denominator
  with all inference fields withheld below the publication threshold.

`get_public_dashboard_snapshot_v2()` selects one shared latest country period,
keeps the full catalog count separate from its bounded preview array, and returns
an honest empty observation state when no country cells exist. Summed per-country
source counts are labelled `sourceCountryContributions`; they are not represented
as a globally deduplicated independent-source count. Browser RLS exposes only
cells whose period ends on the current UTC date; historical cells remain
private audit data and cannot masquerade as fresh coverage.

`get_public_dashboard_snapshot_v3()` preserves v2 as its catalog and reviewed
published-map base, then adds a no-argument, bounded `SECURITY DEFINER`
projection for data that already exists behind the browser boundary:

- reviewed-study denominators grouped by TCGdex set and country for the current
  365-day UTC period; denominator rows never disappear when a threshold is
  crossed;
- below-threshold rows use `insufficient`; threshold-sufficient rows without a
  reviewed baseline/interval use `pending`. Both states keep every rate,
  numerator, baseline, posterior, interval, and delta field null;
- a published v2 country aggregate takes precedence over its reviewed
  denominator row, while exact reviewed rows keep the atlas and country detail
  routes populated before the aggregate publisher is ready;
- an exact public source allowlist for TCGdex, YouTube metadata discovery, and
  the five reviewed studies, exposing only status, freshness, a safe reference,
  and bounded notes;
- aggregate heartbeat status for the ready `collector`, `scheduler`, and
  `watchdog` roles, without host, worker, version, job, payload, or error detail.

The source status check validates the complete immutable policy contract,
including routes, robots behavior, limits, retention, and a SHA-256 comparison
of the private config; no private config value is returned. The YouTube count in
v3 remains activity metadata only. Video identity, title,
query, channel, geography, content, and all evidence fields stay private and
cannot become an opening, hit, denominator, or rate. v3 reads only exact source
keys and policy versions, caps reviewed sets at 100 and countries at 249,
inherits v2's 1,000-set catalog bound, and grants execution only to browser
roles.

The migrations define the private catalog/ingest/analytics relations, public aggregate tables, and versioned public/Admin RPCs. Their existence is not evidence of live observations. Every schema change—including each collector finalizer—must pass a clean reset and pgTAP run, then be verified against the exact approved hosted project before its behavior is claimed as deployed.

## Lifecycle

Collection payloads and model runs use bounded retention. YouTube API metadata
is a deliberately transient exception stored outside `ingest.source_items` in
an `UNLOGGED`, forced-RLS cache. `UNLOGGED` means it is not written to WAL or
replicated to standbys and can be truncated after a crash; that loss is accepted
because the official API is the refresh source. Each successful upsert sets an
independent database-clock expiry 28 days ahead. An exact daily cleanup schedule
with a bounded 12-hour restart catch-up hard-deletes rows whose `expires_at` has
passed; collection enablement fails if either the six-hour discovery schedule or
daily cleanup schedule drifts. No discovery row can be promoted
or referenced as an extraction, opening, batch, duplicate, analytic, Admin, or
public record because no such schema relationship or code path exists. Managed
logical backups independently remove every YouTube cache data row, retain the
reviewed-study ledger, and replace request-gate state with the exact canonical
idle TCGdex, YouTube, and public-study rows, while
provider-managed snapshot retention must be revalidated before collection is
enabled. Cleanup/watchdog health and stale-success alerts are also enablement
requirements because a prolonged outage can exceed the supported catch-up
window. Other reviewed source material and published aggregate auditability
keep their existing preservation rules; deletion must not silently rewrite
historical public claims.
