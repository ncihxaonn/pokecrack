-- Final service-role boundary: table reads plus narrow SECURITY DEFINER RPCs.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(24);

select is(
  (select count(*)::integer
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname in ('catalog', 'ingest', 'analytics', 'public')
     and relations.relkind in ('r', 'p')
     and not (
       (
         schemas.nspname = 'analytics'
         and relations.relname in (
           'reviewed_global_aggregate_baselines',
           'reviewed_global_aggregate_audit',
           'reviewed_global_aggregate_independent_sources',
           'reviewed_global_aggregate_authorized_source_bindings',
           'reviewed_global_aggregate_input_admissions'
         )
       )
       or (
         schemas.nspname = 'ingest'
         and relations.relname in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions',
           'source_family_candidates', 'source_family_admissions',
           'source_family_tombstones', 'source_family_identity_keys',
           'source_family_runs', 'source_family_clock', 'source_family_control',
           'numbered_family_control', 'numbered_family_candidates',
           'numbered_family_admissions', 'numbered_family_identity_keys', 'numbered_family_runs',
           'research_intake_references', 'research_intake_control'
         )
       )
     )),
  52,
  'the least-privilege matrix covers every non-publication private application table'
);

select is(
  (select count(*)::integer
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname in ('catalog', 'ingest', 'analytics', 'public')
     and relations.relkind in ('r', 'p')
     and not (
       (
         schemas.nspname = 'analytics'
         and relations.relname in (
           'reviewed_global_aggregate_baselines',
           'reviewed_global_aggregate_audit',
           'reviewed_global_aggregate_independent_sources',
           'reviewed_global_aggregate_authorized_source_bindings',
           'reviewed_global_aggregate_input_admissions'
         )
       )
       or (
         schemas.nspname = 'ingest'
         and relations.relname in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions',
           'source_family_candidates', 'source_family_admissions',
           'source_family_tombstones', 'source_family_identity_keys',
           'source_family_runs', 'source_family_clock', 'source_family_control',
           'numbered_family_control', 'numbered_family_candidates',
           'numbered_family_admissions', 'numbered_family_identity_keys', 'numbered_family_runs',
           'research_intake_references', 'research_intake_control'
         )
       )
     )
     and has_table_privilege('service_role', relations.oid, 'select')),
  48,
  'service_role can read every non-private-publication table except the opaque request gate'
);

select ok(
  (select count(*) = 5
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'analytics'
     and relations.relkind in ('r', 'p')
     and relations.relname in (
       'reviewed_global_aggregate_baselines',
       'reviewed_global_aggregate_audit',
       'reviewed_global_aggregate_independent_sources',
       'reviewed_global_aggregate_authorized_source_bindings',
       'reviewed_global_aggregate_input_admissions'
     ))
  and (select bool_and(relations.relrowsecurity and relations.relforcerowsecurity)
       from pg_class as relations
       join pg_namespace as schemas on schemas.oid = relations.relnamespace
       where schemas.nspname = 'analytics'
         and relations.relname in (
           'reviewed_global_aggregate_baselines',
           'reviewed_global_aggregate_audit',
           'reviewed_global_aggregate_independent_sources',
           'reviewed_global_aggregate_authorized_source_bindings',
           'reviewed_global_aggregate_input_admissions'
         ))
  and (select count(*) = 0
       from pg_policies as policies
       where policies.schemaname = 'analytics'
         and policies.tablename in (
           'reviewed_global_aggregate_baselines',
           'reviewed_global_aggregate_audit',
           'reviewed_global_aggregate_independent_sources',
           'reviewed_global_aggregate_authorized_source_bindings',
           'reviewed_global_aggregate_input_admissions'
         ))
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'analytics'
      and relations.relname in (
        'reviewed_global_aggregate_baselines',
        'reviewed_global_aggregate_audit',
        'reviewed_global_aggregate_independent_sources',
        'reviewed_global_aggregate_authorized_source_bindings',
        'reviewed_global_aggregate_input_admissions'
      )
      and (
        has_table_privilege('service_role', relations.oid, 'select')
        or has_table_privilege('service_role', relations.oid, 'insert')
        or has_table_privilege('service_role', relations.oid, 'update')
        or has_table_privilege('service_role', relations.oid, 'delete')
        or has_table_privilege('service_role', relations.oid, 'truncate')
        or has_table_privilege('service_role', relations.oid, 'references')
        or has_table_privilege('service_role', relations.oid, 'trigger')
        or has_table_privilege('service_role', relations.oid, 'maintain')
      )
  )
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'analytics'
      and relations.relname in (
        'reviewed_global_aggregate_baselines',
        'reviewed_global_aggregate_audit',
        'reviewed_global_aggregate_independent_sources',
        'reviewed_global_aggregate_authorized_source_bindings',
        'reviewed_global_aggregate_input_admissions'
      )
      and (
        has_table_privilege('anon', relations.oid, 'select')
        or has_table_privilege('authenticated', relations.oid, 'select')
        or has_table_privilege('public', relations.oid, 'select')
      )
  ),
  'reviewed global aggregate inputs and foundation are explicit private force-RLS with no direct application access'
);

