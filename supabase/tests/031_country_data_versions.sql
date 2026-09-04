create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'country data versions preserve the established v2 browser contract'
);

select ok(
  position('''dataVersions'', versions.value' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('''collectionClass'', ''coverage_only''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('coverageAttributionBases' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('config ->> ''geography_basis''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('config ->> ''set_language''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('config ->> ''set_name''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'the projection labels each country with language, source-native set, and product metadata'
);

insert into catalog.sets (
  id,
  external_source,
  external_id,
  name,
  slug,
  language,
  release_date,
  series_name,
  rarity_taxonomy,
  metadata,
  is_active,
  is_demo
) values (
  'b1000000-0000-4000-8000-000000000001',
  'tcgdex',
  'me02.5',
  'Ascended Heroes',
  'pgtap-country-version-ascended-heroes',
  'en',
  '2026-02-20',
  'Mega Evolution',
  '{}'::jsonb,
  '{}'::jsonb,
  true,
  false
)
on conflict on constraint sets_external_identity_unique do update
set name = excluded.name,
    slug = excluded.slug,
    release_date = excluded.release_date,
    series_name = excluded.series_name,
    is_active = true,
    is_demo = false,
    updated_at = clock_timestamp();

insert into ingest.public_study_coverage_observations (
  study_key,
  source_policy_id,
  country_code,
  country_name,
  source_observed_at,
  pack_count,
  set_external_id,
  product_scope,
  collector_version,
  parser_version,
  source_policy_version,
  evidence_sha256,
  first_verified_at,
  last_verified_at,
  is_demo
) values (
  'cardchill-ascended-heroes-gb-90-v1',
  (
    select id
    from ingest.source_policies
    where source_key = 'public_study_cardchill_gb_90'
      and not is_demo
  ),
  'GB',
  'United Kingdom',
  '2026-03-03 11:26:21+00',
  90,
  'me02.5',
  'etb',
  'public-study-cardchill-ascended-heroes-v1',
  'cardchill-ascended-heroes-evidence-v1',
  'public-study-cardchill-ascended-heroes-v1',
  '828293f936003eae257223efdbe5cd2a8fe8f799d6ca4bba9063e01fd476a9be',
  statement_timestamp(),
  statement_timestamp(),
  false
)
on conflict (study_key) do update
set last_verified_at = excluded.last_verified_at;

select is(
  (
    select country.item -> 'dataVersions' ->> 0
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  'en · me02.5 · Ascended Heroes · ETB',
  'the country row exposes its exact reviewed data version'
);

select is(
  (
    select country.item ->> 'collectionClass'
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  'coverage_only',
  'every v2 country row declares the coverage-only collection class'
);

select is(
  (
    select country.item -> 'coverageAttributionBases' ->> 0
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  'publisher_country',
  'the country row derives its attribution basis from the reviewed contract'
);

select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    cross join lateral jsonb_array_elements_text(
      country.item -> 'coverageAttributionBases'
    ) as basis(value)
    where basis.value not in (
      'publisher_country',
      'author_public_residence',
      'product_market'
    )
  )
  and not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    cross join lateral jsonb_array_elements_text(
      country.item -> 'coverageAttributionBases'
    ) as basis(value)
    group by country.item ->> 'countryCode'
    having count(*) <> count(distinct basis.value)
  ),
  'coverage attribution bases are non-empty, allowlisted, and unique per country'
);

select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contract
    where contract.config ->> 'geography_basis' = 'product_market'
  )
  or exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'JP'
      and country.item -> 'coverageAttributionBases' ? 'product_market'
  ),
  'a reviewed product-market contract is exposed as the JP product-market bucket'
);

select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where jsonb_typeof(country.item -> 'dataVersions') <> 'array'
      or jsonb_array_length(country.item -> 'dataVersions') = 0
      or country.item ?| array[
        'hitRate',
        'qualifyingHitPackCount',
        'baselineRate',
        'posteriorMean',
        'credibleInterval',
        'deltaFromBaseline'
      ]
  ),
  'version labels remain denominator-only and never add inference fields'
);

select * from finish();
rollback;
