begin;

-- Catalog identities are mode-scoped so a live upstream record can coexist
-- with a visibly synthetic fixture carrying the same external identity.
alter table catalog.sets
  drop constraint sets_slug_key;

alter table catalog.sets
  drop constraint sets_external_identity_unique;

alter table catalog.sets
  add constraint sets_slug_mode_unique unique (slug, is_demo);

alter table catalog.sets
  add constraint sets_external_identity_unique
  unique (external_source, external_id, language, is_demo);

create table catalog.sync_state (
  source text not null,
  scope text not null,
  language text not null,
  is_demo boolean not null default false,
  revision bigint not null default 1,
  etag text,
  content_sha256 text not null,
  item_count integer not null,
  last_checked_at timestamptz not null,
  last_changed_at timestamptz not null,
  last_job_id uuid references ingest.jobs(id)
    on update cascade on delete set null deferrable initially deferred,
  primary key (source, scope, language, is_demo),
  constraint sync_state_source_check check (source ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint sync_state_scope_check check (scope ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint sync_state_language_check check (language ~ '^[a-z]{2,8}$'),
  constraint sync_state_etag_check check (
    etag is null or (
      char_length(etag) between 2 and 512
      and etag !~ '[[:cntrl:]]'
      and etag ~ '^(W/)?"[!#-~]*"$'
    )
  ),
  constraint sync_state_revision_check check (revision >= 1),
  constraint sync_state_sha256_check check (content_sha256 ~ '^[0-9a-f]{64}$'),
  constraint sync_state_item_count_check check (item_count between 0 and 1000000),
  constraint sync_state_timestamps_check check (last_changed_at <= last_checked_at)
);

create index sync_state_checked_idx
  on catalog.sync_state (last_checked_at desc);

alter table catalog.sync_state enable row level security;
alter table catalog.sync_state force row level security;
create policy sync_state_service_role_select
  on catalog.sync_state for select to service_role using (true);
revoke all on table catalog.sync_state from public, anon, authenticated, service_role;
grant select on table catalog.sync_state to service_role;

create table ingest.schedule_slots (
  schedule_name text not null,
  slot_at timestamptz not null,
  job_id uuid references ingest.jobs(id)
    on update cascade on delete set null deferrable initially deferred,
  created_at timestamptz not null default now(),
  primary key (schedule_name, slot_at),
  constraint schedule_slots_name_check check (
    schedule_name ~ '^[a-z][a-z0-9_.-]{0,79}$'
  ),
  constraint schedule_slots_minute_check check (
    slot_at = date_trunc('minute', slot_at)
  )
);

-- Earlier scheduler builds stored the durable UTC slot only in the canonical
-- job dedupe key. Preserve that history before the new slot table becomes the
-- authority. Malformed, non-minute, demo, and non-canonical keys are ignored;
-- if historical terminal retries produced duplicates, the first durable job
-- identity wins deterministically.
do $$
declare
  legacy_job record;
  legacy_slot_at timestamptz;
begin
  for legacy_job in
    select
      jobs.id,
      jobs.created_at,
      matched.parts[1] as schedule_name,
      matched.parts[2] as slot_token
    from ingest.jobs as jobs
    cross join lateral regexp_match(
      jobs.dedupe_key,
      '^schedule:([a-z][a-z0-9_.-]{0,79}):([0-9]{8}T[0-9]{4}00Z)$'
    ) as matched(parts)
    where not jobs.is_demo
      and jobs.dedupe_key
        ~ '^schedule:[a-z][a-z0-9_.-]{0,79}:[0-9]{8}T[0-9]{4}00Z$'
    order by jobs.created_at, jobs.id
  loop
    begin
      legacy_slot_at := make_timestamptz(
        substring(legacy_job.slot_token from 1 for 4)::integer,
        substring(legacy_job.slot_token from 5 for 2)::integer,
        substring(legacy_job.slot_token from 7 for 2)::integer,
        substring(legacy_job.slot_token from 10 for 2)::integer,
        substring(legacy_job.slot_token from 12 for 2)::integer,
        substring(legacy_job.slot_token from 14 for 2)::double precision,
        'UTC'
      );
    exception
      when datetime_field_overflow or invalid_datetime_format then
        continue;
    end;

    if to_char(
      legacy_slot_at at time zone 'UTC',
      'YYYYMMDD"T"HH24MISS"Z"'
    ) <> legacy_job.slot_token then
      continue;
    end if;

    insert into ingest.schedule_slots (
      schedule_name, slot_at, job_id, created_at
    ) values (
      legacy_job.schedule_name,
      legacy_slot_at,
      legacy_job.id,
      legacy_job.created_at
    )
    on conflict on constraint schedule_slots_pkey do nothing;
  end loop;
end;
$$;

create unique index schedule_slots_job_uidx
  on ingest.schedule_slots (job_id) where job_id is not null;

alter table ingest.schedule_slots enable row level security;
alter table ingest.schedule_slots force row level security;
create policy schedule_slots_service_role_select
  on ingest.schedule_slots for select to service_role using (true);
revoke all on table ingest.schedule_slots from public, anon, authenticated, service_role;
grant select on table ingest.schedule_slots to service_role;

-- This exact live source was explicitly owner-approved. Credentials remain in
-- the worker environment; only bounded policy and provenance data live here.
insert into ingest.source_policies (
  source_key,
  display_name,
  source_kind,
  domain,
  base_url,
  enabled,
  collector_type,
  access_mode,
  robots_policy,
  routes,
  include_subdomains,
  min_delay_seconds,
  max_pages_per_run,
  max_items_per_run,
  max_concurrency,
  statistics_eligible_default,
  retention_days,
  config,
  version,
  expected_interval_seconds,
  is_demo
) values (
  'tcgdex_catalog',
  'TCGdex Catalog API',
  'official_api',
  'api.tcgdex.net',
  'https://api.tcgdex.net/v2',
  true,
  'official_api',
  'official_api',
  'not_applicable',
  array['official_api']::text[],
  false,
  10,
  1,
  1000,
  1,
  false,
  365,
  '{"scope":"sets","metadata_only":true}'::jsonb,
  'tcgdex-sets-v1',
  86400,
  false
);

-- A durable owner record spans the short database preflight transaction and
-- the bounded network request. Only SECURITY DEFINER lifecycle functions may
-- mutate it; service_role intentionally receives no direct table privileges.
create table ingest.source_request_gates (
  source_key text primary key,
  owner_job_id uuid,
  owner_lease_generation bigint,
  acquired_at timestamptz,
  active_until timestamptz,
  constraint source_request_gates_source_check check (
    source_key = 'tcgdex_catalog'
  ),
  constraint source_request_gates_owner_check check (
    (
      owner_job_id is null
      and owner_lease_generation is null
      and acquired_at is null
      and active_until is null
    )
    or (
      owner_job_id is not null
      and owner_lease_generation >= 1
      and acquired_at is not null
      and active_until > acquired_at
    )
  )
);

insert into ingest.source_request_gates (source_key)
values ('tcgdex_catalog');

alter table ingest.source_request_gates enable row level security;
alter table ingest.source_request_gates force row level security;
revoke all on table ingest.source_request_gates
  from public, anon, authenticated, service_role;

create or replace function ingest.enqueue_scheduled_job_v1(
  schedule_name text,
  scheduled_for timestamptz,
  job_type text,
  payload jsonb default '{}'::jsonb,
  priority integer default 0,
  max_attempts integer default 5
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  enqueue_time timestamptz := clock_timestamp();
  proposed_job_id uuid := gen_random_uuid();
  reserved_job_id uuid;
  legacy_created_at timestamptz;
  returned_job ingest.jobs%rowtype;
  schedule_dedupe_key text;
begin
  if schedule_name is null
    or schedule_name !~ '^[a-z][a-z0-9_.-]{0,79}$'
  then
    raise exception using
      errcode = '22023',
      message = 'schedule_name must use the canonical job-name format';
  end if;
  if scheduled_for is null
    or scheduled_for <> date_trunc('minute', scheduled_for)
  then
    raise exception using
      errcode = '22023',
      message = 'scheduled_for must be an exact UTC minute';
  end if;
  if scheduled_for < enqueue_time - interval '36 hours'
    or scheduled_for > enqueue_time + interval '5 minutes'
  then
    raise exception using
      errcode = '22023',
      message = 'scheduled_for must be within 36 hours past and 5 minutes future';
  end if;
  if job_type is null or job_type !~ '^[a-z][a-z0-9_.-]{0,79}$' then
    raise exception using
      errcode = '22023',
      message = 'job_type must use the canonical job-name format';
  end if;
  if payload is null
    or jsonb_typeof(payload) <> 'object'
    or octet_length(payload::text) > 32768
  then
    raise exception using
      errcode = '22023',
      message = 'payload must be a JSON object no larger than 32768 bytes';
  end if;
  if priority is null or priority < -1000 or priority > 1000 then
    raise exception using
      errcode = '22023',
      message = 'priority must be between -1000 and 1000';
  end if;
  if max_attempts is null or max_attempts < 1 or max_attempts > 100 then
    raise exception using
      errcode = '22023',
      message = 'max_attempts must be between 1 and 100';
  end if;

  schedule_dedupe_key := 'schedule:' || enqueue_scheduled_job_v1.schedule_name || ':'
    || to_char(
      scheduled_for at time zone 'UTC',
      'YYYYMMDD"T"HH24MISS"Z"'
    );

  -- Upgrade compatibility: an older scheduler may have written the canonical
  -- dedupe key before schedule_slots existed. Adopt the first durable job
  -- identity instead of colliding with an active job or duplicating a terminal
  -- one. The migration backfill handles existing rows; this closes rolling
  -- deployment and repair races at the RPC boundary too.
  select jobs.id, jobs.created_at
  into reserved_job_id, legacy_created_at
  from ingest.jobs as jobs
  where jobs.dedupe_key = schedule_dedupe_key
    and not jobs.is_demo
  order by jobs.created_at, jobs.id
  limit 1
  for share of jobs;

  if found then
    insert into ingest.schedule_slots as slots (
      schedule_name, slot_at, job_id, created_at
    ) values (
      enqueue_scheduled_job_v1.schedule_name,
      enqueue_scheduled_job_v1.scheduled_for,
      reserved_job_id,
      legacy_created_at
    )
    on conflict on constraint schedule_slots_pkey do nothing;

    select slots.job_id
    into reserved_job_id
    from ingest.schedule_slots as slots
    where slots.schedule_name = enqueue_scheduled_job_v1.schedule_name
      and slots.slot_at = enqueue_scheduled_job_v1.scheduled_for
    for share of slots;

    if reserved_job_id is null then
      raise exception using
        errcode = 'P0002',
        message = 'schedule slot lost its original job reference';
    end if;

    select jobs.*
    into returned_job
    from ingest.jobs as jobs
    where jobs.id = reserved_job_id;

    if not found then
      raise exception using
        errcode = 'P0002',
        message = 'schedule slot original job is unavailable';
    end if;

    return next returned_job;
    return;
  end if;

  insert into ingest.schedule_slots as slots (
    schedule_name, slot_at, job_id, created_at
  ) values (
    enqueue_scheduled_job_v1.schedule_name,
    enqueue_scheduled_job_v1.scheduled_for,
    proposed_job_id,
    enqueue_time
  )
  on conflict on constraint schedule_slots_pkey do nothing
  returning slots.job_id into reserved_job_id;

  if reserved_job_id is not null then
    insert into ingest.jobs (
      id, job_type, payload, status, priority, attempts, max_attempts,
      available_at, dedupe_key, is_demo
    ) values (
      reserved_job_id, job_type, payload, 'pending', priority, 0, max_attempts,
      enqueue_scheduled_job_v1.scheduled_for, schedule_dedupe_key, false
    )
    returning * into returned_job;
  else
    select slots.job_id
    into reserved_job_id
    from ingest.schedule_slots as slots
    where slots.schedule_name = enqueue_scheduled_job_v1.schedule_name
      and slots.slot_at = enqueue_scheduled_job_v1.scheduled_for
    for share of slots;

    if reserved_job_id is null then
      raise exception using
        errcode = 'P0002',
        message = 'schedule slot lost its original job reference';
    end if;

    select jobs.*
    into returned_job
    from ingest.jobs as jobs
    where jobs.id = reserved_job_id;

    if not found then
      raise exception using
        errcode = 'P0002',
        message = 'schedule slot original job is unavailable';
    end if;
  end if;

  return next returned_job;
end;
$$;

alter function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) owner to postgres;
revoke all on function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) to service_role;
comment on function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) is 'Durably reserves one live UTC-minute schedule slot before inserting its single canonical job.';

