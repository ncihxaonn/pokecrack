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

The tier-D YouTube discovery records defined here never create an opening, hit,
denominator, aggregate, or public signal. Other separately reviewed activity-only
opening records may contribute an explicitly labelled activity count, but never a
pack denominator, hit rate, or anomaly claim. A popular video, a rare-card post,
a listing, or a channel country is not evidence that a region has better packs.

## YouTube discovery boundary

The live adapter uses only the official YouTube Data API. Each job selects one
exact, versioned query by name; job payloads cannot supply arbitrary queries,
URLs, regions, or endpoints. The adapter may call `search.list` and one bounded
`channels.list` enrichment request. It must not download video, audio, captions,
thumbnails, channel names, or raw channel identifiers.

The five exact global-English queries run on one fixed six-hour schedule when
the feature is enabled. Both the registry and network adapter independently
verify the frozen query text, `order=date`, 25-result cap, 30-day publication
window, metadata-only flag, and absence of `regionCode` before network I/O. One
30-second monotonic budget covers request spacing, `search.list`, and the
optional `channels.list` enrichment. Persisted channel identity is a
domain-separated, case-sensitive SHA-256 digest of the opaque API identifier.

Persisted metadata is retention-bounded and always classified as evidence tier
D / `activity_only`. It must be refreshed or deleted within 30 days. Deterministic
parsing may add unverified hints for the three supported sealed product types and
explicitly labelled batch or lot codes. Those hints route later review; they do
not promote evidence.

YouTube `regionCode` describes availability in a viewer market, not the physical
location of an opening, so it is not used for geography. A creator-configured
channel country may be retained as a coarse `youtube_channel_country` proxy. It
must be labelled as a channel activity proxy, never as an observed opening,
purchase, store, batch, or pull-rate location.

## Persistence and failure semantics

The live path is:

1. The UTC scheduler sees only the explicit collection flag and, when enabled,
   enqueues one job per exact query every six hours. Any schedule drift is a
   startup error. Operators must not enable the flag until the collector has its
   dedicated YouTube API key; the scheduler never receives or verifies that key.
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
source identities are isolated. Database triggers prohibit these tier-D rows from
entering extraction, opening, batch-sighting, or duplicate-cluster relationships,
so bounded cleanup can delete the complete API record and its query provenance at
the 30-day boundary unless a later official API call refreshed it.

Managed database backups apply the same boundary. A fail-closed two-pass filter
derives the exact policy and discovery parents from one internally consistent
plain dump, then removes all discovery rows and matching source parents before
compression. It also catches parents rebound away from the policy; malformed or
ambiguous dump structure aborts the backup without advancing its success marker.

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
