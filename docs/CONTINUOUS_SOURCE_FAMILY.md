# Continuous source-family first slice

This is a reviewed PokeSup M2/M3 ingestion loop, not worldwide automatic
website onboarding. The existing 30 fixed contracts remain unchanged. Country
research still produces GitHub reports: no bridge from those reports into this
ledger is implemented. Unknown websites require source-family review. Other
PokeSup products stay `pending_family`; the current catalog is English-only.
Adding a trusted Japanese catalog is a separate reviewed change.

## Source review, 2026-09-09

Independent parent and implementation probes ran on the approved MAM host with
`PokecrackMetadataCollector/0.1`, robots first, 30-second pacing, no redirects,
1 MB response caps, and no body or media retention. Robots returned 200 and
allows the explicit blog, sitemap and metadata routes. It disallows WordPress
admin/includes paths. The blog sitemap exposed 13 opening URLs. Homepage,
page-sitemap and article checks found no independent terms page;
`/privacy-policy/` returned 404. This is the existing reviewed minimal
noncreative factual-use scope, not a claim that robots grants a reuse license.

Approved routes are `https://pokesup.com/robots.txt`,
`https://pokesup.com/blog-sitemap.xml`, canonical M2/M3 opening pages, and
`https://pokesup.com/wp-json/wp/v2/blog?slug=<exact-opening-slug>&_fields=id,slug,date_gmt,link`.
The metadata route was separately probed successfully. No unbounded REST query,
authentication, browser escalation, media fetch or arbitrary link traversal is used.

| Page | Primary post | Publication UTC | Explicit labels | Ordered resource SHA256 |
| --- | ---: | --- | ---: | --- |
| `/blog/unboxing-m2/` | 462 | 2025-09-30 10:44:54 | 30 | `8a3917c08217118210b7681e09bad8c4c20f5436b5d60d207a4c67adbc7a1ca5` |
| `/blog/unboxing-m3/` | 484 | 2026-01-24 08:20:48 | 30 | `18d237b52c62560f175155f363d333074128cdf3853a769c3e8e52154542d24b` |
| `/blog/unboxing-m5/` — excluded | 618 | 2026-05-22 12:01:44 | 30 | `c7840e4b4d035d909cf937e37c71405c3d06462938822c13884727126f158229` |

Actual implementation-parser probes reproduced M2/M3 facts and hashes.
Parent comparison found zero shared active opening image/video IDs in every
pair. M3's video ID occurs only in an M5 comment; comments are not evidence.
Named products, primary post IDs, complete enumerated sections and disjoint
active resources support independent *reported* cohorts, not physical ground
truth. Publication dates are not asserted physical opening timestamps.

Parent independently checked sitemap-derived SV8 base, `-2`, and `-3`: named
box ordinals 1/2/3, 30 distinct image IDs each, and no pairwise active-resource
overlap. That establishes the publisher's numbered template. SV8 is **not**
approved here and contributes no packs. For M2/M3, suffix absent means ordinal
1; `-n` requires the exact named nth opening section and matching primary post.
Every accepted event contains the explicit left/right labels 1–15. No box
multiplier, guessed hits, translated product guess or physical geography is used.

## Runtime and public boundary

Code approval, unexpired source review, exact existing PokeSup access policy,
the owner-controlled `ingest.source_family_control.enabled`, and the separate
`SOURCE_FAMILY_COLLECTION_ENABLED` setting are required. Code review expires
2026-10-09 and must be renewed through reviewed code. Both runtime controls
default off. Revoking the existing source policy or the family control blocks
enqueue, begin, every network acquisition, staging and public projection.
Finalization rechecks access and quarantines instead of admitting revoked work.
A valid disabled/expired family gate is an operational pause: the scheduler
skips that family without blocking existing jobs, and shared worker health
remains valid. Missing or malformed database contracts still fail health checks.

One hourly cycle refreshes the sitemap daily or checks one due event. The
sitemap is bounded to 200 URLs; each event uses at most three requests. The
existing M5 domain gate is shared without altering its fixed contract. Leases,
generation, request sequence and 30-second pacing are checked in PostgreSQL.
Results are staged once, leaf-validated and finalized atomically. Generic job
completion cannot attest this lane. Pending products are not fetched.

Per-post, product/ordinal, individual image and normalized active YouTube video
hashes are durable identity
reservations. Active embeds are bounded to zero or one known YouTube embed;
tracking parameters do not change its identity, and comments are ignored.
Videos never contribute to the pack denominator. Overlaps cannot increase counts. Original admitted date, post,
ordinal and resource identity are immutable across quarantine/expiry. Edited
source dates cannot recycle packs into the strict rolling 365-day window.
Owner retraction leaves a permanent hash tombstone. M5 and its numbered
derivatives are excluded explicitly and all admissions/public reads also join
against the existing fixed contracts.

The existing v2 coverage projection includes valid family rows; v3 inherits
them with no invented numerator. Publisher identity remains `pokesup.com` for
source-diversity counts. Attribution is Japan **product market**, not opening
location. Public rows require publication in the last 365 days and successful
verification within 48 hours. Backlogs beyond this bounded service capacity
lose freshness and hide rows rather than fabricate coverage. No map UI changes.

## Backup, restore and activation

Managed backups exclude transient `source_family_runs`. The sanitizer checks
the exact bounded durable columns, retains immutable cohort facts, reservations
and retraction hashes, and rewrites the family control to `enabled=false`.
Restored snapshots cannot silently resume collection. Existing fixed-ledger
sanitizer/release gates are unchanged; no worker privileges are expanded to
solve backup access. Use the existing owner-capable backup route.

Durable records contain canonical public URLs, bounded IDs, dates and hashes;
no HTML, media, credentials, freeform excerpts or raw response payloads. Minimal
identity/tombstone records persist to prevent resurrection. Successful staging
is deleted in the finalizer; source-agnostic maintenance prunes abandoned staging
after 24 hours even when collection is disabled (at most 1,000 rows per cleanup).
It also cascades when its job is removed and is never in managed backups.

After mandatory review, CI, fresh backup/restore, migration and reviewed
deployment gates, the parent may use the reviewed helper against the verified
owner-only runtime env file:

```sh
python3 deploy/lib/update_source_family_flag.py --env-file /verified/runtime.env --value true
```

The example path is a placeholder, not an approved target. The helper changes
only this flag using owner/mode/symlink checks, a bounded UTF-8 read, an exclusive
temporary file, fsync and an atomic replacement with race checks. Public-study
collection must already be enabled. It does not write the database or restart
services. The parent separately enables the owner-only family control through
the approved database route, then uses the reviewed service workflow. Disable
the DB control for an immediate collection/publication kill; use `--value false`
to persist the runtime opt-out. No production activation occurred in this task.
