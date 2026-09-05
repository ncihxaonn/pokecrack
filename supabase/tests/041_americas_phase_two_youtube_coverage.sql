-- Americas phase two adds five exact coverage-only observations totalling 98 packs.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_cofre_lab_chilling_reign_cr_4',
      'public_study_pokeyabros_perfect_order_co_2',
      'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
      'public_study_thekeiplay_lost_origin_pe_36',
      'public_study_gringo_gameplays_silver_tempest_uy_36'
    )
      and enabled
      and not is_demo
      and collector_type = 'scrapling_http'
      and access_mode = 'public'
      and robots_policy = 'respect'
      and routes = array['scrapling_http']::text[]
      and not include_subdomains
      and min_delay_seconds = 30
      and max_pages_per_run = 2
      and max_items_per_run = 1
      and max_concurrency = 1
      and statistics_eligible_default
      and retention_days = 730
      and expected_interval_seconds = 86400
  ),
  5,
  'all five Americas phase-two policies retain the bounded collector contract'
);

select is(
  (
    select jsonb_object_agg(
      source_key,
      jsonb_build_object(
        'url', base_url,
        'study', config ->> 'study_key',
        'channel', config ->> 'publisher_channel_id',
        'country', config ->> 'country_code',
        'language', config ->> 'set_language',
        'set', config ->> 'set_external_id',
        'product', config ->> 'product_scope',
        'packs', (config ->> 'pack_count')::integer,
        'observedAt', config ->> 'observed_at'
      )
    )
    from ingest.source_policies
    where source_key in (
      'public_study_cofre_lab_chilling_reign_cr_4',
      'public_study_pokeyabros_perfect_order_co_2',
      'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
      'public_study_thekeiplay_lost_origin_pe_36',
      'public_study_gringo_gameplays_silver_tempest_uy_36'
    )
  ),
  '{
    "public_study_cofre_lab_chilling_reign_cr_4":{
      "url":"https://www.youtube.com/watch?v=15eGmqByP0I",
      "study":"cofre-lab-chilling-reign-cr-4-v1",
      "channel":"UCqYl3y-wsJqvwow5_tIa22A",
      "country":"CR","language":"und","set":"swsh6",
      "product":"build_and_battle","packs":4,
      "observedAt":"2021-06-06T05:54:03Z"
    },
    "public_study_pokeyabros_perfect_order_co_2":{
      "url":"https://www.youtube.com/watch?v=n_PdWg27x-o",
      "study":"pokeyabros-perfect-order-co-2-v1",
      "channel":"UC6iMHQS7wp-WVH_pD4leBZw",
      "country":"CO","language":"und","set":"me03",
      "product":"all","packs":2,
      "observedAt":"2026-09-04T14:00:23Z"
    },
    "public_study_andree_insane_cards_cosmic_eclipse_ec_20":{
      "url":"https://www.youtube.com/watch?v=wDDCbJKFTCw",
      "study":"andree-insane-cards-cosmic-eclipse-ec-20-v1",
      "channel":"UCvg1acSdKlzcCXAQQKcMvqg",
      "country":"EC","language":"und","set":"sm12",
      "product":"all","packs":20,
      "observedAt":"2023-06-27T21:00:07Z"
    },
    "public_study_thekeiplay_lost_origin_pe_36":{
      "url":"https://www.youtube.com/watch?v=YKHGiYIhsQU",
      "study":"thekeiplay-lost-origin-pe-36-v1",
      "channel":"UChAro6QS0gP88qhgOTBnuSA",
      "country":"PE","language":"und","set":"swsh11",
      "product":"booster_box","packs":36,
      "observedAt":"2022-09-05T18:00:12Z"
    },
    "public_study_gringo_gameplays_silver_tempest_uy_36":{
      "url":"https://www.youtube.com/watch?v=lYzM0jtPLKw",
      "study":"gringo-gameplays-silver-tempest-uy-36-v1",
      "channel":"UCqxdkBJE9jPp0JEv6eA7riQ",
      "country":"UY","language":"und","set":"swsh12",
      "product":"booster_box","packs":36,
      "observedAt":"2023-03-30T17:14:02Z"
    }
  }'::jsonb,
  'all five source identities, versions, and denominators are exact'
);

select ok(
  not exists (
    select 1
    from ingest.source_policies
    where source_key in (
      'public_study_cofre_lab_chilling_reign_cr_4',
      'public_study_pokeyabros_perfect_order_co_2',
      'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
      'public_study_thekeiplay_lost_origin_pe_36',
      'public_study_gringo_gameplays_silver_tempest_uy_36'
    )
      and config ?| array[
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      ]
  ),
  'no phase-two policy invents a numerator or rate'
);

select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_cofre_lab_chilling_reign_cr_4',
      'public_study_pokeyabros_perfect_order_co_2',
      'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
      'public_study_thekeiplay_lost_origin_pe_36',
      'public_study_gringo_gameplays_silver_tempest_uy_36'
    )
  ),
  5,
  'all five exact sources have durable request gates'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all twenty-four reviewed request gates are present'
);

