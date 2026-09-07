-- Argentina and Chile add two exact 36-pack coverage-only observations.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_cartas_pokemon_argentina_pitch_black_36',
      'public_study_pokemaniaco_lucas_cl_36'
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
  2,
  'both South America policies retain the bounded collector contract'
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
      'public_study_cartas_pokemon_argentina_pitch_black_36',
      'public_study_pokemaniaco_lucas_cl_36'
    )
  ),
  '{
    "public_study_cartas_pokemon_argentina_pitch_black_36":{
      "url":"https://www.youtube.com/watch?v=HcsWjycR1L0",
      "study":"cartas-pokemon-argentina-pitch-black-ar-36-v1",
      "channel":"UCGBtAPv7mLLRgdqeupj2kLg",
      "country":"AR","language":"und","set":"me05",
      "product":"booster_box","packs":36,
      "observedAt":"2026-07-17T18:18:50Z"
    },
    "public_study_pokemaniaco_lucas_cl_36":{
      "url":"https://www.youtube.com/watch?v=Meg4AO9CqHE",
      "study":"pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
      "channel":"UCDKXzvS5YaUJwsHD1wNkWBw",
      "country":"CL","language":"und","set":"me02",
      "product":"booster_box","packs":36,
      "observedAt":"2025-11-13T16:00:06Z"
    }
  }'::jsonb,
  'South America source identities and denominators are exact'
);

select ok(
  not exists (
    select 1
    from ingest.source_policies
    where source_key in (
      'public_study_cartas_pokemon_argentina_pitch_black_36',
      'public_study_pokemaniaco_lucas_cl_36'
    )
      and config ?| array[
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      ]
  ),
  'neither South America policy invents a numerator or rate'
);

select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_cartas_pokemon_argentina_pitch_black_36',
      'public_study_pokemaniaco_lucas_cl_36'
    )
  ),
  2,
  'both exact sources have durable request gates'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all nineteen reviewed request gates are present'
);

select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal in (18, 19)
  ),
  array[
    'cartas-pokemon-argentina-pitch-black-ar-36-v1',
    'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'
  ]::text[],
  'Argentina and Chile occupy append-only ordinals 18 and 19'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal in (18, 19)
      and (
        policies.id is null
        or policies.config is distinct from contracts.config
        or policies.version is distinct from contracts.policy_version
        or policies.base_url is distinct from contracts.canonical_url
      )
  ),
  'South America contracts cannot drift from source policies'
);
select is(
  (
    select jsonb_object_agg(
      study_key,
      encode(extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'), 'hex')
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal in (18, 19)
  ),
  '{
    "cartas-pokemon-argentina-pitch-black-ar-36-v1":"9332e272a335d9e81a6e42c702b5d49630357eaf4a7a8c10d9d5f9d40cc05690",
    "pokemaniaco-lucas-phantasmal-flames-cl-36-v1":"dd5424daf2b83dde579788be5676d1a59403c49ebf516e4601d82ddaf3f6f74f"
  }'::jsonb,
  'both minimal evidence excerpts retain their exact SHA-256'
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
    where definition ~ 'contracts\.ordinal in \([^)]*18[^)]*19'
  ),
  4,
  'all four coverage boundaries admit ordinals 18 and 19'
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
      'cartas-pokemon-argentina-pitch-black-ar-36-v1',
      'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'
    )
  ),
  '{"rows":2,"packs":72,"countries":2,"publishers":2}'::jsonb,
  'the observations total 72 packs in two countries from two publishers'
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
    where country.item ->> 'countryCode' in ('AR', 'CL')
  ),
  '{
    "AR":{
      "packs":"36","sources":"1","class":"coverage_only",
      "versions":["und · me05 · Pitch Black · booster box"]
    },
    "CL":{
      "packs":"36","sources":"1","class":"coverage_only",
      "versions":["und · me02 · Phantasmal Flames · booster box"]
    }
  }'::jsonb,
  'public v3 publishes Argentina and Chile with explicit data versions'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('AR', 'CL')
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
  'Argentina and Chile coverage expose no numerator, rate, or inference'
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
      'cartas_pokemon_argentina_pitch_black_study',
      'pokemaniaco_lucas_phantasmal_flames_study'
    )
  ),
  '{
    "cartas_pokemon_argentina_pitch_black_study":{
      "packs":"36","url":"https://www.youtube.com/watch?v=HcsWjycR1L0"
    },
    "pokemaniaco_lucas_phantasmal_flames_study":{
      "packs":"36","url":"https://www.youtube.com/watch?v=Meg4AO9CqHE"
    }
  }'::jsonb,
  'public v3 exposes both exact source URLs and denominators'
);

select ok(
  (
    select bool_and(position(study_key in pg_get_constraintdef(c.oid)) > 0)
    from unnest(array[
      'cartas-pokemon-argentina-pitch-black-ar-36-v1',
      'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as c
  ),
  'scheduled-job CHECK allowlists both exact study keys'
);

select * from finish();
rollback;
