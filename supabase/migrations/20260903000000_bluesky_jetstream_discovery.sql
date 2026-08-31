begin;

-- Bluesky Jetstream is an official, public, activity-only collector.  Keep
-- it in the same deny-by-default policy registry as the other live sources,
-- but do not route its posts through the statistical opening ledger.
alter table ingest.source_policies
  drop constraint source_policies_collector_type_check;

alter table ingest.source_policies
  drop constraint source_policies_base_url_check;

alter table ingest.source_policies
  add constraint source_policies_base_url_check check (
    base_url is null
    or (base_url ~ '^https://' and char_length(base_url) <= 2048)
    or (
      source_key = 'bluesky_jetstream'
      and base_url = 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
      and char_length(base_url) <= 2048
    )
  );

alter table ingest.source_policies
  add constraint source_policies_collector_type_check check (
    collector_type in (
      'official_api',
      'bluesky_jetstream',
      'scrapling_http',
      'scrapling_dynamic',
      'opencli_authenticated',
      'manual_import',
      'disabled'
    )
  );

alter table ingest.source_policies
  drop constraint source_policies_routes_check;

alter table ingest.source_policies
  add constraint source_policies_routes_check check (
    array_position(routes, null) is null
    and routes <@ array[
      'official_api',
      'bluesky_jetstream',
      'scrapling_http',
      'scrapling_dynamic',
      'opencli_authenticated',
      'manual_import',
      'disabled'
    ]::text[]
    and collector_type = any(routes)
  );

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
  'bluesky_jetstream',
  'Bluesky Jetstream discovery',
  'official_api',
  'jetstream.us-west.bsky.network',
  'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents',
  true,
  'bluesky_jetstream',
  'official_api',
  'not_applicable',
  array['bluesky_jetstream']::text[],
  false,
  1,
  1,
  100,
  1,
  false,
  30,
  '{
    "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
    "collection":"app.bsky.feed.post",
    "operations":["create","update","delete"],
    "kinds":["commit"],
    "subprotocol":"xrpc.v1.json",
    "stream_window_seconds":40,
    "max_events":10000,
    "max_message_bytes":262144,
    "max_stream_bytes":2097152,
    "max_candidates":100,
    "max_deletions":100,
    "max_excerpt_chars":500,
    "keyword_registry":"bluesky-keywords-v1",
    "statistics_eligible":false
  }'::jsonb,
  'bluesky-jetstream-v1',
  60,
  false
);

insert into ingest.source_request_gates (source_key)
values ('bluesky_jetstream');

