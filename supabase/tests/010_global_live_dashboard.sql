-- Global catalog projection, country-map publication, and public v2 contract.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(65);

select has_table('catalog', 'iso_alpha2_codes', 'strict ISO alpha-2 reference exists');
select has_table('public', 'tcgdex_set_index', 'browser-safe TCGdex set index exists');
select has_table('public', 'tcgdex_catalog_status', 'browser-safe TCGdex catalog status exists');
select has_table('public', 'country_period_map_cells', 'global country-period map cells exist');

select is(
  (select count(*)::integer from catalog.iso_alpha2_codes),
  249,
  'the reviewed ISO alpha-2 allowlist contains exactly 249 codes'
);
select ok(
  exists (select 1 from catalog.iso_alpha2_codes where code in ('AQ', 'AU', 'JP', 'US'))
    and not exists (select 1 from catalog.iso_alpha2_codes where code in ('UK', 'ZZ')),
  'official codes are accepted while common aliases and sentinels are absent'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'catalog.iso_alpha2_codes'::regclass),
  'the private ISO reference enables and forces RLS'
);
select ok(
  not has_table_privilege('anon', 'catalog.iso_alpha2_codes', 'select')
    and not has_table_privilege('authenticated', 'catalog.iso_alpha2_codes', 'select'),
  'browser roles cannot read the private ISO reference'
);
select ok(
  (select count(*) = 3 and bool_and(relations.relrowsecurity and relations.relforcerowsecurity)
   from pg_class as relations
   where relations.oid in (
     'public.tcgdex_set_index'::regclass,
     'public.tcgdex_catalog_status'::regclass,
     'public.country_period_map_cells'::regclass
   )),
  'all three global public projections enable and force RLS'
);
select ok(
  (select bool_and(
      has_table_privilege('anon', relation, 'select')
      and has_table_privilege('authenticated', relation, 'select')
    )
   from unnest(array[
     'public.tcgdex_set_index'::regclass,
     'public.tcgdex_catalog_status'::regclass,
     'public.country_period_map_cells'::regclass
   ]) as relations(relation)),
  'browser roles can select each narrow public projection'
);
select ok(
  (select bool_and(
      not has_table_privilege('anon', relation, 'insert')
      and not has_table_privilege('anon', relation, 'update')
      and not has_table_privilege('anon', relation, 'delete')
      and not has_table_privilege('authenticated', relation, 'insert')
      and not has_table_privilege('authenticated', relation, 'update')
      and not has_table_privilege('authenticated', relation, 'delete')
    )
   from unnest(array[
     'public.tcgdex_set_index'::regclass,
     'public.tcgdex_catalog_status'::regclass,
     'public.country_period_map_cells'::regclass
   ]) as relations(relation)),
  'browser roles have no projection-table DML'
);
select ok(
  (select bool_and(has_table_privilege('service_role', relation, 'select'))
   from unnest(array[
     'catalog.iso_alpha2_codes'::regclass,
     'public.tcgdex_set_index'::regclass,
     'public.tcgdex_catalog_status'::regclass,
     'public.country_period_map_cells'::regclass
   ]) as relations(relation)),
  'service_role can inspect all four new tables'
);
select ok(
  (select bool_and(
      not has_table_privilege('service_role', relation, 'insert')
      and not has_table_privilege('service_role', relation, 'update')
      and not has_table_privilege('service_role', relation, 'delete')
      and not has_table_privilege('service_role', relation, 'truncate')
      and not has_table_privilege('service_role', relation, 'references')
      and not has_table_privilege('service_role', relation, 'trigger')
    )
   from unnest(array[
     'catalog.iso_alpha2_codes'::regclass,
     'public.tcgdex_set_index'::regclass,
     'public.tcgdex_catalog_status'::regclass,
     'public.country_period_map_cells'::regclass
   ]) as relations(relation)),
  'service_role remains read-only on all four new tables'
);
select ok(
  not exists (
    select 1
    from pg_class as relations
    cross join lateral aclexplode(
      coalesce(relations.relacl, acldefault('r', relations.relowner))
    ) as privileges
    where relations.oid in (
      'public.tcgdex_set_index'::regclass,
      'public.tcgdex_catalog_status'::regclass,
      'public.country_period_map_cells'::regclass
    )
      and privileges.grantee = 0
      and privileges.privilege_type = 'SELECT'
  ),
  'the PostgreSQL PUBLIC pseudo-role cannot read a global public projection'
);
select ok(
  (select count(*) = 2 and bool_and(not procedures.prosecdef)
   from pg_proc as procedures
   where procedures.oid in (
     'ingest.publish_tcgdex_set_index_v1()'::regprocedure,
     'ingest.publish_tcgdex_catalog_status_v1()'::regprocedure
   )),
  'both projection trigger functions are SECURITY INVOKER'
);
select ok(
  (select count(*) = 2 and bool_and(
      coalesce(procedures.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
    )
   from pg_proc as procedures
   where procedures.oid in (
     'ingest.publish_tcgdex_set_index_v1()'::regprocedure,
     'ingest.publish_tcgdex_catalog_status_v1()'::regprocedure
   )),
  'both projection trigger functions fix search_path to pg_catalog'
);
select ok(
  not exists (
    select 1
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as privileges
    where procedures.oid in (
      'ingest.publish_tcgdex_set_index_v1()'::regprocedure,
      'ingest.publish_tcgdex_catalog_status_v1()'::regprocedure
    )
      and privileges.grantee in (
        0,
        'anon'::regrole::oid,
        'authenticated'::regrole::oid,
        'service_role'::regrole::oid
      )
      and privileges.privilege_type = 'EXECUTE'
  ),
  'browser and service roles cannot directly execute projection trigger functions'
);
select ok(
  (select count(*) = 2 and bool_and(triggers.tgenabled = 'O')
   from pg_trigger as triggers
   where not triggers.tgisinternal
     and triggers.tgname in (
       'sets_publish_tcgdex_set_index',
       'sync_state_publish_tcgdex_catalog_status'
     )),
  'both projection triggers are installed and enabled'
);

select has_function(
  'public',
  'get_public_dashboard_snapshot_v2',
  array[]::text[],
  'global public dashboard v2 RPC exists'
);
select ok(
  not coalesce(
    (select prosecdef from pg_proc
     where oid = 'public.get_public_dashboard_snapshot_v2()'::regprocedure),
    true
  ),
  'global public dashboard v2 is SECURITY INVOKER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, public']
   from pg_proc
   where oid = 'public.get_public_dashboard_snapshot_v2()'::regprocedure),
  'global public dashboard v2 fixes its search path'
);
select doesnt_match(
  pg_get_functiondef('public.get_public_dashboard_snapshot_v2()'::regprocedure),
  '(?is)(dashboard_overview|get_public_dashboard_snapshot_v1|catalog\.|ingest\.|analytics\.)',
  'global public dashboard v2 reads no legacy aggregate or private schema'
);
select ok(
  has_function_privilege(
    'anon', 'public.get_public_dashboard_snapshot_v2()', 'execute'
  ),
  'anon can execute global dashboard v2'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.get_public_dashboard_snapshot_v2()', 'execute'
  ),
  'authenticated can execute global dashboard v2'
);
select ok(
  not exists (
    select 1
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as privileges
    where procedures.oid = 'public.get_public_dashboard_snapshot_v2()'::regprocedure
      and privileges.grantee = 0
      and privileges.privilege_type = 'EXECUTE'
  ),
  'the PostgreSQL PUBLIC pseudo-role cannot execute global dashboard v2'
);
select ok(
  not has_function_privilege(
    'service_role', 'public.get_public_dashboard_snapshot_v2()', 'execute'
  ),
  'service_role cannot bypass the browser boundary by executing global dashboard v2'
);

