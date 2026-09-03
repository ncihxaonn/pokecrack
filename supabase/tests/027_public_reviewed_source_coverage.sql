-- The public source rail is strictly denominator-only. It derives a source
-- tuple only from the same valid rolling-period rows that power the country
-- and set coverage projections.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'public',
  'get_public_study_coverage_v2',
  array[]::text[],
  'the reviewed source coverage remains on the existing browser RPC'
);
select is(
  (select proowner::regrole::text
   from pg_proc
   where oid = 'public.get_public_study_coverage_v2()'::regprocedure),
  'postgres',
  'the source coverage RPC remains postgres-owned'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.get_public_study_coverage_v2()'::regprocedure)
  and (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
       from pg_proc
       where oid = 'public.get_public_study_coverage_v2()'::regprocedure),
  'the source coverage RPC remains SECURITY DEFINER with a fixed search path'
);
select ok(
  has_function_privilege('anon', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and has_function_privilege('authenticated', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and not has_function_privilege('service_role', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and not has_function_privilege('public', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute'),
  'only browser API roles retain execute on the source coverage RPC'
);

select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'the additive source coverage preserves the established v2 browser contract version'
);
select set_eq(
  $$
    select key
    from jsonb_object_keys(public.get_public_study_coverage_v2()) as keys(key)
  $$,
  $$values ('countries'::text), ('period'), ('schemaVersion'), ('sets'), ('sources')$$,
  'the source coverage projection retains the exact public root fields'
);
select ok(
  position('source_coverage as (' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('from valid_rows as rows' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('group by rows.public_id' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('count(distinct rows.country_code)' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('openings.eligible_for_statistics' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('openings.complete_opening' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('openings.validation_status = ''accepted''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('openings.public_status = ''verified''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('<= statement_timestamp()' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'source coverage requires a valid eligible opening and a nonfuture row in the current rolling period'
);
select ok(
  position('when source_coverage.public_id is null then ''{}''::jsonb' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'a source with no valid row omits coverage rather than being represented as zero'
);
select ok(
  position('''packsObserved'', source_coverage.packs_observed' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('''countriesObserved'', source_coverage.countries_observed' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('''completeOpenings'', source_coverage.complete_openings' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'source coverage emits only the three documented denominator fields'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where source.item ? 'coverage'
      and (
        not ((source.item -> 'coverage') ?& array[
          'packsObserved',
          'countriesObserved',
          'completeOpenings'
        ])
        or exists (
          select 1
          from jsonb_object_keys(source.item -> 'coverage') as keys(key)
          where keys.key not in ('packsObserved', 'countriesObserved', 'completeOpenings')
        )
      )
  ),
  'any emitted source coverage has exactly the safe documented field set'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where source.item ? 'coverage'
      and (
        (source.item -> 'coverage' ->> 'packsObserved')::bigint <= 0
        or (source.item -> 'coverage' ->> 'countriesObserved')::integer <= 0
        or (source.item -> 'coverage' ->> 'completeOpenings')::bigint <= 0
        or (source.item -> 'coverage' ->> 'completeOpenings')::bigint
          > (source.item -> 'coverage' ->> 'packsObserved')::bigint
        or (source.item -> 'coverage' ->> 'countriesObserved')::integer
          > (source.item -> 'coverage' ->> 'completeOpenings')::bigint
      )
  ),
  'any emitted source coverage keeps positive, internally consistent denominator counts'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where source.item ? 'coverage'
      and (source.item -> 'coverage') ?| array[
        'hitRate',
        'qualifyingHitPackCount',
        'evidenceExcerpt',
        'evidenceSha256',
        'policyId',
        'sourcePolicy',
        'studyKey',
        'baselineRate',
        'posteriorMean',
        'credibleInterval',
        'deltaFromBaseline'
      ]
  ),
  'source coverage never exposes a numerator, private identity, evidence, or inference field'
);

select set_eq(
  $$
    select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as functions
    cross join lateral pg_catalog.aclexplode(
      coalesce(functions.proacl, pg_catalog.acldefault('f', functions.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where functions.oid = 'public.get_public_study_coverage_v2()'::regprocedure
      and grants.privilege_type = 'EXECUTE'
  $$,
  $$values ('anon'::text), ('authenticated'), ('postgres')$$,
  'only postgres and the browser API roles can execute the source coverage RPC'
);

-- Exercise a real eligible opening row. The browser projection must emit the
-- three source-level denominator counts, then drop them immediately when the
-- linked opening becomes ineligible.
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
  'a1000000-0000-4000-8000-000000000001',
  'tcgdex',
  'me03',
  'Perfect Order',
  'pgtap-source-coverage-perfect-order',
  'en',
  '2026-03-27',
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

insert into ingest.source_items (
  id,
  source_policy_id,
  platform,
  external_id,
  source_url,
  normalized_url,
  domain,
  title,
  text_excerpt,
  published_at,
  discovered_at,
  content_hash,
  collector_type,
  collector_version,
  source_policy_version,
  access_mode,
  usage_classification,
  source_kind,
  language,
  status,
  metadata,
  expires_at,
  is_demo
) values (
  'a2000000-0000-4000-8000-000000000001',
  (
    select id
    from ingest.source_policies
    where source_key = 'public_study_comicbook_us_55' and not is_demo
  ),
  'public-study',
  'pgtap-source-coverage-comicbook',
  'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
  'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
  'comicbook.com',
  'Private fixture title',
  'Private fixture excerpt',
  '2026-03-19 21:00:00+00',
  statement_timestamp(),
  repeat('a', 64),
  'scrapling_http',
  'public-study-comicbook-perfect-order-v1',
  'public-study-comicbook-perfect-order-v1',
  'public',
  'statistics',
  'public_web',
  'en',
  'accepted',
  '{}'::jsonb,
  statement_timestamp() + interval '730 days',
  false
);

insert into ingest.extraction_runs (
  id,
  source_item_id,
  stage,
  provider,
  model,
  prompt_version,
  input_hash,
  output_json,
  decision,
  confidence,
  started_at,
  completed_at,
  expires_at,
  is_demo
) values (
  'a3000000-0000-4000-8000-000000000001',
  'a2000000-0000-4000-8000-000000000001',
  'extract',
  'deterministic-public-study',
  'reviewed-parser-v1',
  'public-study-v1',
  repeat('b', 64),
  '{}'::jsonb,
  'accepted',
  1,
  statement_timestamp(),
  statement_timestamp(),
  statement_timestamp() + interval '730 days',
  false
);

insert into ingest.openings (
  id,
  source_item_id,
  extraction_run_id,
  set_id,
  language,
  pack_count,
  complete_opening,
  country_code,
  opened_at,
  observed_at,
  evidence_tier,
  overall_confidence,
  eligible_for_statistics,
  methodology_version,
  validation_status,
  public_status,
  source_kind,
  expires_at,
  is_demo
) values (
  'a4000000-0000-4000-8000-000000000001',
  'a2000000-0000-4000-8000-000000000001',
  'a3000000-0000-4000-8000-000000000001',
  (
    select id
    from catalog.sets
    where external_source = 'tcgdex'
      and external_id = 'me03'
      and language = 'en'
      and not is_demo
  ),
  'en',
  55,
  true,
  'US',
  '2026-03-19 21:00:00+00',
  statement_timestamp(),
  'B',
  1,
  true,
  'global-observation-v1',
  'accepted',
  'verified',
  'public_web',
  statement_timestamp() + interval '730 days',
  false
);

insert into ingest.public_study_observations (
  study_key,
  source_policy_id,
  source_item_id,
  extraction_run_id,
  opening_id,
  country_code,
  country_name,
  geography_basis,
  geography_confidence,
  source_observed_at,
  pack_count,
  qualifying_hit_pack_count,
  set_external_id,
  product_scope,
  metric_key,
  metric_version,
  collector_version,
  parser_version,
  source_policy_version,
  evidence_sha256,
  first_verified_at,
  last_verified_at,
  is_demo
) values (
  'comicbook-perfect-order-us-55-v1',
  (
    select id
    from ingest.source_policies
    where source_key = 'public_study_comicbook_us_55' and not is_demo
  ),
  'a2000000-0000-4000-8000-000000000001',
  'a3000000-0000-4000-8000-000000000001',
  'a4000000-0000-4000-8000-000000000001',
  'US',
  'United States',
  'publisher_country',
  'tier_b',
  '2026-03-19 21:00:00+00',
  55,
  1,
  'me03',
  'all',
  'qualifying_hit_pack_rate',
  'global-sir-v1',
  'public-study-comicbook-perfect-order-v1',
  'comicbook-perfect-order-evidence-v1',
  'public-study-comicbook-perfect-order-v1',
  'a48e4b6d54243254a8c5a951161238679ecc7d053676b48555022e582428818d',
  statement_timestamp(),
  statement_timestamp(),
  false
);

select set_config(
  'pokecrack.source_coverage_comicbook',
  (
    select source.item::text
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources')
      as source(item)
    where source.item ->> 'id' = 'comicbook_perfect_order_study'
  ),
  true
);
select is(
  current_setting('pokecrack.source_coverage_comicbook')::jsonb -> 'coverage',
  jsonb_build_object(
    'packsObserved', 55,
    'countriesObserved', 1,
    'completeOpenings', 1
  ),
  'a valid current reviewed opening emits its exact source-level denominator tuple'
);

update ingest.openings
set eligible_for_statistics = false,
    updated_at = clock_timestamp()
where id = 'a4000000-0000-4000-8000-000000000001';

select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources')
      as source(item)
    where source.item ->> 'id' = 'comicbook_perfect_order_study'
      and source.item ? 'coverage'
  ),
  'an ineligible linked opening immediately removes the source coverage tuple'
);

set local role anon;
select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'anon can read the additive public source coverage projection'
);
reset role;

set local role authenticated;
select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'authenticated can read the additive public source coverage projection'
);
reset role;

select finish();
rollback;