-- The candidate table is a private, bounded activity ledger.  It deliberately
-- contains no profile, handle, language, country, or statistical fields.
create table ingest.bluesky_jetstream_candidates (
  at_uri text primary key,
  public_url text not null,
  text_excerpt text,
  record_sha256 text not null,
  published_at timestamptz,
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  source_policy_version text not null,
  collector_version text not null,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  last_cursor bigint not null,
  deleted_at timestamptz,
  expires_at timestamptz not null,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bluesky_candidates_at_uri_check check (
    at_uri ~ '^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/[A-Za-z0-9._:%~-]{1,240}$'
  ),
  constraint bluesky_candidates_public_url_check check (
    public_url ~ '^https://bsky\.app/profile/did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/post/[A-Za-z0-9._:%~-]{1,240}$'
    and char_length(public_url) <= 2048
  ),
  constraint bluesky_candidates_excerpt_check check (
    text_excerpt is null
    or (
      char_length(text_excerpt) between 1 and 500
      and translate(text_excerpt, E'\r\n\t', '') !~ '[[:cntrl:]]'
    )
  ),
  constraint bluesky_candidates_hash_check check (
    record_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint bluesky_candidates_published_at_check check (
    published_at is null
    or published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint bluesky_candidates_policy_version_check check (
    btrim(source_policy_version) <> ''
    and char_length(source_policy_version) <= 120
    and btrim(collector_version) <> ''
    and char_length(collector_version) <= 120
  ),
  constraint bluesky_candidates_cursor_check check (last_cursor >= 0),
  constraint bluesky_candidates_time_check check (
    last_seen_at >= first_seen_at
    and expires_at = last_seen_at + interval '30 days'
    and updated_at >= created_at
  ),
  constraint bluesky_candidates_live_only_check check (not is_demo)
);

create index bluesky_candidates_active_idx
  on ingest.bluesky_jetstream_candidates (expires_at, at_uri)
  where deleted_at is null;
create index bluesky_candidates_policy_cursor_idx
  on ingest.bluesky_jetstream_candidates (source_policy_id, last_cursor);

alter table ingest.bluesky_jetstream_candidates enable row level security;
alter table ingest.bluesky_jetstream_candidates force row level security;
create policy bluesky_candidates_service_role_select
  on ingest.bluesky_jetstream_candidates
  for select to service_role using (not is_demo);
revoke all on table ingest.bluesky_jetstream_candidates
  from public, anon, authenticated, service_role;
grant select on table ingest.bluesky_jetstream_candidates to service_role;

-- One immutable row per source+Jetstream sequence makes inclusive replay
-- harmless while retaining enough event identity to reject a conflicting
-- reuse of a sequence number.
create table ingest.bluesky_jetstream_observations (
  id bigint generated always as identity primary key,
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  cursor bigint not null,
  at_uri text not null,
  operation text not null,
  public_url text,
  text_excerpt text,
  record_sha256 text,
  published_at timestamptz,
  observed_at timestamptz not null,
  expires_at timestamptz not null,
  is_demo boolean not null default false,
  constraint bluesky_observations_source_cursor_unique
    unique (source_policy_id, cursor),
  constraint bluesky_observations_cursor_check check (cursor >= 0),
  constraint bluesky_observations_at_uri_check check (
    at_uri ~ '^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/[A-Za-z0-9._:%~-]{1,240}$'
  ),
  constraint bluesky_observations_operation_check check (
    operation in ('upsert', 'delete')
  ),
  constraint bluesky_observations_identity_check check (
    (operation = 'delete'
      and public_url is null
      and text_excerpt is null
      and record_sha256 is null
      and published_at is null)
    or (operation = 'upsert'
      and public_url is not null
      and record_sha256 is not null)
  ),
  constraint bluesky_observations_public_url_check check (
    public_url is null
    or (
      public_url ~ '^https://bsky\.app/profile/did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/post/[A-Za-z0-9._:%~-]{1,240}$'
      and char_length(public_url) <= 2048
    )
  ),
  constraint bluesky_observations_excerpt_check check (
    text_excerpt is null
    or (
      char_length(text_excerpt) between 1 and 500
      and translate(text_excerpt, E'\r\n\t', '') !~ '[[:cntrl:]]'
    )
  ),
  constraint bluesky_observations_hash_check check (
    record_sha256 is null or record_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint bluesky_observations_published_at_check check (
    published_at is null
    or published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint bluesky_observations_time_check check (
    expires_at = observed_at + interval '30 days'
  ),
  constraint bluesky_observations_live_only_check check (not is_demo)
);

create index bluesky_observations_expiry_idx
  on ingest.bluesky_jetstream_observations (expires_at, id);

alter table ingest.bluesky_jetstream_observations enable row level security;
alter table ingest.bluesky_jetstream_observations force row level security;
create policy bluesky_observations_service_role_select
  on ingest.bluesky_jetstream_observations
  for select to service_role using (not is_demo);
revoke all on table ingest.bluesky_jetstream_observations
  from public, anon, authenticated, service_role;
grant select on table ingest.bluesky_jetstream_observations to service_role;

-- The checkpoint is retained across activity-row cleanup so a restart cannot
-- silently replay an unbounded window of Jetstream events.
create table ingest.bluesky_jetstream_checkpoints (
  source_policy_id uuid primary key
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  endpoint text not null,
  protocol text not null,
  collection text not null,
  last_cursor bigint,
  last_collected_at timestamptz,
  events_seen_total bigint not null default 0,
  bytes_seen_total bigint not null default 0,
  candidates_seen_total bigint not null default 0,
  deletions_seen_total bigint not null default 0,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bluesky_checkpoints_endpoint_check check (
    endpoint = 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
  ),
  constraint bluesky_checkpoints_protocol_check check (protocol = 'xrpc.v1.json'),
  constraint bluesky_checkpoints_collection_check check (collection = 'app.bsky.feed.post'),
  constraint bluesky_checkpoints_cursor_check check (last_cursor is null or last_cursor >= 0),
  constraint bluesky_checkpoints_counter_check check (
    events_seen_total >= 0
    and bytes_seen_total >= 0
    and candidates_seen_total >= 0
    and deletions_seen_total >= 0
  ),
  constraint bluesky_checkpoints_live_only_check check (not is_demo)
);

alter table ingest.bluesky_jetstream_checkpoints enable row level security;
alter table ingest.bluesky_jetstream_checkpoints force row level security;
create policy bluesky_checkpoints_service_role_select
  on ingest.bluesky_jetstream_checkpoints
  for select to service_role using (not is_demo);
revoke all on table ingest.bluesky_jetstream_checkpoints
  from public, anon, authenticated, service_role;
grant select on table ingest.bluesky_jetstream_checkpoints to service_role;

insert into ingest.bluesky_jetstream_checkpoints (
  source_policy_id,
  endpoint,
  protocol,
  collection
)
select
  policies.id,
  'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents',
  'xrpc.v1.json',
  'app.bsky.feed.post'
from ingest.source_policies as policies
where policies.source_key = 'bluesky_jetstream';

comment on table ingest.bluesky_jetstream_candidates is
  'Private bounded Bluesky activity candidates. Never opening, rate, geography, profile, or language evidence.';
comment on table ingest.bluesky_jetstream_observations is
  'Private append-only Bluesky event identity ledger, unique by source policy and Jetstream sequence.';
comment on table ingest.bluesky_jetstream_checkpoints is
  'Private fenced Jetstream cursor and aggregate health checkpoint; retained after candidate cleanup.';

-- Parse the canonical sequence representation once at the database boundary.
-- PostgreSQL bigint is deliberately the ceiling used by the worker as well.
create or replace function ingest.bluesky_cursor_v1(value text)
returns bigint
language plpgsql
immutable
parallel safe
set search_path = pg_catalog
as $$
declare
  parsed bigint;
begin
  if value is null
    or value !~ '^(0|[1-9][0-9]{0,18})$'
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky cursor must be a canonical nonnegative decimal integer';
  end if;
  begin
    parsed := value::bigint;
  exception
    when numeric_value_out_of_range or invalid_text_representation then
      raise exception using
        errcode = '22023',
        message = 'Bluesky cursor is outside the approved range';
  end;
  return parsed;
end;
$$;

alter function ingest.bluesky_cursor_v1(text) owner to postgres;
revoke all on function ingest.bluesky_cursor_v1(text)
  from public, anon, authenticated, service_role;
comment on function ingest.bluesky_cursor_v1(text) is
  'Private canonical Jetstream sequence parser; not executable by API or worker roles.';

create or replace function ingest.bluesky_timestamp_v1(
  value text,
  upper_bound timestamptz
)
returns timestamptz
language plpgsql
stable
parallel safe
set search_path = pg_catalog
as $$
declare
  parsed timestamptz;
begin
  if value is null
    or upper_bound is null
    or char_length(value) > 80
    or value ~ '[[:cntrl:]]'
    or value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?(Z|[+-](0[0-9]|1[0-9]|2[0-3]):[0-5][0-9])$'
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky timestamp is invalid';
  end if;
  begin
    parsed := value::timestamptz;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Bluesky timestamp is invalid';
  end;
  if parsed < '2000-01-01 00:00:00+00'::timestamptz
    or parsed > upper_bound
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky timestamp is outside the approved range';
  end if;
  return parsed;
end;
$$;

alter function ingest.bluesky_timestamp_v1(text, timestamptz) owner to postgres;
revoke all on function ingest.bluesky_timestamp_v1(text, timestamptz)
  from public, anon, authenticated, service_role;
comment on function ingest.bluesky_timestamp_v1(text, timestamptz) is
  'Private bounded Jetstream record timestamp parser; not executable by API or worker roles.';

create or replace function ingest.begin_bluesky_jetstream_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint
)
returns table(
  acquired boolean,
  retry_at timestamptz,
  start_cursor bigint
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  leased_job ingest.jobs%rowtype;
  request_gate ingest.source_request_gates%rowtype;
  checkpoint ingest.bluesky_jetstream_checkpoints%rowtype;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  lease_checked_at timestamptz;
  request_retry_at timestamptz;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null
    or btrim(worker_id) = ''
    or char_length(worker_id) > 160
  then
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
  where jobs.id = begin_bluesky_jetstream_job.job_id
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
    or leased_job.job_type <> 'source.bluesky.jetstream'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky begin requires a live source.bluesky.jetstream job with an empty payload';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:bluesky:jetstream:live', 0)
  );

  select
    policies.id,
    policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = 'bluesky_jetstream'
    and policies.display_name = 'Bluesky Jetstream discovery'
    and policies.source_kind = 'official_api'
    and policies.domain = 'jetstream.us-west.bsky.network'
    and policies.base_url =
      'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
    and policies.enabled
    and policies.collector_type = 'bluesky_jetstream'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['bluesky_jetstream']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 100
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = '{
      "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
      "collection":"app.bsky.feed.post",
      "operations":["create","update","delete"],
      "kinds":["commit"],
      "subprotocol":"xrpc.v1.json",
      "stream_window_seconds":40,
      "max_events":10000,
      "max_message_bytes":262144,
      "max_stream_bytes":2097152,
      "max_candidates":100,
      "max_deletions":100,
      "max_excerpt_chars":500,
      "keyword_registry":"bluesky-keywords-v1",
      "statistics_eligible":false
    }'::jsonb
    and policies.version = 'bluesky-jetstream-v1'
    and policies.expected_interval_seconds = 60
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'bluesky_jetstream'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream request gate is unavailable';
  end if;

  select checkpoints.*
  into checkpoint
  from ingest.bluesky_jetstream_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and not checkpoints.is_demo
  for update of checkpoints;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream checkpoint is unavailable';
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
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
    and lease_checked_at < policy_last_attempt_at + interval '1 second'
  then
    if request_retry_at is null
      or request_retry_at < policy_last_attempt_at + interval '1 second'
    then
      request_retry_at := policy_last_attempt_at + interval '1 second';
    end if;
  end if;

  if request_retry_at is not null then
    return query select false, request_retry_at, checkpoint.last_cursor;
    return;
  end if;

  -- A 40-second stream plus close/finalization work fits under this renewed
  -- generation fence while leaving a conservative margin.
  update ingest.jobs as jobs
  set lock_expires_at = greatest(
        jobs.lock_expires_at,
        lease_checked_at + interval '55 seconds'
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
  where gates.source_key = 'bluesky_jetstream';

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  return query select true, null::timestamptz, checkpoint.last_cursor;
end;
$$;

alter function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  owner to postgres;
revoke all on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  to service_role;
comment on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint) is
  'Generation-fenced preflight for one bounded anonymous Bluesky Jetstream activity slice.';

-- The worker returns a deliberately small, versioned result. A cursor is a
-- Jetstream sequence (not the event's RFC3339 time) and is carried as a JSON
-- integer or null. The worker uses start_cursor as the resume boundary and
-- emits candidate/delete cursors only in the strict (start_cursor, end_cursor]
-- window, while nonmatching valid commits may still advance end_cursor.
create or replace function ingest.finalize_bluesky_jetstream_job(
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
  request_gate ingest.source_request_gates%rowtype;
  checkpoint ingest.bluesky_jetstream_checkpoints%rowtype;
  existing_observation ingest.bluesky_jetstream_observations%rowtype;
  existing_candidate ingest.bluesky_jetstream_candidates%rowtype;
  policy_id uuid;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  event_time timestamptz;
  result_start_cursor bigint;
  result_end_cursor bigint;
  result_events_seen bigint;
  result_bytes_seen bigint;
  candidate_count integer;
  deletion_count integer;
  candidate_record record;
  deletion_record record;
  candidate_value jsonb;
  deletion_value jsonb;
  candidate_at_uri text;
  candidate_public_url text;
  candidate_excerpt text;
  candidate_hash text;
  candidate_published_at timestamptz;
  candidate_cursor bigint;
  deletion_at_uri text;
  deletion_cursor bigint;
  persisted_observation_id bigint;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null
    or btrim(worker_id) = ''
    or char_length(worker_id) > 160
  then
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
  where jobs.id = finalize_bluesky_jetstream_job.job_id
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
    or leased_job.job_type <> 'source.bluesky.jetstream'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky finalizer requires a live source.bluesky.jetstream job with an empty payload';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:bluesky:jetstream:live', 0)
  );

  -- Re-read the immutable policy after the network request.  A changed
  -- endpoint, filter, limit, or kill switch rolls the entire finalization
  -- back instead of allowing a stale worker to persist data.
  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'bluesky_jetstream'
    and policies.display_name = 'Bluesky Jetstream discovery'
    and policies.source_kind = 'official_api'
    and policies.domain = 'jetstream.us-west.bsky.network'
    and policies.base_url =
      'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
    and policies.enabled
    and policies.collector_type = 'bluesky_jetstream'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['bluesky_jetstream']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 100
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = '{
      "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
      "collection":"app.bsky.feed.post",
      "operations":["create","update","delete"],
      "kinds":["commit"],
      "subprotocol":"xrpc.v1.json",
      "stream_window_seconds":40,
      "max_events":10000,
      "max_message_bytes":262144,
      "max_stream_bytes":2097152,
      "max_candidates":100,
      "max_deletions":100,
      "max_excerpt_chars":500,
      "keyword_registry":"bluesky-keywords-v1",
      "statistics_eligible":false
    }'::jsonb
    and policies.version = 'bluesky-jetstream-v1'
    and policies.expected_interval_seconds = 60
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'bluesky_jetstream'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream request gate is unavailable';
  end if;

  select checkpoints.*
  into checkpoint
  from ingest.bluesky_jetstream_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and not checkpoints.is_demo
  for update of checkpoints;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream checkpoint is unavailable';
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

  if request_gate.owner_job_id is distinct from job_id
    or request_gate.owner_lease_generation is distinct from lease_generation
    or request_gate.active_until is null
    or request_gate.active_until <= lease_checked_at
  then
    raise exception using
      errcode = '55000',
      message = 'Bluesky Jetstream request gate is not owned by this job lease';
  end if;

  completion_time := clock_timestamp();
  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 2097152
    or not (result ?& array[
      'version', 'start_cursor', 'end_cursor', 'events_seen', 'bytes_seen',
      'candidates', 'deletions'
    ])
    or result - array[
      'version', 'start_cursor', 'end_cursor', 'events_seen', 'bytes_seen',
      'candidates', 'deletions'
    ] <> '{}'::jsonb
    or jsonb_typeof(result -> 'version') is distinct from 'string'
    or result ->> 'version' <> '1.0.0'
    or jsonb_typeof(result -> 'start_cursor') not in ('number', 'null')
    or jsonb_typeof(result -> 'end_cursor') not in ('number', 'null')
    or jsonb_typeof(result -> 'events_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'bytes_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'candidates') is distinct from 'array'
    or jsonb_typeof(result -> 'deletions') is distinct from 'array'
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky result must match the exact bounded v1 contract';
  end if;

  if (result ->> 'events_seen') !~ '^(0|[1-9][0-9]{0,9})$'
    or (result ->> 'bytes_seen') !~ '^(0|[1-9][0-9]{0,6})$'
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky event and byte counters must be canonical bounded integers';
  end if;

  begin
    result_start_cursor := case
      when result -> 'start_cursor' = 'null'::jsonb then null
      else ingest.bluesky_cursor_v1(result ->> 'start_cursor')
    end;
    result_end_cursor := case
      when result -> 'end_cursor' = 'null'::jsonb then null
      else ingest.bluesky_cursor_v1(result ->> 'end_cursor')
    end;
    result_events_seen := (result ->> 'events_seen')::bigint;
    result_bytes_seen := (result ->> 'bytes_seen')::bigint;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Bluesky result counters or cursors are outside the approved range';
  end;

  if result_events_seen > 10000
    or result_bytes_seen > 2097152
    or (result_start_cursor is not null and result_end_cursor is not null
      and result_end_cursor < result_start_cursor)
    or result_start_cursor is distinct from checkpoint.last_cursor
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky result exceeds the fixed bounds or does not start at the checkpoint';
  end if;

  candidate_count := jsonb_array_length(result -> 'candidates');
  deletion_count := jsonb_array_length(result -> 'deletions');
  if candidate_count > 100 or deletion_count > 100
    or result_events_seen < candidate_count + deletion_count
    or (result_end_cursor is null and (candidate_count <> 0 or deletion_count <> 0))
    or (result_events_seen > 0 and result_end_cursor is null)
    or (result_events_seen = 0 and (
      candidate_count <> 0 or deletion_count <> 0
      or result_end_cursor is distinct from result_start_cursor
    ))
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky result candidate, deletion, or event bounds are invalid';
  end if;

  -- Validate every candidate before writing any row.  The exact six keys are
  -- the only worker-controlled fields; all source/policy versions come from
  -- the locked database contract.  The final segment of public_url must be
  -- the AT URI record key, preventing an unrelated public link from being
  -- attached to a candidate.
  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
  loop
    candidate_value := candidate_record.value;
    if jsonb_typeof(candidate_value) is distinct from 'object'
      or not (candidate_value ?& array[
        'at_uri', 'public_url', 'text_excerpt', 'record_sha256',
        'published_at', 'cursor'
      ])
      or candidate_value - array[
        'at_uri', 'public_url', 'text_excerpt', 'record_sha256',
        'published_at', 'cursor'
      ] <> '{}'::jsonb
      or jsonb_typeof(candidate_value -> 'at_uri') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'public_url') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'record_sha256') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'published_at') not in ('string', 'null')
      or jsonb_typeof(candidate_value -> 'cursor') is distinct from 'number'
      or (
        candidate_value -> 'text_excerpt' is distinct from 'null'::jsonb
        and jsonb_typeof(candidate_value -> 'text_excerpt') is distinct from 'string'
      )
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky candidates must use the exact bounded v1 item contract';
    end if;

    candidate_at_uri := candidate_value ->> 'at_uri';
    candidate_public_url := candidate_value ->> 'public_url';
    candidate_excerpt := candidate_value ->> 'text_excerpt';
    candidate_hash := candidate_value ->> 'record_sha256';
    if candidate_at_uri !~ '^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/[A-Za-z0-9._:%~-]{1,240}$'
      or candidate_public_url !~ '^https://bsky\.app/profile/did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/post/[A-Za-z0-9._:%~-]{1,240}$'
      or char_length(candidate_public_url) > 2048
      or candidate_hash !~ '^[0-9a-f]{64}$'
      or (candidate_excerpt is not null and (
        char_length(candidate_excerpt) not between 1 and 500
        or translate(candidate_excerpt, E'\r\n\t', '') ~ '[[:cntrl:]]'
      ))
      or candidate_public_url <> 'https://bsky.app/profile/'
        || split_part(candidate_at_uri, '/', 3)
        || '/post/' || split_part(candidate_at_uri, '/', 5)
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky candidate identity, link, text, or hash is invalid';
    end if;

    candidate_cursor := ingest.bluesky_cursor_v1(candidate_value ->> 'cursor');
    if (result_start_cursor is not null and candidate_cursor <= result_start_cursor)
      or result_end_cursor is null
      or candidate_cursor > result_end_cursor
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky candidate cursor is outside the requested inclusive window';
    end if;

    candidate_published_at := case
      when candidate_value -> 'published_at' = 'null'::jsonb then null
      else ingest.bluesky_timestamp_v1(
        candidate_value ->> 'published_at',
        completion_time + interval '1 day'
      )
    end;
  end loop;

  for deletion_record in
    select elements.value
    from jsonb_array_elements(result -> 'deletions') as elements(value)
  loop
    deletion_value := deletion_record.value;
    if jsonb_typeof(deletion_value) is distinct from 'object'
      or not (deletion_value ?& array['at_uri', 'cursor'])
      or deletion_value - array['at_uri', 'cursor'] <> '{}'::jsonb
      or jsonb_typeof(deletion_value -> 'at_uri') is distinct from 'string'
      or jsonb_typeof(deletion_value -> 'cursor') is distinct from 'number'
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky deletions must use the exact bounded v1 item contract';
    end if;
    deletion_at_uri := deletion_value ->> 'at_uri';
    if deletion_at_uri !~ '^at://did:[a-z0-9]+:[A-Za-z0-9._:%-]{1,240}/app\.bsky\.feed\.post/[A-Za-z0-9._:%~-]{1,240}$'
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky deletion identity is invalid';
    end if;
    deletion_cursor := ingest.bluesky_cursor_v1(deletion_value ->> 'cursor');
    if (result_start_cursor is not null and deletion_cursor <= result_start_cursor)
      or result_end_cursor is null
      or deletion_cursor > result_end_cursor
    then
      raise exception using
        errcode = '22023',
        message = 'Bluesky deletion cursor is outside the requested inclusive window';
    end if;
  end loop;

  -- One source sequence denotes one Jetstream event.  Reject duplicate or
  -- ambiguous sequence identities before the first upsert; repeats from the
  -- inclusive boundary are accepted only when their stored event matches.
  if (
    select count(*) <> count(distinct event_rows.cursor)
    from (
      select value ->> 'cursor' as cursor
      from jsonb_array_elements(result -> 'candidates') as values(value)
      union all
      select value ->> 'cursor'
      from jsonb_array_elements(result -> 'deletions') as values(value)
    ) as event_rows
  ) then
    raise exception using
      errcode = '22023',
      message = 'Bluesky result sequences must be unique within one slice';
  end if;

  if (
    select count(*) <> count(distinct value ->> 'at_uri')
    from jsonb_array_elements(result -> 'candidates') as values(value)
  ) or (
    select count(*) <> count(distinct value ->> 'at_uri')
    from jsonb_array_elements(result -> 'deletions') as values(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'Bluesky identities must be unique within each result list';
  end if;

  if (
    select count(*)
    from (
      select value ->> 'at_uri' as at_uri
      from jsonb_array_elements(result -> 'candidates') as values(value)
      intersect
      select value ->> 'at_uri'
      from jsonb_array_elements(result -> 'deletions') as values(value)
    ) as conflicting_uris
  ) > 0 then
    raise exception using
      errcode = '22023',
      message = 'Bluesky candidates and deletions must not share an identity in one slice';
  end if;

  -- Candidate and observation writes are all inside this function's one
  -- transaction.  A repeated inclusive event is checked against the immutable
  -- observation row, then its candidate is safely refreshed without a second
  -- observation.  Deletes produce a private tombstone rather than silently
  -- erasing event history.
  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
    order by (elements.value ->> 'cursor')::numeric
  loop
    candidate_value := candidate_record.value;
    candidate_at_uri := candidate_value ->> 'at_uri';
    candidate_public_url := candidate_value ->> 'public_url';
    candidate_excerpt := candidate_value ->> 'text_excerpt';
    candidate_hash := candidate_value ->> 'record_sha256';
    candidate_cursor := ingest.bluesky_cursor_v1(candidate_value ->> 'cursor');
    candidate_published_at := case
      when candidate_value -> 'published_at' = 'null'::jsonb then null
      else ingest.bluesky_timestamp_v1(
        candidate_value ->> 'published_at',
        completion_time + interval '1 day'
      )
    end;
    event_time := clock_timestamp();

    persisted_observation_id := null;
    insert into ingest.bluesky_jetstream_observations as observations (
      source_policy_id,
      cursor,
      at_uri,
      operation,
      public_url,
      text_excerpt,
      record_sha256,
      published_at,
      observed_at,
      expires_at,
      is_demo
    ) values (
      policy_id,
      candidate_cursor,
      candidate_at_uri,
      'upsert',
      candidate_public_url,
      candidate_excerpt,
      candidate_hash,
      candidate_published_at,
      event_time,
      event_time + interval '30 days',
      false
    )
    on conflict (source_policy_id, cursor) do nothing
    returning observations.id into persisted_observation_id;

    if persisted_observation_id is null then
      select observations.*
      into existing_observation
      from ingest.bluesky_jetstream_observations as observations
      where observations.source_policy_id = policy_id
        and observations.cursor = candidate_cursor
      for update of observations;
      if not found
        or existing_observation.operation <> 'upsert'
        or existing_observation.at_uri <> candidate_at_uri
        or existing_observation.public_url is distinct from candidate_public_url
        or existing_observation.text_excerpt is distinct from candidate_excerpt
        or existing_observation.record_sha256 is distinct from candidate_hash
        or existing_observation.published_at is distinct from candidate_published_at
      then
        raise exception using
          errcode = '22023',
          message = 'Bluesky inclusive replay sequence conflicts with its stored event';
      end if;
    end if;

    select candidates.*
    into existing_candidate
    from ingest.bluesky_jetstream_candidates as candidates
    where candidates.at_uri = candidate_at_uri
    for update of candidates;

    if found then
      if existing_candidate.is_demo
        or existing_candidate.source_policy_id <> policy_id
        or candidate_cursor < existing_candidate.last_cursor
      then
        raise exception using
          errcode = '22023',
          message = 'Bluesky candidate would reuse a private identity or move its cursor backward';
      end if;
      if candidate_cursor = existing_candidate.last_cursor then
        if existing_candidate.deleted_at is not null
          or existing_candidate.public_url <> candidate_public_url
          or existing_candidate.text_excerpt is distinct from candidate_excerpt
          or existing_candidate.record_sha256 <> candidate_hash
          or existing_candidate.published_at is distinct from candidate_published_at
        then
          raise exception using
            errcode = '22023',
            message = 'Bluesky candidate replay conflicts with its stored state';
        end if;
      else
        update ingest.bluesky_jetstream_candidates as candidates
        set public_url = candidate_public_url,
            text_excerpt = candidate_excerpt,
            record_sha256 = candidate_hash,
            published_at = candidate_published_at,
            source_policy_version = 'bluesky-jetstream-v1',
            collector_version = 'bluesky-jetstream-v1',
            last_seen_at = event_time,
            last_cursor = candidate_cursor,
            deleted_at = null,
            expires_at = event_time + interval '30 days',
            updated_at = event_time
        where candidates.at_uri = candidate_at_uri;
      end if;
    else
      insert into ingest.bluesky_jetstream_candidates (
        at_uri,
        public_url,
        text_excerpt,
        record_sha256,
        published_at,
        source_policy_id,
        source_policy_version,
        collector_version,
        first_seen_at,
        last_seen_at,
        last_cursor,
        deleted_at,
        expires_at,
        is_demo,
        created_at,
        updated_at
      ) values (
        candidate_at_uri,
        candidate_public_url,
        candidate_excerpt,
        candidate_hash,
        candidate_published_at,
        policy_id,
        'bluesky-jetstream-v1',
        'bluesky-jetstream-v1',
        event_time,
        event_time,
        candidate_cursor,
        null,
        event_time + interval '30 days',
        false,
        event_time,
        event_time
      );
    end if;
  end loop;

  for deletion_record in
    select elements.value
    from jsonb_array_elements(result -> 'deletions') as elements(value)
    order by (elements.value ->> 'cursor')::numeric
  loop
    deletion_value := deletion_record.value;
    deletion_at_uri := deletion_value ->> 'at_uri';
    deletion_cursor := ingest.bluesky_cursor_v1(deletion_value ->> 'cursor');
    event_time := clock_timestamp();

    persisted_observation_id := null;
    insert into ingest.bluesky_jetstream_observations as observations (
      source_policy_id,
      cursor,
      at_uri,
      operation,
      observed_at,
      expires_at,
      is_demo
    ) values (
      policy_id,
      deletion_cursor,
      deletion_at_uri,
      'delete',
      event_time,
      event_time + interval '30 days',
      false
    )
    on conflict (source_policy_id, cursor) do nothing
    returning observations.id into persisted_observation_id;

    if persisted_observation_id is null then
      select observations.*
      into existing_observation
      from ingest.bluesky_jetstream_observations as observations
      where observations.source_policy_id = policy_id
        and observations.cursor = deletion_cursor
      for update of observations;
      if not found
        or existing_observation.operation <> 'delete'
        or existing_observation.at_uri <> deletion_at_uri
      then
        raise exception using
          errcode = '22023',
          message = 'Bluesky inclusive replay deletion conflicts with its stored event';
      end if;
    end if;

    select candidates.*
    into existing_candidate
    from ingest.bluesky_jetstream_candidates as candidates
    where candidates.at_uri = deletion_at_uri
    for update of candidates;

    if found then
      if existing_candidate.is_demo
        or existing_candidate.source_policy_id <> policy_id
        or deletion_cursor < existing_candidate.last_cursor
      then
        raise exception using
          errcode = '22023',
          message = 'Bluesky deletion would reuse a private identity or move its cursor backward';
      elsif deletion_cursor = existing_candidate.last_cursor then
        if existing_candidate.deleted_at is null then
          raise exception using
            errcode = '22023',
            message = 'Bluesky deletion replay conflicts with a live candidate state';
        end if;
      else
        update ingest.bluesky_jetstream_candidates as candidates
        set source_policy_version = 'bluesky-jetstream-v1',
            collector_version = 'bluesky-jetstream-v1',
            last_seen_at = event_time,
            last_cursor = deletion_cursor,
            deleted_at = event_time,
            expires_at = event_time + interval '30 days',
            updated_at = event_time
        where candidates.at_uri = deletion_at_uri;
      end if;
    end if;
  end loop;

  completion_time := clock_timestamp();
  update ingest.bluesky_jetstream_checkpoints as checkpoints
  set last_cursor = result_end_cursor,
      last_collected_at = completion_time,
      events_seen_total = checkpoints.events_seen_total + result_events_seen,
      bytes_seen_total = checkpoints.bytes_seen_total + result_bytes_seen,
      candidates_seen_total = checkpoints.candidates_seen_total + candidate_count,
      deletions_seen_total = checkpoints.deletions_seen_total + deletion_count,
      updated_at = completion_time
  where checkpoints.source_policy_id = policy_id
    and not checkpoints.is_demo
    and checkpoints.last_cursor is not distinct from result_start_cursor;
  if not found then
    raise exception using
      errcode = '40001',
      message = 'Bluesky Jetstream checkpoint changed before atomic cursor advance';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = greatest(
        coalesce(policies.last_attempt_at, '-infinity'::timestamptz),
        completion_time
      ),
      last_success_at = completion_time,
      updated_at = completion_time
  where policies.id = policy_id;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream source policy changed during finalization';
  end if;

  update ingest.jobs as jobs
  set status = 'completed',
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = completion_time,
      last_error_code = null,
      last_error_message = null,
      updated_at = completion_time
  where jobs.id = job_id
    and jobs.status = 'running'
    and jobs.locked_by = worker_id
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > completion_time
    and not jobs.is_demo
  returning jobs.* into completed_job;
  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'Bluesky Jetstream completion lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = job_id
    and gates.owner_lease_generation = $3;
  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'Bluesky Jetstream completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb) is
  'Fenced atomic Bluesky Jetstream v1 finalizer. It persists only bounded private activity candidates and sequence observations; it never promotes evidence or geography.';

-- Scheduled jobs remain fail closed at the table boundary. Bluesky uses one
-- exact empty payload and one exact schedule name enforced again by the RPC.
alter table ingest.jobs
  drop constraint jobs_live_scheduled_enqueue_allowlist_check;

alter table ingest.jobs
  add constraint jobs_live_scheduled_enqueue_allowlist_check
  check (
    is_demo
    or dedupe_key is null
    or dedupe_key !~ '^schedule:'
    or (
      job_type in (
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.bluesky.jetstream'
      )
      and payload = '{}'::jsonb
    )
    or (
      job_type = 'source.youtube.discovery'
      and payload ?& array['query_name']
      and payload - array['query_name'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'query_name') = 'string'
      and payload ->> 'query_name' in (
        'pokemon-tcg-booster-box-opening',
        'pokemon-tcg-etb-opening',
        'pokemon-tcg-booster-bundle-opening',
        'pokemon-tcg-pack-opening',
        'pokemon-tcg-opening-batch-code'
      )
    )
    or (
      job_type = 'source.public_study.opening'
      -- Coverage-only studies use the separately fenced
      -- reviewed-coverage-schedule prefix and constraint; this schedule:
      -- boundary intentionally retains only the two statistical-ledger keys.
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
      )
    )
  );

-- Preserve the already-reviewed enqueue implementations byte-for-byte except
-- for the new exact job type, its empty payload, and its canonical schedule.
-- Guards make future upstream drift fail the migration instead of widening an
-- allowlist accidentally.
do $migration$
declare
  definition text;
  updated_definition text;
begin
  select pg_get_functiondef(
    'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'::regprocedure
  ) into definition;

  updated_definition := replace(
    definition,
    $old$    'source.public_study.opening'
  ) then$old$,
    $new$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if job_type = 'source.youtube.discovery' and ($old$,
    $new$  if job_type = 'source.bluesky.jetstream' and (
    payload <> '{}'::jsonb
    or schedule_name <> 'bluesky_jetstream'
  ) then
    raise exception using
      errcode = '22023',
      message = 'Bluesky jobs require an empty payload and the exact bluesky_jetstream schedule';
  end if;
  if job_type = 'source.youtube.discovery' and ($new$
  );

  if updated_definition = definition
    or position($needle$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$needle$ in updated_definition) = 0
    or position($needle$    'source.public_study.opening'
  ) then$needle$ in updated_definition) <> 0
    or position($needle$schedule_name <> 'bluesky_jetstream'$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_scheduled_job_v1 no longer matches the reviewed Bluesky extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamptz,integer)'::regprocedure
  ) into definition;

  updated_definition := replace(
    definition,
    $old$    'source.public_study.opening'
  ) then$old$,
    $new$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if p_job_type = 'source.youtube.discovery' and ($old$,
    $new$  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'Bluesky jobs require an empty payload';
  end if;
  if p_job_type = 'source.youtube.discovery' and ($new$
  );

  if updated_definition = definition
    or position($needle$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$needle$ in updated_definition) = 0
    or position($needle$    'source.public_study.opening'
  ) then$needle$ in updated_definition) <> 0
    or position($needle$p_job_type = 'source.bluesky.jetstream'$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_job_v1 no longer matches the reviewed Bluesky extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$    'source.public_study.opening'
  ) then$old$,
    $new$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$new$
  );
  if updated_definition = definition
    or position($needle$    'source.public_study.opening',
    'source.bluesky.jetstream'
  ) then$needle$ in updated_definition) = 0
    or position($needle$    'source.public_study.opening'
  ) then$needle$ in updated_definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'complete_job_v2 no longer matches the reviewed Bluesky extension point';
  end if;
  execute updated_definition;
