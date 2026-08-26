begin;

alter table ingest.jobs
  add column lease_generation bigint not null default 0;

alter table ingest.jobs
  add constraint jobs_lease_generation_check
  check (lease_generation >= 0);

comment on column ingest.jobs.lease_generation is
  'Monotonic fencing generation. Every claim rotates the lease authority even when worker_id is reused.';

-- This protocol upgrade is intentionally stop-the-world for workers. Any lease
-- created by the legacy owner-only protocol is invalidated before v2 claims can
-- be issued. Cleanup is the only live handler at this point and is idempotent;
-- future non-idempotent handlers require their own typed finalizer before use.
with migration_clock as (
  select clock_timestamp() as now
)
update ingest.jobs as j
set status = case
      when j.attempts >= j.max_attempts then 'dead'
      else 'pending'
    end,
    lease_generation = j.lease_generation + 1,
    locked_by = null,
    locked_at = null,
    lock_expires_at = null,
    available_at = case
      when j.attempts >= j.max_attempts then j.available_at
      else migration_clock.now
    end,
    completed_at = case
      when j.attempts >= j.max_attempts then migration_clock.now
      else null
    end,
    last_error_code = 'worker_protocol_upgrade',
    last_error_message = 'lease invalidated during fencing protocol upgrade',
    updated_at = migration_clock.now
from migration_clock
where j.status = 'running';

-- Preserve the reviewed cleanup implementation behind a new internal name,
-- then make the legacy naked entry point fail closed even for a postgres-owner
-- DSN. This prevents a stopped-but-accidentally-restarted old worker binary
-- from recreating the effect/completion split after the protocol migration.
alter function ingest.prune_expired_ephemera(timestamptz, integer)
  rename to prune_expired_ephemera_v2;

