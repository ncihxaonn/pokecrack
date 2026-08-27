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

alter table ingest.source_items
  alter column content_hash drop not null;

-- Composite provenance foreign keys bind the immutable live/demo mode to the
-- parent identity. The redundant unique constraints are required FK targets.
alter table ingest.source_items
  add constraint source_items_id_mode_unique unique (id, is_demo);
alter table ingest.jobs
  add constraint jobs_id_mode_unique unique (id, is_demo);

create unique index source_items_normalized_url_uidx
  on ingest.source_items (normalized_url, is_demo);
create unique index source_items_platform_external_uidx
  on ingest.source_items (platform, external_id, is_demo)
  where platform is not null and external_id is not null;

comment on column ingest.source_items.content_hash is
  'Optional SHA-256 of bounded text content. Metadata-only discoveries may have no text and therefore no content hash.';

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
  2,
  50,
  1,
  false,
  30,
  '{"metadata_only":true,"media_download":false,"discovery_scope":"global","geography_status":"unresolved","evidence_tier":"D","statistics_eligible":false,"parser_version":"youtube-metadata-v1","max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb,
  'youtube-global-discovery-v1',
  21600,
  false
);

insert into ingest.source_request_gates (source_key)
values ('youtube_discovery');

-- One row records the latest sighting of a source identity by one approved
-- query. Channel country is an official-channel proxy only; no column in this
-- table represents an observed opening location.
create table ingest.source_discoveries (
  id uuid primary key default gen_random_uuid(),
  source_item_id uuid not null,
  query_name text not null,
  job_id uuid not null,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  result_rank integer not null,
  channel_country_code text,
  geography_status text not null,
  geography_basis text not null,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_discoveries_query_check check (
    query_name in (
      'pokemon-tcg-booster-box-opening',
      'pokemon-tcg-etb-opening',
      'pokemon-tcg-booster-bundle-opening',
      'pokemon-tcg-pack-opening',
      'pokemon-tcg-opening-batch-code'
    )
  ),
  constraint source_discoveries_rank_check check (result_rank between 1 and 50),
  constraint source_discoveries_time_check check (last_seen_at >= first_seen_at),
  constraint source_discoveries_geography_check check (
    (
      channel_country_code is null
      and geography_status = 'unresolved'
      and geography_basis = 'unresolved'
    )
    or (
      channel_country_code ~ '^[A-Z]{2}$'
      and geography_status = 'channel_country_proxy'
      and geography_basis = 'youtube_channel_country'
    )
  ),
  constraint source_discoveries_identity_unique
    unique (source_item_id, query_name, is_demo),
  constraint source_discoveries_job_rank_unique
    unique (job_id, query_name, result_rank, is_demo),
  constraint source_discoveries_source_item_mode_fkey
    foreign key (source_item_id, is_demo)
    references ingest.source_items (id, is_demo)
    on update restrict on delete cascade,
  constraint source_discoveries_job_mode_fkey
    foreign key (job_id, is_demo)
    references ingest.jobs (id, is_demo)
    on update restrict on delete restrict
);

create index source_discoveries_query_seen_idx
  on ingest.source_discoveries (query_name, last_seen_at desc, is_demo);
create index source_discoveries_channel_country_seen_idx
  on ingest.source_discoveries (channel_country_code, last_seen_at desc, is_demo)
  where channel_country_code is not null;

alter table ingest.source_discoveries enable row level security;
alter table ingest.source_discoveries force row level security;
create policy source_discoveries_service_role_select
  on ingest.source_discoveries for select to service_role using (true);
revoke all on table ingest.source_discoveries
  from public, anon, authenticated, service_role;
grant select on table ingest.source_discoveries to service_role;

comment on table ingest.source_discoveries is
  'Private query provenance for metadata-only YouTube activity discovery. Channel country is an official-channel proxy, never an observed opening location.';

