-- The isolated Bluesky lane must be a first-class runtime-evidence service
-- set, not a health-only deployment exception. This test provisions only the
-- disposable login edge required by the boolean attestation; the transaction
-- rolls it back and never supplies a password.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create role pokecrack_bluesky_worker_login
  login
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls
  connection limit 2;
grant pokecrack_bluesky_worker to pokecrack_bluesky_worker_login
  with inherit false, set true;

select ok(
  (select count(*) = 7 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_bluesky_release_v1())),
  'the dedicated Bluesky capability attestation is fully ready before runtime verification'
);

select is(
  ingest.bluesky_worker_runtime_ready_v1(),
  true,
  'the dedicated Bluesky runtime readiness function compiles and accepts the reviewed endpoint contract'
);

select is(
  jsonb_typeof(ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  )),
  'object',
  'the aggregate runtime verifier accepts the exact Bluesky service set'
);

select is(
  (ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  ) -> 'workers' ->> 'expected_count')::integer,
  4,
  'Bluesky runtime evidence expects the three core workers and one dedicated collector'
);

select is(
  (ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  ) -> 'checkpoints' ->> 'expected_count')::integer,
  2,
  'Bluesky runtime evidence expects only the catalog and Bluesky checkpoints'
);

select ok(
  (ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  ) ->> 'status') in ('healthy', 'warming_up', 'failed'),
  'Bluesky runtime evidence returns an explicit bounded status'
);

select ok(
  not (ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  ))::text ~* '"(payload|url|cursor|policy_id|gate_id|worker_id|job_id|credential|identity)"\\s*:',
  'Bluesky runtime evidence remains aggregate-only'
);

-- A normal bounded collector run owns its request gate while the release
-- verifier executes.  That active state is valid only when the lease and
-- dedicated worker identity exactly match; it must not make deployment
-- evidence intermittently fail just because collection is in progress.
with active_job as (
  insert into ingest.jobs (
    job_type,
    payload,
    status,
    attempts,
    max_attempts,
    locked_at,
    lock_expires_at,
    locked_by,
    lease_generation,
    retention_until,
    is_demo
  ) values (
    'source.bluesky.jetstream',
    '{}'::jsonb,
    'running',
    1,
    5,
    clock_timestamp(),
    clock_timestamp() + interval '2 minutes',
    'bluesky-collector-runtime-evidence',
    1,
    clock_timestamp() + interval '90 days',
    false
  )
  returning id, lease_generation, locked_at, lock_expires_at
)
update ingest.source_request_gates as gates
set owner_job_id = active_job.id,
    owner_lease_generation = active_job.lease_generation,
    acquired_at = active_job.locked_at,
    active_until = active_job.lock_expires_at
from active_job
where gates.source_key = 'bluesky_jetstream';

select ok(
  (select count(*) = 7 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_bluesky_release_v1())),
  'a fresh active Bluesky gate tied to its exact dedicated lease remains ready'
);

select is(
  jsonb_typeof(ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
  )),
  'object',
  'runtime evidence accepts an exact active Bluesky gate'
);

update ingest.jobs
set locked_by = 'foreign-runtime-evidence'
where locked_by = 'bluesky-collector-runtime-evidence';

select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_policy_exact',
  'false'::jsonb,
  'a gate held by a non-dedicated worker fails the Bluesky policy contract closed'
);

update ingest.jobs
set locked_by = 'bluesky-collector-runtime-evidence'
where locked_by = 'foreign-runtime-evidence';

update ingest.source_request_gates
set owner_lease_generation = owner_lease_generation + 1
where source_key = 'bluesky_jetstream';

select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_policy_exact',
  'false'::jsonb,
  'a gate with a mismatched lease generation fails the Bluesky policy contract closed'
);

update ingest.source_request_gates
set owner_lease_generation = owner_lease_generation - 1
where source_key = 'bluesky_jetstream';

select ok(
  (select count(*) = 7 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_bluesky_release_v1())),
  'the exact active gate returns to ready after temporary drift is removed'
);

alter role pokecrack_bluesky_worker_login set statement_timeout = '1s';
select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 21600, 180, 'tcgdex-bluesky'
    )$$,
  NULL,
  'runtime evidence Bluesky capability is unavailable or drifted',
  'Bluesky role drift fails closed before aggregate evidence is returned'
);
alter role pokecrack_bluesky_worker_login reset statement_timeout;

select * from finish();
rollback;
