-- PokeSup is a Japanese, denominator-only coverage contract. It may publish
-- a source-native data version, but never an English catalog identity or rate.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select config
    from ingest.source_policies
    where source_key = 'public_study_pokesup_jp_30'
      and not is_demo
  ),
  ('{
    "study_key":"pokesup-abyss-eye-jp-30-v1",
    "canonical_url":"https://pokesup.com/blog/unboxing-m5/",
    "collector_version":"public-study-pokesup-abyss-eye-v1",
    "parser_version":"pokesup-abyss-eye-evidence-v1",
    "country_code":"JP",
    "country_name":"Japan",
    "geography_basis":"product_market",
    "geography_confidence":"tier_b",
    "set_external_id":"M5",
    "set_language":"ja",
    "set_name":"アビスアイ",
    "set_official_url":"https://www.pokemon-card.com/ex/m5/",
    "product_scope":"booster_box",
    "pack_count":30,
    "observed_at":"2026-05-22T12:01:44Z",
    "denominator_complete":true,
    "robots_url":"https://pokesup.com/robots.txt",
    "robots_checked_at":"2026-09-04",
    "terms_checked_at":"2026-09-04",
    "terms_status":"no_independent_terms_page",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb),
  'the PokeSup source policy has the exact Japanese coverage config and review checkpoints'
);
select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key = 'public_study_pokesup_jp_30'
      and not is_demo
  ),
  1,
  'exactly one live PokeSup source policy exists'
);
select ok(
  exists (
    select 1
    from ingest.source_request_gates
    where source_key = 'public_study_pokesup_jp_30'
  ),
  'the PokeSup source has a durable request gate'
);