-- YouTube discovery rows are transient metadata, not evidence submissions.
-- The private live provenance row is an immutable marker even if a broad
-- service role later rebinds source_policy_id, so that rebind cannot bypass
-- either this promotion guard or the 30-day cleanup boundary.
create or replace function ingest.is_youtube_discovery_metadata_source(
  source_item_id uuid,
  source_policy_id uuid default null
)
returns boolean
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  select
    exists (
      select 1
      from ingest.source_policies as policies
      where policies.id = $2
        and policies.source_key = 'youtube_discovery'
    )
    or exists (
      select 1
      from ingest.source_items as source_items
      join ingest.source_policies as policies
        on policies.id = source_items.source_policy_id
      where source_items.id = $1
        and policies.source_key = 'youtube_discovery'
    )
    or exists (
      select 1
      from ingest.source_discoveries as discoveries
      where discoveries.source_item_id = $1
        and not discoveries.is_demo
    );
$$;

alter function ingest.is_youtube_discovery_metadata_source(uuid, uuid)
  owner to postgres;
revoke all on function ingest.is_youtube_discovery_metadata_source(uuid, uuid)
  from public, anon, authenticated, service_role;
comment on function ingest.is_youtube_discovery_metadata_source(uuid, uuid) is
  'Internal policy-or-provenance classifier for transient YouTube discovery source identities.';

create or replace function ingest.reject_youtube_discovery_evidence_reference()
returns trigger
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  if ingest.is_youtube_discovery_metadata_source(new.source_item_id) then
    raise exception using
      errcode = '23514',
      message = 'YouTube discovery metadata cannot be referenced as evidence';
  end if;

  return new;
end;
$$;

alter function ingest.reject_youtube_discovery_evidence_reference()
  owner to postgres;
revoke all on function ingest.reject_youtube_discovery_evidence_reference()
  from public, anon, authenticated, service_role;
comment on function ingest.reject_youtube_discovery_evidence_reference() is
  'Trigger-only invariant preventing transient YouTube discovery metadata from entering evidence tables, including after source-policy rebinding.';

create or replace function ingest.reject_youtube_discovery_duplicate_cluster()
returns trigger
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  if new.duplicate_cluster_id is not null
    and (
      ingest.is_youtube_discovery_metadata_source(new.id, new.source_policy_id)
      or ingest.is_youtube_discovery_metadata_source(new.duplicate_cluster_id)
    )
  then
    raise exception using
      errcode = '23514',
      message = 'YouTube discovery metadata cannot participate in duplicate clusters';
  end if;

  return new;
end;
$$;

alter function ingest.reject_youtube_discovery_duplicate_cluster()
  owner to postgres;
revoke all on function ingest.reject_youtube_discovery_duplicate_cluster()
  from public, anon, authenticated, service_role;
comment on function ingest.reject_youtube_discovery_duplicate_cluster() is
  'Trigger-only invariant keeping transient YouTube discovery rows out of both sides of downstream duplicate clusters.';

create or replace function ingest.reject_youtube_discovery_policy_rebind()
returns trigger
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  -- PostgreSQL data-modifying CTEs share one statement snapshot. Allowing an
  -- ordinary identity to adopt this policy would therefore let a sibling CTE
  -- create an evidence reference before either cross-table lookup can observe
  -- the other's write. Discovery identities are created only by the fenced
  -- finalizer, so reject ordinary-to-discovery adoption outright.
  if tg_op = 'UPDATE'
    and not ingest.is_youtube_discovery_metadata_source(
      old.id,
      old.source_policy_id
    )
    and ingest.is_youtube_discovery_metadata_source(
      new.id,
      new.source_policy_id
    )
  then
    raise exception using
      errcode = '23514',
      message = 'Ordinary source identities cannot be rebound into YouTube discovery metadata';
  end if;

  if ingest.is_youtube_discovery_metadata_source(new.id, new.source_policy_id)
    and (
      new.duplicate_cluster_id is not null
      or exists (
        select 1
        from ingest.source_items as source_items
        where source_items.id <> new.id
          and source_items.duplicate_cluster_id = new.id
      )
      or exists (
        select 1
        from ingest.extraction_runs as runs
        where runs.source_item_id = new.id
      )
      or exists (
        select 1
        from ingest.openings as openings
        where openings.source_item_id = new.id
      )
      or exists (
        select 1
        from ingest.batch_sightings as sightings
        where sightings.source_item_id = new.id
      )
    )
  then
    raise exception using
      errcode = '23514',
      message = 'YouTube discovery metadata cannot inherit existing evidence or duplicate references';
  end if;

  return new;
end;
$$;

alter function ingest.reject_youtube_discovery_policy_rebind()
  owner to postgres;
