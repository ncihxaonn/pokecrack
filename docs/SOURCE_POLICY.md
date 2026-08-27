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
`finalize_youtube_discovery_job`. The adapter can call only the fixed official
`search.list` and bounded `channels.list` endpoints. Neither live path accepts an
arbitrary URL or fetches video, audio, captions, thumbnails, cards, rarity,
openings, or probability evidence. The disabled fixture proves fail-closed
behavior. Real retailer domains are not enabled by default.

## Required review before enabling a source

Record owner, purpose/fields, terms/API policy URL and review date, robots behavior, rate/concurrency/page caps, cache policy, authentication basis, regional/privacy concerns, statistics eligibility default, retention and kill switch. Test the exact adapter against a fixture. Re-review on terms, DOM/API or ownership change.

## Prohibitions

No CAPTCHA bypass, stealth/proxy rotation, credential sharing, purchased datasets of unclear provenance, private-message collection, automated purchasing, full third-party video retention, hidden account creation, or collection after an access denial. Login success does not grant permission to collect or republish.

## Provenance

Store source policy/version, canonical identity, collection timestamp, adapter version and hashes privately. Public output should expose source class/diversity and methodology, not sensitive account identity or raw payload. Takedown/terms incidents disable the policy first, preserve minimal audit evidence, and remove retained content as required.
