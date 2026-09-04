# Global data pipeline contract

PokeCrack's global collection contract can discover and normalize eligible
evidence without restricting discovery to one country. The reviewed web-study
path currently contains five denominator-backed Tier-B studies: 55 packs for
the United States, 17 and 90 packs for the United Kingdom, 36 packs for the
United States, and 54 packs attributed to Singapore's publisher country. Each
country remains below the three-source publication gate, so this does **not**
establish representative worldwide coverage or a global pull-rate claim.
The 2026-09-04 reviewed Pokesup change prepares ordinal 6 as a sixth exact
denominator observation: 30 packs for the JP product market, coverage-only and
not yet live-observed.

## Data classes

| Class | Examples | Allowed use |
| --- | --- | --- |
| `catalog` | TCGdex set metadata | Set/language identity and catalog matching only |
| `activity_only` | Minimal YouTube search-result metadata; bounded Mastodon public hashtag activity | Private discovery coverage only |
| Denominator coverage | Complete reviewed public-study opening persisted only in `ingest.public_study_coverage_observations` | Public pack/opening/source counts only; no numerator, rate, or inference |
| `statistics` | Complete, nonduplicate opening with a verified pack denominator and tier A/B evidence | Observed-rate calculations after deterministic and independent validation |

The tier-D YouTube discovery records defined here never create an opening, hit,
denominator, aggregate, or public signal. Other separately reviewed activity-only
opening records may contribute an explicitly labelled activity count, but never a
pack denominator, hit rate, or anomaly claim. A popular video, a rare-card post,
a listing, or a channel country is not evidence that a region has better packs.
Denominator coverage is neither `activity_only` nor automatic statistical
eligibility: the coverage ledger can retain a real `pack_count` while excluding
the row from every numerator, rate, inference, and statistical-promotion path.

## Reviewed public-study boundary

The public-study path accepts only its immutable study identities, URLs, policy
versions, article-title tokens, and exact evidence excerpts. The worker reads
`robots.txt`, waits the policy's 30-second follow-up delay, requests one HTML
page, and parses only the policy-selected static content container. A redirect,
content-type drift, oversized body, changed title/evidence, malformed UTF-8, or
robots denial fails closed. Raw HTML, media, author handles, comments, and exact
addresses are never retained.

The worker returns only the canonical URL, title, bounded evidence excerpt,
SHA-256, and version identities. Country or product-market bucket, observed
date, set, pack denominator, product scope, and geography confidence come only
from the exact database policy; a network result cannot override them.
Qualifying-hit facts exist only for contracts admitted to the statistical
ledger. Coverage-only contracts instead use the fenced coverage finalizer,
which writes only `ingest.public_study_coverage_observations`; aggregate studies
never fabricate card-level `opening_hits`.

The existing five reviewed sources use `geography_basis=publisher_country` and
`geography_confidence=tier_b`. This is coarse provenance, not proof of the room
in which packs were opened. Pokesup ordinal 6 instead uses
`geography_basis=product_market` with the same Tier-B confidence. Its JP bucket
identifies the Japanese product version, not publisher country, author address,
or opening location.

## Pokesup M5 denominator-coverage boundary

The 2026-09-04 policy review prepares the exact static-HTML route
`https://pokesup.com/blog/unboxing-m5/`. Robots allowed the reviewed route; no
independent terms page was found; and the footer states
`© ポケサプ All Rights Reserved`. Only non-copyrightable minimum facts and the
short labels needed to verify all 30 packs may be extracted. Article prose and
images are not copied, no media is fetched, and raw HTML is not retained.