revoke all on function ingest.reject_youtube_discovery_policy_rebind()
  from public, anon, authenticated, service_role;
comment on function ingest.reject_youtube_discovery_policy_rebind() is
  'Trigger-only invariant forbidding ordinary-to-discovery policy adoption and preventing discovery identities from inheriting references.';

-- Row-level BEFORE guards fail fast, while these deferred checks validate the
-- complete transaction state. The latter closes data-modifying CTE snapshot
-- gaps where sibling writes are intentionally invisible until statement end.
create or replace function ingest.enforce_youtube_discovery_metadata_end_state()
returns trigger
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  current_source ingest.source_items%rowtype;
  referenced_source_id uuid;
begin
  if tg_relid = 'ingest.extraction_runs'::regclass then
    select runs.source_item_id
    into referenced_source_id
    from ingest.extraction_runs as runs
    where runs.id = new.id;
  elsif tg_relid = 'ingest.openings'::regclass then
    select openings.source_item_id
    into referenced_source_id
    from ingest.openings as openings
    where openings.id = new.id;
  elsif tg_relid = 'ingest.batch_sightings'::regclass then
    select sightings.source_item_id
    into referenced_source_id
    from ingest.batch_sightings as sightings
    where sightings.id = new.id;
  end if;

  if tg_relid in (
    'ingest.extraction_runs'::regclass,
    'ingest.openings'::regclass,
    'ingest.batch_sightings'::regclass
  ) then
    if not found then
      return null;
    end if;

    if ingest.is_youtube_discovery_metadata_source(referenced_source_id) then
      raise exception using
        errcode = '23514',
        message = 'YouTube discovery metadata cannot be referenced as evidence';
    end if;

    return null;
  end if;

  if tg_relid = 'ingest.source_discoveries'::regclass then
    select source_items.*
    into current_source
    from ingest.source_discoveries as discoveries
    join ingest.source_items as source_items
      on source_items.id = discoveries.source_item_id
     and source_items.is_demo = discoveries.is_demo
    where discoveries.id = new.id;
  else
    select source_items.*
    into current_source
    from ingest.source_items as source_items
    where source_items.id = new.id;
  end if;

  if not found then
    return null;
  end if;

  if ingest.is_youtube_discovery_metadata_source(
      current_source.id,
      current_source.source_policy_id
    )
    and (
      current_source.duplicate_cluster_id is not null
      or exists (
        select 1
        from ingest.source_items as source_items
        where source_items.id <> current_source.id
          and source_items.duplicate_cluster_id = current_source.id
      )
      or exists (
        select 1
        from ingest.extraction_runs as runs
        where runs.source_item_id = current_source.id
      )
      or exists (
        select 1
        from ingest.openings as openings
        where openings.source_item_id = current_source.id
      )
      or exists (
        select 1
        from ingest.batch_sightings as sightings
        where sightings.source_item_id = current_source.id
      )
    )
  then
    raise exception using
      errcode = '23514',
      message = 'YouTube discovery metadata has an invalid downstream reference';
  end if;

  return null;
end;
$$;

alter function ingest.enforce_youtube_discovery_metadata_end_state()
  owner to postgres;
revoke all on function ingest.enforce_youtube_discovery_metadata_end_state()
  from public, anon, authenticated, service_role;
comment on function ingest.enforce_youtube_discovery_metadata_end_state() is
  'Deferred trigger invariant validating the final transaction graph for transient YouTube metadata.';

create trigger extraction_runs_reject_youtube_discovery
before insert or update of source_item_id on ingest.extraction_runs
for each row execute function ingest.reject_youtube_discovery_evidence_reference();
create trigger openings_reject_youtube_discovery
before insert or update of source_item_id on ingest.openings
for each row execute function ingest.reject_youtube_discovery_evidence_reference();
create trigger batch_sightings_reject_youtube_discovery
before insert or update of source_item_id on ingest.batch_sightings
for each row execute function ingest.reject_youtube_discovery_evidence_reference();
create trigger source_items_reject_youtube_discovery_duplicate_cluster
before insert or update of duplicate_cluster_id on ingest.source_items
for each row execute function ingest.reject_youtube_discovery_duplicate_cluster();
create trigger source_items_reject_youtube_discovery_policy_rebind
before insert or update of source_policy_id on ingest.source_items
for each row execute function ingest.reject_youtube_discovery_policy_rebind();

