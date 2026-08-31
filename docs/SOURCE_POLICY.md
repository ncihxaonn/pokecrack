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
(credential required; no video download), and `example.com` only as a
fixture-safe adapter. Live TCGdex collection accepts one daily scheduled job for
`https://api.tcgdex.net/v2/en/sets`; each bounded attempt performs at most one
fixed conditional GET, capped at 2 MiB and 1,000 sets, after both a local
allowlist check and a fenced live database-policy check. It stores only English
set names, upstream IDs, counts, ETag and a content hash.

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

### Mastodon public hashtag activity

The Mastodon path is LOCAL ONLY and, when explicitly enabled, uses only the
reviewed public hashtag activity routes on `mastodon.social`. It sends the
fixed `PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)` User-Agent
and applies a process-wide and database-fenced two-second minimum interval,
targeting no more than 150 requests per five minutes against the instance's
default 300-request budget. Live `X-RateLimit-*` headers and `Retry-After` are
binding; a missing, malformed, expired, or conflicting boundary fails closed.
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
