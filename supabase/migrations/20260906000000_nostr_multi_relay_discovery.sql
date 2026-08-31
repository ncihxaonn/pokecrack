begin;

-- Nostr is an anonymous, activity-only source.  The relay inventory and all
-- request parameters are fixed here; workers may select only one of the three
-- reviewed relay keys and may not supply an endpoint, profile, or filter.
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
    or (
      source_key = 'nostr_relay_primal'
      and base_url = 'wss://relay.primal.net/'
      and char_length(base_url) <= 2048
    )
    or (
      source_key = 'nostr_relay_nos_lol'
      and base_url = 'wss://nos.lol/'
      and char_length(base_url) <= 2048
    )
    or (
      source_key = 'nostr_relay_nostr_net'
      and base_url = 'wss://relay.nostr.net/'
      and char_length(base_url) <= 2048
    )
  );

alter table ingest.source_policies
  drop constraint source_policies_collector_type_check;

alter table ingest.source_policies
  add constraint source_policies_collector_type_check check (
    collector_type in (
      'official_api',
      'bluesky_jetstream',
      'nostr_relay',
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
      'nostr_relay',
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
) values
(
  'nostr_relay_primal',
  'Nostr relay relay.primal.net discovery',
  'public_web',
  'relay.primal.net',
  'wss://relay.primal.net/',
  true,
  'nostr_relay',
  'public',
  'not_applicable',
  array['nostr_relay']::text[],
  false,
  1,
  1,
  100,
  1,
  false,
  30,
  '{
    "relay_key":"primal",
    "endpoint":"wss://relay.primal.net/",
    "nip11_url":"https://relay.primal.net/",
    "protocol":"nip01",
    "policy_state":"degraded_missing_relay_specific_terms",
    "required_nips":[1,9,11],
    "approved_tags":["pokemontcg","PokemonTCG","pokemoncards","PokemonCards","ポケカ","ポケモンカード","포켓몬카드","宝可梦卡牌","寶可夢卡牌"],
    "replay_overlap_seconds":300,
    "stream_window_seconds":15,
    "max_events":100,
    "max_message_bytes":262144,
    "max_stream_bytes":2097152,
    "max_candidates":100,
    "max_deletions":100,
    "max_delete_targets":16,
    "statistics_eligible":false
  }'::jsonb,
  'nostr-multi-relay-v1',
  60,
  false
),
(
  'nostr_relay_nos_lol',
  'Nostr relay nos.lol discovery',
  'public_web',
  'nos.lol',
  'wss://nos.lol/',
  true,
  'nostr_relay',
  'public',
  'not_applicable',
  array['nostr_relay']::text[],
  false,
  1,
  1,
  100,
  1,
  false,
  30,
  '{
    "relay_key":"nos_lol",
    "endpoint":"wss://nos.lol/",
    "nip11_url":"https://nos.lol/",
    "protocol":"nip01",
    "policy_state":"degraded_missing_relay_specific_terms",
    "required_nips":[1,9,11],
    "approved_tags":["pokemontcg","PokemonTCG","pokemoncards","PokemonCards","ポケカ","ポケモンカード","포켓몬카드","宝可梦卡牌","寶可夢卡牌"],
    "replay_overlap_seconds":300,
    "stream_window_seconds":15,
    "max_events":100,
    "max_message_bytes":262144,
    "max_stream_bytes":2097152,
    "max_candidates":100,
    "max_deletions":100,
    "max_delete_targets":16,
    "statistics_eligible":false
  }'::jsonb,
  'nostr-multi-relay-v1',
  60,
  false
),
(
  'nostr_relay_nostr_net',
  'Nostr relay relay.nostr.net discovery',
  'public_web',
  'relay.nostr.net',
  'wss://relay.nostr.net/',
  true,
  'nostr_relay',
  'public',
  'not_applicable',
  array['nostr_relay']::text[],
  false,
  1,
  1,
  100,
  1,
  false,
  30,
  '{
    "relay_key":"nostr_net",
    "endpoint":"wss://relay.nostr.net/",
    "nip11_url":"https://relay.nostr.net/",
    "protocol":"nip01",
    "policy_state":"degraded_missing_relay_specific_terms",
    "required_nips":[1,9,11],
    "approved_tags":["pokemontcg","PokemonTCG","pokemoncards","PokemonCards","ポケカ","ポケモンカード","포켓몬카드","宝可梦卡牌","寶可夢卡牌"],
    "replay_overlap_seconds":300,
    "stream_window_seconds":15,
    "max_events":100,
    "max_message_bytes":262144,
    "max_stream_bytes":2097152,
    "max_candidates":100,
    "max_deletions":100,
    "max_delete_targets":16,
    "statistics_eligible":false
  }'::jsonb,
  'nostr-multi-relay-v1',
  60,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('nostr_relay_primal'),
  ('nostr_relay_nos_lol'),
  ('nostr_relay_nostr_net');

