-- Bounded v3 source, service, reviewed-set, and country-detail projection.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(39);

select has_function(
  'public',
  'get_public_dashboard_snapshot_v3',
  array[]::text[],
  'public pipeline snapshot v3 exists'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.get_public_dashboard_snapshot_v3()'::regprocedure),
  'public pipeline snapshot v3 is SECURITY DEFINER'
);
select is(
  (select proowner::regrole::text
   from pg_proc
   where oid = 'public.get_public_dashboard_snapshot_v3()'::regprocedure),
  'postgres',
  'public pipeline snapshot v3 is owned by postgres'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc
   where oid = 'public.get_public_dashboard_snapshot_v3()'::regprocedure),
  'public pipeline snapshot v3 fixes search_path to pg_catalog only'
);
select ok(
  has_function_privilege(
    'anon', 'public.get_public_dashboard_snapshot_v3()', 'execute'
  ),
  'anon can execute public pipeline snapshot v3'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.get_public_dashboard_snapshot_v3()', 'execute'
  ),
  'authenticated can execute public pipeline snapshot v3'
);
select ok(
  not has_function_privilege(
    'service_role', 'public.get_public_dashboard_snapshot_v3()', 'execute'
  ),
  'service_role cannot execute the browser snapshot directly'
);
select ok(
  not exists (
    select 1
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as privileges
    where procedures.oid =
      'public.get_public_dashboard_snapshot_v3()'::regprocedure
      and privileges.grantee = 0
      and privileges.privilege_type = 'EXECUTE'
  ),
  'the PostgreSQL PUBLIC pseudo-role cannot execute v3'
);
select ok(
  position(
    'public.get_public_dashboard_snapshot_v2()'
    in pg_get_functiondef(
      'public.get_public_dashboard_snapshot_v3()'::regprocedure
    )
  ) > 0
    and position(
      'ingest.source_policies'
      in pg_get_functiondef(
        'public.get_public_dashboard_snapshot_v3()'::regprocedure
      )
    ) > 0
    and position(
      'ingest.youtube_discoveries'
      in pg_get_functiondef(
        'public.get_public_dashboard_snapshot_v3()'::regprocedure
      )
    ) > 0
    and position(
      'ingest.public_study_observations'
      in pg_get_functiondef(
        'public.get_public_dashboard_snapshot_v3()'::regprocedure
      )
    ) > 0
    and position(
      'ingest.worker_heartbeats'
      in pg_get_functiondef(
        'public.get_public_dashboard_snapshot_v3()'::regprocedure
      )
    ) > 0
    and position(
      'catalog.sets'
      in pg_get_functiondef(
        'public.get_public_dashboard_snapshot_v3()'::regprocedure
      )
    ) > 0,
  'v3 reads only the reviewed base and exact private summary relations'
);
select doesnt_match(
  pg_get_functiondef('public.get_public_dashboard_snapshot_v3()'::regprocedure),
  '(?is)discoveries\.(video_id|title|source_url)|heartbeats\.worker_id|jobs\.payload|last_error_(code|message)|source_items|extraction_runs|opening_hits',
  'v3 never selects private discovery identity, worker identity, payloads, errors, or evidence rows'
);
select set_eq(
  $$select coalesce(roles.rolname, 'PUBLIC')::text
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as privileges
    left join pg_roles as roles on roles.oid = privileges.grantee
    where procedures.oid =
      'public.get_public_dashboard_snapshot_v3()'::regprocedure
      and privileges.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('anon'), ('authenticated')$$,
  'v3 has only owner and browser-role execute ACLs'
);

insert into public.country_period_map_cells (
  country_code,
  country_name,
  period_start,
  period_end,
  language,
  set_scope,
  product_scope,
  metric_key,
  metric_version,
  observed_packs,
  complete_openings,
  independent_source_count,
  observed_rate,
  posterior_mean,
  baseline_rate,
  credible_interval_low,
  credible_interval_high,
  delta_from_baseline,
  signal_status,
  methodology_version,
  updated_at,
  is_demo
) values (
  'US',
  'United States',
  (statement_timestamp() at time zone 'UTC')::date - 365,
  (statement_timestamp() at time zone 'UTC')::date - 1,
  'en',
  'all',
  'all',
  'qualifying_hit_pack_rate',
  'global-sir-v1',
  10,
  1,
  1,
  null,
  null,
  null,
  null,
  null,
  null,
  'Insufficient sample',
  'global-observation-v1',
  statement_timestamp() - interval '1 day',
  false
);