select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal between 20 and 24
  ),
  array[
    'cofre-lab-chilling-reign-cr-4-v1',
    'pokeyabros-perfect-order-co-2-v1',
    'andree-insane-cards-cosmic-eclipse-ec-20-v1',
    'thekeiplay-lost-origin-pe-36-v1',
    'gringo-gameplays-silver-tempest-uy-36-v1'
  ]::text[],
  'five Americas contracts occupy append-only ordinals 20 through 24'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal between 20 and 24
      and (
        policies.id is null
        or policies.config is distinct from contracts.config
        or policies.version is distinct from contracts.policy_version
        or policies.base_url is distinct from contracts.canonical_url
      )
  ),
  'phase-two contracts cannot drift from source policies'
);
select is(
  (
    select jsonb_object_agg(
      study_key,
      encode(extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'), 'hex')
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal between 20 and 24
  ),
  '{
    "cofre-lab-chilling-reign-cr-4-v1":"8b307620e562e591d30922b077bb65960a50fd0be272e6c844c4233e536fc167",
    "pokeyabros-perfect-order-co-2-v1":"0414e5fcd9d3708873ed5c84e78f9c523fb66ba7a30211d8f798c12c5533b7f8",
    "andree-insane-cards-cosmic-eclipse-ec-20-v1":"9ebb6592d57fc2b452bbbd00b71e4e69633eec0a389069b1e475f4489a8fb0e9",
    "thekeiplay-lost-origin-pe-36-v1":"4c7a43da824a182cf0a550e46e21c34f1caadca259ff99d6485819ae95dd04ee",
    "gringo-gameplays-silver-tempest-uy-36-v1":"5f65c8f1ceca00fe06f56dbf684c50f1ca4116ce084aa9fbd4ead930b19d7264"
  }'::jsonb,
  'all five minimal evidence excerpts retain their reviewed SHA-256'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal between 20 and 24
      and (
        config ?| array[
          'qualifying_hit_pack_count',
          'qualifying_metric',
          'metric_version',
          'observed_rate',
          'rate'
        ]
        or evidence_excerpt ~* '<[[:space:]]*(img|video|audio|iframe)'
        or char_length(evidence_excerpt) > 300
      )
  ),
  'contracts contain neither statistical fields nor copied media or transcripts'
);

select is(
  (
    select count(*)::integer
    from unnest(array[
      pg_get_functiondef(
        'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure
      ),
      pg_get_functiondef(
        'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
      ),
      pg_get_functiondef(
        'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure
      ),
      pg_get_functiondef(
        'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
      )
    ]) as definitions(definition)
    where definition ~ 'contracts\.ordinal in \([^)]*20[^)]*21[^)]*22[^)]*23[^)]*24'
  ),
  4,
  'all four coverage boundaries admit ordinals 20 through 24'
);

select is(
  (
    select jsonb_build_object(
      'rows', count(*),
      'packs', sum(pack_count),
      'countries', count(distinct country_code),
      'publishers', count(distinct policies.config ->> 'publisher_channel_id')
    )
    from ingest.public_study_coverage_observations as coverage
    join ingest.source_policies as policies
      on policies.id = coverage.source_policy_id
    where coverage.study_key in (
      'cofre-lab-chilling-reign-cr-4-v1',
      'pokeyabros-perfect-order-co-2-v1',
      'andree-insane-cards-cosmic-eclipse-ec-20-v1',
      'thekeiplay-lost-origin-pe-36-v1',
      'gringo-gameplays-silver-tempest-uy-36-v1'
    )
  ),
  '{"rows":5,"packs":98,"countries":5,"publishers":5}'::jsonb,
  'the observations total 98 packs in five countries from five publishers'
);

select is(
  (
    select jsonb_object_agg(
      country.item ->> 'countryCode',
      jsonb_build_object(
        'packs', country.item ->> 'packsObserved',
        'sources', country.item ->> 'independentSources',
        'class', country.item ->> 'collectionClass',
        'versions', country.item -> 'dataVersions'
      )
    )
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('CR', 'CO', 'EC', 'PE', 'UY')
  ),
  '{
    "CR":{"packs":"4","sources":"1","class":"coverage_only","versions":["und · swsh6 · Chilling Reign · build and battle"]},
    "CO":{"packs":"2","sources":"1","class":"coverage_only","versions":["und · me03 · Perfect Order · all products"]},
    "EC":{"packs":"20","sources":"1","class":"coverage_only","versions":["und · sm12 · Cosmic Eclipse · all products"]},
    "PE":{"packs":"36","sources":"1","class":"coverage_only","versions":["und · swsh11 · Lost Origin · booster box"]},
    "UY":{"packs":"36","sources":"1","class":"coverage_only","versions":["und · swsh12 · Silver Tempest · booster box"]}
  }'::jsonb,
  'public v3 publishes all five countries with explicit data versions'
);

