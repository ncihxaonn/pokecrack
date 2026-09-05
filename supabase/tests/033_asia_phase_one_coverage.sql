-- Korea, Taiwan, and Thailand are reviewed denominator-only coverage studies.
-- They may publish exact source-native data versions, but never rates.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_limitsend_kr_30',
      'public_study_buyfunlife_tw_40',
      'public_study_allonline_th_10'
    )
      and enabled
      and not is_demo
      and collector_type = 'scrapling_http'
      and access_mode = 'public'
      and robots_policy = 'respect'
      and routes = array['scrapling_http']::text[]
      and min_delay_seconds = 30
      and max_pages_per_run = 2
      and max_items_per_run = 1
      and max_concurrency = 1
      and retention_days = 730
      and expected_interval_seconds = 86400
  ),
  3,
  'all three Asian source policies retain the bounded live collector contract'
);
select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_limitsend_kr_30',
      'public_study_buyfunlife_tw_40',
      'public_study_allonline_th_10'
    )
  ),
  3,
  'all three Asian sources have durable request gates'
);
select has_function(
  'ingest',
  'reviewed_public_study_gates_ready_v1',
  array[]::text[],
  'the boolean-only reviewed request-gate readiness function exists'
);
select ok(
  has_function_privilege(
    'service_role',
    'ingest.reviewed_public_study_gates_ready_v1()',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'ingest.reviewed_public_study_gates_ready_v1()',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'ingest.reviewed_public_study_gates_ready_v1()',
    'execute'
  ),
  'only service_role can execute the boolean request-gate readiness check'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all current reviewed source gates are present'
);
delete from ingest.source_request_gates
where source_key = 'public_study_buyfunlife_tw_40';
select ok(
  not ingest.reviewed_public_study_gates_ready_v1(),
  'one missing source gate makes public-study readiness fail closed'
);
insert into ingest.source_request_gates (source_key)
values ('public_study_buyfunlife_tw_40');

