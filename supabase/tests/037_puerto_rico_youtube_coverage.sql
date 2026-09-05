-- Puerto Rico has two exact coverage-only observations from one public
-- publisher channel. They contribute 54 observed packs and no normalized SIR
-- numerator, rate, or inference.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (
    select count(*)::integer
    from ingest.source_policies
    where source_key in (
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
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
  'both Puerto Rico source policies retain the bounded live collector contract'
);

select is(
  (
    select jsonb_object_agg(
      source_key,
      jsonb_build_object(
        'domain', domain,
        'url', base_url,
        'study', config ->> 'study_key',
        'channel', config ->> 'publisher_channel_id',
        'countryEvidence', config ->> 'publisher_country_evidence',
        'set', config ->> 'set_external_id',
        'setScope', config ->> 'set_scope',
        'product', config ->> 'product_scope',
        'packs', (config ->> 'pack_count')::integer,
        'observedAt', config ->> 'observed_at'
      )
    )
    from ingest.source_policies
    where source_key in (
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
    )
  ),
  '{
    "public_study_richards_bricks_pr_18":{
      "domain":"www.youtube.com",
      "url":"https://www.youtube.com/watch?v=OON-ICjlrd4",
      "study":"richards-bricks-charizard-upc-pr-18-v1",
      "channel":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
      "countryEvidence":"country:\"Puerto Rico\"",
      "set":"mixed-tpci-2025",
      "setScope":"mixed_multi_expansion",
      "product":"all",
      "packs":18,
      "observedAt":"2025-12-24T11:03:10Z"
    },
    "public_study_richards_bricks_pr_36":{
      "domain":"m.youtube.com",
      "url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0",
      "study":"richards-bricks-mega-evolution-box-pr-36-v1",
      "channel":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
      "countryEvidence":"country:\"Puerto Rico\"",
      "set":"me01",
      "setScope":"single_expansion",
      "product":"booster_box",
      "packs":36,
      "observedAt":"2025-10-20T15:30:33Z"
    }
  }'::jsonb,
  'Puerto Rico source identity, publisher evidence, data versions, and denominators are exact'
);

select ok(
  not exists (
    select 1
    from ingest.source_policies
    where source_key in (
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
    )
      and config ?| array[
        'qualifying_hit_pack_count',
        'qualifying_metric',
        'metric_version',
        'observed_rate',
        'rate'
      ]
  ),
  'neither Puerto Rico source policy invents a normalized numerator or rate'
);

select is(
  (
    select count(*)::integer
    from ingest.source_request_gates
    where source_key in (
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
    )
  ),
  2,
  'both Puerto Rico sources have durable request gates'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all twelve reviewed source gates are present'
);

select is(
  (select count(*)::integer from ingest.reviewed_public_study_contracts()),
  12,
  'the reviewed registry contains twelve ordered contracts'
);
select is(
  (
    select array_agg(study_key order by ordinal)
    from ingest.reviewed_public_study_contracts()
    where ordinal in (11, 12)
  ),
  array[
    'richards-bricks-charizard-upc-pr-18-v1',
    'richards-bricks-mega-evolution-box-pr-36-v1'
  ]::text[],
  'the two Puerto Rico studies occupy exact append-only ordinals 11 and 12'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts() as contracts
    left join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
      and not policies.is_demo
    where contracts.ordinal in (11, 12)
      and (
        policies.id is null
        or policies.config is distinct from contracts.config
        or policies.version is distinct from contracts.policy_version
        or policies.base_url is distinct from contracts.canonical_url
      )
  ),
  'Puerto Rico registry identities cannot drift from database source policies'
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
    where ordinal in (11, 12)
  ),
  '{
    "richards-bricks-charizard-upc-pr-18-v1":"ee0ec8cb243d26d0fc8d46b4788bb8eff2205353466c0d8e0c3c2d7cd48293f1",
    "richards-bricks-mega-evolution-box-pr-36-v1":"97371af1d78a7d91e48e55a02f0376d4cd399297ea50fc150b3d966963e2d18c"
  }'::jsonb,
  'both Puerto Rico evidence excerpts retain their exact reviewed SHA-256'
);
select ok(
  not exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal in (11, 12)
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
  'Puerto Rico contracts contain neither statistical fields nor copied media or transcript'
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
    where position(
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12)'
      in definition
    ) > 0
  ),
  4,
  'all four coverage ingestion boundaries admit the same nine-contract allowlist'
);
select matches(
  pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  ),
  'mixed-tpci-2025',
  'the finalizer admits the exact reviewed mixed-expansion identity'
);
select ok(
  (
    select bool_and(position(fragments.value in definitions.definition) > 0)
    from (
      select pg_get_functiondef(
        'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
      ) as definition
    ) as definitions
    cross join unnest(array[
      'richards-bricks-mega-evolution-box-pr-36-v1',
      'me01',
      'single_expansion',
      'Mega Evolution',
      'booster_box'
    ]) as fragments(value)
  ),
  'the 36-pack finalizer identity is self-contained before any catalog sync'
);
select ok(
  (
    select bool_and(
      position(study_key in pg_get_constraintdef(constraints.oid)) > 0
    )
    from unnest(array[
      'richards-bricks-charizard-upc-pr-18-v1',
      'richards-bricks-mega-evolution-box-pr-36-v1'
    ]) as studies(study_key)
    cross join lateral (
      select oid
      from pg_constraint
      where conrelid = 'ingest.jobs'::regclass
        and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
    ) as constraints
  ),
  'the scheduled-job CHECK allowlists both exact Puerto Rico study keys'
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
      'richards-bricks-charizard-upc-pr-18-v1',
      'richards-bricks-mega-evolution-box-pr-36-v1',
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
    ]) as identities(value)
    where position(identities.value in definitions.definition) > 0
  ),
  'the statistical begin/finalize path never admits a Puerto Rico coverage identity'
);

