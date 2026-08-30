# Global data pipeline contract

PokeCrack's global collection contract can discover and normalize eligible
evidence without restricting discovery to one country. The reviewed web-study
path currently contains five denominator-backed Tier-B studies: 55 packs for
the United States, 17 and 90 packs for the United Kingdom, 36 packs for the
United States, and 54 packs attributed to Singapore's publisher country. Each
country remains below the three-source publication gate, so this does **not**
establish representative worldwide coverage or a global pull-rate claim.

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

## Reviewed public-study boundary

The statistics path accepts only five immutable study identities, URLs, policy
versions, article-title tokens, and exact evidence excerpts. The worker reads
`robots.txt`, waits the policy's 30-second follow-up delay, requests one HTML
page, and parses only text inside the page's `<article>` element. A redirect,
content-type drift, oversized body, changed title/evidence, malformed UTF-8, or
robots denial fails closed. Raw HTML, media, author handles, comments, and exact
addresses are never retained.

The worker returns only the canonical URL, title, bounded evidence excerpt,
SHA-256, and version identities. Country, observed date, set, pack denominator,
qualifying-hit-pack count, product scope, and geography confidence come only
from the exact database policy; a network result cannot override them. The
typed finalizer atomically creates one source item, deterministic extraction
audit, complete opening denominator, and immutable private ledger row.
Aggregate studies never fabricate card-level `opening_hits`.

All current countries use `geography_basis=publisher_country` and
`geography_confidence=tier_b`. This is coarse provenance, not proof of the room
in which packs were opened. The private reviewed ledgers retain any qualifying
numerator for audit, while the public cell exposes only pack/opening/source
counts until all publication thresholds are met.

## YouTube discovery boundary

The network-capable adapter uses only the official YouTube Data API. Each job
selects one exact, versioned query by name; job payloads cannot supply arbitrary
queries, URLs, regions, or endpoints. The adapter may make exactly one bounded
`search.list` request. It must not call `channels.list` or download video, audio,
captions, thumbnails, descriptions, channel metadata, or raw channel identifiers.

The five exact global-English queries run on one fixed two-hour schedule when
the feature is enabled. Both the registry and network adapter independently
verify the frozen query text, `order=date`, 25-result cap, 30-day publication
window, metadata-only flag, and absence of `regionCode` before network I/O. The
single request has a fixed 30-second deadline. The curl pipes are drained
incrementally with a 2 MiB stdout hard cap and a separate 64 KiB stderr cap;
`--max-filesize` and declared length remain defense-in-depth checks.

The request also sends `publishedBefore` from the same UTC cutoff used for its
30-day window. A scheduled premiere or upcoming live result that still arrives
with a later publication timestamp is validated structurally and skipped as an
item; it does not fail the otherwise valid discovery job or get rewritten as an
observed activity with a null timestamp.

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
   enqueues one job per exact query every two hours. Any schedule drift is a
   startup error. The same flag freezes cleanup to its exact daily schedule.
   Operators must not enable the flag until the collector has exactly one
   approved YouTube transport credential; the scheduler never receives or
   verifies that credential.
2. PostgreSQL verifies the exact job payload, current lease generation, enabled
   source policy, request spacing, and persistent request-gate ownership before
   any network request.
3. The worker performs one bounded official API call and normalizes the response
   into an exact versioned result contract.
4. A typed database finalizer rechecks the lease, source kill switch, result
   shape, identity consistency, and request gate. It then upserts only the
   dedicated private `ingest.youtube_discoveries` cache, completes the job, and
   releases the gate in one transaction.

If the curl subprocess cannot be confirmed reaped, the worker does not convert
that uncertainty into an ordinary failed job. It raises a fatal boundary that
bypasses normal failure/finalizer handling, so the persistent request gate stays
leased until database expiry and prevents a second concurrent upstream request.
`KeyboardInterrupt`/`SystemExit` follow the same non-finalizing shutdown path.

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
accepts only one internally consistent pre-YouTube, YouTube-only, or
post-public-study schema. It removes every disposable
`ingest.youtube_discoveries` row but retains the immutable public-study ledgers.
Request-gate data is excluded by `pg_dump`, independently rejected by the
sanitizer, and replaced with the exact idle TCGdex, YouTube, and (when present)
five public-study source keys immediately before RLS is enabled; live lease
ownership is never restored. The exact gate columns, constraints, primary key,
forced/enabled RLS, policy identities, and ledger presence must match the
preflight. Partial or ambiguous structure aborts without advancing the success
marker.

## Global validation versus publication

Private extraction and validation may preserve an explicit two-letter uppercase
country fact from any country. Missing geography is never defaulted to Australia
and cannot become rate-eligible. Public v1 remains the frozen
Australia/English-only contract. The forward global-dashboard migration adds a
separate strict ISO country dimension, country-period publication table, and
public v2 snapshot; it does not loosen v1. The dedicated reviewed-study
finalizer is the only current writer for real country denominators. YouTube and
catalog metadata still have no route to that table. Historical rolling cells
remain readable to the service boundary for audit, while browser RLS exposes
only the current UTC-ending period so aged-out evidence cannot look fresh.

The v2 map selects one latest complete period for all countries. A cell must
contain a positive pack denominator and complete-opening/source counts. Every
rate field is withheld below 30 observed packs or three independent sources;
Watch and Possible anomaly remain unavailable below 200 packs. The browser also
receives a narrow TCGdex set-catalog projection, explicitly labelled catalog-only
and never counted as opening evidence.

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

- Use exactly one YouTube transport: either a dedicated API-restricted raw key,
  or one explicitly selected Maton YouTube OAuth connection. Never configure
  both. Only the collector receives the credential/connection identity; the
  scheduler receives the enable flag alone.
- Keep the collection enable flag off when the key is absent, invalid, or being
  rotated.
- Store production credentials outside Git in a mode `0600` environment file.
- Keep the database source policy as the independent runtime kill switch.
- Keep the exact two-hour discovery cron and daily cleanup cron. Require healthy
  scheduler/watchdog heartbeats plus stale-cleanup and queue-delay alerts; the
  12-hour catch-up is a bounded recovery path, not an unlimited outage guarantee.
- Before enabling collection, create and verify a dedicated `NOINHERIT` worker
  database role with only the queue and fenced-RPC permissions it needs. The
  existing broad `service_role` membership is not an acceptable steady-state
  collector credential.
- Separate a dedicated `NOINHERIT` backup credential with only required reads,
  role/grant access, and the PostgreSQL 17 request-gate schema lock. Do not leave
  backup `MAINTAIN` capability reachable by the steady-state worker credential.
- Revalidate the hosted provider's automatic-backup and point-in-time retention
  behavior before enabling the feature; logical backup filtering alone cannot
  sanitize provider-managed snapshots.
- Review YouTube API retention and developer-policy changes before increasing
  retained fields, duration, query volume, or endpoint scope.

Primary references: [YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list),
[quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), and
[YouTube API developer policies](https://developers.google.com/youtube/terms/developer-policies).
