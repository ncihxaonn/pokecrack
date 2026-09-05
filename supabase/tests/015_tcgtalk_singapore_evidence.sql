-- Singapore reviewed coverage is denominator-only and attributed to the
-- publisher country; it cannot publish a numerator, rate, or opening location.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(52);

select has_table(
  'ingest',
  'public_study_coverage_observations',
  'the denominator-only coverage ledger exists'
);
select is(
  (
    select jsonb_build_object(
      'source_key', source_key,
      'display_name', display_name,
      'source_kind', source_kind,
      'domain', domain,
      'base_url', base_url,
      'enabled', enabled,
      'collector_type', collector_type,
      'access_mode', access_mode,
      'robots_policy', robots_policy,
      'routes', routes,
      'include_subdomains', include_subdomains,
      'min_delay_seconds', min_delay_seconds,
      'max_pages_per_run', max_pages_per_run,
      'max_items_per_run', max_items_per_run,
      'max_concurrency', max_concurrency,
      'statistics_eligible_default', statistics_eligible_default,
      'retention_days', retention_days,
      'version', version,
      'expected_interval_seconds', expected_interval_seconds,
      'is_demo', is_demo
    )::text
    from ingest.source_policies
    where source_key = 'public_study_tcgtalk_sg_54'
  ),
  ('{
    "source_key":"public_study_tcgtalk_sg_54",
    "display_name":"tcgTalk Perfect Order 54-pack study",
    "source_kind":"public_web",
    "domain":"tcgtalk.com",
    "base_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
    "enabled":true,
    "collector_type":"scrapling_http",
    "access_mode":"public",
    "robots_policy":"respect",
    "routes":["scrapling_http"],
    "include_subdomains":false,
    "min_delay_seconds":30.000,
    "max_pages_per_run":2,
    "max_items_per_run":1,
    "max_concurrency":1,
    "statistics_eligible_default":true,
    "retention_days":730,
    "version":"public-study-tcgtalk-perfect-order-v1",
    "expected_interval_seconds":86400,
    "is_demo":false
  }'::jsonb)::text,
  'the SG source policy has the exact reviewed transport contract'
);
select is(
  (
    select config::text
    from ingest.source_policies
    where source_key = 'public_study_tcgtalk_sg_54'
  ),
  ('{
    "study_key":"tcgtalk-perfect-order-sg-54-v1",
    "canonical_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
    "collector_version":"public-study-tcgtalk-perfect-order-v1",
    "parser_version":"tcgtalk-perfect-order-evidence-v1",
    "country_code":"SG",
    "country_name":"Singapore",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me03",
    "product_scope":"booster_bundle",
    "pack_count":54,
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-03-25T12:40:00Z",
    "denominator_complete":true
  }'::jsonb)::text,
  'the SG policy config exactly matches the worker identity, including its private review pin'
);
select is(
  (select count(*)::integer from ingest.source_policies
   where source_key = 'public_study_tcgtalk_sg_54'),
  1,
  'exactly one SG source policy exists'
);
select ok(
  exists (
    select 1
    from ingest.source_request_gates
    where source_key = 'public_study_tcgtalk_sg_54'
  ),
  'the SG source has one durable request gate'
);

