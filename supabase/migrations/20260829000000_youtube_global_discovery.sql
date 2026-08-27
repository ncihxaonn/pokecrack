begin;

-- Request gates are keyed by canonical source policy names. TCGdex was the
-- first gated source, but the lifecycle table is intentionally shared by all
-- bounded official API collectors.
alter table ingest.source_request_gates
  drop constraint source_request_gates_source_check;

alter table ingest.source_request_gates
  add constraint source_request_gates_source_check check (
    source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'
  );

-- A synthetic fixture and a live upstream identity may coexist, while every
-- identity remains unique inside its own explicitly labelled mode.
drop index ingest.source_items_normalized_url_uidx;
drop index ingest.source_items_platform_external_uidx;

-- The redundant mode key is the target for the mode-scoped duplicate-cluster
-- self-reference below.
alter table ingest.source_items
  add constraint source_items_id_mode_unique unique (id, is_demo);

-- A duplicate cluster is meaningful only inside one explicitly labelled data
-- mode. Fail closed on any legacy cross-mode edge before replacing the broad
-- single-column self-reference.
do $$
begin
  if exists (
    select 1
    from ingest.source_items as source_items
    join ingest.source_items as cluster_sources
      on cluster_sources.id = source_items.duplicate_cluster_id
    where source_items.is_demo is distinct from cluster_sources.is_demo
  ) then
    raise exception using
      errcode = '23514',
      message = 'source item duplicate clusters must not cross live/demo mode';
  end if;
end;
$$;

alter table ingest.source_items
  drop constraint source_items_duplicate_cluster_id_fkey;
alter table ingest.source_items
  add constraint source_items_duplicate_cluster_mode_fkey
  foreign key (duplicate_cluster_id, is_demo)
  references ingest.source_items (id, is_demo)
  on update restrict
  on delete set null (duplicate_cluster_id);

create unique index source_items_normalized_url_uidx
  on ingest.source_items (normalized_url, is_demo);
create unique index source_items_platform_external_uidx
  on ingest.source_items (platform, external_id, is_demo)
  where platform is not null and external_id is not null;

-- This exact live policy is a metadata-only discovery boundary. The worker
-- still requires an explicit worker credential before it registers or
-- schedules these jobs; enabling the policy here only arms the DB kill switch.
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
  'youtube_discovery',
  'YouTube Global Discovery API',
  'official_api',
  'youtube.googleapis.com',
  'https://youtube.googleapis.com/youtube/v3',
  true,
  'official_api',
  'official_api',
  'not_applicable',
  array['official_api']::text[],
  false,
  2,
  1,
  25,
  1,
  false,
  28,
  '{"metadata_only":true,"media_download":false,"max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb,
  'youtube-global-discovery-v1',
  21600,
  false
);

insert into ingest.source_request_gates (source_key)
values ('youtube_discovery');

-- Official API search results are a disposable activity cache, never source
-- evidence. UNLOGGED prevents WAL/standby copies and is acceptable because the
-- cache is safe to re-fetch after a crash.
create unlogged table ingest.youtube_discoveries (
  video_id text primary key,
  source_policy_id uuid not null
    references ingest.source_policies (id)
    on update restrict on delete restrict,
  source_url text not null,
  title text,
  published_at timestamptz,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  expires_at timestamptz not null,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint youtube_discoveries_video_id_check
    check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  constraint youtube_discoveries_source_url_check
    check (
      source_url = 'https://www.youtube.com/watch?v=' || video_id
      and char_length(source_url) <= 128
    ),
  constraint youtube_discoveries_title_check
    check (
      title is null
      or (
        char_length(title) <= 500
        and title !~ '[[:cntrl:]]'
      )
    ),
  constraint youtube_discoveries_published_at_check
    check (
      published_at is null
      or published_at >= '2005-01-01 00:00:00+00'::timestamptz
    ),
  constraint youtube_discoveries_time_check
    check (
      last_seen_at >= first_seen_at
      and expires_at = last_seen_at + interval '28 days'
      and updated_at >= created_at
    ),
  constraint youtube_discoveries_live_only_check check (not is_demo)
);

create index youtube_discoveries_expiry_idx
  on ingest.youtube_discoveries (expires_at, video_id);

alter table ingest.youtube_discoveries enable row level security;
alter table ingest.youtube_discoveries force row level security;
create policy youtube_discoveries_service_role_select
  on ingest.youtube_discoveries
  for select
  to service_role
  using (true);