end;
$migration$;

-- Cleanup gives each private activity table an independent 500,000-row budget.
-- The collector can persist at most 216,000 candidates and 432,000 observations
-- during the scheduler's reviewed 36-hour recovery window. Ten-thousand-row
-- sub-batches bound each locking query while the larger per-table budget keeps
-- the 30-day retention path ahead of the maximum accepted ingestion rate. The
-- checkpoint is deliberately never selected or deleted, so restarts cannot
-- silently replay an unbounded stream window.
create or replace function ingest.prune_bluesky_jetstream_v1(
  cutoff timestamptz,
  max_rows integer default 500000
)
returns table(candidates_deleted integer, observations_deleted integer)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  deleted_candidates integer := 0;
  deleted_observations integer := 0;
  batch_deleted integer := 0;
  batch_limit integer := 0;
begin
  if cutoff is null then
    raise exception using errcode = '22023', message = 'cutoff must not be null';
  end if;
  if max_rows is null or max_rows < 1 or max_rows > 500000 then
    raise exception using
      errcode = '22023',
      message = 'max_rows must be between 1 and 500000 per table';
  end if;

  loop
    batch_limit := least(10000, max_rows - deleted_candidates);
    exit when batch_limit <= 0;
    with locked_candidates as (
      select candidates.at_uri
      from ingest.bluesky_jetstream_candidates as candidates
      where candidates.expires_at <= cutoff
      order by candidates.expires_at, candidates.at_uri
      for update of candidates skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.bluesky_jetstream_candidates as candidates
      using locked_candidates
      where candidates.at_uri = locked_candidates.at_uri
      returning 1
    )
    select count(*)::integer into batch_deleted from deleted;
    deleted_candidates := deleted_candidates + batch_deleted;
    exit when batch_deleted < batch_limit;
  end loop;

  loop
    batch_limit := least(10000, max_rows - deleted_observations);
    exit when batch_limit <= 0;
    with locked_observations as (
      select observations.id
      from ingest.bluesky_jetstream_observations as observations
      where observations.expires_at <= cutoff
      order by observations.expires_at, observations.id
      for update of observations skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.bluesky_jetstream_observations as observations
      using locked_observations
      where observations.id = locked_observations.id
      returning 1
    )
    select count(*)::integer into batch_deleted from deleted;
    deleted_observations := deleted_observations + batch_deleted;
    exit when batch_deleted < batch_limit;
  end loop;

  return query select deleted_candidates, deleted_observations;