select ok(
  (select count(*) = 4
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'ingest'
     and relations.relkind in ('r', 'p')
     and relations.relname in (
       'authorized_opening_submissions',
       'authorized_opening_review_events',
       'authorized_opening_observations',
       'authorized_opening_retractions'
     ))
  and (select bool_and(relations.relrowsecurity and relations.relforcerowsecurity)
       from pg_class as relations
       join pg_namespace as schemas on schemas.oid = relations.relnamespace
       where schemas.nspname = 'ingest'
         and relations.relname in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         ))
  and (select count(*) = 4
       from pg_policies as policies
       where policies.schemaname = 'ingest'
         and policies.tablename in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         )
         and policies.roles = array['service_role']::name[]
         and policies.cmd = 'SELECT')
  and (select count(*) = 4
       from pg_class as relations
       join pg_namespace as schemas on schemas.oid = relations.relnamespace
       where schemas.nspname = 'ingest'
         and relations.relname in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         )
         and has_table_privilege('service_role', relations.oid, 'select'))
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'ingest'
      and relations.relname in (
        'authorized_opening_submissions',
        'authorized_opening_review_events',
        'authorized_opening_observations',
        'authorized_opening_retractions'
      )
      and (
        has_table_privilege('service_role', relations.oid, 'insert')
        or has_table_privilege('service_role', relations.oid, 'update')
        or has_table_privilege('service_role', relations.oid, 'delete')
        or has_table_privilege('service_role', relations.oid, 'truncate')
        or has_table_privilege('service_role', relations.oid, 'references')
        or has_table_privilege('service_role', relations.oid, 'trigger')
        or has_table_privilege('service_role', relations.oid, 'maintain')
      )
  )
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'ingest'
      and relations.relname in (
        'authorized_opening_submissions',
        'authorized_opening_review_events',
        'authorized_opening_observations',
        'authorized_opening_retractions'
      )
      and (
        has_table_privilege('anon', relations.oid, 'select')
        or has_table_privilege('authenticated', relations.oid, 'select')
        or has_table_privilege('public', relations.oid, 'select')
      )
  ),
  'authorized-opening ledgers are explicit private force-RLS, SELECT-only service tables'
);

select is(
  (select count(*)::integer
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname in ('catalog', 'ingest', 'analytics', 'public')
     and relations.relkind in ('r', 'p')
     and (
       has_table_privilege('service_role', relations.oid, 'insert')
       or has_table_privilege('service_role', relations.oid, 'update')
       or has_table_privilege('service_role', relations.oid, 'delete')
       or has_table_privilege('service_role', relations.oid, 'truncate')
       or has_table_privilege('service_role', relations.oid, 'references')
       or has_table_privilege('service_role', relations.oid, 'trigger')
     )),
  0,
  'service_role has no direct mutation privilege on any application table'
);

select ok(
  not has_table_privilege('service_role', 'ingest.source_request_gates', 'select'),
  'request-gate ownership remains opaque to service_role'
);

select ok(
  has_table_privilege('service_role', 'ingest.source_request_gates', 'maintain'),
  'service_role can lock the opaque request gate for schema-only backup'
);

select ok(
  not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'ingest'
      and relations.relname in (
        'nostr_relay_candidates',
        'nostr_relay_observations',
        'nostr_relay_checkpoints'
      )
      and has_table_privilege('service_role', relations.oid, 'select')
  ),
  'service_role cannot read the isolated Nostr activity ledgers'
);