select ok(
  (
    select classes.relrowsecurity and classes.relforcerowsecurity
    from pg_catalog.pg_class as classes
    where classes.oid = 'ingest.public_study_coverage_observations'::regclass
  ),
  'the coverage ledger keeps enabled and forced RLS'
);
select ok(
  has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'SELECT'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'INSERT'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'UPDATE'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'DELETE'
  ),
  'service_role can read live coverage through RLS but cannot mutate the ledger directly'
);

set local role service_role;
select is(
  (
    select count(*)::integer
    from ingest.public_study_coverage_observations
    where study_key in (
      'richards-bricks-charizard-upc-pr-18-v1',
      'richards-bricks-mega-evolution-box-pr-36-v1'
    )
  ),
  2,
  'the production worker role sees both non-demo rows through the exact RLS policy'
);
select lives_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'richards-bricks-charizard-upc-pr-18-v1', 14, 'pgtap-pr-18-direct',
    transaction_timestamp() + interval '1 day', 3
  )$$,
  'the direct coverage queue accepts the exact 18-pack study'
);
select lives_ok(
  $$select * from ingest.enqueue_public_study_coverage_job_v1(
    'richards-bricks-mega-evolution-box-pr-36-v1', 14, 'pgtap-pr-36-direct',
    transaction_timestamp() + interval '1 day', 3
  )$$,
  'the direct coverage queue accepts the exact 36-pack study'
);

do $puerto_rico_runtime$
declare
  study record;
  queued_job_id uuid;
  claimed_job_id uuid;
  generation_value bigint;
  acquired_value boolean;
begin
  for study in
    select *
    from (values
      (
        'richards-bricks-charizard-upc-pr-18-v1'::text,
        'Abriendo el Mega Charizard X ex Ultra-Premium Collection'::text,
        'https://www.youtube.com/watch?v=OON-ICjlrd4'::text,
        E'Abriendo el Mega Charizard X ex Ultra-Premium Collection\nBooster Pack (18)'::text,
        'ee0ec8cb243d26d0fc8d46b4788bb8eff2205353466c0d8e0c3c2d7cd48293f1'::text,
        'richards-bricks-charizard-upc-evidence-v1'::text
      ),
      (
        'richards-bricks-mega-evolution-box-pr-36-v1'::text,
        'Mega Evolution Booster Box unboxing'::text,
        'https://m.youtube.com/watch?v=p_8k9ZkHV_0'::text,
        E'Mega Evolution Booster Box unboxing\n36 booster packs from the Pokémon TCG: Mega Evolution expansion'::text,
        '97371af1d78a7d91e48e55a02f0376d4cd399297ea50fc150b3d966963e2d18c'::text,
        'richards-bricks-mega-evolution-box-evidence-v1'::text
      )
    ) as values_list(
      study_key, title, source_url, evidence_excerpt, evidence_sha256,
      parser_version
    )
  loop
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
      'pgtap-puerto-rico-worker',
      array['source.public_study.opening'],
      1,
      600
    ) as jobs;
    if claimed_job_id is distinct from queued_job_id then
      raise exception 'Puerto Rico coverage job % was not claimed exactly',
        study.study_key;
    end if;

    select begun.acquired
    into acquired_value
    from ingest.begin_public_study_job_v2(
      queued_job_id,
      'pgtap-puerto-rico-worker',
      generation_value,
      study.study_key
    ) as begun;
    if acquired_value is distinct from true then
      raise exception 'Puerto Rico coverage request gate % was not acquired',
        study.study_key;
    end if;

    perform ingest.finalize_public_study_coverage_job_v1(
      queued_job_id,
      'pgtap-puerto-rico-worker',
      generation_value,
      study.study_key,
      jsonb_build_object(
        'version', 1,
        'study_key', study.study_key,
        'source_url', study.source_url,
        'title', study.title,
        'evidence_excerpt', study.evidence_excerpt,
        'evidence_sha256', study.evidence_sha256,
        'collector_version', 'public-study-richards-bricks-youtube-v1',
        'parser_version', study.parser_version,
        'source_policy_version', 'public-study-richards-bricks-youtube-v1'
      )
    );
  end loop;
