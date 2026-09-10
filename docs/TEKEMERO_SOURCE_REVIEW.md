# Tekemero: one complete M3 opening

Review record: [issue 161](https://github.com/ncihxaonn/pokecrack/issues/161).
The user explicitly approved minimal factual collection and publication of this
specific 30-pack report on 2026-09-10, subject to source review, tests and GitHub
release gates. This is not blanket permission for the domain or other reports.

## Scope and identity

- Exact source: <https://tekemero.com/260715-02/>; WordPress post 447.
- The query alias `https://tekemero.com/?p=447` is the same cohort, not additive.
- One self-purchased sealed booster box; the original report states all 30 packs
  were opened. No inventory multiplication, third-party comparison or inferred
  hit numerator contributes to the denominator.
- Product: Japanese M3, ムニキスゼロ, independently matched to the
  [official product page](https://www.pokemon-card.com/ex/m3/).
- Geography: `JP`, **product market**, confidence `tier_b`. Physical opening
  location and opening time are unknown, not inferred from the language/domain.
- Original publication: `2026-07-15T15:48:03+09:00`
  (`2026-07-15T06:48:03Z`). The later `dateModified` is not a new opening/date.
- Stable cohort: `tekemero-post-447-m3-complete-box`.

## Access and rights

MAM-only read-only probes fetched robots first, followed the 30-second minimum
delay, disabled redirects, bounded responses to 1 MB, and retained no HTML,
media, cookies, personal profiles, weighing tables or report prose. The robots
document allowed the exact URL; observed SHA-256:
`754143b6441e3aa0fca083350d76173d3f38f5b0e162f91bfc04d54f8d015d6d`.

The full [privacy page](https://tekemero.com/privacy-policy/) was reviewed.
No automated-access prohibition was found there and no separate terms were
found; this is **not an affirmative content-reuse licence**. User authorization
is limited to minimal noncreative facts, not reproduction of the source.
Stop on denied robots, access restrictions, changed terms or evidence drift.
Do not bypass an access denial or broaden to the separate 10-pack report.

## Evidence and admission

The parser binds one visible primary article (`post-447`) and its primary body
to the exact canonical URL, original JSON-LD publication, title and complete
opening paragraph. WordPress's implicit paragraph closing is accommodated;
hidden/outside/duplicate/changed evidence is rejected. Only hashes, facts and
the minimal `30パック` excerpt are retained, never the body itself.

Observed normalized evidence hashes (real MAM probe, not fixture output):

| Bound field | SHA-256 |
| --- | --- |
| Title | `f55b0821fb41a66088b925b5d89f36a3d78c2d4e1417d53fe4f8681b98b39b42` |
| Complete opening paragraph | `29a5a4d3cf31a546b13f84649839d2329aa15f2e2834ec80ec9ffaf382004bfa` |
| Visible primary body | `1d70d72e779134e2cc5030b7075ee8d03283bec3991da606f95b03c2e927c8d8` |

The source-specific contract, scheduler identity, private SQL gate and backup
contract must agree exactly. Tests use synthetic prose and never include the
original report. No observation is seeded by the migration. Only an actual
reviewed collector job, through the existing fenced finalizer, may publish
the single cohort. Source admission or a passing build alone is not evidence
that 30 packs have been collected or published.