select is(
  (select count(*)::integer
   from pg_policies
   where schemaname in ('catalog', 'ingest', 'analytics', 'public')
     and 'service_role' = any(roles)
     and cmd = 'ALL'),
  0,
  'no broad service_role FOR ALL policy survives the migration'
);

select is(
  (select count(*)::integer
   from pg_policies
   where schemaname in ('catalog', 'ingest', 'analytics', 'public')
     and 'service_role' = any(roles)
     and cmd = 'SELECT'
     and not (
       (
         schemaname = 'analytics'
         and tablename in (
           'reviewed_global_aggregate_baselines',
           'reviewed_global_aggregate_audit',
           'reviewed_global_aggregate_independent_sources',
           'reviewed_global_aggregate_authorized_source_bindings',
           'reviewed_global_aggregate_input_admissions'
         )
       )
       or (
         schemaname = 'ingest'
         and tablename in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         )
       )
     )),
  48,
  'every readable non-private-publication service_role table has one read-only policy; isolated ledgers have none'
);

select ok(
  (select bool_and(
      has_function_privilege('service_role', functions.oid, 'execute')
      and not has_function_privilege('anon', functions.oid, 'execute')
      and not has_function_privilege('authenticated', functions.oid, 'execute')
    )
   from unnest(array[
     'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure,
     'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamp with time zone)'::regprocedure,
     'ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)'::regprocedure,
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure,
     'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
     'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
     'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamp with time zone,text,integer,integer)'::regprocedure
   ]) as functions(oid)),
  'only service_role can execute the replacement worker write RPCs'
);

select ok(
  (select bool_and(procedures.prosecdef)
   from pg_proc as procedures
   where procedures.oid = any(array[
     'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure,
     'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamp with time zone)'::regprocedure,
     'ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)'::regprocedure,
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure,
     'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
     'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
     'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamp with time zone,text,integer,integer)'::regprocedure
   ])),
  'replacement worker write RPCs are SECURITY DEFINER'
);

select ok(
  (select bool_and(coalesce(procedures.proconfig, '{}'::text[]) @> array['search_path=pg_catalog'])
   from pg_proc as procedures
   where procedures.oid = any(array[
     'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure,
     'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamp with time zone)'::regprocedure,
     'ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)'::regprocedure,
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure,
     'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
     'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
     'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamp with time zone,integer)'::regprocedure,
     'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamp with time zone,text,integer,integer)'::regprocedure
   ])),
  'replacement worker write RPCs use an immutable catalog-only search_path'
);

set local role service_role;
do $service_role_runtime$
declare
  denied_state text;
  heartbeat_at timestamptz;
  youtube_job_id uuid;
  youtube_generation bigint;
  youtube_acquired boolean;
  finalized_count integer;
  cleanup_job_id uuid;
  cleanup_generation bigint;
  paused_count integer;
