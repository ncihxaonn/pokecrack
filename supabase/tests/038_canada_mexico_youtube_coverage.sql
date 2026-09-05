-- Canada and Mexico each have one exact coverage-only public observation.
-- Together they contribute 59 observed packs and no normalized SIR numerator,
-- rate, or inference.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_indigo_geek_mx_50',
      'public_study_pokehanna_ca_9'
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
  'both Canada/Mexico policies retain the bounded live collector contract'
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
        'countryEvidence', config ->> 'publisher_country_evidence',
        'set', config ->> 'set_external_id',
        'language', config ->> 'set_language',
        'product', config ->> 'product_scope',
        'packs', (config ->> 'pack_count')::integer,
        'observedAt', config ->> 'observed_at'
      )
    )
    from ingest.source_policies
    where source_key in (
      'public_study_indigo_geek_mx_50',
      'public_study_pokehanna_ca_9'
    )
  ),
  '{
    "public_study_indigo_geek_mx_50":{
      "url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8",
      "study":"indigo-geek-megaevolucion-mx-50-v1",
      "channel":"UCGri3BoVzarWIYCzg8MEQjw",
      "country":"MX",
      "countryEvidence":"country:\"Mexico\"",
      "set":"me01",
      "language":"es-MX",
      "product":"all",
      "packs":50,
      "observedAt":"2025-09-12T13:00:41Z"
    },
    "public_study_pokehanna_ca_9":{
      "url":"https://www.youtube.com/watch?v=Jj0IxqUYat8",
      "study":"pokehanna-ascended-heroes-ca-9-v1",
      "channel":"UC6stWaGoj-9rsEOzYv56ftQ",
      "country":"CA",
      "countryEvidence":"country:\"Canada\"",
      "set":"me02.5",
      "language":"en",
      "product":"etb",
      "packs":9,
      "observedAt":"2026-04-05T18:00:15Z"
    }
  }'::jsonb,
  'country identities, data versions, source URLs, and denominators are exact'
);

select ok(
  not exists (
    select 1
    from ingest.source_policies
    where source_key in (
      'public_study_indigo_geek_mx_50',
      'public_study_pokehanna_ca_9'
    )
      and config ?| array[
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      ]
  ),
  'neither policy invents a normalized numerator or rate'
);

select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_indigo_geek_mx_50',
      'public_study_pokehanna_ca_9'
    )
  ),
  2,
  'both sources have durable request gates'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all fourteen reviewed request gates are present'
);

select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 14
  ),
  14,
  'the reviewed registry retains its fourteen-contract Canada/Mexico prefix'
);
select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal in (13, 14)
  ),
  array[
    'indigo-geek-megaevolucion-mx-50-v1',
    'pokehanna-ascended-heroes-ca-9-v1'
  ]::text[],
  'Mexico and Canada occupy exact append-only ordinals 13 and 14'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal in (13, 14)
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
    where ordinal in (13, 14)
  ),
  '{
    "indigo-geek-megaevolucion-mx-50-v1":"c270707bfa43c79b8362a4cf5cab1bad377f0da4402904e0af02fe62c7bdb1d2",
    "pokehanna-ascended-heroes-ca-9-v1":"d9c012acf1e003942eebdefda80058358f85ca1c718e59e5edd4dcd25b9c3ce9"
  }'::jsonb,
  'both minimal evidence excerpts retain their exact reviewed SHA-256'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal in (13, 14)
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
      'contracts\.ordinal in \([^)]*13[^)]*14'
  ),
  4,
  'all four coverage boundaries admit the same eleven-contract allowlist'
);
select ok(
  (
    select bool_and(position(study_key in pg_get_constraintdef(c.oid)) > 0)
    from unnest(array[
      'indigo-geek-megaevolucion-mx-50-v1',
      'pokehanna-ascended-heroes-ca-9-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as c
  ),
  'the scheduled-job CHECK allowlists both exact study keys'
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
      'indigo-geek-megaevolucion-mx-50-v1',
      'pokehanna-ascended-heroes-ca-9-v1'
    ]) as identities(value)
    where position(identities.value in definitions.definition) > 0
  ),
  'the statistical begin/finalize path admits neither coverage-only identity'
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
      'indigo-geek-megaevolucion-mx-50-v1',
      'pokehanna-ascended-heroes-ca-9-v1'
    )
  ),
  '{"rows":2,"packs":59,"countries":2,"publishers":2}'::jsonb,
  'the two observations total 59 packs in two countries from two publishers'
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
      'indigo-geek-megaevolucion-mx-50-v1',
      'pokehanna-ascended-heroes-ca-9-v1'
    )
  ),
  '{
    "indigo-geek-megaevolucion-mx-50-v1":{
      "country":"MX","packs":50,"set":"me01","product":"all",
      "hash":"c270707bfa43c79b8362a4cf5cab1bad377f0da4402904e0af02fe62c7bdb1d2"
    },
    "pokehanna-ascended-heroes-ca-9-v1":{
      "country":"CA","packs":9,"set":"me02.5","product":"etb",
      "hash":"d9c012acf1e003942eebdefda80058358f85ca1c718e59e5edd4dcd25b9c3ce9"
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
    where country.item ->> 'countryCode' in ('CA', 'MX')
  ),
  '{
    "CA":{
      "packs":"9","sources":"1","class":"coverage_only",
      "versions":["en · me02.5 · Ascended Heroes · ETB"]
    },
    "MX":{
      "packs":"50","sources":"1","class":"coverage_only",
      "versions":["es-MX · me01 · Megaevolución · all products"]
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
    where country.item ->> 'countryCode' in ('CA', 'MX')
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
      'indigo_geek_megaevolucion_study',
      'pokehanna_ascended_heroes_study'
    )
  ),
  '{
    "indigo_geek_megaevolucion_study":{
      "packs":"50","url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8"
    },
    "pokehanna_ascended_heroes_study":{
      "packs":"9","url":"https://www.youtube.com/watch?v=Jj0IxqUYat8"
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
      'indigo_geek_megaevolucion_study',
      'pokehanna_ascended_heroes_study'
    )
      and (
        source.item -> 'coverage' ? 'ratePacksObserved'
        or source.item -> 'coverage' ? 'qualifyingHitPacks'
        or source.item -> 'coverage' ? 'observedRate'
      )
  ),
  'neither source card exposes a fabricated rate'
);

select * from finish();
rollback;