end;
$puerto_rico_runtime$;
reset role;

select is(
  (
    select jsonb_object_agg(
      jobs.payload ->> 'study_key',
      jsonb_build_object(
        'status', jobs.status,
        'unlocked', jobs.locked_by is null
          and jobs.locked_at is null
          and jobs.lock_expires_at is null,
        'completed', jobs.completed_at is not null
      )
    )
    from ingest.jobs as jobs
    where jobs.dedupe_key like 'reviewed-coverage-schedule:%'
      and jobs.payload ->> 'study_key' in (
        'richards-bricks-charizard-upc-pr-18-v1',
        'richards-bricks-mega-evolution-box-pr-36-v1'
      )
  ),
  '{
    "richards-bricks-charizard-upc-pr-18-v1":{
      "status":"completed","unlocked":true,"completed":true
    },
    "richards-bricks-mega-evolution-box-pr-36-v1":{
      "status":"completed","unlocked":true,"completed":true
    }
  }'::jsonb,
  'both production-role lifecycle runs complete and clear every job lease field'
);
select is(
  (
    select count(*)::integer
    from ingest.source_request_gates as gates
    where gates.source_key in (
      'public_study_richards_bricks_pr_18',
      'public_study_richards_bricks_pr_36'
    )
      and gates.owner_job_id is null
      and gates.owner_lease_generation is null
      and gates.acquired_at is null
      and gates.active_until is null
  ),
  2,
  'both production request gates are fully released after completion'
);

select is(
  (
    select jsonb_build_object(
      'openings', count(*),
      'packs', sum(pack_count),
      'countries', count(distinct country_code),
      'publishers', count(distinct config ->> 'publisher_channel_id')
    )
    from ingest.public_study_coverage_observations as coverage
    join ingest.source_policies as policies
      on policies.id = coverage.source_policy_id
    where coverage.study_key in (
      'richards-bricks-charizard-upc-pr-18-v1',
      'richards-bricks-mega-evolution-box-pr-36-v1'
    )
  ),
  '{"openings":2,"packs":54,"countries":1,"publishers":1}'::jsonb,
  'the two observations total 54 packs for one country and one publisher channel'
);

select ok(
  exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'PR'
      and country.item ->> 'countryName' = 'Puerto Rico'
      and country.item ->> 'packsObserved' = '54'
      and country.item ->> 'independentSources' = '1'
      and country.item ->> 'collectionClass' = 'coverage_only'
  ),
  'public v3 publishes 54 coverage-only packs from one Puerto Rico publisher'
);
select is(
  (
    select country.item -> 'dataVersions'
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'PR'
  ),
  '[
    "en · me01 · Mega Evolution · booster box",
    "en · mixed-tpci-2025 · Mixed English TPCI expansions · all products"
  ]'::jsonb,
  'Puerto Rico exposes both exact human-readable data versions'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country(item)
    where country.item ->> 'countryCode' = 'PR'
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
  'Puerto Rico country coverage exposes no numerator, rate, or inference'
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
      'richards_bricks_charizard_upc_study',
      'richards_bricks_mega_evolution_box_study'
    )
  ),
  '{
    "richards_bricks_charizard_upc_study":{
      "packs":"18",
      "url":"https://www.youtube.com/watch?v=OON-ICjlrd4"
    },
    "richards_bricks_mega_evolution_box_study":{
      "packs":"36",
      "url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0"
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
      'richards_bricks_charizard_upc_study',
      'richards_bricks_mega_evolution_box_study'
    )
      and (
        source.item -> 'coverage' ? 'ratePacksObserved'
        or source.item -> 'coverage' ? 'qualifyingHitPacks'
        or source.item -> 'coverage' ? 'observedRate'
      )
  ),
  'neither Puerto Rico source card exposes a fabricated rate'
);

select * from finish();
rollback;