create constraint trigger source_items_enforce_youtube_discovery_end_state
after insert or update on ingest.source_items
deferrable initially deferred
for each row execute function ingest.enforce_youtube_discovery_metadata_end_state();
create constraint trigger source_discoveries_enforce_youtube_discovery_end_state
after insert or update on ingest.source_discoveries
deferrable initially deferred
for each row execute function ingest.enforce_youtube_discovery_metadata_end_state();
create constraint trigger extraction_runs_enforce_youtube_discovery_end_state
after insert or update on ingest.extraction_runs
deferrable initially deferred
for each row execute function ingest.enforce_youtube_discovery_metadata_end_state();
create constraint trigger openings_enforce_youtube_discovery_end_state
after insert or update on ingest.openings
deferrable initially deferred
for each row execute function ingest.enforce_youtube_discovery_metadata_end_state();
create constraint trigger batch_sightings_enforce_youtube_discovery_end_state
after insert or update on ingest.batch_sightings
deferrable initially deferred
for each row execute function ingest.enforce_youtube_discovery_metadata_end_state();

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
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 50
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = '{"metadata_only":true,"media_download":false,"discovery_scope":"global","geography_status":"unresolved","evidence_tier":"D","statistics_eligible":false,"parser_version":"youtube-metadata-v1","max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb
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

  -- search.list plus one bounded channels.list enrichment call share an
  -- absolute transport budget; retain a cleanup margin in the DB lease.
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
  youtube_source_count integer := 0;
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
    select source_items.id
    from ingest.source_items as source_items
    left join ingest.source_policies as policies
      on policies.id = source_items.source_policy_id
    -- Use the immutable provenance clock for both eligibility and ordering so
    -- a mutable cache expiry cannot starve an expired marker behind max_rows.
    left join lateral (
      select
        max(discoveries.last_seen_at) + interval '30 days' as effective_expiry
      from ingest.source_discoveries as discoveries
      where discoveries.source_item_id = source_items.id
        and discoveries.is_demo = source_items.is_demo
        and not discoveries.is_demo
    ) as marker_expiry on true
    where not source_items.is_demo
      and (
        marker_expiry.effective_expiry <= cutoff
        or (
          marker_expiry.effective_expiry is null
          and policies.source_key = 'youtube_discovery'
          and not policies.is_demo
          and source_items.expires_at <= cutoff
        )
      )
    order by coalesce(
      marker_expiry.effective_expiry,
      source_items.expires_at
    ), source_items.id
    for update of source_items skip locked
    limit max_rows
  )
  delete from ingest.source_items as source_items
  using candidates
  where source_items.id = candidates.id;
  get diagnostics youtube_source_count = row_count;

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
    'youtube_source_items_deleted', youtube_source_count,
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
  'Internal bounded hard cleanup of expired YouTube discovery identities using immutable provenance time, with cascading private provenance. Callable only by a typed fenced finalizer.';

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
  query_name text;
  result_items jsonb;
  item_record record;
  item_value jsonb;
  item_metadata jsonb;
  item_rank integer;
  item_external_id text;
  item_source_url text;
  item_normalized_url text;
  item_title text;
  item_text_excerpt text;
  item_published_at timestamptz;
  item_author_hash text;
  item_content_hash text;
  item_language text;
  item_collector_version text;
  item_source_policy_version text;
  item_channel_country_code text;
  item_geography_status text;
  item_geography_basis text;
  existing_item ingest.source_items%rowtype;
  source_item_id uuid;
  conflicting_identity_exists boolean;
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
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 50
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = '{"metadata_only":true,"media_download":false,"discovery_scope":"global","geography_status":"unresolved","evidence_tier":"D","statistics_eligible":false,"parser_version":"youtube-metadata-v1","max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb
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

  if jsonb_array_length(result -> 'items') > 50 then
    raise exception using
      errcode = '22023',
      message = 'YouTube result must contain at most 50 items';
  end if;

  result_items := result -> 'items';

  -- Validate the complete payload before any persistence. Casts are isolated
  -- behind primitive checks so hostile JSON cannot escape the 22023 contract.
  for item_record in
    select elements.value, elements.ordinality::integer as rank
    from jsonb_array_elements(result_items) with ordinality
      as elements(value, ordinality)
  loop
    item_value := item_record.value;
    item_rank := item_record.rank;

    if jsonb_typeof(item_value) is distinct from 'object'
      or not (item_value ?& array[
        'external_id', 'source_url', 'normalized_url', 'title', 'text_excerpt',
        'published_at', 'author_hash', 'content_hash', 'language', 'metadata',
        'collector_version', 'source_policy_version'
      ])
      or item_value - array[
        'external_id', 'source_url', 'normalized_url', 'title', 'text_excerpt',
        'published_at', 'author_hash', 'content_hash', 'language', 'metadata',
        'collector_version', 'source_policy_version'
      ] <> '{}'::jsonb
      or jsonb_typeof(item_value -> 'external_id') is distinct from 'string'
      or jsonb_typeof(item_value -> 'source_url') is distinct from 'string'
      or jsonb_typeof(item_value -> 'normalized_url') is distinct from 'string'
      or jsonb_typeof(item_value -> 'language') is distinct from 'string'
      or jsonb_typeof(item_value -> 'metadata') is distinct from 'object'
      or jsonb_typeof(item_value -> 'collector_version') is distinct from 'string'
      or jsonb_typeof(item_value -> 'source_policy_version') is distinct from 'string'
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube items must use the exact bounded v1 item contract';
    end if;

    if (item_value -> 'title' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'title') is distinct from 'string')
      or (item_value -> 'text_excerpt' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'text_excerpt') is distinct from 'string')
      or (item_value -> 'published_at' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'published_at') is distinct from 'string')
      or (item_value -> 'author_hash' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'author_hash') is distinct from 'string')
      or (item_value -> 'content_hash' is distinct from 'null'::jsonb
        and jsonb_typeof(item_value -> 'content_hash') is distinct from 'string')
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube items must use the exact bounded v1 item contract';
    end if;

    item_external_id := item_value ->> 'external_id';
    item_source_url := item_value ->> 'source_url';
    item_normalized_url := item_value ->> 'normalized_url';
    item_title := item_value ->> 'title';
    item_text_excerpt := item_value ->> 'text_excerpt';
    item_author_hash := item_value ->> 'author_hash';
    item_content_hash := item_value ->> 'content_hash';
    item_language := item_value ->> 'language';
    item_metadata := item_value -> 'metadata';
    item_collector_version := item_value ->> 'collector_version';
    item_source_policy_version := item_value ->> 'source_policy_version';

    if item_external_id !~ '^[A-Za-z0-9_-]{11}$'
      or item_source_url <> 'https://www.youtube.com/watch?v=' || item_external_id
      or item_normalized_url <> 'https://www.youtube.com/watch?v=' || item_external_id
      or item_language <> 'en'
      or item_collector_version <> 'youtube-global-discovery-v1'
      or item_source_policy_version <> 'youtube-global-discovery-v1'
      or (item_title is not null and (
        char_length(item_title) > 500 or item_title ~ '[[:cntrl:]]'
      ))
      or (item_text_excerpt is not null and (
        char_length(item_text_excerpt) > 20000
        or regexp_replace(item_text_excerpt, E'[\\t\\n\\r]', '', 'g') ~ '[[:cntrl:]]'
      ))
      or (item_author_hash is not null and item_author_hash !~ '^[0-9a-f]{64}$')
      or (item_content_hash is not null and item_content_hash !~ '^[0-9a-f]{64}$')
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube item identity, hash, language, text, or version is invalid';
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

    if octet_length(item_metadata::text) > 4096
      or not (item_metadata ?& array[
        'query_name', 'metadata_only', 'media_download', 'discovery_scope',
        'geography_status', 'evidence_tier', 'statistics_eligible',
        'parser_version', 'product_type_hints', 'batch_code_hints',
        'channel_country_code', 'geography_basis'
      ])
      or item_metadata - array[
        'query_name', 'metadata_only', 'media_download', 'discovery_scope',
        'geography_status', 'evidence_tier', 'statistics_eligible',
        'parser_version', 'product_type_hints', 'batch_code_hints',
        'channel_country_code', 'geography_basis'
      ] <> '{}'::jsonb
      or jsonb_typeof(item_metadata -> 'query_name') is distinct from 'string'
      or item_metadata ->> 'query_name' <> query_name
      or item_metadata -> 'metadata_only' is distinct from 'true'::jsonb
      or item_metadata -> 'media_download' is distinct from 'false'::jsonb
      or item_metadata -> 'discovery_scope' is distinct from '"global"'::jsonb
      or item_metadata -> 'evidence_tier' is distinct from '"D"'::jsonb
      or item_metadata -> 'statistics_eligible' is distinct from 'false'::jsonb
      or item_metadata -> 'parser_version' is distinct from '"youtube-metadata-v1"'::jsonb
      or jsonb_typeof(item_metadata -> 'product_type_hints') is distinct from 'array'
      or jsonb_typeof(item_metadata -> 'batch_code_hints') is distinct from 'array'
      or jsonb_typeof(item_metadata -> 'geography_status') is distinct from 'string'
      or jsonb_typeof(item_metadata -> 'geography_basis') is distinct from 'string'
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube metadata must match the exact activity-only v1 contract';
    end if;

    if jsonb_array_length(item_metadata -> 'product_type_hints') > 3
      or exists (
        select 1
        from jsonb_array_elements(item_metadata -> 'product_type_hints') as hints(value)
        where jsonb_typeof(hints.value) is distinct from 'string'
          or (hints.value #>> '{}') not in ('booster_box', 'etb', 'booster_bundle')
      )
      or (
        select count(*) <> count(distinct hints.value #>> '{}')
        from jsonb_array_elements(item_metadata -> 'product_type_hints') as hints(value)
      )
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube product type hints must be a unique approved bounded array';
    end if;

    if jsonb_array_length(item_metadata -> 'batch_code_hints') > 5
      or exists (
        select 1
        from jsonb_array_elements(item_metadata -> 'batch_code_hints') as hints(value)
        where jsonb_typeof(hints.value) is distinct from 'string'
          or (hints.value #>> '{}') !~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'
      )
      or (
        select count(*) <> count(distinct hints.value #>> '{}')
        from jsonb_array_elements(item_metadata -> 'batch_code_hints') as hints(value)
      )
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube batch code hints must be unique bounded unverified activity metadata';
    end if;

    if item_metadata -> 'channel_country_code' is distinct from 'null'::jsonb
      and jsonb_typeof(item_metadata -> 'channel_country_code') is distinct from 'string'
    then
      raise exception using
        errcode = '22023',
        message = 'YouTube channel country proxy must use the exact geography pair';
    end if;

    item_channel_country_code := item_metadata ->> 'channel_country_code';
    item_geography_status := item_metadata ->> 'geography_status';
    item_geography_basis := item_metadata ->> 'geography_basis';
    if (
      item_channel_country_code is null
      and (
        item_geography_status <> 'unresolved'
        or item_geography_basis <> 'unresolved'
      )
    ) or (
      item_channel_country_code is not null
      and (
        item_channel_country_code !~ '^[A-Z]{2}$'
        or item_geography_status <> 'channel_country_proxy'
        or item_geography_basis <> 'youtube_channel_country'
      )
    ) then
      raise exception using
        errcode = '22023',
        message = 'YouTube channel country proxy must use the exact geography pair';
    end if;
  end loop;

  if (
    select count(*) <> count(distinct elements.value ->> 'external_id')
      or count(*) <> count(distinct elements.value ->> 'normalized_url')
    from jsonb_array_elements(result_items) as elements(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'YouTube result identities must be unique within one query';
  end if;

  for item_record in
    select elements.value, elements.ordinality::integer as rank
    from jsonb_array_elements(result_items) with ordinality
      as elements(value, ordinality)
    order by elements.ordinality
  loop
    item_value := item_record.value;
    item_rank := item_record.rank;
    item_external_id := item_value ->> 'external_id';
    item_source_url := item_value ->> 'source_url';
    item_normalized_url := item_value ->> 'normalized_url';
    item_title := item_value ->> 'title';
    item_text_excerpt := item_value ->> 'text_excerpt';
    item_author_hash := item_value ->> 'author_hash';
    item_content_hash := item_value ->> 'content_hash';
    item_language := item_value ->> 'language';
    item_metadata := item_value -> 'metadata';
    item_collector_version := item_value ->> 'collector_version';
    item_source_policy_version := item_value ->> 'source_policy_version';
    item_channel_country_code := item_metadata ->> 'channel_country_code';
    item_geography_status := item_metadata ->> 'geography_status';
    item_geography_basis := item_metadata ->> 'geography_basis';

    item_published_at := null;
    if item_value -> 'published_at' is distinct from 'null'::jsonb then
      item_published_at := (item_value ->> 'published_at')::timestamptz;
    end if;

    select source_items.*
    into existing_item
    from ingest.source_items as source_items
    where not source_items.is_demo
      and (
        source_items.normalized_url = item_normalized_url
        or (
          source_items.platform = 'youtube'
          and source_items.external_id = item_external_id
        )
      )
    order by source_items.id
    limit 1
    for update of source_items;

    if found then
      select exists (
        select 1
        from ingest.source_items as source_items
        where not source_items.is_demo
          and source_items.id <> existing_item.id
          and (
            source_items.normalized_url = item_normalized_url
            or (
              source_items.platform = 'youtube'
              and source_items.external_id = item_external_id
            )
          )
      ) into conflicting_identity_exists;

      if conflicting_identity_exists
        or existing_item.source_policy_id <> policy_id
        or existing_item.platform is distinct from 'youtube'
        or existing_item.external_id is distinct from item_external_id
        or existing_item.source_url is distinct from item_source_url
        or existing_item.normalized_url is distinct from item_normalized_url
        or existing_item.domain is distinct from 'youtube.com'
        or existing_item.is_demo
      then
        raise exception using
          errcode = '23505',
          message = 'YouTube discovery identity conflicts with an existing live source item';
      end if;

      update ingest.source_items as source_items
      set title = item_title,
          text_excerpt = item_text_excerpt,
          published_at = item_published_at,
          author_hash = item_author_hash,
          content_hash = item_content_hash,
          collector_type = 'official_api',
          collector_version = item_collector_version,
          source_policy_version = item_source_policy_version,
          access_mode = 'official_api',
          source_kind = 'official_api',
          language = item_language,
          metadata = item_metadata,
          expires_at = lease_checked_at + interval '30 days',
          updated_at = lease_checked_at
      where source_items.id = existing_item.id
        and not source_items.is_demo
      returning source_items.id into source_item_id;
    else
      insert into ingest.source_items (
        source_policy_id,
        platform,
        external_id,
        source_url,
        normalized_url,
        domain,
        title,
        text_excerpt,
        published_at,
        discovered_at,
        author_hash,
        content_hash,
        collector_type,
        collector_version,
        source_policy_version,
        access_mode,
        usage_classification,
        source_kind,
        language,
        status,
        attempt_count,
        metadata,
        expires_at,
        is_demo
      ) values (
        policy_id,
        'youtube',
        item_external_id,
        item_source_url,
        item_normalized_url,
        'youtube.com',
        item_title,
        item_text_excerpt,
        item_published_at,
        lease_checked_at,
        item_author_hash,
        item_content_hash,
        'official_api',
        item_collector_version,
        item_source_policy_version,
        'official_api',
        'activity_only',
        'official_api',
        item_language,
        'activity_only',
        0,
        item_metadata,
        lease_checked_at + interval '30 days',
        false
      )
      returning id into source_item_id;
    end if;

    insert into ingest.source_discoveries as discoveries (
      source_item_id,
      query_name,
      job_id,
      first_seen_at,
      last_seen_at,
      result_rank,
      channel_country_code,
      geography_status,
      geography_basis,
      is_demo,
      created_at,
      updated_at
    ) values (
      source_item_id,
      query_name,
      job_id,
      lease_checked_at,
      lease_checked_at,
      item_rank,
      item_channel_country_code,
      item_geography_status,
      item_geography_basis,
      false,
      lease_checked_at,
      lease_checked_at
    )
    on conflict on constraint source_discoveries_identity_unique
    do update set
      job_id = excluded.job_id,
      last_seen_at = excluded.last_seen_at,
      result_rank = excluded.result_rank,
      channel_country_code = excluded.channel_country_code,
      geography_status = excluded.geography_status,
      geography_basis = excluded.geography_basis,
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
  'Fenced atomic persistence of bounded global YouTube metadata as private Tier D activity-only discovery, followed by job completion and exact gate release.';

commit;
