# Hatena numbered opening ingestion — implementation contract

Status: **pure parser implemented; runtime integration not implemented or enabled**.
This document does not admit observations.

The parser and synthetic tests run on MAM. A direct bounded live-page probe
returned 10 numbered packs, publication `2026-01-10T08:11:34+00:00`, unknown
physical geography/opening time, and evidence SHA256
`20d59aa3cf06d73fedd24b8ac6c1a462254472345b68be1a61697e6432cf0e4c`.
This digest identifies page evidence, not a proven independent physical cohort.

## Objective

Extend continuous ingestion beyond the existing PokeSup-only family. A reviewed
publisher/template should allow new complete numbered opening reports to enter
the existing discovery, deduplication and automatic publication pipeline without
requiring a separate code change for every article. Unknown publishers must not
inherit this publisher's access review.

## First independently observed publisher

- Canonical candidate: `https://www.kozaru02.com/entry/pokecakaifulog`.
- Original publication metadata: `2026-01-10T08:11:34Z`.
- Product text observed: `MEGAドリームex`.
- Explicit labels: `1パック目` through `10パック目`, in order.
- All ten labels are inside body `figure > figcaption` elements, not `h1`–`h4`
  headings. A heading-based parser would incorrectly find no opening evidence.
- Related research reference: `https://www.kozaru02.com/entry/pokekakaifu`.
  Research groups both articles together. Verify the actual relationship before
  creating a cohort key; two URLs must not count as two physical openings.
- Physical opening country and opening timestamp are **unverified**. Neither
  publication metadata, blog title, author's home nor search country establishes
  where or when these packs were opened. The research cohort label containing
  `20260105` is not the observed article publication date.

On 2026-09-10, bounded MAM reads confirmed robots allowed the candidate route.
Robots SHA256: `85fce41b61ab2150f8b9a3fa11c603518d66673bd7f303c861f4618cce5eb6ec`.
The linked `/privacypolicy` was read in full: no explicit automated-access ban was
found, but it grants no content reuse licence. Scope remains minimum factual
extraction, not article/image copying. No credentials, media or article bodies
are retained. This review does not automatically approve Hatena-wide crawling.

## Implementation requirements

1. Use the observed article/body `figure > figcaption` boundaries, not headings.
   The research regex finding ten labels is not a production completeness parser.
2. Add a pure numbered-report parser that checks the exact canonical identity,
   singular original publication metadata, reviewed product label, and contiguous
   nonduplicated numbered opening captions. Ignore comments, navigation, hidden
   templates and scripts. Do not multiply boxes or infer missing pack positions.
3. Return minimal facts and a stable evidence digest, never raw body, images,
   author profile, hit-rate numerator or an invented opening country/date.
4. Define publisher-level discovery and original-cohort identity separately from
   page identity. Check the related article and reject duplicate/reposted cohorts.
5. Extend family routing and count-free research intake rather than adding an
   isolated manual-only public record. No worker-supplied URL may become an
   arbitrary fetch target; preserve bounded, reviewed HTTPS routes.
6. Extend database staging/finalization and public projection together. Publication
   must use the deduplicated admitted cohort, not research counts. Unknown physical
   geography must not be represented as a verified Japanese opening location.
7. Keep pacing, response bounds, access expiry, deletion/tombstone behavior and
   retries. A disabled publisher must not disable unrelated collectors.
8. Update backup sanitization and isolated restore tests for the minimal new
   contract; restored collection switches must remain off.

## Verification and release

Use synthetic fixtures, not copied articles, for parser tests: missing/repeated
positions, unrelated counts, hidden/comment labels, malformed boundaries,
duplicate metadata, future timestamps, product mismatch and repeated cohort.
Verify the actual parser against a bounded MAM fetch without retaining the body.
Run worker checks and relevant PostgreSQL/backup tests on MAM, followed by
structured autoreview. The source-controlled GitHub review, fresh encrypted
backup/restore, migration and exact-revision MAM deployment gates remain required.

Completion evidence must show a newly discovered report reaching an admitted
cohort and the public website, then a repeat run producing no duplicate increment.
Parser tests, this plan, references or a green workflow alone do not prove it.

## Independent remaining global work

This publisher is one extension, not worldwide completion. GitHub's observed
country-research schedule has multi-hour trigger gaps despite a twice-hourly
configuration; autonomous discovery needs a verified reliable scheduling path.
Generic supported-source onboarding and multilingual/social fact extraction
remain incomplete. Do not solve the scheduling gap by copying unrelated MAM
credentials or by using the Mac as a production crawler.