revoke all on table ingest.youtube_discoveries
  from public, anon, authenticated, service_role;
grant select on table ingest.youtube_discoveries to service_role;

comment on table ingest.youtube_discoveries is
  'Private, unlogged, re-fetchable YouTube activity cache. It stores no query, job, channel, geography, description, hash, language, evidence, or source-item association.';

-- Renew every request gate owned by this exact fenced job generation. This
-- retains TCGdex behavior while allowing additional gated official sources.
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
  where gates.owner_job_id = $1
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
  'Atomically renews a fenced live job lease and every matching request gate.';

-- A failure releases only gates held by this job generation. A stale caller
-- can neither transition the job nor release a newer network owner.
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
  cooldown_recorded_at timestamptz;
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

  cooldown_recorded_at := clock_timestamp();
  update ingest.source_policies as policies
  set last_attempt_at = greatest(
        coalesce(policies.last_attempt_at, '-infinity'::timestamptz),
        cooldown_recorded_at
      ),
      last_failure_at = cooldown_recorded_at,
      updated_at = cooldown_recorded_at
  from ingest.source_request_gates as gates
  where gates.owner_job_id = $1
    and gates.owner_lease_generation = $3
    and policies.source_key = gates.source_key
    and not policies.is_demo;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.owner_job_id = $1
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
  'Atomically fails or requeues a fenced live job and releases every matching request gate.';