-- This table is the one-row-per-event activity candidate ledger.  The event
-- id is private event identity, while the author is immediately reduced to a
-- one-way hash.  Raw note text, profiles, media, URLs, keys, and signatures
-- are intentionally absent from the durable schema.
create table ingest.nostr_relay_candidates (
  event_id text primary key,
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  relay_key text not null,
  author_sha256 text not null,
  content_sha256 text not null,
  matched_tags text[] not null,
  published_at timestamptz not null,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  deleted_at timestamptz,
  expires_at timestamptz not null,
  activity_only boolean not null default true,
  statistics_eligible boolean not null default false,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint nostr_candidates_event_id_check check (
    event_id ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_candidates_relay_key_check check (
    relay_key in ('primal', 'nos_lol', 'nostr_net')
  ),
  constraint nostr_candidates_author_hash_check check (
    author_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_candidates_content_hash_check check (
    content_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_candidates_tags_check check (
    array_position(matched_tags, null) is null
    and cardinality(matched_tags) between 1 and 7
    and matched_tags <@ array[
      'pokemontcg', 'pokemoncards', 'ポケカ', 'ポケモンカード',
      '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
    ]::text[]
  ),
  constraint nostr_candidates_published_at_check check (
    published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint nostr_candidates_time_check check (
    last_seen_at >= first_seen_at
    and expires_at = last_seen_at + interval '30 days'
    and updated_at >= created_at
  ),
  constraint nostr_candidates_activity_check check (
    activity_only and not statistics_eligible
  ),
  constraint nostr_candidates_live_only_check check (not is_demo)
);

create index nostr_candidates_active_idx
  on ingest.nostr_relay_candidates (expires_at, event_id)
  where deleted_at is null;
create index nostr_candidates_relay_idx
  on ingest.nostr_relay_candidates (relay_key, last_seen_at desc);

alter table ingest.nostr_relay_candidates enable row level security;
alter table ingest.nostr_relay_candidates force row level security;
create policy nostr_candidates_service_role_select
  on ingest.nostr_relay_candidates for select to service_role using (not is_demo);
revoke all on table ingest.nostr_relay_candidates
  from public, anon, authenticated, service_role;
grant select on table ingest.nostr_relay_candidates to service_role;

-- Observations are immutable per relay/event.  The same event may occur on
-- several relays, but it can create only one global candidate above.  Delete
-- observations retain only hashed author identity and target event ids so an
-- NIP-09 tombstone can be applied without retaining the signed event.
create table ingest.nostr_relay_observations (
  id bigint generated always as identity primary key,
  relay_key text not null,
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  event_id text not null,
  operation text not null,
  author_sha256 text not null,
  content_sha256 text,
  matched_tags text[],
  published_at timestamptz not null,
  target_event_ids text[] not null default '{}'::text[],
  observed_at timestamptz not null,
  expires_at timestamptz not null,
  activity_only boolean not null default true,
  statistics_eligible boolean not null default false,
  is_demo boolean not null default false,
  constraint nostr_observations_relay_key_check check (
    relay_key in ('primal', 'nos_lol', 'nostr_net')
  ),
  constraint nostr_observations_source_event_unique unique (relay_key, event_id),
  constraint nostr_observations_event_id_check check (
    event_id ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_observations_operation_check check (
    operation in ('upsert', 'delete')
  ),
  constraint nostr_observations_author_hash_check check (
    author_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_observations_content_hash_check check (
    content_sha256 is null or content_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint nostr_observations_tags_check check (
    matched_tags is null
    or (
      array_position(matched_tags, null) is null
      and cardinality(matched_tags) between 1 and 7
      and matched_tags <@ array[
        'pokemontcg', 'pokemoncards', 'ポケカ', 'ポケモンカード',
        '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
      ]::text[]
    )
  ),
  constraint nostr_observations_targets_check check (
    array_position(target_event_ids, null) is null
    and cardinality(target_event_ids) between 0 and 16
    and (
      cardinality(target_event_ids) = 0
      or array_to_string(target_event_ids, ',') ~
        '^[0-9a-f]{64}(,[0-9a-f]{64}){0,15}$'
    )
  ),
  constraint nostr_observations_shape_check check (
    (
      operation = 'upsert'
      and content_sha256 is not null
      and matched_tags is not null
      and cardinality(target_event_ids) = 0
    )
    or (
      operation = 'delete'
      and content_sha256 is null
      and matched_tags is null
      and cardinality(target_event_ids) between 1 and 16
    )
  ),
  constraint nostr_observations_published_at_check check (
    published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint nostr_observations_time_check check (
    expires_at = observed_at + interval '30 days'
  ),
  constraint nostr_observations_activity_check check (
    activity_only and not statistics_eligible
  ),
  constraint nostr_observations_live_only_check check (not is_demo)
);

create index nostr_observations_expiry_idx
  on ingest.nostr_relay_observations (expires_at, id);
create index nostr_observations_event_idx
  on ingest.nostr_relay_observations (event_id, observed_at desc);

alter table ingest.nostr_relay_observations enable row level security;
alter table ingest.nostr_relay_observations force row level security;
create policy nostr_observations_service_role_select
  on ingest.nostr_relay_observations for select to service_role using (not is_demo);
revoke all on table ingest.nostr_relay_observations
  from public, anon, authenticated, service_role;
grant select on table ingest.nostr_relay_observations to service_role;

-- Checkpoints survive activity cleanup.  One row is kept for every exact relay
-- policy and is the source of the five-minute inclusive replay overlap.
create table ingest.nostr_relay_checkpoints (
  source_policy_id uuid primary key
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  relay_key text not null unique,
  endpoint text not null,
  nip11_url text not null,
  protocol text not null,
  approved_tags text[] not null,
  last_checkpoint timestamptz,
  events_seen_total bigint not null default 0,
  bytes_seen_total bigint not null default 0,
  candidates_seen_total bigint not null default 0,
  deletions_seen_total bigint not null default 0,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint nostr_checkpoints_relay_key_check check (
    relay_key in ('primal', 'nos_lol', 'nostr_net')
  ),
  constraint nostr_checkpoints_endpoint_check check (
    endpoint in (
      'wss://relay.primal.net/',
      'wss://nos.lol/',
      'wss://relay.nostr.net/'
    )
  ),
  constraint nostr_checkpoints_nip11_url_check check (
    nip11_url in (
      'https://relay.primal.net/',
      'https://nos.lol/',
      'https://relay.nostr.net/'
    )
  ),
  constraint nostr_checkpoints_protocol_check check (protocol = 'nip01'),
  constraint nostr_checkpoints_tags_check check (
    cardinality(approved_tags) = 9
    and array_position(approved_tags, null) is null
  ),
  constraint nostr_checkpoints_counter_check check (
    events_seen_total >= 0
    and bytes_seen_total >= 0
    and candidates_seen_total >= 0
    and deletions_seen_total >= 0
  ),
  constraint nostr_checkpoints_live_only_check check (not is_demo)
);

create index nostr_checkpoints_collected_idx
  on ingest.nostr_relay_checkpoints (last_checkpoint desc);

alter table ingest.nostr_relay_checkpoints enable row level security;
alter table ingest.nostr_relay_checkpoints force row level security;
create policy nostr_checkpoints_service_role_select
  on ingest.nostr_relay_checkpoints for select to service_role using (not is_demo);
revoke all on table ingest.nostr_relay_checkpoints
  from public, anon, authenticated, service_role;
grant select on table ingest.nostr_relay_checkpoints to service_role;

insert into ingest.nostr_relay_checkpoints (
  source_policy_id, relay_key, endpoint, nip11_url, protocol, approved_tags
)
select
  policies.id,
  policies.config ->> 'relay_key',
  policies.config ->> 'endpoint',
  policies.config ->> 'nip11_url',
  policies.config ->> 'protocol',
  array[
    'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
    'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
  ]::text[]
from ingest.source_policies as policies
where policies.source_key in (
  'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
);

comment on table ingest.nostr_relay_candidates is
  'Private bounded Nostr activity candidates. Activity-only and never opening, profile, geography, or rate evidence.';
comment on table ingest.nostr_relay_observations is
  'Private immutable per-relay Nostr event observations. Raw note fields, keys, URLs, and signatures are not retained.';
comment on table ingest.nostr_relay_checkpoints is
  'Private per-relay NIP-01 checkpoint retained after candidate and observation cleanup.';

-- The worker sends only canonical RFC3339 text at this boundary.  Parsing and
-- bounding it here prevents a permissive timestamptz cast from widening a
-- relay window or accepting a future-dated event.
create or replace function ingest.nostr_timestamp_v1(
  value text,
  lower_bound timestamptz,
  upper_bound timestamptz
)
returns timestamptz
language plpgsql
immutable
parallel safe
set search_path = pg_catalog
as $$
declare
  parsed timestamptz;
begin
  if value is null
    or lower_bound is null
    or upper_bound is null
    or char_length(value) > 80
    or value ~ '[[:cntrl:]]'
    or value !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]{1,6})?(Z|[+-](0[0-9]|1[0-9]|2[0-3]):[0-5][0-9])$'
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr timestamp is invalid';
  end if;
  begin
    parsed := value::timestamptz;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Nostr timestamp is invalid';
  end;
  if parsed < lower_bound or parsed > upper_bound then
    raise exception using
      errcode = '22023',
      message = 'Nostr timestamp is outside the approved range';
  end if;
  return parsed;
end;
$$;

alter function ingest.nostr_timestamp_v1(text, timestamptz, timestamptz)
  owner to postgres;
revoke all on function ingest.nostr_timestamp_v1(text, timestamptz, timestamptz)
  from public, anon, authenticated, service_role;
comment on function ingest.nostr_timestamp_v1(text, timestamptz, timestamptz) is
  'Private bounded Nostr timestamp parser; not executable by API or worker roles.';

-- Acquire one exact relay lease and return a five-minute inclusive replay
-- window.  The checkpoint itself is deliberately not advanced until the
-- fenced finalizer has validated the complete result.
create or replace function ingest.begin_nostr_relay_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  relay_key text
)
returns table(
  acquired boolean,
  retry_at timestamptz,
  since timestamptz,
  until timestamptz,
  checkpoint timestamptz,
  recent_candidate_ids text[]
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
  checkpoint_row ingest.nostr_relay_checkpoints%rowtype;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  lease_checked_at timestamptz;
  request_retry_at timestamptz;
  window_since timestamptz;
  window_until timestamptz;
  policy_source_key text;
  policy_display_name text;
  relay_endpoint text;
  relay_nip11_url text;
  expected_config jsonb;
  candidate_ids text[];
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
  if relay_key is null or relay_key not in ('primal', 'nos_lol', 'nostr_net') then
    raise exception using
      errcode = '22023',
      message = 'relay_key is not an approved Nostr relay';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = begin_nostr_relay_job.job_id
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
    or leased_job.job_type <> 'source.nostr.relay'
    or leased_job.payload <> jsonb_build_object('relay_key', relay_key)
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr begin requires one live source.nostr.relay job with its exact relay payload';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:nostr:live', 0)
  );

  policy_source_key := case relay_key
    when 'primal' then 'nostr_relay_primal'
    when 'nos_lol' then 'nostr_relay_nos_lol'
    else 'nostr_relay_nostr_net'
  end;
  policy_display_name := case relay_key
    when 'primal' then 'Nostr relay relay.primal.net discovery'
    when 'nos_lol' then 'Nostr relay nos.lol discovery'
    else 'Nostr relay relay.nostr.net discovery'
  end;
  relay_endpoint := case relay_key
    when 'primal' then 'wss://relay.primal.net/'
    when 'nos_lol' then 'wss://nos.lol/'
    else 'wss://relay.nostr.net/'
  end;
  relay_nip11_url := case relay_key
    when 'primal' then 'https://relay.primal.net/'
    when 'nos_lol' then 'https://nos.lol/'
    else 'https://relay.nostr.net/'
  end;
  expected_config := jsonb_build_object(
    'relay_key', relay_key,
    'endpoint', relay_endpoint,
    'nip11_url', relay_nip11_url,
    'protocol', 'nip01',
    'policy_state', 'degraded_missing_relay_specific_terms',
    'required_nips', jsonb_build_array(1, 9, 11),
    'approved_tags', jsonb_build_array(
      'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
      'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
    ),
    'replay_overlap_seconds', 300,
    'stream_window_seconds', 15,
    'max_events', 100,
    'max_message_bytes', 262144,
    'max_stream_bytes', 2097152,
    'max_candidates', 100,
    'max_deletions', 100,
    'max_delete_targets', 16,
    'statistics_eligible', false
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = policy_source_key
    and policies.display_name = policy_display_name
    and policies.source_kind = 'public_web'
    and policies.domain = case relay_key
      when 'primal' then 'relay.primal.net'
      when 'nos_lol' then 'nos.lol'
      else 'relay.nostr.net'
    end
    and policies.base_url = relay_endpoint
    and policies.enabled
    and policies.collector_type = 'nostr_relay'
    and policies.access_mode = 'public'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['nostr_relay']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 100
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = expected_config
    and policies.version = 'nostr-multi-relay-v1'
    and policies.expected_interval_seconds = 60
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Nostr relay source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = policy_source_key
  for update of gates;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Nostr relay request gate is unavailable';
  end if;

  select checkpoints.*
  into checkpoint_row
  from ingest.nostr_relay_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and checkpoints.relay_key = begin_nostr_relay_job.relay_key
    and checkpoints.endpoint = relay_endpoint
    and checkpoints.nip11_url = relay_nip11_url
    and checkpoints.protocol = 'nip01'
    and checkpoints.approved_tags = array[
      'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
      'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
    ]::text[]
    and not checkpoints.is_demo
  for update of checkpoints;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Nostr relay checkpoint is unavailable';
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

  -- NIP-01 FILTER timestamps are integer Unix seconds.  Return and fence
  -- whole-second boundaries so the worker and relay cannot disagree by a
  -- fractional second at either edge of the authorised window.
  window_until := date_trunc('second', lease_checked_at);
  window_since := date_trunc('second', greatest(
    coalesce(
      checkpoint_row.last_checkpoint - interval '5 minutes',
      window_until - interval '5 minutes'
    ),
    '2000-01-01 00:00:00+00'::timestamptz
  ));

  -- A second collection attempt can be claimed before the wall clock has
  -- crossed the whole-second NIP-01 checkpoint. Defer before owning the
  -- request gate; otherwise no valid result could advance monotonically.
  if checkpoint_row.last_checkpoint is not null
    and window_until <= checkpoint_row.last_checkpoint
  then
    return query select
      false,
      greatest(
        checkpoint_row.last_checkpoint + interval '1 second',
        lease_checked_at + interval '1 second'
      ),
      window_since,
      window_until,
      checkpoint_row.last_checkpoint,
      '{}'::text[];
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
    return query select
      false,
      request_retry_at,
      window_since,
      window_until,
      checkpoint_row.last_checkpoint,
      '{}'::text[];
    return;
  end if;

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
      acquired_at = window_until,
      active_until = leased_job.lock_expires_at
  where gates.source_key = policy_source_key;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Nostr relay request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  select coalesce(array_agg(recent.event_id order by recent.last_seen_at desc, recent.event_id), '{}'::text[])
  into candidate_ids
  from (
    select candidates.event_id, candidates.last_seen_at
    from ingest.nostr_relay_candidates as candidates
    where candidates.deleted_at is null
      and candidates.expires_at > window_until
      and not candidates.is_demo
    order by candidates.last_seen_at desc, candidates.event_id
    limit 100
  ) as recent;

  return query select
    true,
    null::timestamptz,
    window_since,
    window_until,
    checkpoint_row.last_checkpoint,
    coalesce(candidate_ids, '{}'::text[]);
end;
$$;

alter function ingest.begin_nostr_relay_job(uuid, text, bigint, text)
  owner to postgres;
revoke all on function ingest.begin_nostr_relay_job(uuid, text, bigint, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_nostr_relay_job(uuid, text, bigint, text)
  to service_role;
comment on function ingest.begin_nostr_relay_job(uuid, text, bigint, text) is
  'Generation-fenced preflight for one bounded anonymous NIP-01 relay activity slice with a fixed five-minute replay overlap.';

-- Validate and persist one complete relay result atomically.  The worker has
-- already verified the signed event transiently; this boundary accepts only
-- event ids, hashes, approved tags, timestamps, and hashed author identity.
-- No raw signing material can enter this RPC or either durable activity table.
create or replace function ingest.finalize_nostr_relay_job(
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
  checkpoint_row ingest.nostr_relay_checkpoints%rowtype;
  existing_observation ingest.nostr_relay_observations%rowtype;
  existing_candidate ingest.nostr_relay_candidates%rowtype;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  event_time timestamptz;
  result_relay_key text;
  result_since timestamptz;
  result_until timestamptz;
  result_checkpoint timestamptz;
  expected_since timestamptz;
  result_events_seen bigint;
  result_bytes_seen bigint;
  candidate_count integer;
  deletion_count integer;
  candidate_record record;
  deletion_record record;
  target_record record;
  candidate_value jsonb;
  deletion_value jsonb;
  candidate_event_id text;
  candidate_author_sha256 text;
  candidate_content_sha256 text;
  candidate_published_at timestamptz;
  candidate_tags text[];
  deletion_event_id text;
  deletion_author_sha256 text;
  deletion_published_at timestamptz;
  deletion_targets text[];
  target_event_id text;
  policy_source_key text;
  policy_display_name text;
  relay_endpoint text;
  relay_nip11_url text;
  expected_config jsonb;
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
  where jobs.id = finalize_nostr_relay_job.job_id
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
  if leased_job.is_demo or leased_job.job_type <> 'source.nostr.relay' then
    raise exception using
      errcode = '22023',
      message = 'Nostr finalizer requires a live source.nostr.relay job';
  end if;

  completion_time := clock_timestamp();
  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 2097152
    or not (result ?& array[
      'version', 'relay_key', 'since', 'until', 'checkpoint', 'incomplete',
      'events_seen', 'bytes_seen', 'candidates', 'deletions'
    ])
    or result - array[
      'version', 'relay_key', 'since', 'until', 'checkpoint', 'incomplete',
      'events_seen', 'bytes_seen', 'candidates', 'deletions'
    ] <> '{}'::jsonb
    or jsonb_typeof(result -> 'version') is distinct from 'string'
    or result ->> 'version' <> '1.0.0'
    or jsonb_typeof(result -> 'relay_key') is distinct from 'string'
    or jsonb_typeof(result -> 'since') is distinct from 'string'
    or jsonb_typeof(result -> 'until') is distinct from 'string'
    or jsonb_typeof(result -> 'checkpoint') not in ('string', 'null')
    or jsonb_typeof(result -> 'incomplete') is distinct from 'boolean'
    or result -> 'incomplete' <> 'false'::jsonb
    or jsonb_typeof(result -> 'events_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'bytes_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'candidates') is distinct from 'array'
    or jsonb_typeof(result -> 'deletions') is distinct from 'array'
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr result must match the exact bounded v1.0.0 contract';
  end if;

  result_relay_key := result ->> 'relay_key';
  if result_relay_key not in ('primal', 'nos_lol', 'nostr_net') then
    raise exception using
      errcode = '22023', message = 'Nostr result relay_key is not approved';
  end if;
  if (result ->> 'events_seen') !~ '^(0|[1-9][0-9]{0,6})$'
    or (result ->> 'bytes_seen') !~ '^(0|[1-9][0-9]{0,6})$'
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr event and byte counters must be canonical bounded integers';
  end if;
  begin
    result_events_seen := (result ->> 'events_seen')::bigint;
    result_bytes_seen := (result ->> 'bytes_seen')::bigint;
    result_until := ingest.nostr_timestamp_v1(
      result ->> 'until',
      '2000-01-01 00:00:00+00'::timestamptz,
      completion_time
    );
    result_since := ingest.nostr_timestamp_v1(
      result ->> 'since',
      '2000-01-01 00:00:00+00'::timestamptz,
      result_until
    );
    result_checkpoint := case
      when result -> 'checkpoint' = 'null'::jsonb then null
      else ingest.nostr_timestamp_v1(
        result ->> 'checkpoint',
        '2000-01-01 00:00:00+00'::timestamptz,
        result_until
      )
    end;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Nostr result timestamps or counters are outside the approved range';
  end;
  if result_events_seen > 100
    or result_bytes_seen > 2097152
  then
    raise exception using
      errcode = '22023', message = 'Nostr result exceeds the fixed stream bounds';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:nostr:live', 0)
  );

  policy_source_key := case result_relay_key
    when 'primal' then 'nostr_relay_primal'
    when 'nos_lol' then 'nostr_relay_nos_lol'
    else 'nostr_relay_nostr_net'
  end;
  policy_display_name := case result_relay_key
    when 'primal' then 'Nostr relay relay.primal.net discovery'
    when 'nos_lol' then 'Nostr relay nos.lol discovery'
    else 'Nostr relay relay.nostr.net discovery'
  end;
  relay_endpoint := case result_relay_key
    when 'primal' then 'wss://relay.primal.net/'
    when 'nos_lol' then 'wss://nos.lol/'
    else 'wss://relay.nostr.net/'
  end;
  relay_nip11_url := case result_relay_key
    when 'primal' then 'https://relay.primal.net/'
    when 'nos_lol' then 'https://nos.lol/'
    else 'https://relay.nostr.net/'
  end;
  expected_config := jsonb_build_object(
    'relay_key', result_relay_key,
    'endpoint', relay_endpoint,
    'nip11_url', relay_nip11_url,
    'protocol', 'nip01',
    'policy_state', 'degraded_missing_relay_specific_terms',
    'required_nips', jsonb_build_array(1, 9, 11),
    'approved_tags', jsonb_build_array(
      'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
      'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
    ),
    'replay_overlap_seconds', 300,
    'stream_window_seconds', 15,
    'max_events', 100,
    'max_message_bytes', 262144,
    'max_stream_bytes', 2097152,
    'max_candidates', 100,
    'max_deletions', 100,
    'max_delete_targets', 16,
    'statistics_eligible', false
  );

  if leased_job.payload <> jsonb_build_object('relay_key', result_relay_key) then
    raise exception using
      errcode = '22023',
      message = 'Nostr job payload and result relay_key must match exactly';
  end if;

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = policy_source_key
    and policies.display_name = policy_display_name
    and policies.source_kind = 'public_web'
    and policies.domain = case result_relay_key
      when 'primal' then 'relay.primal.net'
      when 'nos_lol' then 'nos.lol'
      else 'relay.nostr.net'
    end
    and policies.base_url = relay_endpoint
    and policies.enabled
    and policies.collector_type = 'nostr_relay'
    and policies.access_mode = 'public'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['nostr_relay']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 1
    and policies.max_items_per_run = 100
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = expected_config
    and policies.version = 'nostr-multi-relay-v1'
    and policies.expected_interval_seconds = 60
    and not policies.is_demo
  for update of policies;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Nostr relay source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = policy_source_key
  for update of gates;
  if not found then
    raise exception using
      errcode = '55000', message = 'live Nostr relay request gate is unavailable';
  end if;
  select checkpoints.*
  into checkpoint_row
  from ingest.nostr_relay_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and checkpoints.relay_key = result_relay_key
    and checkpoints.endpoint = relay_endpoint
    and checkpoints.nip11_url = relay_nip11_url
    and checkpoints.protocol = 'nip01'
    and checkpoints.approved_tags = array[
      'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
      'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
    ]::text[]
    and not checkpoints.is_demo
  for update of checkpoints;
  if not found then
    raise exception using
      errcode = '55000', message = 'live Nostr relay checkpoint is unavailable';
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
  if request_gate.owner_job_id is distinct from job_id
    or request_gate.owner_lease_generation is distinct from lease_generation
    or request_gate.active_until is null
    or request_gate.active_until <= lease_checked_at
  then
    raise exception using
      errcode = '55000',
      message = 'Nostr relay request gate is not owned by this job lease';
  end if;
  if request_gate.acquired_at is null
    or result_until <> request_gate.acquired_at
  then
    raise exception using
      errcode = '40001',
      message = 'Nostr result until timestamp does not match the fenced begin window';
  end if;
  if checkpoint_row.last_checkpoint is not null
    and result_until <= checkpoint_row.last_checkpoint
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr checkpoint must advance monotonically';
  end if;

  if result_checkpoint is distinct from checkpoint_row.last_checkpoint then
    raise exception using
      errcode = '40001',
      message = 'Nostr result checkpoint does not match the fenced checkpoint';
  end if;
  expected_since := date_trunc('second', greatest(
    coalesce(
      checkpoint_row.last_checkpoint - interval '5 minutes',
      result_until - interval '5 minutes'
    ),
    '2000-01-01 00:00:00+00'::timestamptz
  ));
  if result_since <> expected_since then
    raise exception using
      errcode = '22023',
      message = 'Nostr result since timestamp does not include exactly the approved overlap';
  end if;

  candidate_count := jsonb_array_length(result -> 'candidates');
  deletion_count := jsonb_array_length(result -> 'deletions');
  if candidate_count > 100
    or deletion_count > 100
    or result_events_seen < candidate_count + deletion_count
    or result_events_seen = 0 and (candidate_count <> 0 or deletion_count <> 0)
  then
    raise exception using
      errcode = '22023',
      message = 'Nostr candidate, deletion, or event bounds are invalid';
  end if;

  -- Every candidate has exactly eight keys.  The DTO contains no raw event
  -- content, public URL, or signing material; author_sha256 is the only
  -- durable author correlation value.
  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
  loop
    candidate_value := candidate_record.value;
    if jsonb_typeof(candidate_value) is distinct from 'object'
      or not (candidate_value ?& array[
        'event_id', 'author_sha256', 'published_at', 'content_sha256',
        'matched_tags', 'relay_key', 'activity_only', 'statistics_eligible'
      ])
      or candidate_value - array[
        'event_id', 'author_sha256', 'published_at', 'content_sha256',
        'matched_tags', 'relay_key', 'activity_only', 'statistics_eligible'
      ] <> '{}'::jsonb
      or jsonb_typeof(candidate_value -> 'event_id') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'author_sha256') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'published_at') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'content_sha256') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'matched_tags') is distinct from 'array'
      or jsonb_typeof(candidate_value -> 'relay_key') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'activity_only') is distinct from 'boolean'
      or jsonb_typeof(candidate_value -> 'statistics_eligible') is distinct from 'boolean'
      or candidate_value ->> 'relay_key' <> result_relay_key
      or candidate_value -> 'activity_only' <> 'true'::jsonb
      or candidate_value -> 'statistics_eligible' <> 'false'::jsonb
    then
      raise exception using
        errcode = '22023',
        message = 'Nostr candidates must use the exact hashed-author item contract';
    end if;

    candidate_event_id := candidate_value ->> 'event_id';
    candidate_author_sha256 := candidate_value ->> 'author_sha256';
    candidate_content_sha256 := candidate_value ->> 'content_sha256';
    if candidate_event_id !~ '^[0-9a-f]{64}$'
      or candidate_author_sha256 !~ '^[0-9a-f]{64}$'
      or candidate_content_sha256 !~ '^[0-9a-f]{64}$'
      or jsonb_array_length(candidate_value -> 'matched_tags') not between 1 and 7
      or (
        select count(*) <> count(distinct tag_rows.value)
        from jsonb_array_elements_text(candidate_value -> 'matched_tags') as tag_rows(value)
      )
      or exists (
        select 1
        from jsonb_array_elements_text(candidate_value -> 'matched_tags') as tag_rows(value)
        where tag_rows.value not in (
          'pokemontcg', 'pokemoncards', 'ポケカ', 'ポケモンカード',
          '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
        )
      )
    then
      raise exception using
        errcode = '22023',
        message = 'Nostr candidate identity, hash, or approved tags are invalid';
    end if;
    candidate_published_at := ingest.nostr_timestamp_v1(
      candidate_value ->> 'published_at',
      result_since,
      result_until
    );
  end loop;

  -- A deletion is also exact and bounded.  Its targets are only references;
  -- unknown targets are intentionally harmless and never synthesize a row.
  for deletion_record in
    select elements.value
    from jsonb_array_elements(result -> 'deletions') as elements(value)
  loop
    deletion_value := deletion_record.value;
    if jsonb_typeof(deletion_value) is distinct from 'object'
      or not (deletion_value ?& array[
        'event_id', 'author_sha256', 'published_at', 'kind', 'relay_key',
        'target_event_ids'
      ])
      or deletion_value - array[
        'event_id', 'author_sha256', 'published_at', 'kind', 'relay_key',
        'target_event_ids'
      ] <> '{}'::jsonb
      or jsonb_typeof(deletion_value -> 'event_id') is distinct from 'string'
      or jsonb_typeof(deletion_value -> 'author_sha256') is distinct from 'string'
      or jsonb_typeof(deletion_value -> 'published_at') is distinct from 'string'
      or jsonb_typeof(deletion_value -> 'kind') is distinct from 'number'
      or deletion_value ->> 'kind' <> '5'
      or jsonb_typeof(deletion_value -> 'relay_key') is distinct from 'string'
      or deletion_value ->> 'relay_key' <> result_relay_key
      or jsonb_typeof(deletion_value -> 'target_event_ids') is distinct from 'array'
    then
      raise exception using
        errcode = '22023',
        message = 'Nostr deletions must use the exact hashed-author item contract';
    end if;
    deletion_event_id := deletion_value ->> 'event_id';
    deletion_author_sha256 := deletion_value ->> 'author_sha256';
    if deletion_event_id !~ '^[0-9a-f]{64}$'
      or deletion_author_sha256 !~ '^[0-9a-f]{64}$'
      or jsonb_array_length(deletion_value -> 'target_event_ids') not between 1 and 16
      or (
        select count(*) <> count(distinct target_rows.value)
        from jsonb_array_elements_text(deletion_value -> 'target_event_ids') as target_rows(value)
      )
      or exists (
        select 1
        from jsonb_array_elements_text(deletion_value -> 'target_event_ids') as target_rows(value)
        where target_rows.value !~ '^[0-9a-f]{64}$'
      )
    then
      raise exception using
        errcode = '22023',
        message = 'Nostr deletion identity or target bounds are invalid';
    end if;
    deletion_published_at := ingest.nostr_timestamp_v1(
      deletion_value ->> 'published_at',
      result_since,
      result_until
    );
  end loop;

  if (
    select count(*) <> count(distinct event_rows.event_id)
    from (
      select value ->> 'event_id' as event_id
      from jsonb_array_elements(result -> 'candidates') as candidate_values(value)
      union all
      select value ->> 'event_id'
      from jsonb_array_elements(result -> 'deletions') as deletion_values(value)
    ) as event_rows
  ) then
    raise exception using
      errcode = '22023', message = 'Nostr event ids must be unique in one result';
  end if;

  -- Candidate observations are immutable per relay/event.  A repeated
  -- inclusive replay is accepted only when all stored fields are identical.
  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
  loop
    candidate_value := candidate_record.value;
    candidate_event_id := candidate_value ->> 'event_id';
    candidate_author_sha256 := candidate_value ->> 'author_sha256';
    candidate_content_sha256 := candidate_value ->> 'content_sha256';
    candidate_published_at := ingest.nostr_timestamp_v1(
      candidate_value ->> 'published_at', result_since, result_until
    );
    candidate_tags := array(
      select jsonb_array_elements_text(candidate_value -> 'matched_tags')
    );
    event_time := clock_timestamp();
    persisted_observation_id := null;
    insert into ingest.nostr_relay_observations as observations (
      relay_key, source_policy_id, event_id, operation, author_sha256,
      content_sha256, matched_tags, published_at, target_event_ids,
      observed_at, expires_at, activity_only, statistics_eligible, is_demo
    ) values (
      result_relay_key, policy_id, candidate_event_id, 'upsert',
      candidate_author_sha256, candidate_content_sha256, candidate_tags,
      candidate_published_at, '{}'::text[], event_time,
      event_time + interval '30 days', true, false, false
    )
    on conflict (relay_key, event_id) do nothing
    returning observations.id into persisted_observation_id;

    if persisted_observation_id is null then
      select observations.*
      into existing_observation
      from ingest.nostr_relay_observations as observations
      where observations.relay_key = result_relay_key
        and observations.event_id = candidate_event_id
      for update of observations;
      if not found
        or existing_observation.operation <> 'upsert'
        or existing_observation.source_policy_id <> policy_id
        or existing_observation.author_sha256 <> candidate_author_sha256
        or existing_observation.content_sha256 <> candidate_content_sha256
        or existing_observation.matched_tags <> candidate_tags
        or existing_observation.published_at <> candidate_published_at
      then
        raise exception using
          errcode = '22023',
          message = 'Nostr inclusive replay observation conflicts with its stored event';
      end if;
    end if;

    select candidates.*
    into existing_candidate
    from ingest.nostr_relay_candidates as candidates
    where candidates.event_id = candidate_event_id
    for update of candidates;
    if found then
      if existing_candidate.is_demo
        or existing_candidate.author_sha256 <> candidate_author_sha256
        or existing_candidate.content_sha256 <> candidate_content_sha256
        or existing_candidate.matched_tags <> candidate_tags
        or existing_candidate.published_at <> candidate_published_at
      then
        raise exception using
          errcode = '22023',
          message = 'Nostr cross-relay event identity conflicts with its stored candidate';
      end if;
      update ingest.nostr_relay_candidates as candidates
      set last_seen_at = greatest(candidates.last_seen_at, event_time),
          expires_at = greatest(candidates.expires_at, event_time + interval '30 days'),
          updated_at = event_time
      where candidates.event_id = candidate_event_id;
    else
      insert into ingest.nostr_relay_candidates (
        event_id, source_policy_id, relay_key, author_sha256, content_sha256,
        matched_tags, published_at, first_seen_at, last_seen_at, deleted_at,
        expires_at, activity_only, statistics_eligible, is_demo,
        created_at, updated_at
      ) values (
        candidate_event_id, policy_id, result_relay_key, candidate_author_sha256,
        candidate_content_sha256, candidate_tags, candidate_published_at,
        event_time, event_time, null, event_time + interval '30 days',
        true, false, false, event_time, event_time
      );
    end if;
  end loop;

  for deletion_record in
    select elements.value
    from jsonb_array_elements(result -> 'deletions') as elements(value)
  loop
    deletion_value := deletion_record.value;
    deletion_event_id := deletion_value ->> 'event_id';
    deletion_author_sha256 := deletion_value ->> 'author_sha256';
    deletion_published_at := ingest.nostr_timestamp_v1(
      deletion_value ->> 'published_at', result_since, result_until
    );
    deletion_targets := array(
      select jsonb_array_elements_text(deletion_value -> 'target_event_ids')
    );
    event_time := clock_timestamp();
    persisted_observation_id := null;
    insert into ingest.nostr_relay_observations as observations (
      relay_key, source_policy_id, event_id, operation, author_sha256,
      content_sha256, matched_tags, published_at, target_event_ids,
      observed_at, expires_at, activity_only, statistics_eligible, is_demo
    ) values (
      result_relay_key, policy_id, deletion_event_id, 'delete',
      deletion_author_sha256, null, null, deletion_published_at,
      deletion_targets, event_time, event_time + interval '30 days',
      true, false, false
    )
    on conflict (relay_key, event_id) do nothing
    returning observations.id into persisted_observation_id;

    if persisted_observation_id is null then
      select observations.*
      into existing_observation
      from ingest.nostr_relay_observations as observations
      where observations.relay_key = result_relay_key
        and observations.event_id = deletion_event_id
      for update of observations;
      if not found
        or existing_observation.operation <> 'delete'
        or existing_observation.source_policy_id <> policy_id
        or existing_observation.author_sha256 <> deletion_author_sha256
        or existing_observation.published_at <> deletion_published_at
        or existing_observation.target_event_ids <> deletion_targets
      then
        raise exception using
          errcode = '22023',
          message = 'Nostr inclusive replay deletion conflicts with its stored event';
      end if;
    end if;

    -- A tombstone is effective only for the same hashed author and only when
    -- its signed event is at least as new as the target.  Unknown, older, or
    -- cross-author targets are ignored without synthesizing a candidate.
    for target_record in
      select jsonb_array_elements_text(deletion_value -> 'target_event_ids') as event_id
    loop
      target_event_id := target_record.event_id;
      select candidates.*
      into existing_candidate
      from ingest.nostr_relay_candidates as candidates
      where candidates.event_id = target_event_id
      for update of candidates;
      if found
        and existing_candidate.author_sha256 = deletion_author_sha256
        and deletion_published_at >= existing_candidate.published_at
      then
        update ingest.nostr_relay_candidates as candidates
        set deleted_at = coalesce(candidates.deleted_at, event_time),
            last_seen_at = greatest(candidates.last_seen_at, event_time),
            expires_at = greatest(candidates.expires_at, event_time + interval '30 days'),
            updated_at = event_time
        where candidates.event_id = target_event_id;
      end if;
    end loop;
  end loop;

  completion_time := clock_timestamp();
  update ingest.nostr_relay_checkpoints as checkpoints
  set last_checkpoint = result_until,
      events_seen_total = checkpoints.events_seen_total + result_events_seen,
      bytes_seen_total = checkpoints.bytes_seen_total + result_bytes_seen,
      candidates_seen_total = checkpoints.candidates_seen_total + candidate_count,
      deletions_seen_total = checkpoints.deletions_seen_total + deletion_count,
      updated_at = completion_time
  where checkpoints.source_policy_id = policy_id
    and checkpoints.relay_key = result_relay_key
    and not checkpoints.is_demo
    and checkpoints.last_checkpoint is not distinct from result_checkpoint;
  if not found then
    raise exception using
      errcode = '40001',
      message = 'Nostr checkpoint changed before atomic window advance';
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
      message = 'live Nostr relay source policy changed during finalization';
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
    and jobs.lease_generation = lease_generation
    and jobs.lock_expires_at > completion_time
    and not jobs.is_demo
  returning jobs.* into completed_job;
  if not found then
    raise exception using
      errcode = 'P0002', message = 'Nostr completion lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = policy_source_key
    and gates.owner_job_id = job_id
    and gates.owner_lease_generation = lease_generation;
  if not found then
    raise exception using
      errcode = 'P0002', message = 'Nostr completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb) is
  'Fenced atomic Nostr v1.0.0 finalizer. It persists only bounded activity hashes and same-author deletion tombstones; unknown or cross-author deletes never create candidates.';

-- Scheduled Nostr jobs carry exactly one relay key.  Re-issue the existing
-- guards with a narrow extension so a future migration cannot accidentally
-- turn an arbitrary relay URL or payload into a live scheduled request.
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
      job_type = 'source.nostr.relay'
      and payload ?& array['relay_key']
      and payload - array['relay_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'relay_key') = 'string'
      and payload ->> 'relay_key' in ('primal', 'nos_lol', 'nostr_net')
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
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
      )
    )
  );

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
    $old$    'source.bluesky.jetstream'
  ) then$old$,
    $new$    'source.bluesky.jetstream',
    'source.nostr.relay'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if job_type = 'source.bluesky.jetstream' and ($old$,
    $new$  if job_type = 'source.nostr.relay' and (
    not (payload ?& array['relay_key'])
    or payload - array['relay_key'] <> '{}'::jsonb
    or jsonb_typeof(payload -> 'relay_key') is distinct from 'string'
    or payload ->> 'relay_key' not in ('primal', 'nos_lol', 'nostr_net')
    or schedule_name <> 'nostr_' || payload ->> 'relay_key'
  ) then
    raise exception using
      errcode = '22023',
      message = 'Nostr jobs require one exact relay_key and canonical schedule name';
  end if;
  if job_type = 'source.nostr.relay' and not exists (
    select 1
    from ingest.source_policies as policies
    where policies.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    )
      and policies.enabled
      and not policies.is_demo
      and policies.collector_type = 'nostr_relay'
      and policies.config ->> 'relay_key' = payload ->> 'relay_key'
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed Nostr relay source policy is unavailable';
  end if;
  if job_type = 'source.bluesky.jetstream' and ($new$
  );
  if updated_definition = definition
    or position($needle$    'source.nostr.relay'
  ) then$needle$ in updated_definition) = 0
    or position($needle$  if job_type = 'source.nostr.relay' and ($needle$ in updated_definition) = 0
    or position($needle$Nostr jobs require one exact relay_key$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_scheduled_job_v1 no longer matches the reviewed Nostr extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamptz,integer)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$    'source.bluesky.jetstream'
  ) then$old$,
    $new$    'source.bluesky.jetstream',
    'source.nostr.relay'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then$old$,
    $new$  if p_job_type = 'source.nostr.relay' and (
    not (p_payload ?& array['relay_key'])
    or p_payload - array['relay_key'] <> '{}'::jsonb
    or jsonb_typeof(p_payload -> 'relay_key') is distinct from 'string'
    or p_payload ->> 'relay_key' not in ('primal', 'nos_lol', 'nostr_net')
  ) then
    raise exception using
      errcode = '22023',
      message = 'Nostr jobs require one exact relay_key';
  end if;
  if p_job_type = 'source.nostr.relay' and not exists (
    select 1
    from ingest.source_policies as policies
    where policies.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    )
      and policies.enabled
      and not policies.is_demo
      and policies.collector_type = 'nostr_relay'
      and policies.config ->> 'relay_key' = p_payload ->> 'relay_key'
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed Nostr relay source policy is unavailable';
  end if;
  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then$new$
  );
  if updated_definition = definition
    or position($needle$    'source.nostr.relay'
  ) then$needle$ in updated_definition) = 0
    or position($needle$  if p_job_type = 'source.nostr.relay' and ($needle$ in updated_definition) = 0
    or position($needle$  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_job_v1 no longer matches the reviewed Nostr extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$    'source.bluesky.jetstream'
  ) then$old$,
    $new$    'source.bluesky.jetstream',
    'source.nostr.relay'
  ) then$new$
  );
  if updated_definition = definition
    or position($needle$    'source.nostr.relay'$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'complete_job_v2 no longer matches the reviewed Nostr extension point';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) owner to postgres;
