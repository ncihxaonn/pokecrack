-- Forward migration 260 keeps the shared service_role queue lifecycle inert
-- for Bluesky while preserving generic behavior for every other job family.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create function pg_temp.sqlstate_of(statement text)
returns text
language plpgsql
volatile
as $$
begin
  execute statement;
  return null;
exception
  when others then
    return sqlstate;
end;
$$;

select ok(
  (select prosecdef
      and proowner::regrole::text = 'postgres'
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, ingest']
   from pg_catalog.pg_proc
   where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'the shared claim boundary remains a postgres-owned fixed-search-path SECURITY DEFINER'
);
select ok(
  not has_function_privilege(
      'service_role',
      'ingest.claim_bluesky_jetstream_jobs_v1(text,integer)',
      'execute'
    )
    and has_function_privilege(
      'pokecrack_bluesky_worker',
      'ingest.claim_bluesky_jetstream_jobs_v1(text,integer)',
      'execute'
    ),
  'only the dedicated Bluesky capability can execute its claim wrapper'
);
select ok(
  (select prosecdef
      and not has_table_privilege(
        'pokecrack_bluesky_worker', 'ingest.jobs', 'select'
      )
      and not has_table_privilege(
        'pokecrack_bluesky_worker', 'ingest.jobs', 'insert'
      )
      and not has_table_privilege(
        'pokecrack_bluesky_worker', 'ingest.jobs', 'update'
      )
      and not has_table_privilege(
        'pokecrack_bluesky_worker', 'ingest.jobs', 'delete'
      )
   from pg_catalog.pg_proc
   where oid =
     'ingest.claim_bluesky_jetstream_jobs_v1(text,integer)'::regprocedure),
  'the dedicated wrapper is SECURITY DEFINER and the capability has no direct jobs table privileges'
);

insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, locked_at, lock_expires_at, locked_by, lease_generation,
  is_demo
) values
  (
    'bc000000-0000-4000-8000-000000000001',
    'source.bluesky.jetstream', '{}'::jsonb, 'pending', -50, 0, 3,
    clock_timestamp() - interval '1 minute', null, null, null, 0, false
  ),
  (
    'bc000000-0000-4000-8000-000000000002',
    'source.bluesky.jetstream', '{}'::jsonb, 'pending', -50, 3, 3,
    clock_timestamp() - interval '1 minute', null, null, null, 0, false
  ),
  (
    'bc000000-0000-4000-8000-000000000003',
    'source.bluesky.jetstream', '{}'::jsonb, 'running', -50, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'generic-queue-guard', 1, false
  ),
  (
    'bc000000-0000-4000-8000-000000000004',
    'source.bluesky.jetstream', '{}'::jsonb, 'running', -50, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'bluesky-collector-test', 1, false
  ),
  (
    'bc000000-0000-4000-8000-000000000005',
    'source.bluesky.jetstream', '{}'::jsonb, 'running', -50, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'bluesky-collector-test', 1, false
  ),
  (
    'bc000000-0000-4000-8000-000000000006',
    'queue.guard.other', '{}'::jsonb, 'pending', 0, 0, 3,
    clock_timestamp() - interval '1 minute', null, null, null, 0, false
  ),
  (
    'bc000000-0000-4000-8000-000000000007',
    'queue.guard.other', '{}'::jsonb, 'running', 0, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'generic-queue-guard', 1, false
  ),
  (
    'bc000000-0000-4000-8000-000000000008',
    'queue.guard.other', '{}'::jsonb, 'running', 0, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'generic-queue-guard', 1, false
  ),
  (
    'bc000000-0000-4000-8000-000000000009',
    'queue.guard.other', '{}'::jsonb, 'running', 0, 1, 3,
    clock_timestamp() - interval '1 minute',
    clock_timestamp() - interval '1 second',
    clock_timestamp() + interval '10 minutes',
    'generic-queue-guard', 1, false
  );

create temporary table bluesky_generic_before on commit drop as
select
  id,
  status,
  attempts,
  locked_by,
  locked_at,
  lock_expires_at,
  lease_generation,
  last_error_code,
  last_error_message,
  completed_at,
  updated_at
from ingest.jobs
where id in (
  'bc000000-0000-4000-8000-000000000001',
  'bc000000-0000-4000-8000-000000000002',
  'bc000000-0000-4000-8000-000000000003'
);

-- The shared service_role caller cannot claim Bluesky, including its
-- exhausted-row dead-letter sweep, and cannot mutate an existing lease.
set local role service_role;
select is(
  (select count(*)::integer from ingest.claim_jobs_v2(
    'generic-queue-guard', array['source.bluesky.jetstream'], 1, 600
  )),
  0,
  'generic service_role claim returns no Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.heartbeat_job_v2(
    'bc000000-0000-4000-8000-000000000003',
    'generic-queue-guard', 1, 600
  )),
  0,
  'generic service_role heartbeat is inert for a Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.fail_job_v2(
    'bc000000-0000-4000-8000-000000000003',
    'generic-queue-guard', 1, 'generic_guard', 'must remain inert', false
  )),
  0,
  'generic service_role failure is inert for a Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.pause_job_for_budget_v2(
    'bc000000-0000-4000-8000-000000000003',
    'generic-queue-guard', 1, clock_timestamp() + interval '1 hour'
  )),
  0,
  'generic service_role budget pause is inert for a Bluesky lease'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.complete_job_v2(
      'bc000000-0000-4000-8000-000000000003',
      'generic-queue-guard', 1
    )
  $sql$),
  '22023',
  'generic service_role completion rejects the dedicated Bluesky job type'
);
reset role;

