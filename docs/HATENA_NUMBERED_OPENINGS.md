# Hatena numbered opening ingestion — implementation contract

Status: **report/feed parsers, worker cycle, private database lane, runtime routing,
research intake, backup and public projection implemented and tested on isolated
MAM; production release and real admission verification still pending**.
This document does not admit observations.

The parser and synthetic tests run on MAM. A direct bounded live-page probe
returned 10 numbered packs, publication `2026-01-10T08:11:34+00:00`, unknown
physical geography/opening time, and evidence SHA256
`44cf08ce3b60c2eb61f6d43ef61b6038b1beadd1c2ee9ef48f874686c8e15325`.
This digest identifies page evidence, not a proven independent physical cohort.
It now includes the ordered hashes of ten numbered-image references. The earlier
caption-only digest was `20d59aa3cf06d73fedd24b8ac6c1a462254472345b68be1a61697e6432cf0e4c`;
that earlier format must not be accepted as resource-backed identity evidence.

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
  Research groups both articles together. A bounded MAM check found its original
  publication `2026-01-10T03:29:36Z` and one body link to the numbered report, but
  no complete numbered pack captions. It is a related reference, not an additional
  admissible opening. These facts do not alone prove physical cohort identity.
- Hash-only HTML resource-reference comparison found 16 body image references in
  the numbered report, including ten numbered-figure references; the related
  article has seven body references and no numbered ones. Three body references
  overlap, but none of the ten numbered references appears in the related article.
  Shared decorative/product images must not establish duplicate opening identity.
  No images were fetched. Observed resource host: `cdn-ak.f.st-hatena.com`.
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

### Publisher update discovery

On 2026-09-10 a bounded MAM homepage check found advertised Atom `/feed` and RSS
`/rss` links. A robots-checked Atom request, spaced 30 seconds after robots,
returned 30 entries, including both opening references above. Entry article links
omit `rel` (Atom's default alternate relation); enclosure links point to images
and must not be followed. The pure `hatena_discovery` module returns only sorted,
unique canonical article candidates from direct entry links. It excludes nested
content, foreign hosts, query/fragment URLs and non-article relations; caps input
at 1 MB and 200 entries; rejects XML declarations that introduce DTD/entities.
No feed prose, media, inferred geography or pack count is returned.

This feed provides recent updates, not a complete historical archive. Historical
sitemap discovery remains incomplete; periodic runtime ingestion is wired but
disabled until release. A feed
entry is not an admitted opening and cannot increment the public denominator.

### Admission integration

The `numbered_families` worker cycle now acquires a database-selected target,
authorizes each request with job/worker/lease-generation fencing, checks robots,
paces reads, and stages either count-free feed candidates or minimal numbered
evidence. Bad source content stages only a quarantine flag, not raw content or
exception text. It returns a dedicated completion effect for atomic admission.
Transport failures, lost request authorization and temporary server failures
defer without quarantining the source. Server retry delays are respected.
It never directly completes a job or publishes a record. The job DTO carries
`is_demo`, defaulting to true when provenance is absent; only literal database
false allows this collector to make requests.

Migration `20261024000000_numbered_source_family.sql` implements private RPCs (`begin_numbered_family_v1`,
`authorize_numbered_family_request_v1`, `stage_numbered_family_v1`,
`finalize_numbered_family_v1`), a disabled-by-default owner control, five-minute
enqueue slots, feed/candidate selection, permanent numbered-resource hash
reservations and owner retraction. The collector persists server/transport backoff
through `defer_numbered_family_v1` so other jobs cannot bypass a publisher delay.
Enqueue allows only one outstanding cycle and skips idle/cooling publishers.
Independent SQL tests exercise actual staging/finalization and repeat/repost
deduplication, not merely mocked worker calls. Ephemeral staging is removed by
the existing source-independent cleanup job even while collection is disabled.

The migration has only been applied to isolated MAM test databases, not production.
The scheduler and composition handler are wired behind the default-off
`NUMBERED_FAMILY_COLLECTION_ENABLED` flag, which requires the existing parent
source-family flag. Migration `20261026000000_numbered_research_intake.sql`
routes exact supported search URLs into the private evidence queue without
per-article configuration; repeat imports preserve existing and retracted states.
Migration `20261025000000_unknown_location_coverage.sql` adds a separate global
unknown-location aggregate without inventing country buckets. Generated types,
web RPC fallback and backup restore contracts must ship together before enabling
collection. Restored collection controls remain disabled. Neither synthetic SQL admissions
nor unit tests constitute live data. The database validates the fenced collector's
minimal attestation; it does not independently fetch source pages or prove physical
cohort identity from resource hashes.

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
   Retain only identity hashes of images attached to numbered captions for this
   purpose, not all body images. The pure parser now exposes these hashes. Each
   numbered figure must have exactly one visible image reference with the observed
   `https://cdn-ak.f.st-hatena.com/images/fotolife/k/kozaru02/YYYYMMDD/YYYYMMDDHHMMSS.jpg`
   shape, no query or fragment, and no repeated reference within the opening.
   The directory's eight-digit token must equal the filename's first eight digits.
   These are opaque resource identifiers, not verified calendar timestamps or
   evidence of when packs were opened; no calendar interpretation is performed.
   Hash input is `hatena-numbered-image-v1:` plus that canonical reference. Changing
   the article URL leaves resource keys unchanged; ordinary body images are ignored.
   A page evidence digest is not a replacement for cross-page numbered-resource
   checks. These references are not image-content fingerprints and cannot detect
   a re-upload under a different resource identifier. No image is dereferenced.
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
