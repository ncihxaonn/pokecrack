# Source policy

`config/sources.yaml` is an explicit, versioned allowlist with `default: disabled`. Unknown domains resolve disabled. A source needs an exact domain (or deliberate subdomain rule), enabled adapter/route, access mode, request limits, retention, metadata policy and reason before collection. The registry has no `force`, override, ignore-policy, or fetch-anyway path; adding one in a CLI, environment variable, job payload, retry, or adapter is prohibited. Policy authorization must occur before network I/O.

## Exact collector vocabulary

Every source route uses one of the following exact values and no aliases: `official_api`, `scrapling_http`, `scrapling_dynamic`, `opencli_authenticated`, `manual_import`, or `disabled`. An unconfigured domain and an unrecognized collector both fail closed to `disabled`.

## Priority

1. Official catalog/discovery APIs under their published terms.
2. Public static HTTP when allowed by terms/robots and a bounded adapter.
3. Dynamic Scrapling only when static HTTP cannot supply the approved fields.
4. Authenticated OpenCLI/Browser Bridge only for an owner-authorized account and permitted metadata.
5. Manual synthetic fixture import for tests.

The current registry enables TCGdex catalog metadata, YouTube Data API metadata
(credential required; no video download), exact reviewed public-study pages,
and `example.com` only as a fixture-safe adapter. Live TCGdex collection accepts
two independent daily UTC
scheduled windows at 02:00 and 14:00 for
`https://api.tcgdex.net/v2/en/sets`; each bounded attempt performs at most one
fixed conditional GET, capped at 2 MiB and 1,000 sets, after both a local
allowlist check and a fenced live database-policy check. It stores only English
set names, upstream IDs, counts, ETag and a content hash. The durable schedule
slot is the idempotency boundary, so a missed window can be caught up without
duplicating an already-created slot.

Live YouTube discovery defaults off. When explicitly enabled, its schedule is
frozen to every six hours and enqueues exactly five versioned global-English
queries. The scheduler receives the flag but no credential; only the collector
receives a dedicated YouTube Data API key. Every request is fenced by
`begin_youtube_discovery_job` and every result by
`finalize_youtube_discovery_job`. The adapter can make only one fixed official
`search.list` request per job; it never calls `channels.list`. It persists only
the exact minimal video identity, URL, title, publication timestamp and policy
lifecycle fields in a dedicated transient table. Neither live path accepts an
arbitrary URL or fetches video, audio, captions, thumbnails, descriptions,
channel metadata, cards, rarity, openings, or probability evidence. The
disabled fixture proves fail-closed behavior. Real retailer domains are not
enabled by default.

### Pokesup M5 exact coverage source

The `policy_review_date=2026-09-04` review prepares an exact live
`scrapling_http` source for the static HTML page
`https://pokesup.com/blog/unboxing-m5/`. Robots allowed the reviewed route. No
independent terms page was found, and the page footer states
`© ポケサプ All Rights Reserved`. The missing terms page is not a permission
grant: the rights notice and this policy limit extraction to non-copyrightable
minimum facts and short pack labels. Article body prose and images are not
copied, media is not fetched, raw HTML is not retained, and any rights, robots,
page-structure, or ownership drift disables the route pending review.

This source is a coverage-only denominator observation, not `activity_only` or
discovery metadata. Its reviewed facts are `pack_count=30`, one complete
booster-box opening, one source, `observed_at` equal to the article publication
timestamp, and product version identity `ja/M5/アビスアイ/booster_box`. The JP
bucket is Tier-B product-market evidence (`country_code=JP`,
`geography_basis=product_market`, `geography_confidence=tier_b`); it is not
evidence of Pokesup's publisher country, an author address, or the physical
opening location. The official
[Japanese M5 product page](https://www.pokemon-card.com/ex/m5/) verifies only
the Japanese product identity and proves none of those Pokesup location facts.

The existing fenced coverage pipeline requires
`statistics_eligible_default=true` for policy validity. Here that field permits
admission to `ingest.public_study_coverage_observations` only; it does not make
the observation rate-eligible. Reviewed contract ordinal 6 has no qualifying
hit count or rate metric, never enters `ingest.public_study_observations`, and
cannot be statistically promoted. The coverage ledger itself has no numerator.
After a verified live collection, the public coverage projection may show only
30 packs, 1 opening, and 1 source; it must expose no numerator, observed rate,
posterior, interval, delta, or signal. Japanese `SAR` is not mapped to `SIR`.

This is an exact source enablement being prepared for release, not evidence that
collection has already happened. It becomes live-observed only after the
coordinated migration and worker revision are deployed and the first collection
and public coverage projection are independently verified.

### Mastodon public hashtag activity

The Mastodon path is LOCAL ONLY and, when explicitly enabled, uses only the
reviewed public hashtag activity routes on `mastodon.social`. It sends the
fixed `PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)` User-Agent
and applies a per-process and database-fenced two-second minimum interval,
targeting no more than 150 requests per five minutes against the instance's
default 300-request budget. Live `X-RateLimit-*` headers and `Retry-After` are
binding; a missing, malformed, expired, or conflicting boundary fails closed.
The process limiter is only local pacing; the database gate and fenced cooldown
transition are authoritative across workers.
No login, token, redirect, proxy, arbitrary endpoint, or arbitrary hashtag is
allowed. The policy records the reviewed about, privacy, rules, robots, and
terms URLs and the 2026-08-31 review checkpoints; production enablement still
requires the recommended operator acknowledgment.

Only bounded activity metadata is retained: an opaque status hash, timestamp,
and approved tag keys. The path never stores or displays raw payloads, post
body/text, account identity or handles, profiles, media, URLs/links, or
location. Activity candidates and observations expire after 30 days. The only
exception is one opaque per-tag cursor checkpoint, which persists beyond the
activity TTL solely to resume collection and is not evidence. Mastodon rows
have `statistics_eligible=false` and are never opening evidence, a pack
denominator, rate evidence, or a basis for a statistical claim. The public
source note may safely describe this as `mastodon.social public hashtag
activity only`.

## Required review before enabling a source

Record owner, purpose/fields, terms/API policy URL and review date, robots behavior, rate/concurrency/page caps, cache policy, authentication basis, regional/privacy concerns, statistics eligibility default, retention and kill switch. Test the exact adapter against a fixture. Re-review on terms, DOM/API or ownership change.

## Prohibitions

No CAPTCHA bypass, stealth/proxy rotation, credential sharing, purchased datasets of unclear provenance, private-message collection, automated purchasing, full third-party video retention, hidden account creation, or collection after an access denial. Login success does not grant permission to collect or republish.

## Provenance

Store source policy/version, canonical identity, collection timestamp, adapter version and only the source-specific fields approved by its exact contract. YouTube discovery is an explicit minimal-field exception: it retains a source-policy reference, while the fenced finalizer validates but does not store the collector/policy version strings; no hashes, query/rank provenance, channel data, inferred classifications, or derived hints are retained. Public output should expose source class/diversity and methodology, not sensitive account identity or raw payload. Takedown/terms incidents disable the policy first, preserve only permitted audit evidence, and remove retained content as required.