select ok(
  (select count(*) = 2
      and bool_and(status = 'pending')
   from ingest.jobs
   where id in (
     'bc000000-0000-4000-8000-000000000001',
     'bc000000-0000-4000-8000-000000000002'
   )),
  'generic claim does not lease pending or dead-letter exhausted Bluesky jobs'
);
select ok(
  (select count(*) = 1
      and bool_and(
        jobs.status = baseline.status
        and jobs.attempts = baseline.attempts
        and jobs.locked_by is not distinct from baseline.locked_by
        and jobs.locked_at is not distinct from baseline.locked_at
        and jobs.lock_expires_at is not distinct from baseline.lock_expires_at
        and jobs.lease_generation = baseline.lease_generation
        and jobs.last_error_code is not distinct from baseline.last_error_code
        and jobs.last_error_message is not distinct from baseline.last_error_message
        and jobs.completed_at is not distinct from baseline.completed_at
        and jobs.updated_at = baseline.updated_at
      )
   from ingest.jobs as jobs
   join bluesky_generic_before as baseline using (id)
   where jobs.id = 'bc000000-0000-4000-8000-000000000003'),
  'generic lifecycle calls leave the existing Bluesky lease byte-for-byte unchanged'
);

-- A non-Bluesky job remains fully served by the same generic lifecycle.
set local role service_role;
select is(
  (select count(*)::integer from ingest.claim_jobs_v2(
    'generic-queue-guard', array['queue.guard.other'], 1, 600
  )),
  1,
  'generic claim still leases a non-Bluesky job'
);
select is(
  (select count(*)::integer from ingest.heartbeat_job_v2(
    'bc000000-0000-4000-8000-000000000007',
    'generic-queue-guard', 1, 600
  )),
  1,
  'generic heartbeat still renews a non-Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.fail_job_v2(
    'bc000000-0000-4000-8000-000000000008',
    'generic-queue-guard', 1, 'generic_failure', 'expected generic transition', false
  )),
  1,
  'generic failure still transitions a non-Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.pause_job_for_budget_v2(
    'bc000000-0000-4000-8000-000000000009',
    'generic-queue-guard', 1, clock_timestamp() + interval '1 hour'
  )),
  1,
  'generic budget pause still transitions a non-Bluesky lease'
);
reset role;
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'bc000000-0000-4000-8000-000000000006'),
  'the generic non-Bluesky claim records a live lease'
);
select ok(
  (select status = 'dead' and last_error_code = 'generic_failure'
   from ingest.jobs where id = 'bc000000-0000-4000-8000-000000000008'),
  'the generic non-Bluesky failure retains its terminal transition'
);
select ok(
  (select status = 'pending' and locked_by is null
   from ingest.jobs where id = 'bc000000-0000-4000-8000-000000000009'),
  'the generic non-Bluesky pause releases its lease'
);

-- The dedicated capability remains able to operate the exact Bluesky lane.
grant pokecrack_bluesky_worker to current_user with inherit false, set true;
set local role pokecrack_bluesky_worker;
select is(
  (select count(*)::integer from ingest.claim_bluesky_jetstream_jobs_v1(
    'bluesky-collector-test', 600
  )),
  1,
  'the dedicated wrapper claims one Bluesky job'
);
select is(
  (select count(*)::integer from ingest.heartbeat_bluesky_jetstream_job_v1(
    'bc000000-0000-4000-8000-000000000001',
    'bluesky-collector-test', 1, 600
  )),
  1,
  'the dedicated wrapper renews the Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.fail_bluesky_jetstream_job_v1(
    'bc000000-0000-4000-8000-000000000004',
    'bluesky-collector-test', 1, 'dedicated_failure',
    'expected dedicated transition', false
  )),
  1,
  'the dedicated wrapper can fail a Bluesky lease'
);
select is(
  (select count(*)::integer from ingest.pause_bluesky_jetstream_job_v1(
    'bc000000-0000-4000-8000-000000000005',
    'bluesky-collector-test', 1, clock_timestamp() + interval '1 hour'
  )),
  1,
  'the dedicated wrapper can pause a Bluesky lease'
);
reset role;
revoke pokecrack_bluesky_worker from current_user;

select ok(
  (select status = 'dead' and last_error_code = 'max_attempts_exhausted'
   from ingest.jobs where id = 'bc000000-0000-4000-8000-000000000002'),
  'the dedicated claim wrapper owns the Bluesky exhausted-row sweep'
);
select ok(
  (select status = 'dead' and last_error_code = 'dedicated_failure'
   from ingest.jobs where id = 'bc000000-0000-4000-8000-000000000004'),
  'the dedicated failure wrapper owns the Bluesky terminal transition'
);
select ok(
  (select status = 'pending' and locked_by is null
   from ingest.jobs where id = 'bc000000-0000-4000-8000-000000000005'),
  'the dedicated pause wrapper releases the Bluesky lease'
);

select * from finish();
rollback;