set local role anon;
select set_config(
  'pokecrack.public_pipeline_expired_snapshot',
  public.get_public_dashboard_snapshot_v3()::text,
  true
);
reset role;
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_expired_snapshot')::jsonb
      -> 'mapCells'
  ),
  0,
  'v3 never republishes a historical map period through definer privileges'
);
select is(
  current_setting('pokecrack.public_pipeline_expired_snapshot')::jsonb
    #>> '{observations,status}',
  'empty',
  'a historical-only map becomes an honest current-period empty state'
);

update ingest.source_policies
set last_success_at = statement_timestamp(),
    last_failure_at = null
where source_key in (
  'youtube_discovery',
  'public_study_comicbook_us_55',
  'public_study_wargamer_gb_17'
)
  and not is_demo;

insert into ingest.youtube_discoveries (
  video_id,
  source_policy_id,
  source_url,
  title,
  published_at,
  first_seen_at,
  last_seen_at,
  expires_at,
  is_demo
) values (
  'AbCdEfGhI12',
  (
    select id from ingest.source_policies
    where source_key = 'youtube_discovery' and not is_demo
  ),
  'https://www.youtube.com/watch?v=AbCdEfGhI12',
  'DO-NOT-LEAK-V3-TITLE',
  statement_timestamp() - interval '1 day',
  statement_timestamp(),
  statement_timestamp(),
  statement_timestamp() + interval '28 days',
  false
);

insert into ingest.worker_heartbeats (
  worker_id,
  worker_type,
  version,
  last_seen_at,
  metadata,
  is_demo
) values
  ('pgtap-v3-collector', 'collector', 'test-v3', statement_timestamp(), '{}'::jsonb, false),
  ('pgtap-v3-scheduler', 'scheduler', 'test-v3', statement_timestamp(), '{}'::jsonb, false),
  ('pgtap-v3-watchdog', 'watchdog', 'test-v3', statement_timestamp(), '{}'::jsonb, false);

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
  '91000000-0000-4000-8000-000000000001',
  'tcgdex',
  'me03',
  'Perfect Order',
  'v3-perfect-order',
  'en',
  '2026-03-27',
  'Mega Evolution',
  '{}'::jsonb,
  '{}'::jsonb,
  true,
  false
);

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
  '92000000-0000-4000-8000-000000000001',
  (
    select id from ingest.source_policies
    where source_key = 'public_study_comicbook_us_55' and not is_demo
  ),
  'public-study',
  'comicbook-perfect-order-us-55-v1',
  'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
  'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
  'comicbook.com',
  'PRIVATE TEST TITLE',
  'PRIVATE TEST EXCERPT',
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
  '93000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000001',
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
  '94000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000001',
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
    select id from ingest.source_policies
    where source_key = 'public_study_comicbook_us_55' and not is_demo
  ),
  '92000000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001',
  '94000000-0000-4000-8000-000000000001',
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
  repeat('c', 64),
  statement_timestamp(),
  statement_timestamp(),
  false
);

insert into public.country_period_map_cells (
  country_code,
  country_name,
  period_start,
  period_end,
  language,
  set_scope,
  product_scope,
  metric_key,
  metric_version,
  observed_packs,
  complete_openings,
  independent_source_count,
  observed_rate,
  posterior_mean,
  baseline_rate,
  credible_interval_low,
  credible_interval_high,
  delta_from_baseline,
  signal_status,
  methodology_version,
  updated_at,
  is_demo
) values (
  'US',
  'United States',
  (statement_timestamp() at time zone 'UTC')::date - 364,
  (statement_timestamp() at time zone 'UTC')::date,
  'en',
  'all',
  'all',
  'qualifying_hit_pack_rate',
  'global-sir-v1',
  55,
  1,
  1,
  null,
  null,
  null,
  null,
  null,
  null,
  'Insufficient sample',
  'global-observation-v1',
  statement_timestamp(),
  false
);

set local role anon;
select set_config(
  'pokecrack.public_pipeline_snapshot',
  public.get_public_dashboard_snapshot_v3()::text,
  true
);
reset role;