create or replace function ingest.begin_youtube_discovery_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint
)
returns table(
  acquired boolean,
  retry_at timestamptz
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
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  request_gate ingest.source_request_gates%rowtype;
  request_retry_at timestamptz;
  query_name text;
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
  where jobs.id = begin_youtube_discovery_job.job_id
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
    or leased_job.job_type <> 'source.youtube.discovery'
    or jsonb_typeof(leased_job.payload) is distinct from 'object'
    or not (leased_job.payload ?& array['query_name'])
    or leased_job.payload - array['query_name'] <> '{}'::jsonb
    or jsonb_typeof(leased_job.payload -> 'query_name') is distinct from 'string'
  then
    raise exception using
      errcode = '22023',
      message = 'YouTube begin requires a live source.youtube.discovery job with one approved query_name';
  end if;

  query_name := leased_job.payload ->> 'query_name';
  if query_name not in (
    'pokemon-tcg-booster-box-opening',
    'pokemon-tcg-etb-opening',
    'pokemon-tcg-booster-bundle-opening',
    'pokemon-tcg-pack-opening',
    'pokemon-tcg-opening-batch-code'
  ) then
    raise exception using
      errcode = '22023',
      message = 'YouTube begin requires a live source.youtube.discovery job with one approved query_name';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:youtube:discovery:live', 0)
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = 'youtube_discovery'
    and policies.display_name = 'YouTube Global Discovery API'
    and policies.source_kind = 'official_api'
    and policies.domain = 'youtube.googleapis.com'
    and policies.base_url = 'https://youtube.googleapis.com/youtube/v3'
    and policies.enabled
    and policies.collector_type = 'official_api'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['official_api']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 2
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 25
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 28
    and policies.config = '{"metadata_only":true,"media_download":false,"max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb
    and policies.version = 'youtube-global-discovery-v1'
    and policies.expected_interval_seconds = 21600
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery source policy is unavailable or disabled';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'youtube_discovery'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery request gate is unavailable';
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

  request_retry_at := null;
  if request_gate.owner_job_id is not null
    and request_gate.active_until > lease_checked_at
  then
    request_retry_at := least(
      request_gate.active_until,
      lease_checked_at + interval '2 seconds'
    );
  end if;

  if policy_last_attempt_at is not null
    and lease_checked_at < policy_last_attempt_at + interval '2 seconds'
  then
    if request_retry_at is null
      or request_retry_at < policy_last_attempt_at + interval '2 seconds'
    then
      request_retry_at := policy_last_attempt_at + interval '2 seconds';
    end if;
  end if;

  if request_retry_at is not null then
    return query select false, request_retry_at;
    return;
  end if;

  -- One bounded search.list request has an absolute transport budget; retain
  -- a cleanup margin in the DB lease.
  update ingest.jobs as jobs
  set lock_expires_at = greatest(
        jobs.lock_expires_at,
        lease_checked_at + interval '75 seconds'
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
  where gates.source_key = 'youtube_discovery';

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  return query select true, null::timestamptz;
end;
$$;

alter function ingest.begin_youtube_discovery_job(uuid, text, bigint)
  owner to postgres;
revoke all on function ingest.begin_youtube_discovery_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_youtube_discovery_job(uuid, text, bigint)
  to service_role;
comment on function ingest.begin_youtube_discovery_job(uuid, text, bigint) is
  'Fenced pre-network gate for one exact allowlisted live YouTube metadata query.';

-- Retention is an enforceable data boundary, not only a source-policy label.
-- The cleanup remains internal and is reachable solely through the existing
-- fenced maintenance.cleanup finalizer.
create or replace function ingest.prune_expired_ephemera_v2(
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
declare
  youtube_discovery_count integer := 0;
  excerpt_count integer := 0;
  extraction_count integer := 0;
  signal_count integer := 0;
begin
  if cutoff is null then
    raise exception using errcode = '22023', message = 'cutoff must not be null';
  end if;
  if max_rows is null or max_rows < 1 or max_rows > 100000 then
    raise exception using
      errcode = '22023',
      message = 'max_rows must be between 1 and 100000';
  end if;

  with candidates as materialized (
    select discoveries.video_id
    from ingest.youtube_discoveries as discoveries
    where not discoveries.is_demo
      and discoveries.expires_at <= cutoff
    order by discoveries.expires_at, discoveries.video_id
    for update of discoveries skip locked
    limit max_rows
  )
  delete from ingest.youtube_discoveries as discoveries
  using candidates
  where discoveries.video_id = candidates.video_id;
  get diagnostics youtube_discovery_count = row_count;

  with candidates as materialized (
    select source_items.id
    from ingest.source_items as source_items
    where source_items.expires_at <= cutoff
      and source_items.text_excerpt is not null
    order by source_items.expires_at, source_items.id
    for update of source_items skip locked
    limit max_rows
  )
  update ingest.source_items as source_items
  set text_excerpt = null,
      updated_at = clock_timestamp()
  from candidates
  where source_items.id = candidates.id;
  get diagnostics excerpt_count = row_count;

  with candidates as materialized (
    select runs.id
    from ingest.extraction_runs as runs
    where runs.expires_at <= cutoff
      and not exists (
        select 1 from ingest.openings as openings
        where openings.extraction_run_id = runs.id
      )
    order by runs.expires_at, runs.id
    for update of runs skip locked
    limit max_rows
  )
  delete from ingest.extraction_runs as runs
  using candidates
  where runs.id = candidates.id;
  get diagnostics extraction_count = row_count;

  with candidates as materialized (
    select signals.id
    from analytics.signals as signals
    where signals.expires_at <= cutoff
    order by signals.expires_at, signals.id
    for update of signals skip locked
    limit max_rows
  )
  delete from analytics.signals as signals
  using candidates
  where signals.id = candidates.id;
  get diagnostics signal_count = row_count;

  return jsonb_build_object(
    'youtube_discoveries_deleted', youtube_discovery_count,
    'source_excerpts_cleared', excerpt_count,
    'extraction_runs_deleted', extraction_count,
    'signals_deleted', signal_count,
    'openings_deleted', 0
  );
end;
$$;

alter function ingest.prune_expired_ephemera_v2(timestamptz, integer)
  owner to postgres;
revoke all on function ingest.prune_expired_ephemera_v2(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_expired_ephemera_v2(timestamptz, integer) is
  'Internal bounded hard cleanup of expired dedicated YouTube activity-cache rows. Callable only by a typed fenced finalizer.';

create or replace function ingest.finalize_youtube_discovery_job(
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
  policy_id uuid;
  request_gate ingest.source_request_gates%rowtype;
  lease_checked_at timestamptz;
  policy_attempt_time timestamptz;
  completion_time timestamptz;
  discovery_seen_at timestamptz;
  query_name text;
  result_items jsonb;
  item_record record;
  item_value jsonb;
  item_external_id text;
  item_source_url text;
  item_title text;
  item_published_at timestamptz;
  item_collector_version text;
  item_source_policy_version text;
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
  where jobs.id = finalize_youtube_discovery_job.job_id
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
    or leased_job.job_type <> 'source.youtube.discovery'
    or jsonb_typeof(leased_job.payload) is distinct from 'object'
    or not (leased_job.payload ?& array['query_name'])
    or leased_job.payload - array['query_name'] <> '{}'::jsonb
    or jsonb_typeof(leased_job.payload -> 'query_name') is distinct from 'string'
  then
    raise exception using
      errcode = '22023',
      message = 'YouTube finalizer requires a live source.youtube.discovery job with one approved query_name';
  end if;

  query_name := leased_job.payload ->> 'query_name';
  if query_name not in (
    'pokemon-tcg-booster-box-opening',
    'pokemon-tcg-etb-opening',
    'pokemon-tcg-booster-bundle-opening',
    'pokemon-tcg-pack-opening',
    'pokemon-tcg-opening-batch-code'
  ) then
    raise exception using
      errcode = '22023',
      message = 'YouTube finalizer requires a live source.youtube.discovery job with one approved query_name';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:youtube:discovery:live', 0)
  );

  -- Re-read the exact policy after network I/O. Any kill-switch or contract
  -- change while a request is in flight aborts persistence atomically.
  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'youtube_discovery'
    and policies.display_name = 'YouTube Global Discovery API'
    and policies.source_kind = 'official_api'
    and policies.domain = 'youtube.googleapis.com'
    and policies.base_url = 'https://youtube.googleapis.com/youtube/v3'
    and policies.enabled
    and policies.collector_type = 'official_api'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['official_api']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 2
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 25
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 28
    and policies.config = '{"metadata_only":true,"media_download":false,"max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb
    and policies.version = 'youtube-global-discovery-v1'
    and policies.expected_interval_seconds = 21600
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery source policy is unavailable or disabled';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'youtube_discovery'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery request gate is unavailable';
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

  if request_gate.owner_job_id is distinct from $1
    or request_gate.owner_lease_generation is distinct from $3
    or request_gate.active_until is null
    or request_gate.active_until <= lease_checked_at
  then
    raise exception using
      errcode = '55000',
      message = 'YouTube discovery request gate is not owned by this job lease';
  end if;

  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 2097152
    or not (result ?& array['version', 'query_name', 'items'])
    or result - array['version', 'query_name', 'items'] <> '{}'::jsonb
    or result -> 'version' is distinct from '1'::jsonb
    or jsonb_typeof(result -> 'query_name') is distinct from 'string'
    or result ->> 'query_name' <> query_name
    or jsonb_typeof(result -> 'items') is distinct from 'array'
  then
    raise exception using
      errcode = '22023',
      message = 'YouTube result must match the exact bounded v1 contract';
  end if;

  if jsonb_array_length(result -> 'items') > 25 then
    raise exception using
      errcode = '22023',
      message = 'YouTube result must contain at most 25 items';
  end if;

  result_items := result -> 'items';

  -- Validate the complete payload before any persistence. Casts are isolated
  -- behind primitive checks so hostile JSON cannot escape the 22023 contract.
  for item_record in
    select elements.value
    from jsonb_array_elements(result_items) as elements(value)
  loop
    item_value := item_record.value;

    if jsonb_typeof(item_value) is distinct from 'object'
      or not (item_value ?& array[
        'external_id', 'source_url', 'title', 'published_at',
        'collector_version', 'source_policy_version'
      ])
      or item_value - array[
        'external_id', 'source_url', 'title', 'published_at',
        'collector_version', 'source_policy_version'
      ] <> '{}'::jsonb
      or jsonb_typeof(item_value -> 'external_id') is distinct from 'string'
      or jsonb_typeof(item_value -> 'source_url') is distinct from 'string'
      or jsonb_typeof(item_value -> 'collector_version') is distinct from 'string'
      or jsonb_typeof(item_value -> 'source_policy_version') is distinct from 'string'
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube items must use the exact bounded v1 item contract';
    end if;

    if (item_value -> 'title' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'title') is distinct from 'string')
      or (item_value -> 'published_at' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'published_at') is distinct from 'string')
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube items must use the exact bounded v1 item contract';
    end if;

    item_external_id := item_value ->> 'external_id';
    item_source_url := item_value ->> 'source_url';
    item_title := item_value ->> 'title';
    item_collector_version := item_value ->> 'collector_version';
    item_source_policy_version := item_value ->> 'source_policy_version';

    if item_external_id !~ '^[A-Za-z0-9_-]{11}$'
      or item_source_url <> 'https://www.youtube.com/watch?v=' || item_external_id
      or item_collector_version <> 'youtube-global-discovery-v1'
      or item_source_policy_version <> 'youtube-global-discovery-v1'
      or (item_title is not null and (
        char_length(item_title) > 500 or item_title ~ '[[:cntrl:]]'
      ))
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube item identity, title, or version is invalid';
    end if;

    item_published_at := null;
    if item_value -> 'published_at' is distinct from 'null'::jsonb then
      if char_length(item_value ->> 'published_at') > 64
        or item_value ->> 'published_at' ~ '[[:cntrl:]]'
      then
        raise exception using
          errcode = '22023',
          message = 'YouTube item published_at is invalid';
      end if;
      begin
        item_published_at := (item_value ->> 'published_at')::timestamptz;
      exception
        when others then
          raise exception using
            errcode = '22023',
            message = 'YouTube item published_at is invalid';
      end;
      if item_published_at < '2005-01-01 00:00:00+00'::timestamptz
        or item_published_at > lease_checked_at + interval '1 day'
      then
        raise exception using
          errcode = '22023',
          message = 'YouTube item published_at is outside the bounded date range';
      end if;
    end if;

  end loop;

  if (
    select count(*) <> count(distinct elements.value ->> 'external_id')
    from jsonb_array_elements(result_items) as elements(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'YouTube result identities must be unique within one query';
  end if;

  for item_record in
    select elements.value
    from jsonb_array_elements(result_items) as elements(value)
  loop
    item_value := item_record.value;
    item_external_id := item_value ->> 'external_id';
    item_source_url := item_value ->> 'source_url';
    item_title := item_value ->> 'title';
    item_published_at := null;
    if item_value -> 'published_at' is distinct from 'null'::jsonb then
      item_published_at := (item_value ->> 'published_at')::timestamptz;
    end if;

    -- Stamp each disposable cache row at its actual DB persistence boundary.
    -- Do not reuse the pre-validation lease clock for provider retention.
    discovery_seen_at := clock_timestamp();

    insert into ingest.youtube_discoveries as discoveries (
      video_id,
      source_policy_id,
      source_url,
      title,
      published_at,
      first_seen_at,
      last_seen_at,
      expires_at,
      is_demo,
      created_at,
      updated_at
    ) values (
      item_external_id,
      policy_id,
      item_source_url,
      item_title,
      item_published_at,
      discovery_seen_at,
      discovery_seen_at,
      discovery_seen_at + interval '28 days',
      false,
      discovery_seen_at,
      discovery_seen_at
    )
    on conflict (video_id)
    do update set
      source_policy_id = excluded.source_policy_id,
      source_url = excluded.source_url,
      title = excluded.title,
      published_at = excluded.published_at,
      last_seen_at = excluded.last_seen_at,
      expires_at = excluded.expires_at,
      is_demo = false,
      updated_at = excluded.updated_at
    where not discoveries.is_demo;
  end loop;

  policy_attempt_time := clock_timestamp();
  update ingest.source_policies as policies
  set last_attempt_at = greatest(
        coalesce(policies.last_attempt_at, '-infinity'::timestamptz),
        policy_attempt_time
      ),
      last_success_at = policy_attempt_time,
      updated_at = policy_attempt_time
  where policies.id = policy_id;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live YouTube discovery source policy changed during finalization';
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
    and not jobs.is_demo
  returning jobs.* into completed_job;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'YouTube discovery completion lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'youtube_discovery'
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'YouTube discovery completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_youtube_discovery_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_youtube_discovery_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_youtube_discovery_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_youtube_discovery_job(uuid, text, bigint, jsonb) is
  'Fenced atomic refresh of the private unlogged YouTube activity cache, followed by job completion and exact gate release. No query or evidence association is persisted.';

-- Every live application login is a caller of narrow SECURITY DEFINER RPCs,
-- never a table writer. The existing service_role grants pre-date the fenced
-- queue/finalizer protocol and would otherwise let an inheriting worker bypass
-- every lease, policy, retention and audit check below.
create or replace function ingest.enqueue_job_v1(
  p_job_type text,
  p_payload jsonb default '{}'::jsonb,
  p_priority integer default 0,
  p_dedupe_key text default null,
  p_available_at timestamptz default null,
  p_max_attempts integer default 5
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
begin
  if p_job_type not in (
    'catalog.tcgdex.sets.sync',
    'maintenance.cleanup',
    'source.youtube.discovery'
  ) then
    raise exception using
      errcode = '22023',
      message = 'job_type is not approved for direct enqueue';
  end if;
  if p_payload is null
    or jsonb_typeof(p_payload) is distinct from 'object'
    or octet_length(p_payload::text) > 4096
  then
    raise exception using
      errcode = '22023',
      message = 'payload must be a bounded JSON object';
  end if;
  if p_job_type in ('catalog.tcgdex.sets.sync', 'maintenance.cleanup')
    and p_payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'catalog and cleanup jobs require an empty payload';
  end if;
  if p_job_type = 'source.youtube.discovery' and (
    not (p_payload ?& array['query_name'])
    or p_payload - array['query_name'] <> '{}'::jsonb
    or jsonb_typeof(p_payload -> 'query_name') is distinct from 'string'
    or p_payload ->> 'query_name' not in (
      'pokemon-tcg-booster-box-opening',
      'pokemon-tcg-etb-opening',
      'pokemon-tcg-booster-bundle-opening',
      'pokemon-tcg-pack-opening',
      'pokemon-tcg-opening-batch-code'
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'YouTube jobs require one exact approved query_name';
  end if;
  if p_priority is null or p_priority < -1000 or p_priority > 1000 then
    raise exception using
      errcode = '22023',
      message = 'priority must be between -1000 and 1000';
  end if;
  if p_max_attempts is null or p_max_attempts < 1 or p_max_attempts > 100 then
    raise exception using
      errcode = '22023',
      message = 'max_attempts must be between 1 and 100';
  end if;
  if p_dedupe_key is not null and (
    btrim(p_dedupe_key) = '' or char_length(p_dedupe_key) > 256
  ) then
    raise exception using
      errcode = '22023',
      message = 'dedupe_key must contain 1 to 256 characters when present';
  end if;

  return query
  insert into ingest.jobs as jobs (
    job_type,
    payload,
    status,
    priority,
    dedupe_key,
    available_at,
    attempts,
    max_attempts,
    created_at,
    updated_at,
    is_demo
  ) values (
    p_job_type,
    p_payload,
    'pending',
    p_priority,
    p_dedupe_key,
    coalesce(p_available_at, enqueue_time),
    0,
    p_max_attempts,
    enqueue_time,
    enqueue_time,
    false
  )
  on conflict (job_type, dedupe_key, is_demo)
    where dedupe_key is not null and status in ('pending', 'running')
  do update set updated_at = jobs.updated_at
  returning jobs.*;
end;
$$;

alter function ingest.enqueue_job_v1(text, jsonb, integer, text, timestamptz, integer)
  owner to postgres;
revoke all on function ingest.enqueue_job_v1(text, jsonb, integer, text, timestamptz, integer)
  from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_job_v1(text, jsonb, integer, text, timestamptz, integer)
  to service_role;
comment on function ingest.enqueue_job_v1(text, jsonb, integer, text, timestamptz, integer) is
  'Bounded enqueue for the three exact live job families; arbitrary job types and payloads are rejected.';

create or replace function ingest.complete_job_v2(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint
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
  completion_time timestamptz;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null or btrim(p_worker_id) = '' or char_length(p_worker_id) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = p_job_id
  for update of jobs;

  if not found then
    return;
  end if;

  completion_time := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from p_worker_id
    or leased_job.lease_generation <> p_lease_generation
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= completion_time
  then
    return;
  end if;
  if leased_job.is_demo or leased_job.job_type in (
    'catalog.tcgdex.sets.sync',
    'maintenance.cleanup',
    'source.youtube.discovery'
  ) then
    raise exception using
      errcode = '22023',
      message = 'typed live jobs require their dedicated fenced finalizer';
  end if;

  return query
  update ingest.jobs as jobs
  set status = 'completed',
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = completion_time,
      last_error_code = null,
      last_error_message = null,
      updated_at = completion_time
  where jobs.id = p_job_id
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > completion_time
    and not jobs.is_demo
  returning jobs.*;
end;
$$;

alter function ingest.complete_job_v2(uuid, text, bigint) owner to postgres;
revoke all on function ingest.complete_job_v2(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.complete_job_v2(uuid, text, bigint)
  to service_role;
comment on function ingest.complete_job_v2(uuid, text, bigint) is
  'Generation-fenced no-effect completion. Typed collector and cleanup jobs must use their dedicated atomic finalizers.';

create or replace function ingest.pause_job_for_budget_v2(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_retry_at timestamptz
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  pause_time timestamptz;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null or btrim(p_worker_id) = '' or char_length(p_worker_id) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  pause_time := clock_timestamp();
  if p_retry_at is null or p_retry_at <= pause_time or p_retry_at > pause_time + interval '31 days' then
    raise exception using
      errcode = '22023',
      message = 'retry_at must be within the next 31 days';
  end if;

  return query
  update ingest.jobs as jobs
  set status = 'pending',
      attempts = greatest(0, jobs.attempts - 1),
      available_at = p_retry_at,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = null,
      last_error_code = null,
      last_error_message = null,
      updated_at = pause_time
  where jobs.id = p_job_id
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > pause_time
    and not jobs.is_demo
  returning jobs.*;
end;
$$;

alter function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz)
  owner to postgres;
revoke all on function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz)
  from public, anon, authenticated, service_role;
grant execute on function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz)
  to service_role;
comment on function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz) is
  'Generation-fenced budget pause with a bounded future retry timestamp.';

create or replace function ingest.upsert_worker_heartbeat_v1(
  p_worker_id text,
  p_worker_type text,
  p_version text,
  p_metadata jsonb
)
returns table(last_seen_at timestamptz)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  heartbeat_time timestamptz := clock_timestamp();
begin
  if p_worker_id is null or btrim(p_worker_id) = '' or char_length(p_worker_id) > 160 then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if p_worker_type not in ('collector', 'scheduler', 'watchdog') then
    raise exception using
      errcode = '22023',
      message = 'worker_type is not a supported live role';
  end if;
  if p_version is null or btrim(p_version) = '' or char_length(p_version) > 80 then
    raise exception using
      errcode = '22023',
      message = 'version must contain 1 to 80 characters';
  end if;
  if p_metadata is null
    or jsonb_typeof(p_metadata) is distinct from 'object'
    or p_metadata - array['command', 'data_mode', 'max_concurrency', 'role_ready'] <> '{}'::jsonb
    or not (p_metadata ?& array['command', 'data_mode', 'max_concurrency', 'role_ready'])
    or p_metadata ->> 'command' <> 'health'
    or p_metadata ->> 'data_mode' <> 'live'
    or p_metadata -> 'max_concurrency' is distinct from '1'::jsonb
    or p_metadata -> 'role_ready' is distinct from 'true'::jsonb
    or octet_length(p_metadata::text) > 1024
  then
    raise exception using
      errcode = '22023',
      message = 'metadata must match the exact live health contract';
  end if;

  return query
  insert into ingest.worker_heartbeats as heartbeats (
    worker_id,
    worker_type,
    version,
    last_seen_at,
    metadata,
    is_demo
  ) values (
    p_worker_id,
    p_worker_type,
    p_version,
    heartbeat_time,
    p_metadata,
    false
  )
  on conflict (worker_id)
  do update set
    worker_type = excluded.worker_type,
    version = excluded.version,
    last_seen_at = excluded.last_seen_at,
    metadata = heartbeats.metadata || excluded.metadata
  where not heartbeats.is_demo
  returning heartbeats.last_seen_at;
end;
$$;

alter function ingest.upsert_worker_heartbeat_v1(text, text, text, jsonb)
  owner to postgres;
revoke all on function ingest.upsert_worker_heartbeat_v1(text, text, text, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.upsert_worker_heartbeat_v1(text, text, text, jsonb)
  to service_role;
comment on function ingest.upsert_worker_heartbeat_v1(text, text, text, jsonb) is
  'Bounded live-role health heartbeat; arbitrary metadata and unsupported roles are rejected.';

drop policy sets_service_role_all on catalog.sets;
drop policy products_service_role_all on catalog.products;
drop policy cards_service_role_all on catalog.cards;
drop policy regions_service_role_all on catalog.regions;
drop policy retailers_service_role_all on catalog.retailers;
drop policy stores_service_role_all on catalog.stores;
create policy sets_service_role_select on catalog.sets for select to service_role using (true);
create policy products_service_role_select on catalog.products for select to service_role using (true);
create policy cards_service_role_select on catalog.cards for select to service_role using (true);
create policy regions_service_role_select on catalog.regions for select to service_role using (true);
create policy retailers_service_role_select on catalog.retailers for select to service_role using (true);
create policy stores_service_role_select on catalog.stores for select to service_role using (true);

drop policy source_policies_service_role_all on ingest.source_policies;
drop policy source_items_service_role_all on ingest.source_items;
drop policy extraction_runs_service_role_all on ingest.extraction_runs;
drop policy openings_service_role_all on ingest.openings;
drop policy opening_hits_service_role_all on ingest.opening_hits;
drop policy batch_sightings_service_role_all on ingest.batch_sightings;
drop policy jobs_service_role_all on ingest.jobs;
drop policy worker_heartbeats_service_role_all on ingest.worker_heartbeats;
drop policy browser_sessions_service_role_all on ingest.browser_sessions;
drop policy ai_usage_daily_service_role_all on ingest.ai_usage_daily;
drop policy admin_audit_log_service_role_all on ingest.admin_audit_log;
create policy source_policies_service_role_select on ingest.source_policies for select to service_role using (true);
create policy source_items_service_role_select on ingest.source_items for select to service_role using (true);
create policy extraction_runs_service_role_select on ingest.extraction_runs for select to service_role using (true);
create policy openings_service_role_select on ingest.openings for select to service_role using (true);
create policy opening_hits_service_role_select on ingest.opening_hits for select to service_role using (true);
create policy batch_sightings_service_role_select on ingest.batch_sightings for select to service_role using (true);
create policy jobs_service_role_select on ingest.jobs for select to service_role using (true);
create policy worker_heartbeats_service_role_select on ingest.worker_heartbeats for select to service_role using (true);
create policy browser_sessions_service_role_select on ingest.browser_sessions for select to service_role using (true);
create policy ai_usage_daily_service_role_select on ingest.ai_usage_daily for select to service_role using (true);
create policy admin_audit_log_service_role_select on ingest.admin_audit_log for select to service_role using (true);

drop policy dashboard_daily_service_role_all on analytics.dashboard_daily;
drop policy set_metrics_daily_service_role_all on analytics.set_metrics_daily;
drop policy region_metrics_daily_service_role_all on analytics.region_metrics_daily;
drop policy retailer_metrics_daily_service_role_all on analytics.retailer_metrics_daily;
drop policy batch_metrics_daily_service_role_all on analytics.batch_metrics_daily;
drop policy signals_service_role_all on analytics.signals;
create policy dashboard_daily_service_role_select on analytics.dashboard_daily for select to service_role using (true);
create policy set_metrics_daily_service_role_select on analytics.set_metrics_daily for select to service_role using (true);
create policy region_metrics_daily_service_role_select on analytics.region_metrics_daily for select to service_role using (true);
create policy retailer_metrics_daily_service_role_select on analytics.retailer_metrics_daily for select to service_role using (true);
create policy batch_metrics_daily_service_role_select on analytics.batch_metrics_daily for select to service_role using (true);
create policy signals_service_role_select on analytics.signals for select to service_role using (true);

drop policy dashboard_overview_service_all on public.dashboard_overview;
drop policy set_summaries_service_all on public.set_summaries;
drop policy region_summaries_service_all on public.region_summaries;
drop policy retailer_summaries_service_all on public.retailer_summaries;
drop policy batch_summaries_service_all on public.batch_summaries;
drop policy recent_activity_service_all on public.recent_activity;
drop policy public_signals_service_all on public.public_signals;
drop policy data_freshness_service_all on public.data_freshness;
drop policy system_status_service_all on public.system_status;
create policy dashboard_overview_service_select on public.dashboard_overview for select to service_role using (true);
create policy set_summaries_service_select on public.set_summaries for select to service_role using (true);
create policy region_summaries_service_select on public.region_summaries for select to service_role using (true);
create policy retailer_summaries_service_select on public.retailer_summaries for select to service_role using (true);
create policy batch_summaries_service_select on public.batch_summaries for select to service_role using (true);
create policy recent_activity_service_select on public.recent_activity for select to service_role using (true);
create policy public_signals_service_select on public.public_signals for select to service_role using (true);
create policy data_freshness_service_select on public.data_freshness for select to service_role using (true);
create policy system_status_service_select on public.system_status for select to service_role using (true);

revoke all privileges
  on all tables in schema catalog, ingest, analytics, public
  from service_role;
grant select on all tables in schema catalog, ingest, analytics, public
  to service_role;
-- Request-gate ownership remains fully opaque outside its SECURITY DEFINER
-- lifecycle functions; this exception predates and survives the read-only sweep.
revoke all on table ingest.source_request_gates from service_role;

commit;