create or replace function ingest.heartbeat_job_v2(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  lease_seconds integer
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
  renewed_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
begin
  if $1 is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if $2 is null or btrim($2) = '' or char_length($2) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if $3 is null or $3 < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  if $4 is null or $4 < 1 or $4 > 86400 then
    raise exception using
      errcode = '22023',
      message = 'lease_seconds must be between 1 and 86400';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = $1
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.is_demo
    or leased_job.status <> 'running'
    or leased_job.locked_by is distinct from $2
    or leased_job.lease_generation <> $3
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  update ingest.jobs as jobs
  set lock_expires_at = lease_checked_at + make_interval(secs => $4),
      updated_at = lease_checked_at
  where jobs.id = $1
    and jobs.status = 'running'
    and jobs.locked_by = $2
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into renewed_job;

  if not found then
    return;
  end if;

  update ingest.source_request_gates as gates
  set active_until = renewed_job.lock_expires_at
  where gates.source_key = 'tcgdex_catalog'
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  return next renewed_job;
end;
$$;

alter function ingest.heartbeat_job_v2(uuid, text, bigint, integer)
  owner to postgres;
revoke all on function ingest.heartbeat_job_v2(uuid, text, bigint, integer)
  from public, anon, authenticated, service_role;
grant execute on function ingest.heartbeat_job_v2(uuid, text, bigint, integer)
  to service_role;
comment on function ingest.heartbeat_job_v2(uuid, text, bigint, integer) is
  'Atomically renews a fenced live job lease and any matching TCGdex request gate.';

create or replace function ingest.fail_job_v2(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  error_code text,
  error_message text,
  retryable boolean
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
  failed_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
begin
  if $1 is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if $2 is null or btrim($2) = '' or char_length($2) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if $3 is null or $3 < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  if $4 is null or btrim($4) = '' or char_length($4) > 160 then
    raise exception using
      errcode = '22023',
      message = 'error_code must contain 1 to 160 characters';
  end if;
  if $5 is null or char_length($5) > 8000 then
    raise exception using
      errcode = '22023',
      message = 'error_message must contain at most 8000 characters';
  end if;
  if $6 is null then
    raise exception using errcode = '22023', message = 'retryable must not be null';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = $1
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.is_demo
    or leased_job.status <> 'running'
    or leased_job.locked_by is distinct from $2
    or leased_job.lease_generation <> $3
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  update ingest.jobs as jobs
  set status = case
        when not $6 or jobs.attempts >= jobs.max_attempts then 'dead'
        else 'pending'
      end,
      available_at = case
        when not $6 or jobs.attempts >= jobs.max_attempts then jobs.available_at
        else lease_checked_at + make_interval(
          secs => least(
            3600,
            30 * power(2, least(10, greatest(0, jobs.attempts - 1)))
          )::integer
        )
      end,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = case
        when not $6 or jobs.attempts >= jobs.max_attempts then lease_checked_at
        else null
      end,
      last_error_code = $4,
      last_error_message = $5,
      updated_at = lease_checked_at
  where jobs.id = $1
    and jobs.status = 'running'
    and jobs.locked_by = $2
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into failed_job;

  if not found then
    return;
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'tcgdex_catalog'
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  return next failed_job;
end;
$$;

alter function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean)
  owner to postgres;
revoke all on function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean)
  from public, anon, authenticated, service_role;