delete from catalog.sync_state
where source = 'tcgdex' and scope = 'sets' and language = 'en' and not is_demo;
delete from catalog.sets
where external_source = 'tcgdex' and language = 'en' and not is_demo;
delete from public.country_period_map_cells;

select is(
  public.get_public_dashboard_snapshot_v2() ->> 'schemaVersion',
  '2.0.0',
  'empty global v2 preserves its explicit schema version'
);
select is(
  public.get_public_dashboard_snapshot_v2() ->> 'mode',
  'live',
  'empty global v2 never substitutes demo mode'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{catalog,setCount}')::integer,
  0,
  'empty global v2 reports zero current catalog rows'
);
select is(
  public.get_public_dashboard_snapshot_v2() #>> '{observations,status}',
  'empty',
  'empty global v2 reports an explicit empty observation state'
);
select is(
  jsonb_typeof(public.get_public_dashboard_snapshot_v2() #> '{observations,period}'),
  'null',
  'empty global v2 does not fabricate an observation period'
);
select is(
  jsonb_array_length(public.get_public_dashboard_snapshot_v2() -> 'mapCells'),
  0,
  'empty global v2 publishes no synthetic map cells'
);

insert into catalog.sync_state (
  source,
  scope,
  language,
  is_demo,
  revision,
  etag,
  content_sha256,
  item_count,
  last_checked_at,
  last_changed_at,
  last_job_id
) values (
  'tcgdex',
  'sets',
  'en',
  false,
  1,
  null,
  repeat('a', 64),
  1,
  clock_timestamp(),
  clock_timestamp() - interval '10 minutes',
  null
);
select ok(
  (select revision = 1 and set_count = 1 and is_current and not is_demo
   from public.tcgdex_catalog_status
   where source = 'tcgdex' and scope = 'sets' and language = 'en'),
  'sync-state trigger publishes only the safe live catalog status'
);
update catalog.sync_state
set scope = 'other'
where source = 'tcgdex' and scope = 'sets' and language = 'en' and not is_demo;
select ok(
  not exists (
    select 1
    from public.tcgdex_catalog_status
    where source = 'tcgdex'
      and scope = 'sets'
      and language = 'en'
      and not is_demo
      and is_current
  ),
  'moving a checkpoint out of the projected identity retires its old public status'
);
update catalog.sync_state
set scope = 'sets'
where source = 'tcgdex' and scope = 'other' and language = 'en' and not is_demo;

insert into catalog.sets (
  id,
  external_source,
  external_id,
  name,
  slug,
  language,
  series_name,
  release_date,
  is_active,
  is_demo
) values (
  'aa100000-0000-4000-8000-000000000001',
  'tcgdex',
  'global-live-1',
  'Global Live Set',
  'global-live-set',
  'en',
  'Global Series',
  '2026-08-01',
  true,
  false
);
select ok(
  (select name = 'Global Live Set' and is_current and not is_demo
   from public.tcgdex_set_index
   where set_id = 'aa100000-0000-4000-8000-000000000001'),
  'set trigger publishes a narrow current live row'
);

insert into catalog.sets (
  id,
  external_source,
  external_id,
  name,
  slug,
  language,
  is_active,
  is_demo
) values (
  'aa100000-0000-4000-8000-000000000002',
  'tcgdex',
  'global-demo-1',
  'Global Demo Set',
  'global-live-set',
  'en',
  true,
  true
);
select ok(
  (select count(*) = 2 and count(*) filter (where is_demo) = 1
   from public.tcgdex_set_index
   where slug = 'global-live-set'),
  'live and demo catalog identities coexist without crossing modes'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{catalog,setCount}')::integer,
  1,
  'global v2 counts only the current live set'
);
select is(
  jsonb_array_length(public.get_public_dashboard_snapshot_v2() #> '{catalog,sets}'),
  1,
  'global v2 excludes the same-slug demo set'
);
select is(
  public.get_public_dashboard_snapshot_v2() #>> '{catalog,status}',
  'fresh',
  'matching current index and checkpoint produce a fresh catalog state'
);

update catalog.sets
set is_active = false
where id = 'aa100000-0000-4000-8000-000000000001';
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{catalog,setCount}')::integer,
  0,
  'deactivating a catalog set removes it from the current public index'
);
update catalog.sets
set is_active = true
where id = 'aa100000-0000-4000-8000-000000000001';
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{catalog,setCount}')::integer,
  1,
  'reactivating a catalog set restores it to the current public index'
);
update catalog.sets
set name = 'Global Live Set Updated'
where id = 'aa100000-0000-4000-8000-000000000001';
select is(
  public.get_public_dashboard_snapshot_v2() #>> '{catalog,sets,0,name}',
  'Global Live Set Updated',
  'catalog updates are reflected without exposing raw metadata'
);