select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 9
  ),
  9,
  'the reviewed registry preserves its original nine-contract prefix'
);
select is(
  (
    select ordinal
    from ingest.reviewed_public_study_contracts()
    where study_key = 'pokesup-abyss-eye-jp-30-v1'
  ),
  6,
  'PokeSup keeps the exact appended ordinal 6'
);
select is(
  (
    select config
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  (
    select config
    from ingest.source_policies
    where source_key = 'public_study_pokesup_jp_30'
      and not is_demo
  ),
  'the ordinal-6 registry config cannot drift from the DB source policy'
);
select ok(
  (
    select not (config ?| array[
      'qualifying_hit_pack_count',
      'qualifying_metric',
      'metric_version'
    ])
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  'the PokeSup registry config has no statistical numerator or metric key'
);
select ok(
  (
    select (config ? 'set_language') and not (config ? 'language')
    from ingest.source_policies
    where source_key = 'public_study_pokesup_jp_30'
      and not is_demo
  )
  and (
    select (config ? 'set_language') and not (config ? 'language')
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  'the policy and registry use set_language and never a language config key'
);

select is(
  (
    select evidence_excerpt
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  E'ポケモンカード 拡張パック「アビスアイ」開封結果！レアリティ封入率検証（その1）\nアビスアイ開封（1箱目） 左1パック 左2パック 左3パック 左4パック 左5パック 左6パック 左7パック 左8パック 左9パック 左10パック 左11パック 左12パック 左13パック 左14パック 左15パック 右1パック 右2パック 右3パック 右4パック 右5パック 右6パック 右7パック 右8パック 右9パック 右10パック 右11パック 右12パック 右13パック 右14パック 右15パック',
  'the PokeSup evidence is exactly the two-line title and ordered box labels'
);
select is(
  (
    select encode(
      extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'),
      'hex'
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  'e9e87b7bbab8483200fef8ffd7d927f339138f742876ca222af1f133f7523b08',
  'the PokeSup evidence excerpt has the exact pinned SHA-256'
);
select is(
  (
    select array_length(string_to_array(evidence_excerpt, E'\n'), 1)
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ),
  2,
  'the PokeSup evidence contains exactly two canonical lines'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
      and evidence_excerpt ~* '<[[:space:]]*(img|video|audio|iframe)'
  )
  and (
    select char_length(evidence_excerpt)
    from ingest.reviewed_public_study_contracts()
    where ordinal = 6
  ) < 800,
  'the PokeSup evidence retains no media markup or copied article body'
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
    where position('contracts.ordinal in (3, 4, 5, 6' in definition) > 0
  ),
  4,
  'the four coverage ingestion boundaries continue to accept ordinal 6'
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
    where position('contracts.ordinal in (3, 4, 5)' in definition) > 0
  ),
  0,
  'no coverage ingestion boundary retains the ordinal-5-only predicate'
);
select ok(
  position('contracts.ordinal in (3, 4, 5)' in pg_get_functiondef(
    'public.get_public_study_coverage_v1()'::regprocedure
  )) > 0
  and position('contracts.ordinal in (3, 4, 5, 6)' in pg_get_functiondef(
    'public.get_public_study_coverage_v1()'::regprocedure
  )) = 0
  and position('pokesup-abyss-eye-jp-30-v1' in pg_get_functiondef(
    'public.get_public_study_coverage_v1()'::regprocedure
  )) = 0,
  'the legacy v1 projection remains fixed to ordinals 3-5 and never admits PokeSup'
);
select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal in (3, 4, 5)
  ),
  3,
  'the legacy v1 projection continues to represent exactly three reviewed sources'
);

select ok(
  position('sets.language = ''en''' in pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )) > 0
  and position('set_language' in pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )) > 0
  and position('set_name' in pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )) > 0
  and position('?& array[' in pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )) > 0
  and position('set_official_url' in pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )) > 0,
  'the finalizer keeps English catalog validation and safely gates explicit non-English metadata'
);
select ok(
  not exists (
    select 1
    from information_schema.columns
    where table_schema = 'ingest'
      and table_name = 'public_study_coverage_observations'
      and column_name in (
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      )
  ),
  'the coverage ledger has no numerator, rate, or metric columns'
);
select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'ingest.jobs'::regclass
      and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
      and pg_get_constraintdef(oid) like '%pokesup-abyss-eye-jp-30-v1%'
  ),
  'the reviewed coverage schedule CHECK allowlists PokeSup'
);
select is(
  (
    select count(*)::integer
    from unnest(array[
      pg_get_functiondef('ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure),
      pg_get_functiondef('ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure)
    ]) as definitions(definition)
    where position('comicbook-perfect-order-us-55-v1' in definition) > 0
      and position('wargamer-chaos-rising-gb-17-v1' in definition) > 0
      and position('cardchill-ascended-heroes-gb-90-v1' in definition) = 0
      and position('bleedingcool-phantasmal-flames-us-36-v1' in definition) = 0
      and position('tcgtalk-perfect-order-sg-54-v1' in definition) = 0
      and position('pokesup-abyss-eye-jp-30-v1' in definition) = 0
      and position('public_study_pokesup_jp_30' in definition) = 0
  ),
  2,
  'the statistical begin/finalize functions retain only the ordinal-1/2 allowlist and never admit ordinal 6'
);

select ok(
  position('config ->> ''set_language''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('config ->> ''set_name''' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0
  and position('catalog_sets.language = rows.set_language' in pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )) > 0,
  'v2 retains source-native language/name projection without fabricating an English catalog row'
);

select lives_ok(
  $sql$select * from ingest.enqueue_public_study_coverage_job_v1(
    'pokesup-abyss-eye-jp-30-v1',
    14,
    'pgtap-pokesup-direct',
    transaction_timestamp() + interval '1 day',
    3
  )$sql$,
  'the direct PokeSup coverage enqueue accepts the exact reviewed study'
);
select lives_ok(
  $sql$select * from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_pokesup-abyss-eye-jp-30-v1',
    date_trunc('minute', transaction_timestamp()),
    'pokesup-abyss-eye-jp-30-v1',
    14,
    3
  )$sql$,
  'the scheduled PokeSup coverage enqueue accepts the exact reviewed study'
);

do $pokesup_runtime$
declare
  scheduled_job_id uuid;
  claimed_job_id uuid;
  generation_value bigint;
  acquired_value boolean;
begin
  select slots.job_id
  into scheduled_job_id
  from ingest.schedule_slots as slots
  where slots.schedule_name = 'public_study_pokesup-abyss-eye-jp-30-v1'
    and slots.slot_at = date_trunc('minute', transaction_timestamp());

  select jobs.id, jobs.lease_generation
  into claimed_job_id, generation_value
  from ingest.claim_jobs_v2(
    'pgtap-pokesup-worker',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  if claimed_job_id is distinct from scheduled_job_id then
    raise exception 'the PokeSup scheduled coverage job was not claimed exactly once';
  end if;

  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job_v2(
    scheduled_job_id,
    'pgtap-pokesup-worker',
    generation_value,
    'pokesup-abyss-eye-jp-30-v1'
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'the PokeSup request gate was not acquired';
  end if;

  perform ingest.finalize_public_study_coverage_job_v1(
    scheduled_job_id,
    'pgtap-pokesup-worker',
    generation_value,
    'pokesup-abyss-eye-jp-30-v1',
    jsonb_build_object(
      'version', 1,
      'study_key', 'pokesup-abyss-eye-jp-30-v1',
      'source_url', 'https://pokesup.com/blog/unboxing-m5/',
      'title', 'ポケモンカード 拡張パック「アビスアイ」開封結果！レアリティ封入率検証（その1）',
      'evidence_excerpt', E'ポケモンカード 拡張パック「アビスアイ」開封結果！レアリティ封入率検証（その1）\nアビスアイ開封（1箱目） 左1パック 左2パック 左3パック 左4パック 左5パック 左6パック 左7パック 左8パック 左9パック 左10パック 左11パック 左12パック 左13パック 左14パック 左15パック 右1パック 右2パック 右3パック 右4パック 右5パック 右6パック 右7パック 右8パック 右9パック 右10パック 右11パック 右12パック 右13パック 右14パック 右15パック',
      'evidence_sha256', 'e9e87b7bbab8483200fef8ffd7d927f339138f742876ca222af1f133f7523b08',
      'collector_version', 'public-study-pokesup-abyss-eye-v1',
      'parser_version', 'pokesup-abyss-eye-evidence-v1',
      'source_policy_version', 'public-study-pokesup-abyss-eye-v1'
    )
  );
end;
$pokesup_runtime$;

select is(
  (
    select jsonb_build_object(
      'country_code', country_code,
      'country_name', country_name,
      'source_observed_at', source_observed_at,
      'pack_count', pack_count,
      'set_external_id', set_external_id,
      'product_scope', product_scope,
      'collector_version', collector_version,
      'parser_version', parser_version,
      'source_policy_version', source_policy_version,
      'evidence_sha256', evidence_sha256
    )
    from ingest.public_study_coverage_observations
    where study_key = 'pokesup-abyss-eye-jp-30-v1'
  ),
  ('{
    "country_code":"JP",
    "country_name":"Japan",
    "source_observed_at":"2026-05-22T12:01:44+00:00",
    "pack_count":30,
    "set_external_id":"M5",
    "product_scope":"booster_box",
    "collector_version":"public-study-pokesup-abyss-eye-v1",
    "parser_version":"pokesup-abyss-eye-evidence-v1",
    "source_policy_version":"public-study-pokesup-abyss-eye-v1",
    "evidence_sha256":"e9e87b7bbab8483200fef8ffd7d927f339138f742876ca222af1f133f7523b08"
  }'::jsonb),
  'the PokeSup finalizer persists only the reviewed denominator identity'
);
select is(
  (
    select country.item -> 'dataVersions' ->> 0
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'countries') as country(item)
    where country.item ->> 'countryCode' = 'JP'
  ),
  'ja · M5 · アビスアイ · booster box',
  'the v2 country projection exposes the exact Japanese source-native data version'
);
select is(
  (
    select source.item -> 'coverage'
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sources') as source(item)
    where source.item ->> 'id' = 'pokesup_abyss_eye_study'
  ),
  jsonb_build_object(
    'packsObserved', 30,
    'countriesObserved', 1,
    'completeOpenings', 1
  ),
  'the PokeSup public source tuple exposes only denominator coverage counts'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'sets') as set_row(item)
    where set_row.item ->> 'name' = 'アビスアイ'
      or set_row.item ->> 'slug' = 'M5'
  ),
  'v2 never fabricates an English catalog set for the Japanese contract'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v2() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'JP'
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
    where source.item ->> 'id' = 'pokesup_abyss_eye_study'
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
  'the PokeSup v2 projection exposes no numerator, rate, or metric field'
);

update ingest.source_policies
set config = config || '{"terms_checked_at":"2026-09-03"}'::jsonb
where source_key = 'public_study_pokesup_jp_30';
select throws_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'pokesup-abyss-eye-jp-30-v1', 0, 'pgtap-pokesup-drift',
    transaction_timestamp(), 3
  )$$,
  '55000',
  'reviewed coverage policy or request gate is unavailable',
  'policy config drift rejects a new PokeSup coverage job'
);

select finish();
rollback;
