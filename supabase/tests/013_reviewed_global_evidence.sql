-- Denominator-only coverage extension for two additional reviewed sources.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(43);

select has_table(
  'ingest',
  'public_study_coverage_observations',
  'the denominator-only coverage ledger exists'
);
select ok(
  (select relrowsecurity
   from pg_class
   where oid = 'ingest.public_study_coverage_observations'::regclass),
  'coverage ledger enables RLS'
);
select ok(
  (select relforcerowsecurity
   from pg_class
   where oid = 'ingest.public_study_coverage_observations'::regclass),
  'coverage ledger forces RLS'
);
select ok(
  has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'select'
  ),
  'service_role can read the bounded coverage ledger for backup and health checks'
);
select ok(
  not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'insert'
  ),
  'service_role cannot insert coverage rows directly'
);
select ok(
  not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'update'
  ),
  'service_role cannot update coverage rows directly'
);
select ok(
  not has_table_privilege(
    'service_role', 'ingest.public_study_coverage_observations', 'delete'
  ),
  'service_role cannot delete coverage rows directly'
);
select ok(
  not has_table_privilege(
    'anon', 'ingest.public_study_coverage_observations', 'select'
  ),
  'anon cannot read the private coverage ledger'
);

select has_function(
  'ingest',
  'reviewed_public_study_contracts',
  array[]::text[],
  'the immutable reviewed-study contract helper exists'
);
select ok(
  not has_function_privilege(
    'service_role', 'ingest.reviewed_public_study_contracts()', 'execute'
  ),
  'service_role cannot execute the private evidence contract helper'
);
select has_function(
  'ingest',
  'begin_public_study_job_v2',
  array['uuid', 'text', 'bigint', 'text'],
  'the generation-fenced coverage preflight exists'
);
select ok(
  has_function_privilege(
    'service_role',
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)',
    'execute'
  ),
  'service_role can execute the coverage preflight'
);
select ok(
  not has_function_privilege(
    'anon',
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)',
    'execute'
  ),
  'anon cannot execute the coverage preflight'
);
select matches(
  pg_get_functiondef(
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure
  ),
  'contracts\.ordinal in \(3, 4, 5, 6\)',
  'coverage preflight accepts the four reviewed coverage contracts'
);
select has_function(
  'ingest',
  'finalize_public_study_coverage_job_v1',
  array['uuid', 'text', 'bigint', 'text', 'jsonb'],
  'the denominator-only fenced finalizer exists'
);
select ok(
  has_function_privilege(
    'service_role',
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)',
    'execute'
  ),
  'service_role can execute the coverage finalizer'
);
select ok(
  not has_function_privilege(
    'anon',
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)',
    'execute'
  ),
  'anon cannot execute the coverage finalizer'
);
select has_function(
  'ingest',
  'enqueue_scheduled_public_study_coverage_job_v1',
  array['text', 'timestamptz', 'text', 'integer', 'integer'],
  'the exact scheduled coverage enqueue exists'
);
select ok(
  has_function_privilege(
    'service_role',
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)',
    'execute'
  ),
  'service_role can enqueue an exact reviewed coverage job'
);

select has_function(
  'public',
  'get_public_study_coverage_v1',
  array[]::text[],
  'the bounded browser coverage RPC exists'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.get_public_study_coverage_v1()'::regprocedure),
  'coverage RPC is SECURITY DEFINER'
);
select is(
  (select proowner::regrole::text
   from pg_proc
   where oid = 'public.get_public_study_coverage_v1()'::regprocedure),
  'postgres',
  'coverage RPC is owned by postgres'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc
   where oid = 'public.get_public_study_coverage_v1()'::regprocedure),
  'coverage RPC fixes search_path to pg_catalog only'
);
select ok(
  has_function_privilege(
    'anon', 'public.get_public_study_coverage_v1()', 'execute'
  ),
  'anon can execute the bounded coverage RPC'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.get_public_study_coverage_v1()', 'execute'
  ),
  'authenticated can execute the bounded coverage RPC'
);
select ok(
  not has_function_privilege(
    'service_role', 'public.get_public_study_coverage_v1()', 'execute'
  ),
  'service_role cannot execute the browser coverage RPC directly'
);
select is(
  public.get_public_study_coverage_v1() ->> 'schemaVersion',
  '1.0.0',
  'coverage RPC emits its exact versioned contract'
);
select is(
  jsonb_array_length(public.get_public_study_coverage_v1() -> 'sources'),
  3,
  'coverage RPC exposes exactly the three reviewed safe source rows'
);
select doesnt_match(
  public.get_public_study_coverage_v1()::text,
  '(?i)(evidence|sha256|qualifying_hit|job_id|worker_id|gate|policy_id|source_policy)',
  'coverage RPC returns no evidence, numerator, job, worker, gate, or policy identity'
);
select doesnt_match(
  pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  ),
  '(?is)insert into ingest\.(source_items|extraction_runs|openings|public_study_observations)|insert into public\.country_period_map_cells',
  'coverage finalizer cannot write the statistical ledger or public inference table'
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
  'coverage ledger has no numerator or inference column'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.jobs'::regclass
     and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'),
  'cardchill-ascended-heroes-gb-90-v1',
  'scheduled job CHECK explicitly allowlists CardChill'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.jobs'::regclass
     and conname = 'jobs_reviewed_coverage_schedule_allowlist_check'),
  'bleedingcool-phantasmal-flames-us-36-v1',
  'scheduled job CHECK explicitly allowlists Bleeding Cool'
);

