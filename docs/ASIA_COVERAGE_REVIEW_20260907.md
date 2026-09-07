# Asia coverage review — 2026-09-07

## Qualified candidate

- Original publisher: [Garbage Rips 585](https://garbagerips.com/rip/only-garbage-rips-chinese-gem-pack-vol-2-eeveelutions-8jKHh-P7P7M.html).
- One Gem Pack Vol.2 pack; published 2026-02-13T13:30:09Z in the page's VideoObject metadata.
- China **product-market** coverage, not physical opening location. The publisher identifies itself with Rochester, New York.
- [Official product identity](https://www.pokemon.cn/tcg/product/15518.html). The source-native set identifier `gem-pack-vol-2` is not asserted to be an official catalog code.
- Public robots allow the page. The linked site policy was reviewed on MAM; only a short factual excerpt is retained. No HTML, images, video, transcript, contact details, or claimed hit numerator are persisted.
- The adapter pins source URL, title, publication timestamp, video identity, source policy, and evidence hash. Changed or missing evidence fails closed.

## Not qualified for publication

- Hong Kong01 article 60330325: one reporter's M1S box supports a 30-pack candidate, but the aggregate box counts conflict and the site's reuse/storage terms need a suitable permission basis. Not enabled.
- PokeRam video `kNTkSOIljh4`: India candidate; MAM did not return usable public video metadata. No verified identity/date/denominator contract, so not enabled.
- Malaysia: a box *shipped from* Malaysia is not proof of Malaysian publisher or opening location. Counterfeit-card videos are excluded.
- Vietnam: PokeMinja video `k3usBW_SVLc` reports missing footage for two packs. Do not treat it as a verified complete-box observation.
- Philippines: country-targeted purchasing guides do not establish publisher/opening geography. A candidate described as filtered product is not adopted.
- Indonesia: identified candidate videos still need primary identity, date, and complete-pack evidence.

## Release status

This document is an evidence audit, not proof of production deployment. Release requires database replay, CI, structured review, a fresh verified backup, the reviewed migration/deployment workflows, and inspection of the public China product-market entry. No claim that every Asian country is covered is made.

Verification completed on MAM in an isolated source copy/container:

- Worker: 795 tests and 2 subtests passed; lint passed; 117 files passed format checking; mypy passed for 76 source files.
- Live source: robots respected with the 30-second delay, exact adapter accepted one pack and the pinned hash, zero media retained. No production database write occurred.
- New migration: the project's destructive-statement scanner found none. This is not PostgreSQL replay or pgTAP verification, which remain pending.
- Structured review command: `autoreview --mode local --engine codex` ran on MAM after the user explicitly approved source-code submission. It exited successfully with zero actionable findings (correctness confidence 0.91). No alternative reviewer was used.
- At review closeout, GitHub CI, database replay, merge, migration application, and production deployment remained pending. The release run and live endpoint, not this preparation log, establish deployment status.

Working branch: `codex/asia-live-coverage-20260907`, based on `36090f3a3b39fae8806a0a416d5fc86edf1286e1`. The candidate touches source policy/configuration, the exact adapter/registry, readiness checks, Worker tests, one forward migration, one pgTAP test file, and this audit. Existing worktrees are untouched.
