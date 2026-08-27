# Global data pipeline contract

PokeCrack's global collection contract can discover and normalize eligible
evidence without restricting discovery to one country. This revision has only
fixture evidence and collection remains disabled, so it does **not** establish
live multi-country coverage or make a global pull-rate claim from search, social,
marketplace, or catalog metadata.

## Data classes

| Class | Examples | Allowed use |
| --- | --- | --- |
| `catalog` | TCGdex set metadata | Set/language identity and catalog matching only |
| `activity_only` | Minimal YouTube search-result metadata | Private discovery coverage only |
| `statistics` | Complete, nonduplicate opening with a verified pack denominator and tier A/B evidence | Observed-rate calculations after deterministic and independent validation |

The tier-D YouTube discovery records defined here never create an opening, hit,
denominator, aggregate, or public signal. Other separately reviewed activity-only
opening records may contribute an explicitly labelled activity count, but never a
pack denominator, hit rate, or anomaly claim. A popular video, a rare-card post,
a listing, or a channel country is not evidence that a region has better packs.

## YouTube discovery boundary

The network-capable adapter uses only the official YouTube Data API. Each job
selects one exact, versioned query by name; job payloads cannot supply arbitrary
queries, URLs, regions, or endpoints. The adapter may make exactly one bounded
`search.list` request. It must not call `channels.list` or download video, audio,
captions, thumbnails, descriptions, channel metadata, or raw channel identifiers.

The five exact global-English queries run on one fixed six-hour schedule when
the feature is enabled. Both the registry and network adapter independently
verify the frozen query text, `order=date`, 25-result cap, 30-day publication
window, metadata-only flag, and absence of `regionCode` before network I/O. The
single request has a fixed 30-second deadline and a 2 MiB raw-response cap.

Persistence is intentionally minimal: video ID, canonical watch URL, title,
publication timestamp, source-policy reference, first/last-seen timestamps, and
expiry. The finalizer validates the exact collector and source-policy version
strings but does not retain them as cache columns. It stores no query association, result rank,
description, channel identity/country, content hash, inferred language,
product/batch hint, category, engagement metric, or geography. Every row is
private tier-D / `activity_only` metadata and expires after 28 days unless an
official API refresh updates that same exact record.

YouTube `regionCode` describes availability in a viewer market, not the physical
location of an opening, so it is neither requested nor used. Search metadata has
no route to a country, store, purchase, batch, opening, denominator, or rate.

## Persistence and failure semantics

The live path is:

1. The UTC scheduler sees only the explicit collection flag and, when enabled,
   enqueues one job per exact query every six hours. Any schedule drift is a
   startup error. The same flag freezes cleanup to its exact daily schedule.
   Operators must not enable the flag until the collector has its dedicated
   YouTube API key; the scheduler never receives or verifies that key.
2. PostgreSQL verifies the exact job payload, current lease generation, enabled
   source policy, request spacing, and persistent request-gate ownership before
   any network request.
3. The worker performs one bounded official API call and normalizes the response
   into an exact versioned result contract.
4. A typed database finalizer rechecks the lease, source kill switch, result
   shape, identity consistency, and request gate. It then upserts only the
   dedicated private `ingest.youtube_discoveries` cache, completes the job, and
   releases the gate in one transaction.

Stale leases, disabled policies, malformed or oversized responses, identity
collisions, and failed finalization perform no partial persistence. The cache is
an `UNLOGGED`, forced-RLS table with no foreign key or promotion path into generic
source, extraction, opening, batch-sighting, duplicate, analytics, Admin, or
public relations. Crash loss is acceptable; the API is the refresh source. Daily
bounded cleanup deletes each row independently once its database-clock expiry is
reached. A 12-hour scheduler restart catch-up keeps the supported 28-day
lifecycle below 30 days with operational margin; collection must remain off
without watchdog, stale-cleanup, and queue-delay alerts.

Managed logical backups apply the same boundary. A fail-closed two-pass filter
accepts either a coherent pre-YouTube schema with both policy and table absent,
or the exact policy plus one `CREATE UNLOGGED TABLE` definition from one
internally consistent plain dump. In the latter state it removes every
`ingest.youtube_discoveries` data row before compression. It does not remove
generic source rows. Partial, malformed, or ambiguous structure aborts the
backup without advancing its success marker.

## Global validation versus publication

Private extraction and validation may preserve an explicit two-letter uppercase
country fact from any country. Missing geography is never defaulted to Australia
and cannot become rate-eligible. The current public v1 aggregation remains
Australia/English-only until a separately reviewed global metric dimension and
public v2 contract exist. This lets global evidence accumulate privately without
silently changing the current UI or published methodology.

## What is required for global observed rates

The statistical data product must obtain a real denominator. Preferred inputs
are a first-party structured opening submission with continuous evidence, or an
authorized creator submission that states and verifies every opened pack. Each
candidate still requires catalog mapping, duplicate controls, evidence review,
and the existing minimum pack/source thresholds.

Selection bias remains even after validation. Public wording must say “observed
rate” and show the pack count, independent-source count, geography, language,
time window, evidence coverage, and uncertainty. It must not say “official pull
rate”, “guaranteed”, or imply a causal regional/store advantage.

## Operational prerequisites

- Use a dedicated YouTube Data API key restricted to that API and the worker's
  deployment context. Do not put a broad OAuth gateway credential on the VPS.
- Keep the collection enable flag off when the key is absent, invalid, or being
  rotated.
- Store production credentials outside Git in a mode `0600` environment file.
- Keep the database source policy as the independent runtime kill switch.
- Keep the exact six-hour discovery cron and daily cleanup cron. Require healthy
  scheduler/watchdog heartbeats plus stale-cleanup and queue-delay alerts; the
  12-hour catch-up is a bounded recovery path, not an unlimited outage guarantee.
- Before enabling collection, create and verify a dedicated `NOINHERIT` worker
  database role with only the queue and fenced-RPC permissions it needs. The
  existing broad `service_role` membership is not an acceptable steady-state
  collector credential.
- Revalidate the hosted provider's automatic-backup and point-in-time retention
  behavior before enabling the feature; logical backup filtering alone cannot
  sanitize provider-managed snapshots.
- Review YouTube API retention and developer-policy changes before increasing
  retained fields, duration, query volume, or endpoint scope.

Primary references: [YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list),
[quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), and
[YouTube API developer policies](https://developers.google.com/youtube/terms/developer-policies).