grant execute on function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean)
  to service_role;
comment on function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean) is
  'Atomically fails or requeues a fenced live job and releases only its matching TCGdex request gate.';

create or replace function ingest.begin_tcgdex_sets_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint
)
returns table(
  acquired boolean,
  retry_at timestamptz,
  etag text,
  content_sha256 text,
  item_count integer,
  revision bigint
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  leased_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
  checkpoint catalog.sync_state%rowtype;
  checkpoint_exists boolean := false;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  request_gate ingest.source_request_gates%rowtype;
  request_retry_at timestamptz;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null or btrim(worker_id) = '' or char_length(worker_id) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if lease_generation is null or lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = begin_tcgdex_sets_job.job_id
  for update of jobs;

  if not found then
    return;
  end if;

  -- Reject obviously stale callers before contending on the global request
  -- lock, then repeat this fence check with a fresh database clock after all
  -- potentially blocking locks have been acquired.
  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if leased_job.is_demo
    or leased_job.job_type <> 'catalog.tcgdex.sets.sync'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex begin requires a live catalog.tcgdex.sets.sync job with an empty payload';
  end if;

  -- One transaction-wide lock serializes durable gate transitions and
  -- checkpoint base selection across every worker. The gate row itself keeps
  -- ownership after this short transaction commits and while the GET runs.
  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:catalog:tcgdex:sets:en:live', 0)
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = 'tcgdex_catalog'
    and policies.display_name = 'TCGdex Catalog API'
    and policies.source_kind = 'official_api'
    and policies.domain = 'api.tcgdex.net'
    and policies.base_url = 'https://api.tcgdex.net/v2'
    and policies.enabled
    and policies.collector_type = 'official_api'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['official_api']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 10
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 1000
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 365
    and policies.config = '{"scope":"sets","metadata_only":true}'::jsonb
    and policies.version = 'tcgdex-sets-v1'
    and policies.expected_interval_seconds = 86400
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex catalog source policy is unavailable or disabled';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'tcgdex_catalog'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex request gate is unavailable';
  end if;

  select states.*
  into checkpoint
  from catalog.sync_state as states
  where states.source = 'tcgdex'
    and states.scope = 'sets'
    and states.language = 'en'
    and not states.is_demo
  for share of states;
  checkpoint_exists := found;

  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  request_retry_at := null;
  if request_gate.owner_job_id is not null
    and request_gate.active_until > lease_checked_at
  then
    request_retry_at := least(
      request_gate.active_until,
      lease_checked_at + interval '10 seconds'
    );
  end if;

  if policy_last_attempt_at is not null
    and lease_checked_at < policy_last_attempt_at + interval '10 seconds'
  then
    if request_retry_at is null
      or request_retry_at < policy_last_attempt_at + interval '10 seconds'
    then
      request_retry_at := policy_last_attempt_at + interval '10 seconds';
    end if;
  end if;

  if request_retry_at is not null then
    return query select
      false,
      request_retry_at,
      null::text,
      null::text,
      0::integer,
      0::bigint;
    return;
  end if;

  -- A successful grant must leave enough fenced lease for the transport's
  -- absolute 30-second deadline plus cleanup margin. The same expiry is copied
  -- to the persistent gate so another generation cannot enter mid-request.
  update ingest.jobs as jobs
  set lock_expires_at = greatest(
        jobs.lock_expires_at,
        lease_checked_at + interval '45 seconds'
      ),
      updated_at = lease_checked_at
  where jobs.id = $1
    and jobs.status = 'running'
    and jobs.locked_by = $2
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into leased_job;

  if not found then
    return;
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = $1,
      owner_lease_generation = $3,
      acquired_at = lease_checked_at,
      active_until = leased_job.lock_expires_at
  where gates.source_key = 'tcgdex_catalog';

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  if checkpoint_exists then
    return query select
      true,
      null::timestamptz,
      checkpoint.etag,
      checkpoint.content_sha256,
      checkpoint.item_count,
      checkpoint.revision;
  else
    return query select
      true,
      null::timestamptz,
      null::text,
      null::text,
      0::integer,
      0::bigint;
  end if;
end;
$$;

alter function ingest.begin_tcgdex_sets_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.begin_tcgdex_sets_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_tcgdex_sets_job(uuid, text, bigint)
  to service_role;
comment on function ingest.begin_tcgdex_sets_job(uuid, text, bigint) is
  'Fenced pre-network TCGdex request gate returning acquisition state, retry time, and the live sets checkpoint.';

create or replace function ingest.finalize_tcgdex_sets_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  result jsonb
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
  prior_state catalog.sync_state%rowtype;
  state_exists boolean := false;
  policy_id uuid;
  request_gate ingest.source_request_gates%rowtype;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  result_outcome text;
  result_etag text;
  result_sha256 text;
  result_sets jsonb;
  result_count integer;
  result_expected_revision bigint;
  written_revision bigint;
  set_value jsonb;
  set_external_id text;
  set_name text;
  set_slug_base text;
  set_slug text;
  card_count_total integer;
  card_count_official integer;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null or btrim(worker_id) = '' or char_length(worker_id) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if lease_generation is null or lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = finalize_tcgdex_sets_job.job_id
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if leased_job.is_demo
    or leased_job.job_type <> 'catalog.tcgdex.sets.sync'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex finalizer requires a live catalog.tcgdex.sets.sync job with an empty payload';
  end if;

  -- Serialize this checkpoint across distinct scheduled jobs. Lock order is
  -- job -> global advisory -> exact policy -> request gate -> checkpoint in
  -- both TCGdex RPCs.
  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:catalog:tcgdex:sets:en:live', 0)
  );

  -- Re-check the source kill switch after network I/O. Disabling or changing
  -- this policy while a GET is in flight must prevent all persistence.
  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'tcgdex_catalog'
    and policies.display_name = 'TCGdex Catalog API'
    and policies.source_kind = 'official_api'
    and policies.domain = 'api.tcgdex.net'
    and policies.base_url = 'https://api.tcgdex.net/v2'
    and policies.enabled
    and policies.collector_type = 'official_api'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['official_api']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 10
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 1000
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 365
    and policies.config = '{"scope":"sets","metadata_only":true}'::jsonb
    and policies.version = 'tcgdex-sets-v1'
    and policies.expected_interval_seconds = 86400
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex catalog source policy is unavailable or disabled';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'tcgdex_catalog'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex request gate is unavailable';
  end if;

  select states.*
  into prior_state
  from catalog.sync_state as states
  where states.source = 'tcgdex'
    and states.scope = 'sets'
    and states.language = 'en'
    and not states.is_demo
  for update of states;
  state_exists := found;

  -- The policy/checkpoint locks may have blocked. Only a fresh database clock
  -- sampled after both locks can decide whether the caller still owns a lease.
  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if request_gate.owner_job_id is distinct from $1
    or request_gate.owner_lease_generation is distinct from $3
    or request_gate.active_until is null
    or request_gate.active_until <= lease_checked_at
  then
    raise exception using
      errcode = '55000',
      message = 'TCGdex request gate is not owned by this job lease';
  end if;

  if result is null or jsonb_typeof(result) is distinct from 'object' then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;
  if octet_length(result::text) > 2097152
    or not (result ?& array[
      'version', 'expected_revision', 'outcome', 'etag', 'content_sha256', 'sets'
    ])
    or result - array[
      'version', 'expected_revision', 'outcome', 'etag', 'content_sha256', 'sets'
    ] <> '{}'::jsonb
    or result -> 'version' is distinct from '1'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;
  if jsonb_typeof(result -> 'expected_revision') is distinct from 'number'
    or jsonb_typeof(result -> 'outcome') is distinct from 'string'
    or result ->> 'outcome' not in ('changed', 'unchanged', 'not_modified')
    or jsonb_typeof(result -> 'content_sha256') is distinct from 'string'
    or result ->> 'content_sha256' !~ '^[0-9a-f]{64}$'
    or jsonb_typeof(result -> 'sets') is distinct from 'array'
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;

  if result ->> 'expected_revision' !~ '^(0|[1-9][0-9]{0,18})$' then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;
  if (result ->> 'expected_revision')::numeric > 9223372036854775806 then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;

  if result -> 'etag' is distinct from 'null'::jsonb
    and jsonb_typeof(result -> 'etag') is distinct from 'string'
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;

  result_outcome := result ->> 'outcome';
  result_etag := result ->> 'etag';
  result_sha256 := result ->> 'content_sha256';
  result_sets := result -> 'sets';
  result_count := jsonb_array_length(result_sets);
  result_expected_revision := (result ->> 'expected_revision')::bigint;

  if result_etag is not null
    and (
      char_length(result_etag) not between 2 and 512
      or result_etag ~ '[[:cntrl:]]'
      or result_etag !~ '^(W/)?"[!#-~]*"$'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'TCGdex result must match the exact bounded v1 contract';
  end if;

  if (result_outcome = 'changed' and result_count not between 1 and 1000)
    or (result_outcome <> 'changed' and result_count <> 0)
  then
    raise exception using
      errcode = '22023',
      message = 'changed TCGdex results require 1 to 1000 sets and other outcomes require none';
  end if;

  if result_expected_revision <> case
    when state_exists then prior_state.revision
    else 0
  end then
    raise exception using
      errcode = '40001',
      message = 'TCGdex result was computed from a stale checkpoint revision';
  end if;

  if result_outcome = 'changed'
    and state_exists
    and prior_state.content_sha256 = result_sha256
  then
    raise exception using
      errcode = '22023',
      message = 'changed TCGdex results require a new content hash';
  end if;

  if result_outcome <> 'changed'
    and (not state_exists or prior_state.content_sha256 <> result_sha256)
  then
    raise exception using
      errcode = '22023',
      message = 'unchanged and not_modified TCGdex results require a matching live checkpoint';
  end if;

  if result_outcome = 'not_modified'
    and prior_state.etag is distinct from result_etag
  then
    raise exception using
      errcode = '22023',
      message = 'not_modified TCGdex results require the checkpoint ETag';
  end if;

  if result_outcome = 'changed' then
    -- Validate shape and primitive types before performing any casts. SQL does
    -- not promise left-to-right boolean evaluation, so cast-bearing OR chains
    -- can otherwise raise non-contract errors for hostile JSON values.
    for set_value in
      select elements.value
      from jsonb_array_elements(result_sets) as elements(value)
    loop
      if jsonb_typeof(set_value) is distinct from 'object' then
        raise exception using
          errcode = '22023',
          message = 'TCGdex sets must use the exact bounded v1 set contract';
      end if;
      if not (set_value ?& array[
          'id', 'name', 'card_count_total', 'card_count_official'
        ])
        or set_value - array[
          'id', 'name', 'card_count_total', 'card_count_official'
        ] <> '{}'::jsonb
        or jsonb_typeof(set_value -> 'id') is distinct from 'string'
        or jsonb_typeof(set_value -> 'name') is distinct from 'string'
        or jsonb_typeof(set_value -> 'card_count_total') is distinct from 'number'
        or jsonb_typeof(set_value -> 'card_count_official') is distinct from 'number'
      then
        raise exception using
          errcode = '22023',
          message = 'TCGdex sets must use the exact bounded v1 set contract';
      end if;

      set_external_id := set_value ->> 'id';
      set_name := set_value ->> 'name';
      if btrim(set_external_id) = ''
        or btrim(set_external_id) <> set_external_id
        or char_length(set_external_id) > 160
        or set_external_id ~ '[[:cntrl:]]'
        or btrim(set_name) = ''
        or btrim(set_name) <> set_name
        or char_length(set_name) > 160
        or set_name ~ '[[:cntrl:]]'
      then
        raise exception using
          errcode = '22023',
          message = 'TCGdex sets must use the exact bounded v1 set contract';
      end if;

      if set_value ->> 'card_count_total' !~ '^(0|[1-9][0-9]{0,6})$'
        or set_value ->> 'card_count_official' !~ '^(0|[1-9][0-9]{0,6})$'
      then
        raise exception using
          errcode = '22023',
          message = 'TCGdex sets must use the exact bounded v1 set contract';
      end if;
      card_count_total := (set_value ->> 'card_count_total')::integer;
      card_count_official := (set_value ->> 'card_count_official')::integer;
      if card_count_total > 1000000
        or card_count_official > 1000000
        or card_count_official > card_count_total
      then
        raise exception using
          errcode = '22023',
          message = 'TCGdex sets must use the exact bounded v1 set contract';
      end if;
    end loop;

    if (
      select count(*) <> count(distinct elements.value ->> 'id')
      from jsonb_array_elements(result_sets) as elements(value)
    ) then
      raise exception using
        errcode = '22023',
        message = 'TCGdex set ids must be unique within one result';
    end if;

    for set_value in
      select elements.value
      from jsonb_array_elements(result_sets) as elements(value)
      order by elements.value ->> 'id'
    loop
      set_external_id := set_value ->> 'id';
      set_name := set_value ->> 'name';
      card_count_total := (set_value ->> 'card_count_total')::integer;
      card_count_official := (set_value ->> 'card_count_official')::integer;
      set_slug_base := btrim(
        regexp_replace(lower(set_external_id), '[^a-z0-9]+', '-', 'g'),
        '-'
      );
      if set_slug_base = '' then
        set_slug_base := 'set';
      end if;
      set_slug := 'tcgdex-' || left(set_slug_base, 132) || '-'
        || left(
          encode(
            extensions.digest(convert_to(set_external_id, 'UTF8'), 'sha256'),
            'hex'
          ),
          16
        );

      insert into catalog.sets as sets (
        external_source,
        external_id,
        name,
        slug,
        language,
        metadata,
        is_active,
        is_demo
      ) values (
        'tcgdex',
        set_external_id,
        set_name,
        set_slug,
        'en',
        jsonb_build_object(
          'cardCount',
          jsonb_build_object(
            'total', card_count_total,
            'official', card_count_official
          )
        ),
        true,
        false
      )
      on conflict (external_source, external_id, language, is_demo)
      do update set
        name = excluded.name,
        slug = excluded.slug,
        metadata = sets.metadata || excluded.metadata,
        is_active = true
      where not sets.is_demo;
    end loop;

    insert into catalog.sync_state as states (
      source,
      scope,
      language,
      is_demo,
      revision,
      etag,
      content_sha256,
      item_count,
      last_checked_at,
      last_changed_at,
      last_job_id
    ) values (
      'tcgdex',
      'sets',
      'en',
      false,
      result_expected_revision + 1,
      result_etag,
      result_sha256,
      result_count,
      lease_checked_at,
      lease_checked_at,
      job_id
    )
    on conflict (source, scope, language, is_demo)
    do update set
      revision = states.revision + 1,
      etag = excluded.etag,
      content_sha256 = excluded.content_sha256,
      item_count = excluded.item_count,
      last_checked_at = excluded.last_checked_at,
      last_changed_at = excluded.last_changed_at,
      last_job_id = excluded.last_job_id
    where states.revision = result_expected_revision
    returning states.revision into written_revision;

    if not found then
      raise exception using
        errcode = '40001',
        message = 'TCGdex result was computed from a stale checkpoint revision';
    end if;
  else
    update catalog.sync_state as states
    set revision = states.revision + 1,
        etag = case
          when result_outcome = 'unchanged' then result_etag
          else states.etag
        end,
        last_checked_at = lease_checked_at,
        last_job_id = job_id
    where states.source = 'tcgdex'
      and states.scope = 'sets'
      and states.language = 'en'
      and not states.is_demo
      and states.revision = result_expected_revision
    returning states.revision into written_revision;

    if not found then
      raise exception using
        errcode = '40001',
        message = 'TCGdex result was computed from a stale checkpoint revision';
    end if;
  end if;

  update ingest.source_policies as policies
  set last_success_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live TCGdex catalog source policy changed during finalization';
  end if;

  completion_time := clock_timestamp();
  update ingest.jobs as jobs
  set status = 'completed',
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = completion_time,
      last_error_code = null,
      last_error_message = null,
      updated_at = completion_time
  where jobs.id = $1
    and jobs.status = 'running'
    and jobs.locked_by = $2
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > completion_time
  returning jobs.* into completed_job;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'TCGdex completion lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'tcgdex_catalog'
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'TCGdex completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_tcgdex_sets_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_tcgdex_sets_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_tcgdex_sets_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_tcgdex_sets_job(uuid, text, bigint, jsonb) is
  'Fenced atomic TCGdex sets persistence, checkpoint update, policy success, job completion, and request-gate release.';

commit;