select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    ->> 'schemaVersion',
  '2.0.0',
  'v3 preserves the Web schema version'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb ->> 'mode',
  'live',
  'v3 preserves live mode'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'mapCells'
  ),
  1,
  'v3 preserves the one selected map cell'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'regions'
  ),
  1,
  'v3 derives one country-detail row from the map'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    #>> '{regions,0,countryCode}',
  'US',
  'the country-detail row uses the official ISO code'
);
select is(
  (
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb
      #>> '{regions,0,packsObserved}'
  )::integer,
  55,
  'the country-detail row preserves its denominator'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    #> '{regions,0,hitRate}',
  'null'::jsonb,
  'the country-detail row keeps its rate withheld'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sets'
  ),
  1,
  'v3 publishes one denominator-backed reviewed-set summary'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    #>> '{sets,0,name}',
  'Perfect Order',
  'the reviewed set resolves through the live TCGdex catalog'
);
select is(
  (
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb
      #>> '{sets,0,packsObserved}'
  )::integer,
  55,
  'the reviewed-set summary exposes only its denominator'
);
select is(
  (
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb
      #>> '{sets,0,independentSources}'
  )::integer,
  1,
  'the reviewed-set summary reports one independent source'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    #>> '{sets,0,state}',
  'insufficient',
  'the reviewed-set summary remains below the source threshold'
);
select is(
  current_setting('pokecrack.public_pipeline_snapshot')::jsonb
    #> '{sets,0,hitRate}',
  'null'::jsonb,
  'the reviewed-set rate remains withheld'
);
select is(
  (
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb
      #>> '{summary,trackedSets}'
  )::integer,
  1,
  'the dashboard summary counts the one public reviewed set'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sources'
  ),
  4,
  'v3 publishes TCGdex plus three exact operational sources'
);
select set_eq(
  $$select source ->> 'id'
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sources'
    ) as sources(source)$$,
  $$values
    ('tcgdex_catalog'::text),
    ('youtube_discovery'),
    ('comicbook_perfect_order_study'),
    ('wargamer_chaos_rising_study')$$,
  'the public source IDs are an exact allowlist'
);
select ok(
  (
    select bool_and(source ->> 'status' = 'operational')
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sources'
    ) as sources(source)
    where source ->> 'id' <> 'tcgdex_catalog'
  ),
  'every exact pipeline source policy contract is operational before drift'
);
select set_eq(
  $$select distinct keys.key
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sources'
    ) as sources(source)
    cross join lateral jsonb_object_keys(sources.source) as keys(key)$$,
  $$values
    ('id'::text), ('name'), ('kind'), ('access'), ('status'),
    ('lastCollectedAt'), ('url'), ('note')$$,
  'every source exposes only the public source DTO keys'
);
select matches(
  (
    select source ->> 'note'
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'sources'
    ) as sources(source)
    where source ->> 'id' = 'youtube_discovery'
  ),
  '^1 current metadata record\.',
  'YouTube exposes only a bounded current-cache count'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'services'
  ),
  3,
  'v3 publishes three ready live worker roles'
);
select ok(
  (
    select bool_and(service ->> 'status' = 'operational')
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'services'
    ) as services(service)
  ),
  'recent role-level heartbeats make all three services operational'
);
select set_eq(
  $$select service ->> 'id'
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'services'
    ) as services(service)$$,
  $$values ('collector'::text), ('scheduler'), ('watchdog')$$,
  'the public service IDs are an exact allowlist'
);
select set_eq(
  $$select distinct keys.key
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_snapshot')::jsonb -> 'services'
    ) as services(service)
    cross join lateral jsonb_object_keys(services.service) as keys(key)$$,
  $$values ('id'::text), ('name'), ('status'), ('detail'), ('checkedAt')$$,
  'every service exposes only the public service DTO keys'
);
select ok(
  current_setting('pokecrack.public_pipeline_snapshot')
    !~ '(AbCdEfGhI12|DO-NOT-LEAK-V3-TITLE|PRIVATE TEST TITLE|PRIVATE TEST EXCERPT|pgtap-v3-)',
  'the anonymous snapshot contains no discovery, evidence, or worker identity'
);
select ok(
  not has_table_privilege('anon', 'ingest.youtube_discoveries', 'select')
    and not has_table_privilege(
      'anon', 'ingest.public_study_observations', 'select'
    )
    and not has_table_privilege('anon', 'ingest.worker_heartbeats', 'select')
    and not has_table_privilege('anon', 'catalog.sets', 'select'),
  'anon still cannot read any private relation behind v3'
);

update ingest.source_policies
set config = config || '{"metadata_only":false}'::jsonb
where source_key = 'youtube_discovery'
  and not is_demo;

set local role anon;
select set_config(
  'pokecrack.public_pipeline_drifted_snapshot',
  public.get_public_dashboard_snapshot_v3()::text,
  true
);
reset role;

select ok(
  coalesce((
    select source ->> 'status' = 'attention'
      and source -> 'lastCollectedAt' = 'null'::jsonb
      and source ->> 'note' ~ '^0 current metadata records\.'
    from jsonb_array_elements(
      current_setting('pokecrack.public_pipeline_drifted_snapshot')::jsonb
        -> 'sources'
    ) as sources(source)
    where source ->> 'id' = 'youtube_discovery'
  ), false),
  'a source config drift hides stale cache freshness and fails status closed'
);

select * from finish();
rollback;
