# Clear dashboard redesign

PokeCrack is a research dashboard for comparing verified Pokémon TCG openings.
Its first screen should explain the evidence available and the limits of that
evidence, before inviting deeper comparison.

## Direction

The user-provided CRM image and dashboard video inform compact navigation and
quiet surfaces. Artificial Analysis informs metric labels, comparison tables and
visible methodology. Reference media stays outside Git. Existing GitHub/Vercel
hosting and MAM workers remain unchanged; this is not a new Sites application.

- Canvas #f7f8fa; surface #ffffff; ink #182230; secondary #606e80;
  border #e2e7ef; interactive blue #2563eb. Green and amber indicate status.
- Geist Sans: 28px page titles, 18–20px section titles, 14px interface text.
  Tabular figures align numbers; monospace is reserved for identifiers.
- 216px desktop navigation, 64px utility bar, 24px gutters, 12px cards.
- Mobile uses a labelled disclosure menu, compact summaries and independently
  scrollable tables. Keyboard focus and reduced-motion support are retained.
- Signature: the evidence atlas pairs sample volume with observation readiness
  and expandable exact country/product-market data.

```text
Before                         After
full-width navigation          sidebar | utility bar
large promotional title        sidebar | title + short context
large map + long detail lists  sidebar | four factual summary cards
totals below those lists        sidebar | map + readiness
long source cards              sidebar | detail disclosure + source preview
```

## Information and review

No invented growth, charts, identities or live claims. Catalog metadata, discovery
activity and accepted evidence remain separate. Country attribution is not an
opening location. Exact sample rates retain numerators and denominators;
inference stays threshold-gated. Source contributions are not independent sources.

Scope: navigation, public lists/details, sources, methodology, status, admin/login
styling and loading/error shells. Authentication and collection are unchanged.
Avoid duplicated region cards and tables; keep caveats needed for visible metrics
visible. Verify desktop, mobile, navigation, search, empty data and disclosures.
## Public navigation follow-up

Sources, Methodology and Status are no longer public website sections. Desktop/mobile navigation contains only Overview, Sets, Regions, Retailers and Batches; the footer has no reference navigation. Their old URLs redirect to Overview and are excluded from the sitemap. The homepage no longer displays reviewed-source, social-discovery health or methodology panels. Internal collection, source review, health checks, data-quality labels and authentication remain unchanged.