begin
  begin
    update catalog.sets set name = name where false;
    denied_state := 'allowed';
  exception when others then
    denied_state := sqlstate;
  end;
  perform set_config('pokecrack.catalog_dml_state', denied_state, true);

  begin
    update ingest.jobs set updated_at = updated_at where false;
    denied_state := 'allowed';
  exception when others then
    denied_state := sqlstate;
  end;
  perform set_config('pokecrack.ingest_dml_state', denied_state, true);

  begin
    update analytics.dashboard_daily set computed_at = computed_at where false;
    denied_state := 'allowed';
  exception when others then
    denied_state := sqlstate;
  end;
  perform set_config('pokecrack.analytics_dml_state', denied_state, true);

  begin
    update public.dashboard_overview set generated_at = generated_at where false;
    denied_state := 'allowed';
  exception when others then
    denied_state := sqlstate;
  end;
  perform set_config('pokecrack.public_dml_state', denied_state, true);

  select heartbeats.last_seen_at
  into heartbeat_at
  from ingest.upsert_worker_heartbeat_v1(
    'least-privilege-watchdog',
    'watchdog',
    'test-v1',
    '{"command":"health","data_mode":"live","max_concurrency":1,"role_ready":true}'::jsonb
  ) as heartbeats;
  perform set_config('pokecrack.heartbeat_rpc_ok', (heartbeat_at is not null)::text, true);

  select enqueued.id
  into youtube_job_id
  from ingest.enqueue_job_v1(
    'source.youtube.discovery',
    '{"query_name":"pokemon-tcg-pack-opening"}'::jsonb,
    999,
    'least-privilege:youtube',
    clock_timestamp(),
    3
  ) as enqueued;
  select claimed.id, claimed.lease_generation
  into youtube_job_id, youtube_generation
  from ingest.claim_jobs_v2(
    'least-privilege-collector', array['source.youtube.discovery'], 1, 600
  ) as claimed;
  select begun.acquired
  into youtube_acquired
  from ingest.begin_youtube_discovery_job(
    youtube_job_id, 'least-privilege-collector', youtube_generation
  ) as begun;
  select count(*)::integer
  into finalized_count
  from ingest.finalize_youtube_discovery_job(
    youtube_job_id,
    'least-privilege-collector',
    youtube_generation,
    '{"version":1,"query_name":"pokemon-tcg-pack-opening","items":[{"external_id":"leastpriv01","source_url":"https://www.youtube.com/watch?v=leastpriv01","title":"Least privilege fixture","published_at":null,"collector_version":"youtube-global-discovery-v1","source_policy_version":"youtube-global-discovery-v1"}]}'::jsonb
  );
  perform set_config('pokecrack.youtube_begin_ok', coalesce(youtube_acquired, false)::text, true);
  perform set_config('pokecrack.youtube_finalize_count', finalized_count::text, true);

  perform ingest.enqueue_job_v1(
    'maintenance.cleanup', '{}'::jsonb, 998,
    'least-privilege:cleanup', clock_timestamp(), 3
  );
  select claimed.id, claimed.lease_generation
  into cleanup_job_id, cleanup_generation
  from ingest.claim_jobs_v2(
    'least-privilege-watchdog', array['maintenance.cleanup'], 1, 600
  ) as claimed;
  begin
    perform ingest.complete_job_v2(
      cleanup_job_id, 'least-privilege-watchdog', cleanup_generation
    );
    denied_state := 'allowed';
  exception when others then
    denied_state := sqlstate;
  end;
  perform set_config('pokecrack.typed_completion_state', denied_state, true);
  select count(*)::integer
  into paused_count
  from ingest.pause_job_for_budget_v2(
    cleanup_job_id,
    'least-privilege-watchdog',
    cleanup_generation,
    clock_timestamp() + interval '1 hour'
  );
  perform set_config('pokecrack.pause_rpc_count', paused_count::text, true);
end;
$service_role_runtime$;
reset role;

select is(current_setting('pokecrack.catalog_dml_state'), '42501', 'service_role catalog UPDATE is denied by grants');
select is(current_setting('pokecrack.ingest_dml_state'), '42501', 'service_role ingest UPDATE is denied by grants');
select is(current_setting('pokecrack.analytics_dml_state'), '42501', 'service_role analytics UPDATE is denied by grants');
select is(current_setting('pokecrack.public_dml_state'), '42501', 'service_role public UPDATE is denied by grants');
select is(current_setting('pokecrack.heartbeat_rpc_ok'), 'true', 'bounded heartbeat RPC succeeds without direct table DML');
select is(current_setting('pokecrack.youtube_begin_ok'), 'true', 'bounded enqueue and YouTube preflight RPCs succeed');
select is(current_setting('pokecrack.youtube_finalize_count'), '1', 'fenced YouTube finalizer succeeds under read-only table grants');
select is(
  (select count(*)::integer from ingest.youtube_discoveries where video_id = 'leastpriv01'),
  1,
  'fenced finalizer persists its dedicated cache row'
);
select is(current_setting('pokecrack.typed_completion_state'), '22023', 'generic completion cannot bypass a typed finalizer');
select is(current_setting('pokecrack.pause_rpc_count'), '1', 'fenced budget pause remains available without direct table DML');
select is(
  (select count(*)::integer
   from ingest.worker_heartbeats
   where worker_id = 'least-privilege-watchdog' and not is_demo),
  1,
  'heartbeat RPC wrote exactly one live row'
);

select * from finish();
rollback;