revoke all on function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_scheduled_job_v1(
  text, timestamptz, text, jsonb, integer, integer
) to service_role;
alter function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) owner to postgres;
revoke all on function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) to service_role;
alter function ingest.complete_job_v2(uuid, text, bigint) owner to postgres;
revoke all on function ingest.complete_job_v2(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.complete_job_v2(uuid, text, bigint)
  to service_role;

-- Activity rows are disposable; checkpoints are not.  Cleanup is independently
-- bounded per table and uses ten-thousand-row locking batches so a stale relay
-- cannot monopolize the maintenance transaction.
create or replace function ingest.prune_nostr_relay_v1(
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
      select candidates.event_id
      from ingest.nostr_relay_candidates as candidates
      where candidates.expires_at <= cutoff
      order by candidates.expires_at, candidates.event_id
      for update of candidates skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.nostr_relay_candidates as candidates
      using locked_candidates
      where candidates.event_id = locked_candidates.event_id
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
      from ingest.nostr_relay_observations as observations
      where observations.expires_at <= cutoff
      order by observations.expires_at, observations.id
      for update of observations skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.nostr_relay_observations as observations
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

alter function ingest.prune_nostr_relay_v1(timestamptz, integer)
  owner to postgres;
revoke all on function ingest.prune_nostr_relay_v1(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_nostr_relay_v1(timestamptz, integer) is
  'Owner-only ordered cleanup for private Nostr activity candidates and observations. Per-relay checkpoints are retained.';

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

  perform ingest.prune_nostr_relay_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );$call$
  );
  if updated_definition = definition
    or position('prune_nostr_relay_v1' in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_cleanup_job no longer matches the reviewed Nostr cleanup extension point';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.finalize_cleanup_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.finalize_cleanup_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_cleanup_job(uuid, text, bigint)
  to service_role;

-- The v2 projection is a fixed two-source tuple.  It calls the already
-- reviewed Bluesky-safe source object and computes only aggregate Nostr health
-- and an activity count; no event id, hash, endpoint, gate, or policy id is
-- placed in the public JSON.
create or replace function public.get_public_social_discovery_v2()
returns jsonb
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  with bluesky_source as (
    select jsonb_build_object(
      'id', 'bluesky_jetstream',
      'name', 'Bluesky Jetstream discovery',
      'kind', 'social',
      'access', 'public',
      'status', source ->> 'status',
      'lastCollectedAt', source -> 'lastCollectedAt',
      'url', 'https://bsky.network/docs/jetstream/',
      'note', source ->> 'note'
    ) as source
    from (
      select public.get_public_social_discovery_v1() -> 'sources' -> 0 as source
    ) as reviewed
  ),
  nostr_registered as (
    select
      policies.id,
      policies.enabled,
      policies.config ->> 'relay_key' as relay_key,
      policies.config,
      (
        policies.source_key = case policies.config ->> 'relay_key'
          when 'primal' then 'nostr_relay_primal'
          when 'nos_lol' then 'nostr_relay_nos_lol'
          when 'nostr_net' then 'nostr_relay_nostr_net'
          else ''
        end
        and policies.display_name = case policies.config ->> 'relay_key'
          when 'primal' then 'Nostr relay relay.primal.net discovery'
          when 'nos_lol' then 'Nostr relay nos.lol discovery'
          when 'nostr_net' then 'Nostr relay relay.nostr.net discovery'
          else ''
        end
        and policies.source_kind = 'public_web'
        and policies.domain = case policies.config ->> 'relay_key'
          when 'primal' then 'relay.primal.net'
          when 'nos_lol' then 'nos.lol'
          when 'nostr_net' then 'relay.nostr.net'
          else ''
        end
        and policies.base_url = case policies.config ->> 'relay_key'
          when 'primal' then 'wss://relay.primal.net/'
          when 'nos_lol' then 'wss://nos.lol/'
          when 'nostr_net' then 'wss://relay.nostr.net/'
          else ''
        end
        and policies.collector_type = 'nostr_relay'
        and policies.access_mode = 'public'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['nostr_relay']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 1
        and policies.max_items_per_run = 100
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.version = 'nostr-multi-relay-v1'
        and policies.expected_interval_seconds = 60
        and not policies.is_demo
        and policies.config ->> 'protocol' = 'nip01'
        and policies.config ->> 'policy_state' = 'degraded_missing_relay_specific_terms'
        and policies.config -> 'required_nips' = jsonb_build_array(1, 9, 11)
        and policies.config -> 'approved_tags' = jsonb_build_array(
          'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
          'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
        )
        and policies.config ->> 'endpoint' = policies.base_url
        and policies.config ->> 'nip11_url' = case policies.config ->> 'relay_key'
          when 'primal' then 'https://relay.primal.net/'
          when 'nos_lol' then 'https://nos.lol/'
          when 'nostr_net' then 'https://relay.nostr.net/'
          else ''
        end
        and policies.config ->> 'replay_overlap_seconds' = '300'
        and policies.config ->> 'stream_window_seconds' = '15'
        and policies.config ->> 'max_events' = '100'
        and policies.config ->> 'max_message_bytes' = '262144'
        and policies.config ->> 'max_stream_bytes' = '2097152'
        and policies.config ->> 'max_candidates' = '100'
        and policies.config ->> 'max_deletions' = '100'
        and policies.config ->> 'max_delete_targets' = '16'
        and policies.config ->> 'statistics_eligible' = 'false'
        and policies.config = jsonb_build_object(
          'relay_key', policies.config ->> 'relay_key',
          'endpoint', policies.base_url,
          'nip11_url', policies.config ->> 'nip11_url',
          'protocol', 'nip01',
          'policy_state', 'degraded_missing_relay_specific_terms',
          'required_nips', jsonb_build_array(1, 9, 11),
          'approved_tags', jsonb_build_array(
            'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
            'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
          ),
          'replay_overlap_seconds', 300,
          'stream_window_seconds', 15,
          'max_events', 100,
          'max_message_bytes', 262144,
          'max_stream_bytes', 2097152,
          'max_candidates', 100,
          'max_deletions', 100,
          'max_delete_targets', 16,
          'statistics_eligible', false
        )
      ) as contract_valid
    from ingest.source_policies as policies
    where policies.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    )
  ),
  nostr_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count,
      count(checkpoints.source_policy_id)::integer as checkpoint_count,
      count(checkpoints.source_policy_id) filter (
        where checkpoints.last_checkpoint is not null
          and checkpoints.last_checkpoint >= statement_timestamp() - interval '3 minutes'
          and checkpoints.last_checkpoint <= statement_timestamp()
      )::integer as recent_count,
      min(checkpoints.last_checkpoint) filter (
        where checkpoints.last_checkpoint <= statement_timestamp()
      ) as last_checkpoint,
      (
        select count(*)::integer
        from ingest.nostr_relay_candidates as candidates
        where not candidates.is_demo
          and candidates.deleted_at is null
          and candidates.expires_at > statement_timestamp()
      ) as active_candidate_count
    from nostr_registered as registered
    left join ingest.nostr_relay_checkpoints as checkpoints
      on checkpoints.source_policy_id = registered.id
      and not checkpoints.is_demo
      and checkpoints.relay_key = registered.relay_key
      and checkpoints.endpoint = registered.config ->> 'endpoint'
      and checkpoints.nip11_url = registered.config ->> 'nip11_url'
      and checkpoints.protocol = registered.config ->> 'protocol'
      and checkpoints.approved_tags = array[
        'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
        'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
      ]::text[]
  ),
  nostr_source as (
    select jsonb_build_object(
      'id', 'nostr_multi_relay',
      'name', 'Nostr multi-relay discovery',
      'kind', 'social',
      'access', 'public',
      'status', case
        when nostr_health.registered_count <> 3
          or nostr_health.valid_count <> 3
          or nostr_health.checkpoint_count <> 3
          then 'attention'
        when nostr_health.enabled_count <> 3 then 'paused'
        when nostr_health.recent_count <> 3 then 'delayed'
        else 'operational'
      end,
      'lastCollectedAt', case
        when nostr_health.last_checkpoint is null then null
        else to_char(
          nostr_health.last_checkpoint at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'url', 'https://github.com/nostr-protocol/nips/blob/master/01.md',
      'note', format(
        '%s of 3 reviewed public relays collected recently; %s retained tag-matched activity candidates. Multi-relay coverage can be incomplete and is never opening evidence or a pull-rate denominator.',
        nostr_health.recent_count,
        nostr_health.active_candidate_count
      )
    ) as source
    from nostr_health
  )
  select jsonb_build_object(
    'schemaVersion', '2.0.0',
    'sources', jsonb_build_array(
      bluesky_source.source,
      nostr_source.source
    )
  )
  from bluesky_source
  cross join nostr_source;
$$;

alter function public.get_public_social_discovery_v2() owner to postgres;
revoke all on function public.get_public_social_discovery_v2()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v2()
  to anon, authenticated;
comment on function public.get_public_social_discovery_v2() is
  'Strict public-safe Bluesky-first and Nostr-second social discovery health tuple. It never returns private activity identities, hashes, content, relay endpoints, gates, or policy identifiers.';

commit;
