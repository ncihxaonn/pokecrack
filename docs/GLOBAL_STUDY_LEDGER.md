# Global multi-source study ledger

The requested scope is every country, across credible publicly accessible
sources, deduplicated by the original opening cohort rather than website count.
This replaces a country-checkbox approach; unknown geography must not discard
otherwise useful global evidence or be invented from a website's language.

`data/research/global-studies.json` contains minimal factual research references,
not downloaded bodies, media, credentials, synthetic examples, or admitted
production samples. `scripts/global_studies.py` builds the canonical ledger:

```sh
python3 scripts/global_studies.py data/research/global-studies.json
```

Run computation on MAM or GitHub Actions, not the operator's Mac. Output is JSON
on stdout. This command has no network, database, admission, or publishing route.
It does not circumvent `config/sources.yaml` or grant a collector permission.

## Deduplication and statistical meaning

- Explicit original cohort IDs and reference URLs form connected components.
  Reprints/translations are aliases; reports with the same counts alone are not.
- Reddit whole-post permalinks additionally use the original post ID, so a
  title-slug URL and the short comments URL cannot count as separate reports.
  Original URLs and normalized record fingerprints remain unchanged. Comment
  permalinks, unrelated hosts and different post IDs are not collapsed.
  Explicit `redd.it/<post-id>` shortlinks also join the post; image/video
  subdomains of `redd.it` are not post aliases. Whole-post paths on Reddit's
  desktop/mobile/locale frontends and `/gallery/<post-id>` use the same ID.
  This identity matching is not a fetch allowlist and performs no redirects.
- A disagreement in cohort attributes or counts quarantines the component;
  aggregate updates and overlapping partial samples must never be summed.
- Deduplication resolves only known links. Distinct report groups are **not** a
  verified independent sample count. The verified pack total remains null.
- Each metric preserves exact source-reported integers and its unit: cards per
  pack is not necessarily the probability of a pack containing a hit. Rounded
  percentages are never reverse-engineered into counts.
- Set, language, product, sampling method and geography remain distinct fields.
  Publisher country and product market are not physical opening location.
- Reported studies are not independently audited pack observations. All ledger
  rows remain statistically ineligible for the existing production aggregator.
  Source access review, original-cohort overlap review, product/rarity mapping,
  admission contracts, tests and the normal release gates are still required.

## Initial evidence checked 2026-09-08

The [Fusion Strike original report](https://www.reddit.com/r/PokemonTCG/comments/qqpiol/)
states 4,197 packs, including 41 alternate-art V and 14 alternate-art VMAX cards.
It describes tabulating visibly unsealed, fully opened boxes, mostly booster
boxes with some ETBs. Promotional sampling and unavailable original-session
identities limit independence. Its printed VMAX percentage does not precisely
match 14/4197; preserve the count and discrepancy, not a corrected source claim.

The [Chilling Reign author's report](https://www.reddit.com/r/PokemonTCG/comments/o2nhez/)
states 5,000 tabulated packs. Its linked Cardzard page is the same study, not a
second 5,000-pack sample. The raw-table link returned 502 during this check; no
hit count is imported. The [Shining Fates report](https://www.reddit.com/r/PokemonTCG/comments/lo8m1v/shining_fates_pull_rate_data_from_1087_packs/)
is retained at title-claim level only, not as a verified denominator.

## Continuous discovery

The [country-first campaign](COUNTRY_DATA_CAMPAIGN.md) now owns scheduled
research, following Asia → Oceania → Europe → Africa at country/area level.
`global-research.yml` remains available for manual global/regional diagnostics,
including the Americas; its legacy `auto` selector still uses six-hour slots,
but no timer dispatches it. The legacy Asia workflow is also manual-only.

Research runs on the approved MAM host using the existing Codex ChatGPT login,
with no database or GitHub credentials passed to the research process. Each run
is limited to 12 search queries, six candidate studies, 16 KiB output and ten
minutes. Validation does not approve evidence. GitHub's separate publishing step
stores new normalized reports in bot-owned, content-hashed issues, including
closed issues when reconstructing history. Existing issues are never rewritten.
Identical normalized reports produce no new issue. Related but changed reports
are retained and fed through the cohort conflict detector rather than silently
replacing prior counts. A combined deduplicated JSON snapshot is saved for 90
days as an Actions artifact; durable research history remains in GitHub issues.

The history loader refuses to truncate at 1,000 repository issues or the ledger's
2,000-report/2-MiB capacity. Reaching this guard requires an explicit reviewed
archive/partition expansion, not dropping older samples. No snapshot or research
issue creates production evidence. Research metadata is minimal public facts,
never a cached page body or media. A successful test is not proof the schedule
has run: verify a main-branch run and its artifact after merging.

Failures report a fixed stage and an allowlisted error code, not the original
exception or generated document. `research_unavailable` means the isolated
research command failed; it is not evidence of an invalid login. A `validation`
failure means the returned batch was rejected. A `publication` failure means
history reconstruction or publication failed; it must not trigger a blind retry
without checking the existing run and history. No failure repairs a candidate,
weakens admission checks, or exposes raw provider output. Historical batches and
their fingerprints are unchanged by diagnostics.

## Remaining work (not complete)

Verify the scheduled discovery and accumulating ledger on main;
review and admit real cohorts through the existing source-controlled release
flow; expose reported references separately from verified production statistics;
verify both the public result and recurring collection on MAM. This foundation
alone neither expands live totals nor establishes global coverage.
