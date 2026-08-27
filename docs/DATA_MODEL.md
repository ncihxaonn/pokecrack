# Data model

The SQL migrations are authoritative. They currently establish private `catalog` and `ingest` schemas with default-deny privileges/RLS; browser access must be through explicitly granted public-safe relations. Never infer a deployed schema from these files alone.

## Catalog

- `catalog.sets`: set code/name/series/language/release date and aliases.
- `catalog.products`: sealed product type and pack count, linked to a set.
- `catalog.cards`: catalog identity, collector number, rarity and hit flag.
- `catalog.regions`: country/region/timezone reference.
- `catalog.retailers` and `catalog.stores`: normalized retailer/location reference.

Catalog rows carry `is_demo`; synthetic and live rows must not be conflated.

## Private ingest and control plane

- `ingest.source_policies`: exact domain, source kind, enabled routes, limits and freshness.
- `ingest.source_items`: canonical discovery identity, bounded private excerpt/payload, hashes and retention.
- `ingest.source_discoveries`: private query/job provenance for rediscovered activity metadata, including rank, first/last seen timestamps, and an explicitly labelled channel-country proxy when present.
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

A running job must carry worker/start/expiry fields and an expiry after lease start; only terminal jobs carry `completed_at`. Lease authority is the exact `(locked_by, lease_generation)` pair while `lock_expires_at` is still in the future according to the database clock. Every claim increments the generation, so reusing a stable worker ID cannot revive an older attempt. Canonical URL and platform/external identity are unique within live/demo mode, active queue dedupe keys are unique, and self-duplicate links are forbidden. Discovery can exist without a stable content hash; typed finalizers must still reject identity collisions and enforce their exact result contract.

## Public contract

Public DTOs contain aggregate labels, rates/intervals, sample sizes, freshness and demo provenance. They must exclude source URLs when unsafe, raw payloads, author identifiers/hashes, exact account/profile/session data, job payloads, AI prompts/output, service health internals and credentials. Public relations require explicit grants and tests; adding a table does not make it public.

The migrations define the private catalog/ingest/analytics relations, public aggregate tables, and versioned public/Admin RPCs. Their existence is not evidence of live observations. Every schema change—including each collector finalizer—must pass a clean reset and pgTAP run, then be verified against the exact approved hosted project before its behavior is claimed as deployed.

## Lifecycle

Collection payloads and model runs use bounded retention; YouTube API metadata uses a 30-day expiry unless refreshed. Cleanup removes only expired, unreferenced discovery material and must preserve reviewed downstream decisions and the auditability needed to reproduce a published aggregate version. Deletion jobs should mark/purge source material without rewriting historical public claims silently. Backups contain private data and receive the same or stronger controls as the database.
