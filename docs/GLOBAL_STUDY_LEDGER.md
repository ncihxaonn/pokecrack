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

## Remaining work (not complete)

Connect global multilingual discovery to this accumulating ledger rather than
overwrite three candidates per country; persist provenance and overlap decisions;
review and admit real cohorts through the existing source-controlled release
flow; expose reported references separately from verified production statistics;
verify both the public result and recurring collection on MAM. This foundation
alone neither expands live totals nor establishes global coverage.