revoke all on function ingest.prune_expired_ephemera_v2(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_expired_ephemera_v2(timestamptz, integer) is
  'Internal bounded cleanup implementation. Callable only by a typed fenced finalizer owned by postgres.';

create or replace function ingest.prune_expired_ephemera(
  cutoff timestamptz default now(),
  max_rows integer default 10000
)
returns jsonb
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  raise exception using
    errcode = '0A000',
    message = 'prune_expired_ephemera is disabled; cleanup must use a fenced job finalizer';
end;
$$;

alter function ingest.prune_expired_ephemera(timestamptz, integer) owner to postgres;
revoke all on function ingest.prune_expired_ephemera(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_expired_ephemera(timestamptz, integer) is
  'Disabled legacy naked cleanup entry point. Workers must finalize a generation-fenced cleanup job.';

-- Legacy workers must fail closed instead of silently claiming a generation
-- they do not understand. The signature remains only to produce an explicit,
-- actionable protocol error during a stopped-worker deployment or rollback.
create or replace function ingest.claim_jobs(
  worker_id text,
  job_types text[] default null,
  batch_size integer default 1,
  lease_seconds integer default 300
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog, ingest
as $$
begin
  raise exception using
    errcode = '0A000',
    message = 'claim_jobs is disabled; deploy a lease-fencing worker that uses claim_jobs_v2';
end;
$$;

alter function ingest.claim_jobs(text, text[], integer, integer) owner to postgres;
revoke all on function ingest.claim_jobs(text, text[], integer, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.claim_jobs(text, text[], integer, integer) is
  'Disabled legacy owner-only claim protocol. Generation-aware workers must use claim_jobs_v2.';

create or replace function ingest.claim_jobs_v2(
  worker_id text,
  job_types text[] default null,
  batch_size integer default 1,
  lease_seconds integer default 300
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog, ingest
as $$
declare
  sweep_time timestamptz := clock_timestamp();
  claim_time timestamptz;
begin
  if worker_id is null or btrim(worker_id) = '' or char_length(worker_id) > 160 then
    raise exception using errcode = '22023', message = 'worker_id must contain 1 to 160 characters';
  end if;
  if job_types is not null and (cardinality(job_types) = 0 or array_position(job_types, null) is not null) then
    raise exception using errcode = '22023', message = 'job_types must be null or a non-empty array without nulls';
  end if;
  if batch_size is null or batch_size < 1 or batch_size > 100 then
    raise exception using errcode = '22023', message = 'batch_size must be between 1 and 100';
  end if;
  if lease_seconds is null or lease_seconds < 1 or lease_seconds > 86400 then
    raise exception using errcode = '22023', message = 'lease_seconds must be between 1 and 86400';
  end if;

  update ingest.jobs as exhausted
  set status = 'dead',
      lease_generation = case
        when exhausted.status = 'running' then exhausted.lease_generation + 1
        else exhausted.lease_generation
      end,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      last_error_code = case
        when exhausted.status = 'running' then 'lease_expired_max_attempts'
        else 'max_attempts_exhausted'
      end,
      last_error_message = case
        when exhausted.status = 'running' then 'expired lease exhausted the maximum attempts'
        else 'job reached the maximum attempts before claim'
      end,
      completed_at = sweep_time,
      updated_at = sweep_time
  where exhausted.attempts >= exhausted.max_attempts
    and not exhausted.is_demo
    and (
      (exhausted.status = 'pending' and exhausted.available_at <= sweep_time)
      or (exhausted.status = 'running' and exhausted.lock_expires_at <= sweep_time)
    );

  -- The exhausted-row sweep is intentionally unbounded. Refresh the lease
  -- clock afterwards so a large sweep cannot issue an already-expired lease.
  claim_time := clock_timestamp();

  return query
  with claimable as materialized (
    select j.id
    from ingest.jobs as j
    where j.attempts < j.max_attempts
      and not j.is_demo
      and (job_types is null or j.job_type = any(job_types))
      and (
        (j.status = 'pending' and j.available_at <= claim_time)
        or (j.status = 'running' and j.lock_expires_at <= claim_time)
      )
    order by j.priority desc, j.available_at, j.created_at, j.id
    for update of j skip locked
    limit batch_size
  )
  update ingest.jobs as j
  set status = 'running',
      lease_generation = j.lease_generation + 1,
      locked_at = claim_time,
      lock_expires_at = claim_time + make_interval(secs => lease_seconds),
      locked_by = worker_id,
      attempts = j.attempts + 1,
      last_error_code = null,
      last_error_message = null,
      updated_at = claim_time,
      completed_at = null
  from claimable
  where j.id = claimable.id
  returning j.*;
end;
$$;

alter function ingest.claim_jobs_v2(text, text[], integer, integer) owner to postgres;
revoke all on function ingest.claim_jobs_v2(text, text[], integer, integer)
  from public, anon, authenticated;
grant execute on function ingest.claim_jobs_v2(text, text[], integer, integer)
  to service_role;
comment on function ingest.claim_jobs_v2(text, text[], integer, integer) is
  'Atomically claims live jobs with a monotonically increasing per-lease fencing generation.';

create or replace function ingest.finalize_cleanup_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  leased_job ingest.jobs%rowtype;
  completed_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
  completion_time timestamptz;
begin
  if $1 is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if $2 is null or btrim($2) = '' or char_length($2) > 160 then
    raise exception using errcode = '22023', message = 'worker_id must contain 1 to 160 characters';
  end if;
  if $3 is null or $3 < 1 then
    raise exception using errcode = '22023', message = 'lease_generation must be positive';
  end if;

  select j.*
  into leased_job
  from ingest.jobs as j
  where j.id = $1
  for update of j;

  if not found then
    return;
  end if;

  -- Check the database clock only after acquiring the row lock. A finalizer
  -- waiting behind another transition cannot authorize itself from stale time.
  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from $2
    or leased_job.lease_generation <> $3
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if leased_job.is_demo
    or leased_job.job_type <> 'maintenance.cleanup'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'cleanup finalizer requires a live maintenance.cleanup job with an empty payload';
  end if;

  perform ingest.prune_expired_ephemera_v2(
    cutoff => lease_checked_at,
    max_rows => 10000
  );

  completion_time := clock_timestamp();
  update ingest.jobs as j
  set status = 'completed',
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = completion_time,
      last_error_code = null,
      last_error_message = null,
      updated_at = completion_time
  where j.id = $1
    and j.status = 'running'
    and j.locked_by = $2
    and j.lease_generation = $3
  returning j.* into completed_job;

  if not found then
    -- This should be unreachable while the row lock is held. Raising rather
    -- than returning ensures every cleanup effect is rolled back on anomaly.
    raise exception using errcode = 'P0002', message = 'cleanup completion lost its fenced lease';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_cleanup_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.finalize_cleanup_job(uuid, text, bigint)
  from public, anon, authenticated;
grant execute on function ingest.finalize_cleanup_job(uuid, text, bigint)
  to service_role;
comment on function ingest.finalize_cleanup_job(uuid, text, bigint) is
  'Fenced atomic cleanup: validates and locks one live lease, prunes bounded ephemera, and completes the job in the same transaction.';

commit;
