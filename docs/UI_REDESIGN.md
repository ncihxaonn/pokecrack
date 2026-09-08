# Artificial Analysis reference redesign

PokeCrack is a research dashboard for comparing verified Pokémon TCG openings.
Its first screen should explain the evidence available and the limits of that
evidence, before inviting deeper comparison.

## Direction

The sole visual reference is https://artificialanalysis.ai/, inspected on
2026-09-08. The user explicitly replaced the earlier CRM/dashboard direction:
match the reference's current visual language, do not mix in another design.
Existing GitHub/Vercel hosting and MAM workers remain unchanged; this is not a
new Sites application. Reference branding, copy and proprietary assets are not
copied into Pokecrack.

- Measured palette: white #ffffff, black #000000, navigation #e7e7e7,
  borders #d9d9d9, plum accent #702675, chart violet #7f4bf3.
  Secondary text is #6b6b6b for legibility; semantic warnings remain distinct.
- Measured reference type roles: Victor Serif Basic display, Suisse Intl UI.
  These commercial font files are not supplied/licensed by this project, so
  Georgia and Arial/Helvetica are explicit system substitutes, not a claim of
  exact font parity. Display 80/80px desktop, 48/48px mobile; section 30px,
  chart 24/32px; UI 14px; chart labels 11–12px.
- Top horizontal grey capsule navigation, black Pokecrack wordmark capsule,
  20px page gutters, 8px panel radii, 1px borders, no decorative card shadows.
- Reference structure: large left headline, two narrow right-hand links;
  three equal highlight charts; secondary in-page navigation beside analysis.
  Mobile removes the secondary hero column and stacks charts, with a labelled
  disclosure menu and independently scrollable comparison tables.
- The world map preserves its fixed absolute scales and hatch distinctions,
  now using the reference's violet/neutral color family.

```text
black wordmark | grey capsule navigation             search
large serif headline                       two short links
Highlights ------------------------------------------------
packs chart          openings chart          catalog chart
in-page index | totals / world map / catalog / comparisons
```

## Information and review

No invented growth, charts, identities or live claims. Catalog metadata, discovery
activity and accepted evidence remain separate. Country attribution is not an
opening location. Exact sample rates retain numerators and denominators;
inference stays threshold-gated. Source contributions are not independent sources.

Scope: navigation, public lists/details, admin/login styling and loading/error
shells. Authentication and collection are unchanged. Highlight charts use only
published region counts and the explicitly labelled displayed catalog entries;
they do not sum overlapping coverage buckets or fabricate missing comparisons.
Avoid duplicated region cards and tables; keep caveats needed for visible metrics
visible. Verify desktop, mobile, navigation, search, empty data and disclosures.
## Public navigation follow-up

Sources, Methodology and Status are no longer public website sections. Desktop/mobile navigation contains only Overview, Sets, Regions, Retailers and Batches; the footer has no reference navigation. Their old URLs redirect to Overview and are excluded from the sitemap. The homepage no longer displays reviewed-source, social-discovery health or methodology panels. Internal collection, source review, health checks, data-quality labels and authentication remain unchanged.
