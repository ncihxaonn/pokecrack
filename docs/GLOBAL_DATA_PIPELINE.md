# Global data pipeline contract

PokeCrack's global collection layer discovers and normalizes evidence from
multiple countries. It does **not** make a global pull-rate claim from search,
social, marketplace, or catalog metadata.

## Data classes

| Class | Examples | Allowed use |
| --- | --- | --- |
| `catalog` | TCGdex set metadata | Set/language identity and catalog matching only |
| `activity_only` | YouTube search metadata, channel-country proxy, unverified product or batch hints | Private discovery coverage and review queues only |
| `statistics` | Complete, nonduplicate opening with a verified pack denominator and tier A/B evidence | Observed-rate calculations after deterministic and independent validation |

Activity-only records never create an opening, hit, denominator, aggregate, or
public signal. A popular video, a rare-card post, a listing, or a channel country
is not evidence that a region has better packs.

## YouTube discovery boundary

The live adapter uses only the official YouTube Data API. Each job selects one
exact, versioned query by name; job payloads cannot supply arbitrary queries,
URLs, regions, or endpoints. The adapter may call `search.list` and one bounded
`channels.list` enrichment request. It must not download video, audio, captions,
thumbnails, channel names, or raw channel identifiers.

Persisted metadata is retention-bounded and always classified as evidence tier
D / `activity_only`. Deterministic parsing may add unverified hints for the three
supported sealed product types and explicitly labelled batch or lot codes. Those
hints route later review; they do not promote evidence.

YouTube `regionCode` describes availability in a viewer market, not the physical
location of an opening, so it is not used for geography. A creator-configured
channel country may be retained as a coarse `youtube_channel_country` proxy. It
must be labelled as a channel activity proxy, never as an observed opening,
purchase, store, batch, or pull-rate location.

## Persistence and failure semantics

The live path is:

1. The UTC scheduler enqueues one job per exact query only when the explicit
   collection flag is enabled and a dedicated YouTube API key is configured.
2. PostgreSQL verifies the exact job payload, current lease generation, enabled
   source policy, request spacing, and persistent request-gate ownership before
   any network request.
3. The worker performs bounded official API calls and normalizes the response
   into an exact versioned result contract.
4. A typed database finalizer rechecks the lease, source kill switch, result
   shape, identity consistency, and request gate. It then upserts private source
   items and query provenance, completes the job, and releases the gate in one
   transaction.

Stale leases, disabled policies, malformed or oversized responses, identity
collisions, and failed finalization perform no partial persistence. Live and demo
source identities are isolated.

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
- Review YouTube API retention and developer-policy changes before increasing
  retained fields, duration, query volume, or endpoint scope.

Primary references: [YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list),
[channels.list](https://developers.google.com/youtube/v3/docs/channels/list),
[quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), and
[YouTube API developer policies](https://developers.google.com/youtube/terms/developer-policies).