select throws_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, signal_status, methodology_version, updated_at
    ) values (
      'ZZ', 'Invalid', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 10, 2, 2,
      'Insufficient sample', 'global-v1', clock_timestamp()
    )$$,
  '23503',
  'insert or update on table "country_period_map_cells" violates foreign key constraint "country_period_map_cells_country_code_fkey"',
  'non-ISO country codes are rejected by the reference table'
);
select throws_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at
    ) values (
      'AU', 'Australia', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 29, 3, 3,
      0.2, 0.19, 0.15, 0.1, 0.3, 0.05,
      'Insufficient sample', 'global-v1', clock_timestamp()
    )$$,
  '23514',
  'new row for relation "country_period_map_cells" violates check constraint "country_period_map_publication_check"',
  'insufficient samples cannot leak a reconstructable rate tuple'
);
select lives_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, signal_status, methodology_version, updated_at
    ) values (
      'AU', 'Australia', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 29, 3, 3,
      'Insufficient sample', 'global-v1', clock_timestamp()
    )$$,
  'a real low-sample country row is allowed only with every rate withheld'
);
select throws_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, signal_status,
      methodology_version, updated_at
    ) values (
      'GB', 'United Kingdom', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 30, 3, 3, 0.2,
      'No significant signal', 'global-v1', clock_timestamp()
    )$$,
  '23514',
  'new row for relation "country_period_map_cells" violates check constraint "country_period_map_publication_check"',
  'an eligible country cannot publish a partially null metric tuple'
);
select lives_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at
    ) values (
      'US', 'United States', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 30, 5, 3,
      0.2, 0.19, 0.15, 0.1, 0.3, 0.05,
      'No significant signal', 'global-v1', clock_timestamp()
    )$$,
  '30 packs and three sources can publish one complete non-signal tuple'
);
select throws_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at
    ) values (
      'DE', 'Germany', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 199, 10, 3,
      0.25, 0.24, 0.15, 0.18, 0.3, 0.1,
      'Watch', 'global-v1', clock_timestamp()
    )$$,
  '23514',
  'new row for relation "country_period_map_cells" violates check constraint "country_period_map_publication_check"',
  'Watch remains unavailable below 200 packs'
);
select lives_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at
    ) values (
      'JP', 'Japan', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 200, 10, 3,
      0.25, 0.24, 0.15, 0.18, 0.3, 0.1,
      'Watch', 'global-v1', clock_timestamp()
    )$$,
  'Watch is structurally eligible at 200 packs and three sources'
);
select lives_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at
    ) values (
      'CA', 'Canada', '2026-08-01', '2026-08-07', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 100, 8, 3,
      0.16, 0.16, 0.15, 0.1, 0.22, 0.01,
      'No significant signal', 'global-v1', clock_timestamp()
    )$$,
  'an older complete period remains available for history'
);
select lives_ok(
  $$insert into public.country_period_map_cells (
      country_code, country_name, period_start, period_end, language,
      metric_key, metric_version, observed_packs, complete_openings,
      independent_source_count, observed_rate, posterior_mean, baseline_rate,
      credible_interval_low, credible_interval_high, delta_from_baseline,
      signal_status, methodology_version, updated_at, is_demo
    ) values (
      'CN', 'China', '2026-08-08', '2026-08-14', 'en',
      'qualifying_hit_pack_rate', 'global-v1', 100, 8, 3,
      0.18, 0.18, 0.15, 0.1, 0.24, 0.03,
      'No significant signal', 'global-v1', clock_timestamp(), true
    )$$,
  'a demo country row can coexist only inside the isolated demo mode'
);

