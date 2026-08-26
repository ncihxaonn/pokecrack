-- Lease-generation fencing and atomic cleanup finalization contract.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(50);

select has_column('ingest', 'jobs', 'lease_generation', 'jobs carry a per-lease fencing generation');
select col_type_is('ingest', 'jobs', 'lease_generation', 'bigint', 'lease generation is a monotonic bigint');
select col_not_null('ingest', 'jobs', 'lease_generation', 'every job has a fencing generation');
select matches(
  (select pg_get_constraintdef(c.oid)
   from pg_constraint c
   where c.conrelid = 'ingest.jobs'::regclass
     and c.conname = 'jobs_lease_generation_check'),
  '(?is)lease_generation\s*>=\s*0',
  'lease generation cannot become negative'
);

select has_function('ingest', 'claim_jobs_v2', array['text', 'text[]', 'integer', 'integer'], 'generation-aware claim function exists');
select ok(
  (select prosecdef from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'claim_jobs_v2 is SECURITY DEFINER'
);
select ok(
  (select proretset and prorettype = 'ingest.jobs'::regtype
   from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'claim_jobs_v2 returns SETOF ingest.jobs'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, ingest']
   from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'claim_jobs_v2 fixes its search path'
);
select ok(
  (select pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure)
      ~* 'for\s+update\s+of\s+j\s+skip\s+locked'
    and pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure)
      ~* 'lease_generation\s*=\s*j\.lease_generation\s*\+\s*1'),
  'claim_jobs_v2 locks candidates and rotates the fencing generation'
);
select ok(has_function_privilege('service_role', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'service_role can use claim_jobs_v2');
select ok(not has_function_privilege('anon', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'anon cannot claim jobs');
select ok(not has_function_privilege('authenticated', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'authenticated cannot claim jobs');
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) as acl
    where p.oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure
      and acl.grantee = 0
      and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot use claim_jobs_v2'
);
select ok(not has_function_privilege('service_role', 'ingest.claim_jobs(text,text[],integer,integer)', 'execute'), 'service_role cannot use the legacy claim protocol');
select throws_ok(
  $$select * from ingest.claim_jobs('legacy-worker', null, 1, 60)$$,
  '0A000',
  'claim_jobs is disabled; deploy a lease-fencing worker that uses claim_jobs_v2',
  'legacy claim fails closed even for an owner session'
);

select has_function('ingest', 'finalize_cleanup_job', array['uuid', 'text', 'bigint'], 'typed cleanup finalizer exists');
select ok(
  (select prosecdef from pg_proc where oid = 'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure),
  'cleanup finalizer is SECURITY DEFINER'
);
select ok(
  (select proretset and prorettype = 'ingest.jobs'::regtype
   from pg_proc where oid = 'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure),
  'cleanup finalizer returns exactly the completed job row'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = 'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure),
  'cleanup finalizer fixes its search path to pg_catalog'
);
select ok(
  (select pg_get_functiondef('ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure)
      ~* 'for\s+update\s+of\s+j'
    and pg_get_functiondef('ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure)
      ~* 'perform\s+ingest\.prune_expired_ephemera_v2'
    and pg_get_functiondef('ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure)
      ~* 'update\s+ingest\.jobs'),
  'cleanup finalizer locks the lease, performs cleanup, and completes in one function'
);
select ok(has_function_privilege('service_role', 'ingest.finalize_cleanup_job(uuid,text,bigint)', 'execute'), 'service_role can execute the fenced finalizer');
select ok(not has_function_privilege('anon', 'ingest.finalize_cleanup_job(uuid,text,bigint)', 'execute'), 'anon cannot finalize cleanup');
select ok(not has_function_privilege('authenticated', 'ingest.finalize_cleanup_job(uuid,text,bigint)', 'execute'), 'authenticated cannot finalize cleanup');
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) as acl
    where p.oid = 'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
      and acl.grantee = 0
      and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot finalize cleanup'
);
select ok(
  not has_function_privilege('service_role', 'ingest.prune_expired_ephemera(timestamp with time zone,integer)', 'execute'),
  'service_role cannot execute the legacy naked cleanup entry point'
);
select throws_ok(
  $$select ingest.prune_expired_ephemera()$$,
  '0A000',
  'prune_expired_ephemera is disabled; cleanup must use a fenced job finalizer',
  'legacy naked cleanup fails closed even for an owner session'
);

insert into ingest.source_policies (
  id, source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, config, version, is_demo
) values (
  'fb000000-0000-4000-8000-000000000001', 'fencing-test', 'Fencing Test',
  'fixture', 'fencing.pokecrack.invalid', 'https://fencing.pokecrack.invalid', false,
  'manual_import', 'manual', 'not_applicable', array['manual_import'], '{}', 'test-v1', false
);

insert into ingest.source_items (
  id, source_policy_id, source_url, normalized_url, domain, title, text_excerpt,
  discovered_at, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, usage_classification, source_kind,
  status, metadata, expires_at, is_demo
) values (
  'fb100000-0000-4000-8000-000000000001',
  'fb000000-0000-4000-8000-000000000001',
  'https://fencing.pokecrack.invalid/stale-effect',
  'https://fencing.pokecrack.invalid/stale-effect',
  'fencing.pokecrack.invalid', 'Expired fenced source', 'must survive stale lease',
  clock_timestamp() - interval '2 days', repeat('f', 64), 'manual_import',
  'test-v1', 'test-v1', 'manual', 'operations', 'fixture', 'discovered', '{}',
  clock_timestamp() - interval '1 day', false
);

insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fb200000-0000-4000-8000-000000000001', 'maintenance.cleanup', '{}',
  'pending', 10, 0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);

select is(
  (select lease_generation from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000001'),
  0::bigint,
  'new jobs start at generation zero before their first claim'
);

create temporary table fencing_first_claim on commit drop as
select * from ingest.claim_jobs_v2('watchdog-reused', array['maintenance.cleanup'], 1, 60);
select is((select count(*)::integer from fencing_first_claim), 1, 'the first worker attempt claims the cleanup job');
select is((select lease_generation from fencing_first_claim), 1::bigint, 'the first claim rotates generation to one');

update ingest.jobs
set locked_at = clock_timestamp() - interval '2 minutes',
    lock_expires_at = clock_timestamp() - interval '1 minute'
where id = 'fb200000-0000-4000-8000-000000000001';

select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fb200000-0000-4000-8000-000000000001', 'watchdog-reused', 1
  )),
  0,
  'an expired lease cannot finalize even when owner and generation still match'
);
select is(
  (select text_excerpt from ingest.source_items where id = 'fb100000-0000-4000-8000-000000000001'),
  'must survive stale lease',
  'an expired matching lease performs no cleanup effect'
);

create temporary table fencing_second_claim on commit drop as
select * from ingest.claim_jobs_v2('watchdog-reused', array['maintenance.cleanup'], 1, 60);
select is((select count(*)::integer from fencing_second_claim), 1, 'the same stable worker ID can reclaim an expired attempt');
select is((select lease_generation from fencing_second_claim), 2::bigint, 'reclaim rotates generation despite worker ID reuse');

select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fb200000-0000-4000-8000-000000000001', 'watchdog-reused', 1
  )),
  0,
  'the stale first generation cannot finalize the reclaimed job'
);
select is(
  (select text_excerpt from ingest.source_items where id = 'fb100000-0000-4000-8000-000000000001'),
  'must survive stale lease',
  'stale cleanup finalization performs no cleanup effect'
);
select ok(
  (select status = 'running' and lease_generation = 2 and locked_by = 'watchdog-reused'
   from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000001'),
  'stale finalization leaves the new lease untouched'
);
select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fb200000-0000-4000-8000-000000000001', 'different-worker', 2
  )),
  0,
  'the current generation is insufficient without the exact worker identity'
);
select is(
  (select text_excerpt from ingest.source_items where id = 'fb100000-0000-4000-8000-000000000001'),
  'must survive stale lease',
  'wrong-owner finalization also performs no cleanup effect'
);