The immutable product identity is `ja/M5/アビスアイ/booster_box`, independently
checked against the official
[Japanese M5 product page](https://www.pokemon-card.com/ex/m5/). That official
page proves only the Japanese product identity. It does not prove Pokesup's
publisher location, an author address, or where the box was opened.

Pokesup is a complete coverage-only denominator observation with
`pack_count=30`, one opening, one independent source, and `observed_at` set to
the article publication timestamp. The source policy must retain
`statistics_eligible_default=true` because the existing fenced coverage
preflight requires it. That policy field is not rate eligibility: ordinal 6 is
accepted only by the coverage functions, persists only to
`ingest.public_study_coverage_observations`, never enters
`ingest.public_study_observations`, and has no promotion path. Its contract
contains no qualifying-hit count, qualifying metric, or metric version, and the
coverage ledger has no numerator column. `SAR` remains a Japanese rarity label
and is not mapped to `SIR`.

Once the migration and worker are deployed and the first collection is
verified, the public coverage response may expose exactly 30 packs, 1 opening,
and 1 source for the JP product-market bucket. It must not expose or derive a
numerator, observed rate, posterior, baseline, interval, delta, or signal. Code,
configuration, migrations, fixtures, or a successful build do not establish
that this live observation exists.

For this seven-market M5 review, Australia (`AU`), China (`CN`), Russia (`RU`),
Canada (`CA`), Mexico (`MX`), and Brazil (`BR`) have no qualified source or
observation. An outline is not an observation and contributes no pack count,
opening, source, numerator, or rate evidence.

## Authorized opening aggregate-admission boundary

An authorized creator submission that passes review is still not an aggregate
input by default. An owner must separately bind its opaque source identity to
one declared independent domain and make an immutable admission record. The
admission fingerprint must equal the observation's private provenance-dedupe
HMAC; a conflicting domain mapping for the same identity excludes the affected
records. Retractions are evaluated as of the requested cohort timestamp, so
later retractions remove the input without rewriting historical evidence.

This private bridge has no worker promotion from Bluesky, Nostr, Mastodon,
YouTube, catalog, or other social discovery ledgers. It does not calculate a
rate, baseline, posterior, interval, or map colour. Those require the separate
reviewed publisher and exact statistical implementation.

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

## Mastodon public hashtag activity boundary

The Mastodon path is LOCAL ONLY and reads only public hashtag activity from the
reviewed `mastodon.social` REST routes. It is fixed to the seven approved
hashtag keys, the public local/remote access preflight, the exact User-Agent
`PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)`, and a shared
two-second request interval. The process limiter and fenced database gate target
no more than 150 requests per five minutes against the instance's default
300-request budget. Live `X-RateLimit-*` headers and `Retry-After` remain hard
constraints; malformed, missing, expired, or conflicting boundaries fail
closed.
The process limiter is only local pacing; the Postgres gate, policy reservation,
and fenced rate-limit transition are the cross-worker authority.

The parser reduces each public status to an opaque hash, timestamp, and
approved tag keys. It never saves or displays raw payloads, post body/text,
account identity or handles, profiles, media, URLs/links, or location. Activity
candidates and observations have a 30-day TTL and `statistics_eligible=false`.
One opaque per-tag cursor is the sole exception that persists beyond the
activity TTL so collection can resume; it is not an opening, denominator, or
rate-evidence record. Mastodon activity is never used as opening evidence,
pack-denominator evidence, rate evidence, or a statistical claim. The public
source note can safely say `mastodon.social public hashtag activity only`.

## Persistence and failure semantics

The live path is:

1. The UTC scheduler sees only the explicit collection flag and, when enabled,
   enqueues one job per exact query every six hours. Any schedule drift is a
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
post-public-study/Bluesky schema. It removes every disposable
`ingest.youtube_discoveries` row and every private Bluesky
candidate/observation row, while retaining the immutable public-study ledgers
and exact Bluesky checkpoint.
Request-gate data is excluded by `pg_dump`, independently rejected by the
sanitizer, and replaced with the exact idle TCGdex, YouTube, Bluesky, and all
present reviewed public-study source keys immediately before RLS is enabled; live lease
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
- Keep the exact six-hour discovery cron and daily cleanup cron. Require healthy
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
