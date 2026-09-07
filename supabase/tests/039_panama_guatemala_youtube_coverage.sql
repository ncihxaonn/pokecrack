-- Panama and Guatemala contribute three exact coverage-only observations.
-- The rows total 13 observed packs and expose no numerator, rate, or inference.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_tcg_market_panama_chaos_rising_6',
      'public_study_tcg_market_panama_pitch_black_4',
      'public_study_pokeshow_guatemala_megaevolution_3'
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
  3,
  'all Panama/Guatemala policies retain the bounded live collector contract'
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
        'languageBasis', config ->> 'set_language_basis',
        'set', config ->> 'set_external_id',
        'product', config ->> 'product_scope',
        'packs', (config ->> 'pack_count')::integer,
        'observedAt', config ->> 'observed_at'
      )
    )
    from ingest.source_policies
    where source_key in (
      'public_study_tcg_market_panama_chaos_rising_6',
      'public_study_tcg_market_panama_pitch_black_4',
      'public_study_pokeshow_guatemala_megaevolution_3'
    )
  ),
  '{
    "public_study_tcg_market_panama_chaos_rising_6":{
      "url":"https://www.youtube.com/watch?v=fHQpNECg4y4",
      "study":"tcg-market-chaos-rising-pa-6-v1",
      "channel":"UCa68xVUUIKE8dvcfxCcdyrQ",
      "country":"PA",
      "language":"und",
      "languageBasis":"source_does_not_state_card_language",
      "set":"me04",
      "product":"booster_bundle",
      "packs":6,
      "observedAt":"2026-08-03T00:15:39Z"
    },
    "public_study_tcg_market_panama_pitch_black_4":{
      "url":"https://www.youtube.com/watch?v=6kb1MvcnMJE",
      "study":"tcg-market-pitch-black-pa-4-v1",
      "channel":"UCa68xVUUIKE8dvcfxCcdyrQ",
      "country":"PA",
      "language":"und",
      "languageBasis":"source_does_not_state_card_language",
      "set":"me05",
      "product":"build_and_battle",
      "packs":4,
      "observedAt":"2026-08-05T19:09:10Z"
    },
    "public_study_pokeshow_guatemala_megaevolution_3":{
      "url":"https://www.youtube.com/watch?v=DWRdhUuIUvI",
      "study":"pokeshow-mega-evolution-gt-3-v1",
      "channel":"UChG8m-xoKqrXJDCEoE2i9Jg",
      "country":"GT",
      "language":"und",
      "languageBasis":"source_does_not_state_card_language",
      "set":"me01",
      "product":"three_pack_blister",
      "packs":3,
      "observedAt":"2025-10-06T17:21:33Z"
    }
  }'::jsonb,
  'country identities, versions, source URLs, languages, and denominators are exact'
);

select ok(
  not exists (
    select 1
    from ingest.source_policies
    where source_key in (
      'public_study_tcg_market_panama_chaos_rising_6',
      'public_study_tcg_market_panama_pitch_black_4',
      'public_study_pokeshow_guatemala_megaevolution_3'
    )
      and config ?| array[
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      ]
  ),
  'none of the three policies invents a normalized numerator or rate'
);

select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_tcg_market_panama_chaos_rising_6',
      'public_study_tcg_market_panama_pitch_black_4',
      'public_study_pokeshow_guatemala_megaevolution_3'
    )
  ),
  3,
  'all three exact sources have durable request gates'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all seventeen reviewed request gates are present'
);