select is(
  public.get_public_dashboard_snapshot_v2() #>> '{observations,period,start}',
  '2026-08-08',
  'v2 selects the latest complete period start once for every country'
);
select is(
  public.get_public_dashboard_snapshot_v2() #>> '{observations,period,end}',
  '2026-08-14',
  'v2 selects the latest complete period end once for every country'
);
select is(
  jsonb_array_length(public.get_public_dashboard_snapshot_v2() -> 'mapCells'),
  3,
  'v2 returns the three live countries in the latest complete period'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_dashboard_snapshot_v2() -> 'mapCells'
    ) as cells(item)
    where cells.item ->> 'countryCode' in ('CA', 'CN')
  ),
  'v2 neither mixes an older period nor crosses into demo cells'
);
select is(
  (select jsonb_typeof(cells.item -> 'hitRate')
   from jsonb_array_elements(
     public.get_public_dashboard_snapshot_v2() -> 'mapCells'
   ) as cells(item)
   where cells.item ->> 'countryCode' = 'AU'),
  'null',
  'the low-sample map cell exposes no observed rate'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{observations,countriesObserved}')::integer,
  3,
  'observation readiness counts countries in exactly one period'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{observations,countriesWithPublishedRate}')::integer,
  2,
  'observation readiness distinguishes published from withheld countries'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{observations,observedPacks}')::integer,
  259,
  'observation readiness sums only the latest live period denominator'
);
select is(
  (public.get_public_dashboard_snapshot_v2() #>> '{summary,observedPacks}')::integer,
  259,
  'legacy summary compatibility uses the same latest-period denominator'
);
select matches(
  public.get_public_dashboard_snapshot_v2() #>> '{sources,0,note}',
  'never used as opening evidence or a pull-rate denominator',
  'TCGdex is explicitly labelled catalog-only in the public payload'
);

set local role anon;
select is(
  (select count(*)::integer from public.tcgdex_set_index),
  1,
  'anon RLS returns only the current live catalog row'
);
select is(
  (select count(*)::integer from public.country_period_map_cells),
  4,
  'anon RLS returns live history but never demo map rows'
);
select is(
  jsonb_array_length(public.get_public_dashboard_snapshot_v2() -> 'mapCells'),
  3,
  'anon can execute the same latest-period global snapshot'
);
reset role;

select doesnt_match(
  public.get_public_dashboard_snapshot_v2()::text,
  '(?i)"(etag|content_sha256|last_job_id|metadata|hit_pack_count|is_demo)"\s*:',
  'global v2 omits private checkpoint, raw metadata, numerator, and mode-marker fields'
);

select * from finish();
rollback;