-- Exercise the exact service-role path, including durable enqueue, lease,
-- request-gate acquisition, denominator-only persistence and anonymous read.
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
  'me02.5',
  'Ascended Heroes',
  'pgtap-ascended-heroes',
  'en',
  '2026-01-30',
  'Mega Evolution',
  true,
  false
)
on conflict on constraint sets_external_identity_unique do update
set name = excluded.name,
    release_date = excluded.release_date,
    series_name = excluded.series_name,
    is_active = true,
    updated_at = clock_timestamp();

update ingest.source_policies
set last_attempt_at = null,
    updated_at = clock_timestamp()
where source_key = 'public_study_cardchill_gb_90';

set local role service_role;
select throws_ok(
  $sql$select * from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    null,
    date_trunc('minute', transaction_timestamp()),
    'cardchill-ascended-heroes-gb-90-v1',
    14,
    3
  )$sql$,
  '22023',
  'coverage schedule_name must match its exact study_key',
  'a null coverage schedule name is rejected by the reviewed RPC boundary'
);
select lives_ok(
  $sql$select * from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_cardchill-ascended-heroes-gb-90-v1',
    date_trunc('minute', transaction_timestamp()),
    'cardchill-ascended-heroes-gb-90-v1',
    1000,
    3
  )$sql$,
  'the exact reviewed coverage schedule can reserve one durable slot'
);
select is(
  (
    select count(*)::integer
    from ingest.schedule_slots
    where schedule_name = 'public_study_cardchill-ascended-heroes-gb-90-v1'
      and slot_at = date_trunc('minute', transaction_timestamp())
  ),
  1,
  'the coverage schedule persists exactly one durable slot'
);
select is(
  (
    select jobs.payload
    from ingest.schedule_slots as slots
    join ingest.jobs as jobs on jobs.id = slots.job_id
    where slots.schedule_name = 'public_study_cardchill-ascended-heroes-gb-90-v1'
      and slots.slot_at = date_trunc('minute', transaction_timestamp())
  ),
  jsonb_build_object('study_key', 'cardchill-ascended-heroes-gb-90-v1'),
  'the scheduled coverage job keeps the exact reviewed payload'
);
select set_config(
  'pokecrack.coverage_scheduled_job',
  (
    select slots.job_id::text
    from ingest.schedule_slots as slots
    where slots.schedule_name = 'public_study_cardchill-ascended-heroes-gb-90-v1'
      and slots.slot_at = date_trunc('minute', transaction_timestamp())
  ),
  true
);

do $coverage_runtime$
declare
  job_id_value uuid;
  claimed_job_id_value uuid;
  generation_value bigint;
  acquired_value boolean;
begin
  job_id_value := current_setting('pokecrack.coverage_scheduled_job')::uuid;

  select jobs.id, jobs.lease_generation
  into claimed_job_id_value, generation_value
  from ingest.claim_jobs_v2(
    'pgtap-coverage-worker',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  if claimed_job_id_value is distinct from job_id_value then
    raise exception 'the scheduled coverage job was not claimed exactly once';
  end if;

  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job_v2(
    job_id_value,
    'pgtap-coverage-worker',
    generation_value,
    'cardchill-ascended-heroes-gb-90-v1'
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'coverage request gate was not acquired';
  end if;

  perform ingest.finalize_public_study_coverage_job_v1(
    job_id_value,
    'pgtap-coverage-worker',
    generation_value,
    'cardchill-ascended-heroes-gb-90-v1',
    jsonb_build_object(
      'version', 1,
      'study_key', 'cardchill-ascended-heroes-gb-90-v1',
      'source_url', 'https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real',
      'title', 'Ripping 10 Ascended Heroes ETBs: Is the Mega Attack Pull Rate Real?',
      'evidence_excerpt', E'I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes.\nOut of 90 packs, I pulled 19 Double Rare (ex) cards.\nAcross 10 ETBs, I pulled exactly one SIR.',
      'evidence_sha256',
        '828293f936003eae257223efdbe5cd2a8fe8f799d6ca4bba9063e01fd476a9be',
      'collector_version', 'public-study-cardchill-ascended-heroes-v1',
      'parser_version', 'cardchill-ascended-heroes-evidence-v1',
      'source_policy_version', 'public-study-cardchill-ascended-heroes-v1'
    )
  );
  perform set_config('pokecrack.coverage_job', job_id_value::text, true);
end;
$coverage_runtime$;
reset role;

select is(
  (select count(*)::integer from ingest.public_study_coverage_observations),
  1,
  'the fenced verifier persists one immutable coverage observation'
);
select is(
  (select sum(pack_count)::integer from ingest.public_study_coverage_observations),
  90,
  'the coverage ledger persists only the reviewed denominator'
);
select is(
  (select status from ingest.jobs
   where id = current_setting('pokecrack.coverage_job')::uuid),
  'completed',
  'the dedicated finalizer completes the exact leased job'
);

set local role anon;
select set_config(
  'pokecrack.coverage_public_payload',
  public.get_public_study_coverage_v1()::text,
  true
);
reset role;
select is(
  jsonb_array_length(
    current_setting('pokecrack.coverage_public_payload')::jsonb -> 'countries'
  ),
  1,
  'anonymous coverage exposes one verified country denominator'
);
select is(
  (
    current_setting('pokecrack.coverage_public_payload')::jsonb
      #>> '{countries,0,packsObserved}'
  )::integer,
  90,
  'anonymous coverage reports the exact reviewed pack count'
);
select doesnt_match(
  current_setting('pokecrack.coverage_public_payload'),
  '(?i)(evidence|sha256|qualifying_hit|job_id|worker_id|gate|policy_id|source_policy)',
  'the anonymous runtime payload still exposes no private evidence or numerator'
);

select * from finish();
rollback;