select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 17
  ),
  17,
  'the reviewed registry has exactly the seventeen-contract prefix'
);
select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal in (15, 16, 17)
  ),
  array[
    'tcg-market-chaos-rising-pa-6-v1',
    'tcg-market-pitch-black-pa-4-v1',
    'pokeshow-mega-evolution-gt-3-v1'
  ]::text[],
  'Panama and Guatemala occupy exact append-only ordinals 15 through 17'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal in (15, 16, 17)
      and (
        policies.id is null
        or policies.config is distinct from contracts.config
        or policies.version is distinct from contracts.policy_version
        or policies.base_url is distinct from contracts.canonical_url
      )
  ),
  'registry identities cannot drift from database source policies'
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
    where ordinal in (15, 16, 17)
  ),
  '{
    "tcg-market-chaos-rising-pa-6-v1":"abb892071c34d353e811c9715174512bb47304ac72de2508d188e13956e3e4ef",
    "tcg-market-pitch-black-pa-4-v1":"055d48674555e3a9dc79ced8f5886c7960ad200c7c8bdc4383a5623b5e583857",
    "pokeshow-mega-evolution-gt-3-v1":"b6c535ad4e34f0df39c8b9823a8a6e624fbb9a66c2da8329996b484b04a9feeb"
  }'::jsonb,
  'all minimal evidence excerpts retain their exact reviewed SHA-256'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal in (15, 16, 17)
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
  'contracts contain neither statistical fields nor copied media/transcripts'
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
    where definition ~
      'contracts\.ordinal in \([^)]*15[^)]*16[^)]*17'
  ),
  4,
  'all four coverage boundaries admit the same fourteen-contract allowlist'
);
select ok(
  pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  ) like '%^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$%',
  'the finalizer accepts the explicit ISO undetermined-language code'
);
select ok(
  (
    select bool_and(position(value in pg_get_constraintdef(oid)) > 0)
    from pg_constraint
    cross join unnest(array[
      'four_pack_blister',
      'build_and_battle',
      'three_pack_blister'
    ]) as scopes(value)
    where conrelid = 'ingest.public_study_coverage_observations'::regclass
      and conname = 'public_study_coverage_product_check'
  ),
  'the private coverage ledger admits both exact new product scopes'
);
select ok(
  (
    select bool_and(position(study_key in pg_get_constraintdef(c.oid)) > 0)
    from unnest(array[
      'tcg-market-chaos-rising-pa-6-v1',
      'tcg-market-pitch-black-pa-4-v1',
      'pokeshow-mega-evolution-gt-3-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as c
  ),
  'the scheduled-job CHECK allowlists all three exact study keys'
);
select ok(
  not exists (
    select 1
    from unnest(array[
      pg_get_functiondef(
        'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure
      ),
      pg_get_functiondef(
        'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
      )
    ]) as definitions(definition)
    cross join unnest(array[
      'tcg-market-chaos-rising-pa-6-v1',
      'tcg-market-pitch-black-pa-4-v1',
      'pokeshow-mega-evolution-gt-3-v1'
    ]) as identities(value)
    where position(identities.value in definitions.definition) > 0
  ),
  'the statistical begin/finalize path admits none of the coverage-only identities'
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
      'tcg-market-chaos-rising-pa-6-v1',
      'tcg-market-pitch-black-pa-4-v1',
      'pokeshow-mega-evolution-gt-3-v1'
    )
  ),
  '{"rows":3,"packs":13,"countries":2,"publishers":2}'::jsonb,
  'the observations total 13 packs in two countries from two publishers'
);
select is(
  (
    select jsonb_object_agg(
      coverage.study_key,
      jsonb_build_object(
        'country', coverage.country_code,
        'packs', coverage.pack_count,
        'set', coverage.set_external_id,
        'product', coverage.product_scope,
        'hash', coverage.evidence_sha256
      )
    )
    from ingest.public_study_coverage_observations as coverage
    where coverage.study_key in (
      'tcg-market-chaos-rising-pa-6-v1',
      'tcg-market-pitch-black-pa-4-v1',
      'pokeshow-mega-evolution-gt-3-v1'
    )
  ),
  '{
    "tcg-market-chaos-rising-pa-6-v1":{
      "country":"PA","packs":6,"set":"me04","product":"booster_bundle",
      "hash":"abb892071c34d353e811c9715174512bb47304ac72de2508d188e13956e3e4ef"
    },
    "tcg-market-pitch-black-pa-4-v1":{
      "country":"PA","packs":4,"set":"me05","product":"build_and_battle",
      "hash":"055d48674555e3a9dc79ced8f5886c7960ad200c7c8bdc4383a5623b5e583857"
    },
    "pokeshow-mega-evolution-gt-3-v1":{
      "country":"GT","packs":3,"set":"me01","product":"three_pack_blister",
      "hash":"b6c535ad4e34f0df39c8b9823a8a6e624fbb9a66c2da8329996b484b04a9feeb"
    }
  }'::jsonb,
  'the seeded observations preserve exact immutable facts'
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
    where country.item ->> 'countryCode' in ('GT', 'PA')
  ),
  '{
    "GT":{
      "packs":"3","sources":"1","class":"coverage_only",
      "versions":["und · me01 · Mega Evolution · three pack blister"]
    },
    "PA":{
      "packs":"10","sources":"1","class":"coverage_only",
      "versions":[
        "und · me04 · Chaos Rising · booster bundle",
        "und · me05 · Pitch Black · build and battle"
      ]
    }
  }'::jsonb,
  'public v3 publishes exact country coverage and human-readable data versions'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' in ('GT', 'PA')
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
  'country coverage exposes no numerator, rate, or inference'
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
      'tcg_market_panama_chaos_rising_study',
      'tcg_market_panama_pitch_black_study',
      'pokeshow_guatemala_megaevolution_study'
    )
  ),
  '{
    "tcg_market_panama_chaos_rising_study":{
      "packs":"6","url":"https://www.youtube.com/watch?v=fHQpNECg4y4"
    },
    "tcg_market_panama_pitch_black_study":{
      "packs":"4","url":"https://www.youtube.com/watch?v=6kb1MvcnMJE"
    },
    "pokeshow_guatemala_megaevolution_study":{
      "packs":"3","url":"https://www.youtube.com/watch?v=DWRdhUuIUvI"
    }
  }'::jsonb,
  'public v3 exposes each exact source URL and denominator'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'sources'
    ) as source(item)
    where source.item ->> 'id' in (
      'tcg_market_panama_chaos_rising_study',
      'tcg_market_panama_pitch_black_study',
      'pokeshow_guatemala_megaevolution_study'
    )
      and (
        source.item -> 'coverage' ? 'ratePacksObserved'
        or source.item -> 'coverage' ? 'qualifyingHitPacks'
        or source.item -> 'coverage' ? 'observedRate'
      )
  ),
  'none of the source cards exposes a fabricated rate'
);

select * from finish();
rollback;
