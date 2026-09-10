# PokeSup variable-layout source review

Reviewed 2026-09-10. This extends the existing minimal-fact PokeSup family;
it does not approve arbitrary websites, social-platform extraction, or a new
geographical claim. The existing review expires 2026-10-09. Robots permission
is not a reuse licence. No article text, image, video, weighing table, personal
profile, or media file is retained or republished.

## Independently checked reports

The bounded MAM review fetched robots first, used the production collector
User-Agent, waited at least 30 seconds between requests, refused redirects and
proxies, and capped pages at 1 MB and metadata at 64 KB. The homepage exposed no
independent terms/privacy link. Robots permitted these routes; its SHA256 was
`394ec82b5475a8be35c452c161b6db395066a13f349aa1e17e8b633a98a86237`.
Canonical URLs matched the four-field WordPress response (`id`, `slug`,
`date_gmt`, `link`). Dates below are original publication dates, not crawl dates.

| Report | Post | Publication UTC | Explicit packs | Resource identifiers |
| --- | ---: | --- | ---: | ---: |
| [SV11B](https://pokesup.com/blog/unboxing-sv11b/) | 387 | 2025-06-06 17:31:36 | 20 | 20 |
| [SV11W](https://pokesup.com/blog/unboxing-sv11w/) | 389 | 2025-06-10 03:04:06 | 20 | 20 |
| [SV2A](https://pokesup.com/blog/unboxing-sv2a/) | 190 | 2024-12-01 17:06:13 | 20 | 20 |
| [SV8A](https://pokesup.com/blog/unboxing-sv8a/) | 192 | 2024-12-26 15:34:32 | 10 | 10 |
| [SV9 first](https://pokesup.com/blog/unboxing-sv9/) | 217 | 2025-01-24 00:05:43 | 30 | 30 |
| [SV9 second](https://pokesup.com/blog/unboxing-sv9-2/) | 221 | 2025-01-26 09:42:07 | 30 | 30 |
| [SV9A](https://pokesup.com/blog/unboxing-sv9a/) | 273 | 2025-03-16 09:27:42 | 30 | 10 |

These are **160 candidate reported packs**, not a release receipt or a guarantee
of 160 additional public packs. Admission must still check existing identity
reservations, tombstones, source access and current evidence. No SQL fixture
creates production observations.

Official sources confirm product identities, not the number of packs opened:
[Black Bolt / White Flare](https://www.pokemon-card.com/ex/sv11/index.html),
[Pokémon Card 151](https://www.pokemon-card.com/ex/sv2a/),
[Terastal Festival ex](https://www.pokemon-card.com/ex/sv8a/index.html),
[Battle Partners](https://www.pokemon-card.com/ex/sv9/), and
[Hot Air Arena](https://www.pokemon-card.com/products/sv/sv9a.html?slide=modal).
Japan remains **product market**, never inferred physical opening location.

## Enumeration, not box or image multiplication

SV11B/W enumerate left/right 1–10. SV2A uses the complete short left/right
1–10 form. SV8A enumerates `1パック目` through `10パック目` without sides.
SV9 enumerates left/right 1–15 in short form. SV9A explicitly enumerates
left/right ranges 1–3, 4–6, 7–9, 10–12 and 13–15: ten captions cover exactly
thirty distinct positions. Only that exact ordered range sequence normalizes
to thirty labels. Ten unlabelled images do not imply thirty packs.

Resource paths use `/assets/img/blog/<slug>/pack_<side>_<position>.jpg`, except
SV8A's linear `pack_<position>.jpg`. SV9A has five resource positions per side.
The existing one-/two-digit filename variants remain exact-match layouts.
Missing, repeated, mixed or out-of-range captions/resources fail automatically.
SV2A and SV8A headings include ` BOX`; other headings do not.

Ordered resource-path SHA256 values, independently observed:

| Slug | SHA256 |
| --- | --- |
| unboxing-sv11b | `a8da05c22685cc76a3b8c401dc9b7f1b19af4d7e3d4cdbcfd38ea123b790940f` |
| unboxing-sv11w | `67140f3bf30d7e3e1ac95fda2c24508763fc8b1c168dde32048a1c18493306c4` |
| unboxing-sv2a | `8d35f6c9e437672db8d4d4a6937361e4999f8c04bc8c93906d6360f363a00705` |
| unboxing-sv8a | `16bad74523c81b6ad659ea0a01d5751b84fcb5858e2d9a1563aee6dfff32aad9` |
| unboxing-sv9 | `4069cf384299905ce0ff936ec80788323873cac1760cce505598393162d3a2d6` |
| unboxing-sv9-2 | `2eab648b6864fc41a429124ebddccab68ba90970444f645c3e678cf7189ccc1d` |
| unboxing-sv9a | `1666e125ce7a6d0475759c1489cce375d528deb44c0ec64d8143ec5b2d589681` |

Resource identifiers were pairwise distinct across these seven reports.
SV8A/SV9/SV9-2 each exposed one distinct active embedded-video identifier;
the other four exposed none. The worker retains only deduplication hashes,
does not download videos, and checks identities against existing admissions.
Distinct URLs/hashes support distinct reported cohorts, not proof of physical
independence or unbiased sampling.

## Runtime and recovery

The normal sitemap/hourly workflow discovers and verifies future numbered
reports for these reviewed products. A bounded owner-only catch-up enqueues
at most seven standard family cycles per UTC day, five minutes apart and never
before a candidate's existing daily recheck interval, with no URL/count payload.
The owner-created deduplication key binds each cycle to its checked candidate;
an unrelated due report or sitemap cannot consume that catch-up. Active jobs
are not duplicated across days. Failed work may be re-enqueued on a later day.
It does not change gates, controls, reviews, retries or admissions. The fenced
collector still requires current real proof.

Database staging validates exact product-specific labels and resource layouts.
Finalization derives counts from complete labels, and the public projection
rejects persisted counts inconsistent with the reviewed product. No qualifying
hit numerator is inferred. Date immutability, cross-ledger deduplication,
retractions, 48-hour verification freshness and source-review expiry remain.

Backup sanitization accepts the exact historical 30-pack schema and the exact
new 10/20/30 schema. New products require the new schema and their matching
count. Restore keeps collection disabled. Deploy only after migration tests,
review, GitHub checks and the existing production backup/release gates pass.
