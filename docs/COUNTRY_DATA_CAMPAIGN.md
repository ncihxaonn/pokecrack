# Country-first data campaign

The owner's 2026-09-08 scope freezes the current public UI and prioritizes data:
**Asia → Oceania (Australia first) → Europe → Africa**, at country/area level,
not cities. The owner's 2026-09-09 expansion adds all remaining countries/areas
worldwide. Existing observations and collectors remain intact; the UI stays frozen.

## Target inventory

`scripts/country_targets.py` covers all 249 ISO-alpha2 country/area entries in the
[UN M49 regions](https://unstats.un.org/unsd/methodology/m49/overview/), checked
2026-09-09, plus the existing application's TW product-market bucket. Short
display names and statistical grouping make no claim about sovereignty.

| Phase | Country/area targets | First targets |
| --- | ---: | --- |
| Asia | 51 | Malaysia, Viet Nam, Philippines, Hong Kong, India, Macao |
| Oceania | 29 | Australia, New Zealand, Fiji |
| Europe | 51 | France, Germany, Italy |
| Africa | 60 | South Africa, Egypt, Kenya |
| Northern America | 5 | United States, Canada, Bermuda |
| Latin America and Caribbean | 52 | Mexico, Brazil, Argentina |
| Antarctica | 1 | Antarctica |

The inventory includes dependencies and small areas so missing map geometry
does not silently omit them. A target is not a new observed country. Existing
coverage includes product-market buckets; do not relabel them as physical
opening locations. No city, address, person or contact field is introduced.

## Durable execution

`country-research.yml` owns the twice-hourly timer. The older global and six-country
Asia workflows remain manual-only. All share the reviewed research controls;
the country and global workflows share one concurrency group. No new paid API,
database credential, local-Mac workload or automatic source enablement exists.

Each run selects up to six unchecked countries from the earliest unfinished
phase of the current sweep. Selection reads validated bot-owned, content-hashed
GitHub reports, including closed issues. Failed/invalid research does not record
success and cannot skip a country because a time slot elapsed. Once a phase has
a retained research result for every target, the next phase starts. Once all
249 targets have been checked, another sweep starts in Asia. The campaign ID,
existing country order and signed-by-hash bot reports are unchanged. An existing
four-region sweep continues into the appended phases rather than resetting or
silently omitting them. Antarctica is an area, not a sovereign country; its
inclusion does not assert that any opening records exist there.

One isolated MAM Codex call has a ten-minute deadline, 24 search queries total,
six candidates per target and a 48 KiB report cap (each country's normalized
sub-batch retains its 16 KiB bound). It must search each country
in English and appropriate local languages. Empty results are permitted and
retained as **no suitable candidate found in this bounded pass**, not zero
activity or proof that no source exists. This makes research progress auditable
without pretending source discovery is country publication.

The first complete research sweep needs at least 44 successful jobs at these
batch sizes. A twice-hourly trigger is not an SLA: GitHub delays, usage limits,
source availability and failed runs can extend it. Independent source review
and publication have no fabricated completion deadline.

### Continuing beyond the same leading reports

The scheduled selector prepares a selection-bound continuation hint from the
same validated country history. MAM receives only prior pass counts, canonical
reference URLs and cohort identifiers: no article text, counts, claimed geography,
personal details, access approval or database credentials. The hint is at most
12,000 bytes, 64 URLs and 32 cohort IDs. Earlier results for the selected countries
take priority, then shared cross-country references. A deterministic window rotates
on later sweeps when history exceeds the hint budget; the full durable history and
deduplication ledger are never truncated by this hint.

The prompt prioritizes new original cohorts and varies source types across sweeps,
within the 24-query budget. It does not blacklist an entire host, prevent new
evidence about an existing cohort, or treat absent references as independent.
These hints improve continuity, not guarantee discovery or replace independent
deduplication. Empty passes still mean no eligible result in that bounded pass.
Legacy manual invocations without `--context` remain supported; the scheduled
workflow always supplies it, and malformed or mismatched hints stop before search.
The context is temporary and is not added to public observations or report schemas.

Research prioritizes distinct author-reported opening samples without requiring
hit numerators, known opening locations or exhaustive manual accuracy checks.
Unknown geography, title claims, lower bounds and native box counts retain their
uncertainty; they are not automatically verified packs. The theoretical batch
capacity is 36 candidates, not a promise of new records or public pack growth.
Legacy manual global/Asia output limits remain unchanged.

This does not resolve the separate 1,000-issue history cap, 2,000-record ledger
cap, or the need for independently reviewed repeatable collector families.

## Deduplication, provenance and release

Publication first constructs the full bounded ledger from the tracked seed,
previous global research batches and all country batches. Original URLs,
cohort IDs and existing alias rules deduplicate references across countries and
continents. Conflicting counts remain quarantined. A search target never
overrides a study's independently stated geography; unknown geography remains
unknown. Native boxes/cartons/decks are not converted into pack observations.

Country report retries are idempotent. Changed reports overlapping a retained
country/sweep fail rather than replacing history. Publication verifies the
saved selection and current queue before creating a new bot report. It never
edits existing country reports or marks production data admitted. History and
ledger capacity limits fail explicitly instead of dropping older evidence.

Actions artifacts retain country progress and the combined deduplicated
research ledger for 90 days. Durable minimal research facts remain in GitHub
issues; no bodies, media, credentials, personal identities or private payloads
are retained. Existing release gates still apply to every actual new source:
original evidence, access/rights/robots, cohort independence, exact source
policy and parser, tests, independent review, PR/CI, backup/restore and migration
where required, reviewed MAM deployment, actual collection and public proof.

This campaign does not change the approved UI or treat research-only reports
as live pack counts. Restricted sources remain disabled; no contact or bypass.

## Verification status

Implementation is not proof of a scheduled run. Record the reviewed commit,
CI, successful main-branch country run, retained report/artifact and next
selected countries after release. Live coverage remains independently verified.