select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 9
  ),
  9,
  'the reviewed registry retains its original nine-contract prefix'
);
select is(
  (select ordinal from ingest.reviewed_public_study_contracts()
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  5,
  'Singapore keeps the exact ordinal 5'
);
select is(
  (
    select jsonb_build_object(
      'policy_key', policy_key,
      'public_id', public_id,
      'public_name', public_name,
      'public_note', public_note,
      'display_name', display_name,
      'domain', domain,
      'canonical_url', canonical_url,
      'policy_version', policy_version
    )::text
    from ingest.reviewed_public_study_contracts()
    where ordinal = 5
  ),
  ('{
    "policy_key":"public_study_tcgtalk_sg_54",
    "public_id":"tcgtalk_perfect_order_study",
    "public_name":"tcgTalk Perfect Order study",
    "public_note":"Reviewed 54-pack public study attributed to Singapore''s publisher country; physical opening location is not claimed and its rate remains withheld.",
    "display_name":"tcgTalk Perfect Order 54-pack study",
    "domain":"tcgtalk.com",
    "canonical_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
    "policy_version":"public-study-tcgtalk-perfect-order-v1"
  }'::jsonb)::text,
  'the ordinal-5 public identity is exact and explicitly withholds the rate'
);
select is(
  (
    select config::text
    from ingest.reviewed_public_study_contracts()
    where ordinal = 5
  ),
  (select config::text from ingest.source_policies
   where source_key = 'public_study_tcgtalk_sg_54'),
  'the private contract config and source policy config cannot drift'
);
select is(
  (
    select evidence_excerpt
    from ingest.reviewed_public_study_contracts()
    where ordinal = 5
  ),
  E'Based on community opening of 9 booster bundles (54 packs total)\nOut of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs in this particular opening, with the Meowth EX SIR being the pull.',
  'the SG evidence excerpt is the exact bounded reviewed text'
);
select is(
  (
    select encode(
      extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'),
      'hex'
    )
    from ingest.reviewed_public_study_contracts()
    where ordinal = 5
  ),
  '217f21e0de947139a96b6466563c1d005300598b1dde933264255627c8f0b096',
  'the SG evidence excerpt has the exact pinned SHA-256'
);

select is(
  (
    select count(*)::integer
    from unnest(array[
      pg_get_functiondef('ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure),
      pg_get_functiondef('ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure),
      pg_get_functiondef('public.get_public_study_coverage_v1()'::regprocedure)
    ]) as definitions(definition)
    where position('contracts.ordinal in (3, 4, 5' in definition) > 0
  ),
  5,
  'all five coverage boundaries continue to accept ordinal 5'
);
select is(
  (
    select count(*)::integer
    from unnest(array[
      pg_get_functiondef('ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure),
      pg_get_functiondef('ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure),
      pg_get_functiondef('ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure),
      pg_get_functiondef('public.get_public_study_coverage_v1()'::regprocedure)
    ]) as definitions(definition)
    where position('contracts.ordinal in (3, 4)' in definition) > 0
  ),
  0,
  'no coverage boundary retains the old ordinal predicate'
);

select is(
  (
    select count(*)::integer
    from pg_proc
    where oid in (
      'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
      'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
      'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
      'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
    )
    and proowner = (select oid from pg_roles where rolname = 'postgres')
    and prosecdef
  ),
  4,
  'all four worker coverage functions remain postgres-owned SECURITY DEFINER functions'
);
select is(
  (
    select count(*)::integer
    from pg_proc
    where oid in (
      'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
      'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
      'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
      'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
    )
    and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
  ),
  4,
  'all four worker coverage functions retain the pg_catalog-only search path'
);
select is(
  (
    select count(*)::integer
    from unnest(array[
      'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
      'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
      'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
      'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
    ]) as functions(function_oid)
    where has_function_privilege('service_role', function_oid, 'execute')
  ),
  4,
  'service_role retains EXECUTE on every worker coverage function'
);
select is(
  (
    select count(*)::integer
    from unnest(array[
      'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
      'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
      'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
      'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
    ]) as functions(function_oid)
    where not has_function_privilege('anon', function_oid, 'execute')
      and not has_function_privilege('authenticated', function_oid, 'execute')
  ),
  4,
  'API roles cannot execute any worker coverage function'
);
select is(
  (select proowner::regrole::text from pg_proc
   where oid = 'ingest.reviewed_public_study_contracts()'::regprocedure),
  'postgres',
  'the private contract helper remains postgres-owned'
);
select ok(
  not (select prosecdef from pg_proc
       where oid = 'ingest.reviewed_public_study_contracts()'::regprocedure),
  'the private contract helper remains SECURITY INVOKER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc
   where oid = 'ingest.reviewed_public_study_contracts()'::regprocedure),
  'the private contract helper retains the pg_catalog-only search path'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.reviewed_public_study_contracts()'::regprocedure,
    'execute'
  ),
  'service_role cannot execute the private evidence helper'
);

select is(
  (
    select count(*)::integer
    from pg_proc
    where oid = 'public.get_public_study_coverage_v1()'::regprocedure
      and proowner = (select oid from pg_roles where rolname = 'postgres')
      and prosecdef
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
  ),
  1,
  'the public coverage RPC remains postgres-owned SECURITY DEFINER with a fixed search path'
);
select ok(
  has_function_privilege(
    'anon',
    'public.get_public_study_coverage_v1()'::regprocedure,
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.get_public_study_coverage_v1()'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.get_public_study_coverage_v1()'::regprocedure,
    'execute'
  ),
  'the public coverage RPC retains its exact API-role EXECUTE ACL'
);
select matches(
  (
    select pg_get_constraintdef(oid)
    from pg_constraint
    where conrelid = 'ingest.jobs'::regclass
      and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'
  ),
  'tcgtalk-perfect-order-sg-54-v1',
  'the reviewed coverage schedule CHECK explicitly allowlists SG'
);
select ok(
  not exists (
    select 1
    from information_schema.columns
    where table_schema = 'ingest'
      and table_name = 'public_study_coverage_observations'
      and column_name in (
        'qualifying_hit_pack_count',
        'observed_rate',
        'posterior_mean',
        'baseline_rate',
        'delta_from_baseline'
      )
  ),
  'the denominator-only ledger has no public numerator or inference column'
);

insert into catalog.sets (
  external_source,
  external_id,
  name,
  slug,
  language,
  release_date,
  series_name,
  is_active,
  is_demo
) values (
  'tcgdex',
  'me03',
  'Perfect Order',
  'pgtap-perfect-order-sg',
  'en',
  '2026-03-27',
  'Mega Evolution',
  true,
  false
)
on conflict on constraint sets_external_identity_unique do update
set name = excluded.name,
    slug = excluded.slug,
    release_date = excluded.release_date,
    series_name = excluded.series_name,
    is_active = true,
    is_demo = false,
    updated_at = clock_timestamp();

set local role service_role;
select lives_ok(
  $sql$select * from ingest.enqueue_public_study_coverage_job_v1(
    'tcgtalk-perfect-order-sg-54-v1',
    14,
    'pgtap-sg-direct',
    transaction_timestamp() + interval '1 day',
    3
  )$sql$,
  'the direct SG coverage enqueue accepts the exact reviewed study'
);
select set_config(
  'pokecrack.sg_direct_job',
  (select id::text from ingest.jobs where dedupe_key = 'pgtap-sg-direct'),
  true
);
select is(
  (select payload from ingest.jobs
   where id = current_setting('pokecrack.sg_direct_job')::uuid),
  jsonb_build_object('study_key', 'tcgtalk-perfect-order-sg-54-v1'),
  'the direct SG enqueue persists the exact bounded payload'
);
select lives_ok(
  $sql$select * from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_tcgtalk-perfect-order-sg-54-v1',
    date_trunc('minute', transaction_timestamp()),
    'tcgtalk-perfect-order-sg-54-v1',
    14,
    3
  )$sql$,
  'the scheduled SG coverage enqueue accepts the exact reviewed study'
);
select set_config(
  'pokecrack.sg_scheduled_job',
  (
    select slots.job_id::text
    from ingest.schedule_slots as slots
    where slots.schedule_name = 'public_study_tcgtalk-perfect-order-sg-54-v1'
      and slots.slot_at = date_trunc('minute', transaction_timestamp())
  ),
  true
);
select is(
  (
    select count(*)::integer
    from ingest.schedule_slots
    where schedule_name = 'public_study_tcgtalk-perfect-order-sg-54-v1'
      and slot_at = date_trunc('minute', transaction_timestamp())
  ),
  1,
  'the scheduled SG coverage enqueue reserves exactly one durable slot'
);
select is(
  (select payload from ingest.jobs
   where id = current_setting('pokecrack.sg_scheduled_job')::uuid),
  jsonb_build_object('study_key', 'tcgtalk-perfect-order-sg-54-v1'),
  'the scheduled SG enqueue persists the exact bounded payload'
);

do $sg_runtime$
declare
  scheduled_job_id uuid := current_setting('pokecrack.sg_scheduled_job')::uuid;
  claimed_job_id uuid;
  generation_value bigint;
  acquired_value boolean;
begin
  select jobs.id, jobs.lease_generation
  into claimed_job_id, generation_value
  from ingest.claim_jobs_v2(
    'pgtap-sg-worker',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  if claimed_job_id is distinct from scheduled_job_id then
    raise exception 'the SG scheduled coverage job was not claimed exactly once';
  end if;

  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job_v2(
    scheduled_job_id,
    'pgtap-sg-worker',
    generation_value,
    'tcgtalk-perfect-order-sg-54-v1'
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'the SG request gate was not acquired';
  end if;

  perform ingest.finalize_public_study_coverage_job_v1(
    scheduled_job_id,
    'pgtap-sg-worker',
    generation_value,
    'tcgtalk-perfect-order-sg-54-v1',
    jsonb_build_object(
      'version', 1,
      'study_key', 'tcgtalk-perfect-order-sg-54-v1',
      'source_url', 'https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232',
      'title', 'Perfect Order Pull Rates: What Singapore Collectors Can Expect',
      'evidence_excerpt', E'Based on community opening of 9 booster bundles (54 packs total)\nOut of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs in this particular opening, with the Meowth EX SIR being the pull.',
      'evidence_sha256', '217f21e0de947139a96b6466563c1d005300598b1dde933264255627c8f0b096',
      'collector_version', 'public-study-tcgtalk-perfect-order-v1',
      'parser_version', 'tcgtalk-perfect-order-evidence-v1',
      'source_policy_version', 'public-study-tcgtalk-perfect-order-v1'
    )
  );
end;
$sg_runtime$;
reset role;

select is(
  (
    select count(*)::integer
    from ingest.public_study_coverage_observations
    where study_key = 'tcgtalk-perfect-order-sg-54-v1'
  ),
  1,
  'the SG finalizer persists one coverage row'
);
select is(
  (select source_policy_id from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  (select id from ingest.source_policies
   where source_key = 'public_study_tcgtalk_sg_54'),
  'the SG coverage row points to the exact reviewed policy'
);
select is(
  (select country_code from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  'SG',
  'the SG coverage row has the exact publisher-country code'
);
select is(
  (select country_name from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  'Singapore',
  'the SG coverage row has the exact publisher-country name'
);
select is(
  (select source_observed_at from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  '2026-03-25T12:40:00Z'::timestamptz,
  'the SG coverage row has the exact reviewed observation time'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  54,
  'the SG coverage row stores only the reviewed 54-pack denominator'
);
select is(
  (select set_external_id from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  'me03',
  'the SG coverage row has the exact TCGdex set identity'
);
select is(
  (select product_scope from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  'booster_bundle',
  'the SG coverage row has the exact product scope'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  '217f21e0de947139a96b6466563c1d005300598b1dde933264255627c8f0b096',
  'the SG coverage row stores the exact reviewed evidence hash'
);
select ok(
  (select not is_demo from ingest.public_study_coverage_observations
   where study_key = 'tcgtalk-perfect-order-sg-54-v1'),
  'the SG coverage row is live and not demo data'
);
select is(
  (select status from ingest.jobs
   where id = current_setting('pokecrack.sg_scheduled_job')::uuid),
  'completed',
  'the SG finalizer completes the exact leased job'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates
   where source_key = 'public_study_tcgtalk_sg_54'),
  'the SG request gate is released after completion'
);

set local role anon;
select set_config(
  'pokecrack.sg_public_payload',
  public.get_public_study_coverage_v1()::text,
  true
);
reset role;
select is(
  current_setting('pokecrack.sg_public_payload')::jsonb ->> 'schemaVersion',
  '1.0.0',
  'the public SG coverage payload keeps the versioned contract'
);
select is(
  jsonb_array_length(current_setting('pokecrack.sg_public_payload')::jsonb -> 'sources'),
  3,
  'the public coverage payload exposes all three reviewed source rows'
);
select is(
  (
    select source ->> 'id'
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'sources'
    ) as rows(source)
    where source ->> 'id' = 'tcgtalk_perfect_order_study'
  ),
  'tcgtalk_perfect_order_study',
  'the public payload exposes the exact SG source identity'
);
select is(
  (
    select source ->> 'name'
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'sources'
    ) as rows(source)
    where source ->> 'id' = 'tcgtalk_perfect_order_study'
  ),
  'tcgTalk Perfect Order study',
  'the public payload exposes the exact SG source name'
);
select is(
  jsonb_array_length(current_setting('pokecrack.sg_public_payload')::jsonb -> 'countries'),
  1,
  'the public payload exposes one verified country denominator'
);
select is(
  (
    select country ->> 'countryCode'
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'countries'
    ) as rows(country)
  ),
  'SG',
  'the public payload exposes the Singapore country code'
);
select is(
  (
    select (country ->> 'packsObserved')::integer
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'countries'
    ) as rows(country)
  ),
  54,
  'the public payload exposes the reviewed 54-pack SG denominator'
);
select is(
  (
    select (country ->> 'openings')::integer
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'countries'
    ) as rows(country)
  ),
  1,
  'the public payload exposes one SG coverage observation'
);
select is(
  (
    select (country ->> 'independentSources')::integer
    from jsonb_array_elements(
      current_setting('pokecrack.sg_public_payload')::jsonb -> 'countries'
    ) as rows(country)
  ),
  1,
  'the public payload exposes one independent SG domain'
);
select doesnt_match(
  current_setting('pokecrack.sg_public_payload'),
  '(?i)(evidence_sha256|qualifying_hit_pack_count|observed_rate|posterior_mean|baseline_rate|numerator)',
  'the public SG payload exposes no evidence hash, numerator, rate, or inference field'
);

select * from finish();
rollback;
