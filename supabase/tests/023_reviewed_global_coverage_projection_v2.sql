-- Registry-driven public reviewed-coverage projection.  This suite proves the
-- v2 browser contract aggregates denominator-safe facts server-side and never
-- leaks the private reviewed-study ledger.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'public',
  'get_public_study_coverage_v2',
  array[]::text[],
  'registry-driven reviewed coverage RPC exists'
);
select is(
  (select proowner::regrole::text
   from pg_proc
   where oid = 'public.get_public_study_coverage_v2()'::regprocedure),
  'postgres',
  'coverage v2 RPC is owned by postgres'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.get_public_study_coverage_v2()'::regprocedure),
  'coverage v2 RPC is SECURITY DEFINER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc
   where oid = 'public.get_public_study_coverage_v2()'::regprocedure),
  'coverage v2 RPC fixes search_path to pg_catalog only'
);
select ok(
  has_function_privilege('anon', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and has_function_privilege('authenticated', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and not has_function_privilege('service_role', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute')
  and not has_function_privilege('public', 'public.get_public_study_coverage_v2()'::regprocedure, 'execute'),
  'coverage v2 grants execute only to browser API roles'
);

select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'coverage v2 emits its explicit versioned public contract'
);
select set_eq(
  $$
    select key
    from jsonb_object_keys(public.get_public_study_coverage_v2()) as keys(key)
  $$,
  $$values ('countries'::text), ('period'), ('schemaVersion'), ('sets'), ('sources')$$,
  'coverage v2 exposes only its exact documented public root fields'
);
select cmp_ok(
  jsonb_array_length(public.get_public_study_coverage_v2() -> 'sources'),
  '>=',
  5,
  'coverage v2 exposes every current reviewed source through the registry'
);
select ok(
  exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where item ->> 'id' = 'comicbook_perfect_order_study'
  )
  and exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where item ->> 'id' = 'tcgtalk_perfect_order_study'
  ),
  'the registry projection spans both statistical-ledger and coverage-only reviewed studies'
);
select doesnt_match(
  public.get_public_study_coverage_v2()::text,
  '(?i)(evidence|sha256|qualifying_hit|policy_id|source_policy|job_id|worker_id|gate|study_key|domain)',
  'coverage v2 returns no private evidence, numerator, policy, job, gate, study key, or source domain'
);
select doesnt_match(
  public.get_public_study_coverage_v2()::text,
  '(?i)(hitrate|posterior|baselinerate|credibleinterval|deltafrombaseline)',
  'coverage v2 remains denominator-only and never publishes inference fields'
);

select ok(
  position('ingest.reviewed_public_study_contracts()' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('contracts.ordinal in (' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) = 0
  and position('ingest.public_study_observations' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('ingest.public_study_coverage_observations' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('count(distinct rows.domain)' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('catalog.iso_alpha2_codes' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'coverage v2 uses the full reviewed registry, both ledgers, valid ISO countries, and server-side distinct-domain aggregation'
);

set local role anon;
select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'anon can execute the bounded public coverage projection'
);
reset role;

set local role authenticated;
select is(
  public.get_public_study_coverage_v2() ->> 'schemaVersion',
  '2.0.0',
  'authenticated can execute the bounded public coverage projection'
);
reset role;

select finish();
rollback;
