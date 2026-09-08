# Auckland country coverage: 105 packs

Reviewed 2026-09-09. Country-level only; the current UI is unchanged.

## Primary evidence and limits

- Organizer recap: https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap
- Organizer location: https://www.aucklandcardshow.com/about
- The August 9–10, 2025 Auckland event report identifies one completed Sunday
  Mighty Ape-sponsored Pokémon opening segment containing exactly 105 packs.
- One report/cohort is counted once. Other opening segments, card hits, approximate
  participant counts and attendance are excluded. Mixed expansions and unknown
  language are explicit; no catalog set, hit rate or national total is inferred.
- Publication metadata is 2025-09-30T00:08:20.972Z. Public geography uses the
  existing publisher-country tier-B contract; the separately recorded opening
  country and day do not change that public attribution method.

## Access and retention review

- https://www.aucklandcardshow.com/robots.txt was HTTP 200 on MAM; the generic
  user-agent group permits this exact static article route.
- https://www.aucklandcardshow.com/terms-of-use reserves site content rights.
  This is not blanket republication permission: retain only minimal noncreative
  facts, a short numeric excerpt, source identity and hashes. No article body,
  media, attendee identity, comments, contact details or assets are retained.
- Ordinary public HTTP only: no login, challenge bypass, dynamic fallback,
  alternate host or proxy. Robots are checked before each bounded article read.
- Observed article size: 1,503,292 bytes. Only this reviewed adapter receives a
  2,000,000-byte transport limit; every other route keeps its previous limit.
  At least 30 seconds between requests; one exact route and one item per run.

## Admission and regression checks

The parser verifies visible main-content paragraphs, exact canonical URL,
publication timestamp, event identity and completed 105-pack segment. SHA-256
digests bind the reviewed event and segment prose without storing that prose.
Approximation, plans, changed counts, hidden/script facts, duplicate paragraphs,
policy drift, malformed markup and oversized pages fail closed.

Synthetic unit fixtures use separate test-only hashes; production hashes are
never weakened to accept synthetic evidence. pgTAP exercises the actual fenced
enqueue/claim/begin/finalize path and rejects a numeric-only report title.
Refreshing the cohort must preserve one 105-pack coverage observation and no
rate observation. Backup profile V15 extends, rather than replaces, V1–V14.

## Research progress (not live-country counts)

The bounded first Asia pass covered 51 targets. Empty search reports do not mean
zero openings or exhaustive absence. Oceania's first batch covered AU/NZ/FJ;
the organizer recap above was then found through additional primary-source
research. Further regions continue through the existing country queue.

Publication still requires MAM tests, independent structured review, GitHub CI
and merge, a fresh encrypted production backup with isolated restore validation,
the reviewed forward migration/deployment, and an actual successful collector
refresh. A candidate or seeded row alone is not live runtime proof.

MAM pre-release checks on 2026-09-09: the real static collector received HTTP
200 for robots and the article, respected the 30-second interval and emitted
one candidate with zero media. Its numeric excerpt digest is
`2adc1fd8cfc93ee9b1208dedc19b37aab7b6a720c5ffc8ef1220a8c028c1383d`.
The isolated Postgres run applied the forward migration and passed all 11
runtime/public-payload assertions. Source and scheduler checks passed 70 tests.
These are isolated checks, not a claim that production has been migrated.