create function pg_temp.reject_fenced_completion()
returns trigger
language plpgsql
as $$
begin
  if new.id = 'fb200000-0000-4000-8000-000000000001'::uuid
    and new.status = 'completed'
  then
    raise exception using errcode = 'P0001', message = 'forced cleanup completion failure';
  end if;
  return new;
end;
$$;

create trigger reject_fenced_completion
before update on ingest.jobs
for each row execute function pg_temp.reject_fenced_completion();

select throws_ok(
  $$select * from ingest.finalize_cleanup_job('fb200000-0000-4000-8000-000000000001', 'watchdog-reused', 2)$$,
  'P0001',
  'forced cleanup completion failure',
  'a completion failure aborts the atomic cleanup finalizer'
);
select is(
  (select text_excerpt from ingest.source_items where id = 'fb100000-0000-4000-8000-000000000001'),
  'must survive stale lease',
  'cleanup effects roll back when completion fails'
);
select ok(
  (select status = 'running' and lease_generation = 2
   from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000001'),
  'the job transition rolls back with its cleanup effects'
);

drop trigger reject_fenced_completion on ingest.jobs;

create temporary table fencing_completed_job on commit drop as
select * from ingest.finalize_cleanup_job(
  'fb200000-0000-4000-8000-000000000001', 'watchdog-reused', 2
);
select is((select count(*)::integer from fencing_completed_job), 1, 'the current fenced lease finalizes exactly once');
select ok(
  (select status = 'completed' and lease_generation = 2 from fencing_completed_job),
  'the finalizer returns the completed job with its immutable generation'
);
select is(
  (select text_excerpt from ingest.source_items where id = 'fb100000-0000-4000-8000-000000000001'),
  null::text,
  'valid finalization commits the cleanup effect'
);
select ok(
  (select status = 'completed'
      and completed_at is not null
      and locked_by is null
      and locked_at is null
      and lock_expires_at is null
   from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000001'),
  'valid finalization commits job completion in the same call'
);
select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fb200000-0000-4000-8000-000000000001', 'watchdog-reused', 2
  )),
  0,
  'repeating a completed finalizer is a no-op'
);