select is(
  public.get_public_study_coverage_v3() -> 'period' ->> 'start',
  '2021-06-06',
  'public coverage starts at the earliest honestly dated reviewed source'
);
select is(
  public.get_public_study_coverage_v3() -> 'period' ->> 'end',
  to_char(
    (statement_timestamp() at time zone 'UTC')::date,
    'YYYY-MM-DD'
  ),
  'public coverage ends on the current UTC date'
);
select ok(
  position(
    'from ingest.reviewed_public_study_contracts() as contracts' in
    pg_get_functiondef('public.get_public_study_coverage_v2()'::regprocedure)
  ) > 0
  and position(
    'from ingest.reviewed_public_study_contracts() as contracts' in
    pg_get_functiondef('public.get_public_study_coverage_v3()'::regprocedure)
  ) > 0
  and position(
    '(statement_timestamp() at time zone ''UTC'')::date - 364 as period_start' in
    pg_get_functiondef('public.get_public_study_coverage_v2()'::regprocedure)
  ) = 0
  and position(
    '(statement_timestamp() at time zone ''UTC'')::date - 364 as period_start' in
    pg_get_functiondef('public.get_public_study_coverage_v3()'::regprocedure)
  ) = 0,
  'public v2 and v3 derive their display range from reviewed evidence'
);
select ok(
  (
    select roles.rolname = 'postgres'
      and functions.prosecdef
      and functions.proconfig @> array['search_path=pg_catalog']::text[]
    from pg_proc as functions
    join pg_roles as roles on roles.oid = functions.proowner
    where functions.oid = 'public.get_public_study_coverage_v2()'::regprocedure
  )
  and (
    select roles.rolname = 'postgres'
      and functions.prosecdef
      and functions.proconfig @> array['search_path=pg_catalog']::text[]
    from pg_proc as functions
    join pg_roles as roles on roles.oid = functions.proowner
    where functions.oid = 'public.get_public_study_coverage_v3()'::regprocedure
  )
  and has_function_privilege(
    'anon',
    'public.get_public_study_coverage_v2()'::regprocedure,
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.get_public_study_coverage_v3()'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.get_public_study_coverage_v2()'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.get_public_study_coverage_v3()'::regprocedure,
    'execute'
  ),
  'historical coverage keeps the exact owner, definer, search-path, and role boundary'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('CR', 'CO', 'EC', 'PE', 'UY')
      and (
        country.item ? 'ratePacksObserved'
        or country.item ? 'qualifyingHitPacks'
        or country.item ? 'observedRate'
        or country.item ? 'baselineRate'
        or country.item ? 'posteriorMean'
        or country.item ? 'credibleInterval'
        or country.item ? 'deltaFromBaseline'
        or country.item ? 'signal'
      )
  ),
  'five-country coverage exposes no numerator, rate, or inference'
);

select is(
  (
    select jsonb_object_agg(
      source.item ->> 'id',
      jsonb_build_object(
        'packs', source.item -> 'coverage' ->> 'packsObserved',
        'url', source.item ->> 'url'
      )
    )
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'sources'
    ) as source(item)
    where source.item ->> 'id' in (
      'cofre_lab_chilling_reign_study',
      'pokeyabros_perfect_order_study',
      'andree_insane_cards_cosmic_eclipse_study',
      'thekeiplay_lost_origin_study',
      'gringo_gameplays_silver_tempest_study'
    )
  ),
  '{
    "cofre_lab_chilling_reign_study":{"packs":"4","url":"https://www.youtube.com/watch?v=15eGmqByP0I"},
    "pokeyabros_perfect_order_study":{"packs":"2","url":"https://www.youtube.com/watch?v=n_PdWg27x-o"},
    "andree_insane_cards_cosmic_eclipse_study":{"packs":"20","url":"https://www.youtube.com/watch?v=wDDCbJKFTCw"},
    "thekeiplay_lost_origin_study":{"packs":"36","url":"https://www.youtube.com/watch?v=YKHGiYIhsQU"},
    "gringo_gameplays_silver_tempest_study":{"packs":"36","url":"https://www.youtube.com/watch?v=lYzM0jtPLKw"}
  }'::jsonb,
  'public v3 exposes every exact source URL and denominator'
);

select ok(
  (
    select bool_and(position(study_key in pg_get_constraintdef(c.oid)) > 0)
    from unnest(array[
      'cofre-lab-chilling-reign-cr-4-v1',
      'pokeyabros-perfect-order-co-2-v1',
      'andree-insane-cards-cosmic-eclipse-ec-20-v1',
      'thekeiplay-lost-origin-pe-36-v1',
      'gringo-gameplays-silver-tempest-uy-36-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as c
  ),
  'scheduled-job CHECK allowlists all five exact study keys'
);

select * from finish();
rollback;