end;
$$;

alter function ingest.prune_bluesky_jetstream_v1(timestamptz, integer)
  owner to postgres;
revoke all on function ingest.prune_bluesky_jetstream_v1(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_bluesky_jetstream_v1(timestamptz, integer) is
  'Owner-only ordered cleanup for private Bluesky candidates and observations, independently bounded to 500000 rows per table in 10000-row sub-batches. Checkpoints are retained.';

do $migration$
declare
  definition text;
  updated_definition text;
  cleanup_call constant text := $call$  perform ingest.prune_expired_ephemera_v2(
    cutoff => lease_checked_at,
    max_rows => 10000
  );$call$;
begin
  select pg_get_functiondef(
    'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    cleanup_call,
    cleanup_call || $call$

  perform ingest.prune_bluesky_jetstream_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );$call$
  );
  if updated_definition = definition
    or position('prune_bluesky_jetstream_v1' in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_cleanup_job no longer matches the reviewed Bluesky cleanup extension point';
  end if;
  execute updated_definition;
end;
$migration$;

-- Public callers receive one strict source-health projection only. The RPC
-- never selects an event identity, excerpt, hash, cursor, endpoint, gate, or
-- internal policy identifier.
create or replace function public.get_public_social_discovery_v1()
returns jsonb
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  with registered_policy as (
    select
      policies.enabled,
      (
        policies.display_name = 'Bluesky Jetstream discovery'
        and policies.source_kind = 'official_api'
        and policies.domain = 'jetstream.us-west.bsky.network'
        and policies.base_url =
          'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
        and policies.collector_type = 'bluesky_jetstream'
        and policies.access_mode = 'official_api'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['bluesky_jetstream']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 1
        and policies.max_items_per_run = 100
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.config = '{
          "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
          "collection":"app.bsky.feed.post",
          "operations":["create","update","delete"],
          "kinds":["commit"],
          "subprotocol":"xrpc.v1.json",
          "stream_window_seconds":40,
          "max_events":10000,
          "max_message_bytes":262144,
          "max_stream_bytes":2097152,
          "max_candidates":100,
          "max_deletions":100,
          "max_excerpt_chars":500,
          "keyword_registry":"bluesky-keywords-v1",
          "statistics_eligible":false
        }'::jsonb
        and policies.version = 'bluesky-jetstream-v1'
        and policies.expected_interval_seconds = 60
        and not policies.is_demo
      ) as contract_valid,
      policies.id
    from ingest.source_policies as policies
    where policies.source_key = 'bluesky_jetstream'
  ), public_state as (
    select
      case
        when policies.id is null or not policies.contract_valid then 'attention'
        when not policies.enabled then 'paused'
        when checkpoints.source_policy_id is null then 'attention'
        when checkpoints.last_collected_at is null then 'delayed'
        when checkpoints.last_collected_at < statement_timestamp() - interval '3 minutes'
          then 'delayed'
        else 'operational'
      end as status,
      checkpoints.last_collected_at,
      (
        select count(*)::integer
        from ingest.bluesky_jetstream_candidates as candidates
        where candidates.source_policy_id = policies.id
          and not candidates.is_demo
          and candidates.deleted_at is null
          and candidates.expires_at > statement_timestamp()
      ) as active_candidate_count
    from (select true) as singleton
    left join registered_policy as policies on true
    left join ingest.bluesky_jetstream_checkpoints as checkpoints
      on checkpoints.source_policy_id = policies.id
      and not checkpoints.is_demo
  )
  select jsonb_build_object(
    'schemaVersion', '1.0.0',
    'sources', jsonb_build_array(
      jsonb_build_object(
        'id', 'bluesky_jetstream',
        'name', 'Bluesky Jetstream discovery',
        'kind', 'social',
        'access', 'public',
        'status', public_state.status,
        'lastCollectedAt', public_state.last_collected_at,
        'url', 'https://bsky.network/docs/jetstream/',
        'note', format(
          '%s retained activity candidates. Bounded public-post discovery only; never opening evidence, geography, a hit, or a pull-rate denominator.',
          coalesce(public_state.active_candidate_count, 0)
        )
      )
    )
  )
  from public_state;
$$;

alter function public.get_public_social_discovery_v1() owner to postgres;
revoke all on function public.get_public_social_discovery_v1()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v1()
  to anon, authenticated;
comment on function public.get_public_social_discovery_v1() is
  'Strict public-safe Bluesky collector health projection. It never returns activity identities, text, hashes, cursors, endpoints, gates, or policy identifiers.';

commit;