insert into ingest.jobs (
  id, job_type, payload, status, attempts, max_attempts, available_at,
  retention_until, is_demo
) values (
  'fb200000-0000-4000-8000-000000000002', 'maintenance.cleanup', '{"unexpected":true}',
  'pending', 0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
create temporary table fencing_bad_payload_claim on commit drop as
select * from ingest.claim_jobs_v2('watchdog-payload', array['maintenance.cleanup'], 1, 60);
select throws_ok(
  $$select * from ingest.finalize_cleanup_job('fb200000-0000-4000-8000-000000000002', 'watchdog-payload', 1)$$,
  '22023',
  'cleanup finalizer requires a live maintenance.cleanup job with an empty payload',
  'the typed finalizer rejects an unexpected cleanup payload before effects'
);
select is(
  (select status from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000002'),
  'running',
  'invalid cleanup payload leaves its lease running for normal failure handling'
);

insert into ingest.jobs (
  id, job_type, payload, status, attempts, max_attempts, available_at,
  locked_by, locked_at, lock_expires_at, lease_generation, retention_until, is_demo
) values (
  'fb200000-0000-4000-8000-000000000003', 'deadletter.test', '{}', 'running',
  3, 3, clock_timestamp() - interval '1 hour', 'crashed-worker',
  clock_timestamp() - interval '2 minutes', clock_timestamp() - interval '1 minute',
  7, clock_timestamp() + interval '90 days', false
);
select is(
  (select count(*)::integer from ingest.claim_jobs_v2('deadletter-worker', array['deadletter.test'], 1, 60)),
  0,
  'an expired max-attempt lease is dead-lettered instead of reclaimed'
);
select ok(
  (select status = 'dead'
      and lease_generation = 8
      and completed_at is not null
      and locked_by is null
      and locked_at is null
      and lock_expires_at is null
   from ingest.jobs where id = 'fb200000-0000-4000-8000-000000000003'),
  'dead-lettering also invalidates the expired generation'
);

select * from finish();
rollback;