select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 9
  ),
  9,
  'the reviewed registry retains the original nine-contract prefix'
);
select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal between 7 and 9
  ),
  array[
    'limitsend-inferno-x-kr-30-v1',
    'buyfunlife-ninja-spinner-tw-40-v1',
    'allonline-mega-dream-ex-th-10-v1'
  ]::text[],
  'the three Asian studies occupy exact append-only ordinals 7 through 9'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal between 7 and 9
      and (
        policies.id is null
        or policies.config is distinct from contracts.config
        or policies.version is distinct from contracts.policy_version
        or policies.base_url is distinct from contracts.canonical_url
      )
  ),
  'the Asian registry identities cannot drift from their database source policies'
);
select is(
  (
    select jsonb_object_agg(
      study_key,
      jsonb_build_object(
        'country', config ->> 'country_code',
        'language', config ->> 'set_language',
        'set', config ->> 'set_external_id',
        'name', config ->> 'set_name',
        'scope', config ->> 'product_scope',
        'packs', (config ->> 'pack_count')::integer,
        'basis', config ->> 'geography_basis'
      )
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal between 7 and 9
  ),
  ('{
    "limitsend-inferno-x-kr-30-v1":{
      "country":"KR","language":"ko","set":"M2","name":"인페르노X",
      "scope":"booster_box","packs":30,"basis":"product_market"
    },
    "buyfunlife-ninja-spinner-tw-40-v1":{
      "country":"TW","language":"zh-TW","set":"M4","name":"忍者飛旋",
      "scope":"value_bundle","packs":40,"basis":"product_market"
    },
    "allonline-mega-dream-ex-th-10-v1":{
      "country":"TH","language":"th","set":"MA3","name":"วิวัฒนาการเมก้า ดรีมex",
      "scope":"booster_box","packs":10,"basis":"product_market"
    }
  }'::jsonb),
  'country, language, set, source-native name, product scope, and denominator are exact'
);
select is(
  (
    select jsonb_object_agg(
      study_key,
      encode(
        extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'),
        'hex'
      )
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal between 7 and 9
  ),
  ('{
    "limitsend-inferno-x-kr-30-v1":"4af8a17aec4489a0f3fdd6a3e4c8fb8f7a77a60092825fba3279323b6c654406",
    "buyfunlife-ninja-spinner-tw-40-v1":"2fd4475765c44e61e9603f0603ddf8b8ba7a1d9ff234726c5d6dd631d8937a3d",
    "allonline-mega-dream-ex-th-10-v1":"5c4dfcf632018a5f56489b5e158885086c118c13edf5b129dfc530bd25d93478"
  }'::jsonb),
  'each bounded evidence excerpt retains its exact reviewed SHA-256'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal between 7 and 9
      and (
        config ?| array[
          'qualifying_hit_pack_count',
          'qualifying_metric',
          'metric_version',
          'observed_rate',
          'rate'
        ]
        or evidence_excerpt ~* '<[[:space:]]*(img|video|audio|iframe)'
        or char_length(evidence_excerpt) > 800
      )
  ),
  'the Asian contracts contain neither statistical fields nor copied media/body content'
);
select matches(
  (
    select pg_get_constraintdef(oid)
    from pg_constraint
    where conrelid = 'ingest.public_study_coverage_observations'::regclass
      and conname = 'public_study_coverage_product_check'
  ),
  '''value_bundle''',
  'the denominator-only ledger permits the exact Taiwan value-bundle scope'
);

select is(
  (
    select count(*)::integer
    from unnest(array[
      pg_get_functiondef('ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure),
      pg_get_functiondef('ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure)
    ]) as definitions(definition)
    where position('contracts.ordinal in (3, 4, 5, 6, 7, 8, 9' in definition) > 0
  ),
  4,
  'all four coverage ingestion boundaries retain the seven-contract Asia prefix'
);
select ok(
  (
    select bool_and(
      position(study_key in pg_get_constraintdef(constraints.oid)) > 0
    )
    from unnest(array[
      'limitsend-inferno-x-kr-30-v1',
      'buyfunlife-ninja-spinner-tw-40-v1',
      'allonline-mega-dream-ex-th-10-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as constraints
  ),
  'the scheduled-job CHECK allowlists all three exact Asian study keys'
);
select ok(
  not exists (
    select 1
    from unnest(array[
      pg_get_functiondef('ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure),
      pg_get_functiondef('ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure)
    ]) as definitions(definition)
    cross join unnest(array[
      'limitsend-inferno-x-kr-30-v1',
      'buyfunlife-ninja-spinner-tw-40-v1',
      'allonline-mega-dream-ex-th-10-v1',
      'public_study_limitsend_kr_30',
      'public_study_buyfunlife_tw_40',
      'public_study_allonline_th_10'
    ]) as identities(value)
    where position(identities.value in definitions.definition) > 0
  ),
  'the statistical begin/finalize path never admits an Asian coverage identity'
);

select lives_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'limitsend-inferno-x-kr-30-v1', 14, 'pgtap-asia-kr-direct',
    transaction_timestamp() + interval '1 day', 3
  )$$,
  'the direct coverage queue accepts the exact Korean study'
);
select lives_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'buyfunlife-ninja-spinner-tw-40-v1', 14, 'pgtap-asia-tw-direct',
    transaction_timestamp() + interval '1 day', 3
  )$$,
  'the direct coverage queue accepts the exact Taiwanese study'
);
select lives_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'allonline-mega-dream-ex-th-10-v1', 14, 'pgtap-asia-th-direct',
    transaction_timestamp() + interval '1 day', 3
  )$$,
  'the direct coverage queue accepts the exact Thai study'
);

do $asia_runtime$
declare
  study record;
  reviewed record;
  queued_job_id uuid;
  claimed_job_id uuid;
  generation_value bigint;
  acquired_value boolean;
begin
  for study in
    select *
    from (values
      (
        'limitsend-inferno-x-kr-30-v1'::text,
        '포켓몬카드 낱개팩 구매를 조심해야 하는 이유｜인페르노X 직접 개봉해보니'::text
      ),
      (
        'buyfunlife-ninja-spinner-tw-40-v1'::text,
        '噴4000元大虧！寶可夢忍者飛旋加值組合開箱｜MUR機率多低？卡價分析（新手懶人包）'::text
      ),
      (
        'allonline-mega-dream-ex-th-10-v1'::text,
        'รีวิว การ์ดโปเกมอน วิวัฒนาการดรีมex ตามล่าหาความแรร์ เติมเด็คให้แข็งแกร่ง'::text
      )
    ) as values_list(study_key, title)
  loop
    select contracts.*
    into reviewed
    from ingest.reviewed_public_study_contracts() as contracts
    where contracts.study_key = study.study_key;

    select jobs.id
    into queued_job_id
    from ingest.enqueue_scheduled_public_study_coverage_job_v1(
      'public_study_' || study.study_key,
      date_trunc('minute', transaction_timestamp()),
      study.study_key,
      999,
      3
    ) as jobs;

    select jobs.id, jobs.lease_generation
    into claimed_job_id, generation_value
    from ingest.claim_jobs_v2(
      'pgtap-asia-worker',
      array['source.public_study.opening'],
      1,
      600
    ) as jobs;
    if claimed_job_id is distinct from queued_job_id then
      raise exception 'Asian coverage job % was not claimed exactly', study.study_key;
    end if;

    select begun.acquired
    into acquired_value
    from ingest.begin_public_study_job_v2(
      queued_job_id,
      'pgtap-asia-worker',
      generation_value,
      study.study_key
    ) as begun;
    if acquired_value is distinct from true then
      raise exception 'Asian coverage request gate % was not acquired', study.study_key;
    end if;

    perform ingest.finalize_public_study_coverage_job_v1(
      queued_job_id,
      'pgtap-asia-worker',
      generation_value,
      study.study_key,
      jsonb_build_object(
        'version', 1,
        'study_key', study.study_key,
        'source_url', reviewed.canonical_url,
        'title', study.title,
        'evidence_excerpt', reviewed.evidence_excerpt,
        'evidence_sha256', encode(
          extensions.digest(
            convert_to(reviewed.evidence_excerpt, 'UTF8'),
            'sha256'
          ),
          'hex'
        ),
        'collector_version', reviewed.config ->> 'collector_version',
        'parser_version', reviewed.config ->> 'parser_version',
        'source_policy_version', reviewed.policy_version
      )
    );
  end loop;
end;
$asia_runtime$;

select is(
  (
    select jsonb_build_object(
      'openings', count(*),
      'packs', sum(pack_count),
      'countries', count(distinct country_code)
    )
    from ingest.public_study_coverage_observations
    where study_key in (
      'limitsend-inferno-x-kr-30-v1',
      'buyfunlife-ninja-spinner-tw-40-v1',
      'allonline-mega-dream-ex-th-10-v1'
    )
  ),
  '{"openings":3,"packs":80,"countries":3}'::jsonb,
  'the finalized Asian observations add exactly 80 packs across three openings and countries'
);
select is(
  (
    select jsonb_object_agg(
      country.item ->> 'countryCode',
      country.item -> 'dataVersions' ->> 0
    )
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('KR', 'TW', 'TH')
  ),
  ('{
    "KR":"ko · M2 · 인페르노X · booster box",
    "TW":"zh-TW · M4 · 忍者飛旋 · value bundle",
    "TH":"th · MA3 · วิวัฒนาการเมก้า ดรีมex · booster box"
  }'::jsonb),
  'v2 exposes an exact source-native data version for every new Asian country'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('KR', 'TW', 'TH')
      and country.item ?| array[
        'ratePacksObserved', 'qualifyingHitPacks', 'observedRate',
        'qualifyingMetric', 'metricVersion', 'numerator'
      ]
  )
  and not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'sources'
    ) as source(item)
    where source.item ->> 'id' in (
      'limitsend_inferno_x_study',
      'buyfunlife_ninja_spinner_study',
      'allonline_mega_dream_ex_study'
    )
      and (
        source.item ?| array[
          'ratePacksObserved', 'qualifyingHitPacks', 'observedRate',
          'qualifyingMetric', 'metricVersion', 'numerator'
        ]
        or (source.item -> 'coverage') ?| array[
          'ratePacksObserved', 'qualifyingHitPacks', 'observedRate',
          'qualifyingMetric', 'metricVersion', 'numerator'
        ]
      )
  ),
  'the three Asian v2 projections expose no numerator, rate, or metric field'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'sets'
    ) as set_row(item)
    where set_row.item ->> 'name' in ('인페르노X', '忍者飛旋', 'วิวัฒนาการเมก้า ดรีมex')
  ),
  'v2 does not fabricate English catalog-set rows for source-native Asian contracts'
);

update ingest.source_policies
set config = config || '{"terms_checked_at":"2026-09-03"}'::jsonb
where source_key = 'public_study_buyfunlife_tw_40';
select throws_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'buyfunlife-ninja-spinner-tw-40-v1', 0, 'pgtap-asia-drift',
    transaction_timestamp(), 3
  )$$,
  '55000',
  'reviewed coverage policy or request gate is unavailable',
  'source-policy drift rejects a new Asian coverage job'
);

select * from finish();
rollback;
