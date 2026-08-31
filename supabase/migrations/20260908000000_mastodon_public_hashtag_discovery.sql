begin;

-- Mastodon is a fixed, anonymous, activity-only source.  The source policy
-- and every value below are intentionally repeated at the RPC boundary: a
-- worker cannot turn a scheduler payload into an arbitrary instance, path,
-- hashtag, or retention policy.
alter table ingest.source_policies
  drop constraint source_policies_collector_type_check;

alter table ingest.source_policies
  add constraint source_policies_collector_type_check check (
    collector_type in (
      'official_api',
      'bluesky_jetstream',
      'nostr_relay',
      'mastodon_rest',
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
      'mastodon_rest',
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
  'mastodon_social',
  'Mastodon public hashtag discovery',
  'official_api',
  'mastodon.social',
  'https://mastodon.social/',
  true,
  'mastodon_rest',
  'official_api',
  'not_applicable',
  array['mastodon_rest']::text[],
  false,
  1,
  2,
  80,
  1,
  false,
  30,
  '{
    "instance_key":"mastodon_social",
    "instance_url":"https://mastodon.social/api/v2/instance",
    "rules_url":"https://mastodon.social/api/v1/instance/rules",
    "terms_url":"https://mastodon.social/api/v1/instance/terms_of_service",
    "hashtag_base_url":"https://mastodon.social/api/v1/timelines/tag/",
    "official_docs_url":"https://docs.joinmastodon.org/methods/timelines/",
    "policy_state":"reviewed_public_api_2026-08-31",
    "terms_effective_date":"2026-08-31",
    "required_hashtag_access":{"local":"public","remote":"public"},
    "tag_registry":"mastodon-tags-v1",
    "approved_tags":{
      "pokemontcg":"pokemontcg",
      "pokemoncards":"pokemoncards",
      "pokeca_ja":"ポケカ",
      "pokemon_card_ja":"ポケモンカード",
      "pokemon_card_ko":"포켓몬카드",
      "pokemon_card_zh_hans":"宝可梦卡牌",
      "pokemon_card_zh_hant":"寶可夢卡牌"
    },
    "limit":40,
    "max_pages_per_run":2,
    "max_items_per_run":80,
    "max_response_bytes":2097152,
    "connect_timeout_seconds":10,
    "read_timeout_seconds":15,
    "allow_redirects":false,
    "statistics_eligible":false
  }'::jsonb,
  'mastodon-public-hashtag-v1',
  300,
  false
);

insert into ingest.source_request_gates (source_key)
values ('mastodon_social');

-- Candidate identities are one-way hashes over the fixed instance key and a
-- transient status ID.  A raw Mastodon status ID never appears in this table,
-- in observations, or in the public projection.
create table ingest.mastodon_public_hashtag_candidates (
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  status_key_sha256 text not null,
  matched_tags text[] not null,
  published_at timestamptz not null,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  expires_at timestamptz not null,
  activity_only boolean not null default true,
  statistics_eligible boolean not null default false,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (source_policy_id, status_key_sha256),
  constraint mastodon_candidates_hash_check check (
    status_key_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint mastodon_candidates_tags_check check (
    cardinality(matched_tags) between 1 and 7
    and array_position(matched_tags, null) is null
    and matched_tags <@ array[
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    ]::text[]
  ),
  constraint mastodon_candidates_published_at_check check (
    published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint mastodon_candidates_time_check check (
    last_seen_at >= first_seen_at
    and expires_at = last_seen_at + interval '30 days'
    and updated_at >= created_at
  ),
  constraint mastodon_candidates_activity_check check (
    activity_only and not statistics_eligible
  ),
  constraint mastodon_candidates_live_only_check check (not is_demo)
);

create index mastodon_candidates_active_idx
  on ingest.mastodon_public_hashtag_candidates (expires_at, source_policy_id, status_key_sha256);

alter table ingest.mastodon_public_hashtag_candidates enable row level security;
alter table ingest.mastodon_public_hashtag_candidates force row level security;
create policy mastodon_candidates_service_role_select
  on ingest.mastodon_public_hashtag_candidates
  for select to service_role using (not is_demo);
revoke all on table ingest.mastodon_public_hashtag_candidates
  from public, anon, authenticated, service_role;
grant select on table ingest.mastodon_public_hashtag_candidates to service_role;

-- Observations are append-only per policy, requested tag, and status hash.  A
-- repeated page replay is accepted only when all persisted fields match.
create table ingest.mastodon_public_hashtag_observations (
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  tag_key text not null,
  status_key_sha256 text not null,
  matched_tags text[] not null,
  published_at timestamptz not null,
  observed_at timestamptz not null,
  expires_at timestamptz not null,
  activity_only boolean not null default true,
  statistics_eligible boolean not null default false,
  is_demo boolean not null default false,
  primary key (source_policy_id, tag_key, status_key_sha256),
  constraint mastodon_observations_tag_key_check check (
    tag_key in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
  ),
  constraint mastodon_observations_hash_check check (
    status_key_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint mastodon_observations_tags_check check (
    cardinality(matched_tags) between 1 and 7
    and array_position(matched_tags, null) is null
    and matched_tags <@ array[
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    ]::text[]
    and tag_key = any(matched_tags)
  ),
  constraint mastodon_observations_published_at_check check (
    published_at >= '2000-01-01 00:00:00+00'::timestamptz
  ),
  constraint mastodon_observations_time_check check (
    expires_at = observed_at + interval '30 days'
  ),
  constraint mastodon_observations_activity_check check (
    activity_only and not statistics_eligible
  ),
  constraint mastodon_observations_live_only_check check (not is_demo)
);

create index mastodon_observations_expiry_idx
  on ingest.mastodon_public_hashtag_observations (expires_at, source_policy_id, tag_key, status_key_sha256);

alter table ingest.mastodon_public_hashtag_observations enable row level security;
alter table ingest.mastodon_public_hashtag_observations force row level security;
create policy mastodon_observations_service_role_select
  on ingest.mastodon_public_hashtag_observations
  for select to service_role using (not is_demo);
revoke all on table ingest.mastodon_public_hashtag_observations
  from public, anon, authenticated, service_role;
grant select on table ingest.mastodon_public_hashtag_observations to service_role;

-- Checkpoints intentionally retain the opaque API cursor after disposable
-- activity rows are cleaned.  One row exists per fixed policy/tag pair.
create table ingest.mastodon_public_hashtag_checkpoints (
  source_policy_id uuid not null
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  instance_key text not null,
  tag_key text not null,
  last_status_id text,
  last_collected_at timestamptz,
  incomplete boolean not null default false,
  requests_seen_total bigint not null default 0,
  statuses_seen_total bigint not null default 0,
  bytes_seen_total bigint not null default 0,
  candidates_seen_total bigint not null default 0,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (source_policy_id, tag_key),
  constraint mastodon_checkpoints_instance_check check (
    instance_key = 'mastodon_social'
  ),
  constraint mastodon_checkpoints_tag_key_check check (
    tag_key in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
  ),
  constraint mastodon_checkpoints_status_id_check check (
    last_status_id is null
    or (
      char_length(last_status_id) between 1 and 160
      and btrim(last_status_id) = last_status_id
      and last_status_id !~ '[[:cntrl:]]'
    )
  ),
  constraint mastodon_checkpoints_counter_check check (
    requests_seen_total >= 0
    and statuses_seen_total >= 0
    and bytes_seen_total >= 0
    and candidates_seen_total >= 0
  ),
  constraint mastodon_checkpoints_live_only_check check (not is_demo)
);

create index mastodon_checkpoints_collected_idx
  on ingest.mastodon_public_hashtag_checkpoints (last_collected_at desc);

alter table ingest.mastodon_public_hashtag_checkpoints enable row level security;
alter table ingest.mastodon_public_hashtag_checkpoints force row level security;
create policy mastodon_checkpoints_service_role_select
  on ingest.mastodon_public_hashtag_checkpoints
  for select to service_role using (not is_demo);
revoke all on table ingest.mastodon_public_hashtag_checkpoints
  from public, anon, authenticated, service_role;
grant select on table ingest.mastodon_public_hashtag_checkpoints to service_role;

insert into ingest.mastodon_public_hashtag_checkpoints (
  source_policy_id, instance_key, tag_key
)
select
  policies.id,
  'mastodon_social',
  tag_keys.tag_key
from ingest.source_policies as policies
cross join unnest(array[
  'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
  'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
]::text[]) as tag_keys(tag_key)
where policies.source_key = 'mastodon_social';

-- A single durable cooldown is shared by all seven tag jobs because the
-- source request gate also serializes them.  It survives activity retention.
create table ingest.mastodon_rate_cooldowns (
  source_policy_id uuid primary key
    references ingest.source_policies(id)
    on update restrict on delete restrict,
  instance_key text not null,
  cooldown_until timestamptz not null default '2000-01-01 00:00:00+00'::timestamptz,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint mastodon_cooldowns_instance_check check (
    instance_key = 'mastodon_social'
  ),
  constraint mastodon_cooldowns_live_only_check check (not is_demo),
  constraint mastodon_cooldowns_time_check check (updated_at >= created_at)
);

alter table ingest.mastodon_rate_cooldowns enable row level security;
alter table ingest.mastodon_rate_cooldowns force row level security;
create policy mastodon_cooldowns_service_role_select
  on ingest.mastodon_rate_cooldowns
  for select to service_role using (not is_demo);
revoke all on table ingest.mastodon_rate_cooldowns
  from public, anon, authenticated, service_role;
grant select on table ingest.mastodon_rate_cooldowns to service_role;

insert into ingest.mastodon_rate_cooldowns (source_policy_id, instance_key)
select id, 'mastodon_social'
from ingest.source_policies
where source_key = 'mastodon_social';

comment on table ingest.mastodon_public_hashtag_candidates is
  'Private Mastodon activity candidates keyed by policy and status hash. No status ID, content, account, URL, location, or evidence is retained.';
comment on table ingest.mastodon_public_hashtag_observations is
  'Private append-only Mastodon observations keyed by policy, requested tag, and status hash. Activity-only and never statistical evidence.';
comment on table ingest.mastodon_public_hashtag_checkpoints is
  'Private per-tag Mastodon checkpoint. The opaque status cursor is retained only here across activity cleanup.';
comment on table ingest.mastodon_rate_cooldowns is
  'Private durable Mastodon rate-limit cooldown shared by all fixed public hashtag jobs; retained across activity cleanup.';

-- Helpers are private and deliberately do not grant API or worker execution.
create or replace function ingest.mastodon_tag_keys_v1(value text[])
returns boolean
language sql
immutable
parallel safe
set search_path = pg_catalog
as $$
  select value is not null
    and cardinality(value) between 1 and 7
    and array_position(value, null) is null
    and value = array(
      select approved.tag_key
      from unnest(array[
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      ]::text[]) with ordinality as approved(tag_key, ordinal)
      where approved.tag_key = any(value)
      order by approved.ordinal
    );
$$;

alter function ingest.mastodon_tag_keys_v1(text[]) owner to postgres;
revoke all on function ingest.mastodon_tag_keys_v1(text[])
  from public, anon, authenticated, service_role;

alter table ingest.mastodon_public_hashtag_candidates
  add constraint mastodon_candidates_tags_canonical_check check (
    ingest.mastodon_tag_keys_v1(matched_tags)
  );
alter table ingest.mastodon_public_hashtag_observations
  add constraint mastodon_observations_tags_canonical_check check (
    ingest.mastodon_tag_keys_v1(matched_tags)
  );

create or replace function ingest.mastodon_status_id_v1(value text)
returns text
language plpgsql
immutable
parallel safe
set search_path = pg_catalog
as $$
begin
  if value is null
    or char_length(value) not between 1 and 160
    or btrim(value) <> value
    or value ~ '[[:cntrl:]]'
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon status ID must be bounded opaque text';
  end if;
  return value;
end;
$$;

alter function ingest.mastodon_status_id_v1(text) owner to postgres;
revoke all on function ingest.mastodon_status_id_v1(text)
  from public, anon, authenticated, service_role;

create or replace function ingest.mastodon_timestamp_v1(
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
      message = 'Mastodon timestamp is invalid';
  end if;
  begin
    parsed := value::timestamptz;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Mastodon timestamp is invalid';
  end;
  if parsed < lower_bound or parsed > upper_bound then
    raise exception using
      errcode = '22023',
      message = 'Mastodon timestamp is outside the approved range';
  end if;
  return parsed;
end;
$$;

alter function ingest.mastodon_timestamp_v1(text, timestamptz, timestamptz)
  owner to postgres;
revoke all on function ingest.mastodon_timestamp_v1(text, timestamptz, timestamptz)
  from public, anon, authenticated, service_role;

-- The exact seven ASCII keys are scheduler identities.  Their raw Unicode
-- hashtags are resolved only by the worker from the policy's fixed registry.
create or replace function ingest.begin_mastodon_public_hashtag_job(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  instance_key text,
  tag_key text
)
returns table(
  acquired boolean,
  retry_at timestamptz,
  start_status_id text,
  cooldown_until timestamptz
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
  checkpoint_row ingest.mastodon_public_hashtag_checkpoints%rowtype;
  cooldown_row ingest.mastodon_rate_cooldowns%rowtype;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  lease_checked_at timestamptz;
  request_retry_at timestamptz;
  expected_config jsonb := '{
    "instance_key":"mastodon_social",
    "instance_url":"https://mastodon.social/api/v2/instance",
    "rules_url":"https://mastodon.social/api/v1/instance/rules",
    "terms_url":"https://mastodon.social/api/v1/instance/terms_of_service",
    "hashtag_base_url":"https://mastodon.social/api/v1/timelines/tag/",
    "official_docs_url":"https://docs.joinmastodon.org/methods/timelines/",
    "policy_state":"reviewed_public_api_2026-08-31",
    "terms_effective_date":"2026-08-31",
    "required_hashtag_access":{"local":"public","remote":"public"},
    "tag_registry":"mastodon-tags-v1",
    "approved_tags":{
      "pokemontcg":"pokemontcg",
      "pokemoncards":"pokemoncards",
      "pokeca_ja":"ポケカ",
      "pokemon_card_ja":"ポケモンカード",
      "pokemon_card_ko":"포켓몬카드",
      "pokemon_card_zh_hans":"宝可梦卡牌",
      "pokemon_card_zh_hant":"寶可夢卡牌"
    },
    "limit":40,
    "max_pages_per_run":2,
    "max_items_per_run":80,
    "max_response_bytes":2097152,
    "connect_timeout_seconds":10,
    "read_timeout_seconds":15,
    "allow_redirects":false,
    "statistics_eligible":false
  }'::jsonb;
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
  if instance_key is distinct from 'mastodon_social'
    or tag_key is null
    or tag_key not in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon instance_key or tag_key is not approved';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = begin_mastodon_public_hashtag_job.job_id
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
    or leased_job.job_type <> 'source.mastodon.public_hashtag'
    or leased_job.payload <> jsonb_build_object(
      'instance_key', instance_key,
      'tag_key', tag_key
    )
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon begin requires one live job with its exact payload';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:mastodon:public_hashtag:live', 0)
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = 'mastodon_social'
    and policies.display_name = 'Mastodon public hashtag discovery'
    and policies.source_kind = 'official_api'
    and policies.domain = 'mastodon.social'
    and policies.base_url = 'https://mastodon.social/'
    and policies.enabled
    and policies.collector_type = 'mastodon_rest'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['mastodon_rest']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 80
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = expected_config
    and policies.version = 'mastodon-public-hashtag-v1'
    and policies.expected_interval_seconds = 300
    and not policies.is_demo
  for update of policies;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'mastodon_social'
  for update of gates;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon request gate is unavailable';
  end if;

  select checkpoints.*
  into checkpoint_row
  from ingest.mastodon_public_hashtag_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and checkpoints.instance_key = 'mastodon_social'
    and checkpoints.tag_key = begin_mastodon_public_hashtag_job.tag_key
    and not checkpoints.is_demo
  for update of checkpoints;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon checkpoint is unavailable';
  end if;

  select cooldowns.*
  into cooldown_row
  from ingest.mastodon_rate_cooldowns as cooldowns
  where cooldowns.source_policy_id = policy_id
    and cooldowns.instance_key = 'mastodon_social'
    and not cooldowns.is_demo
  for update of cooldowns;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon rate cooldown is unavailable';
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
  if cooldown_row.cooldown_until > lease_checked_at
    and (request_retry_at is null or cooldown_row.cooldown_until > request_retry_at)
  then
    request_retry_at := cooldown_row.cooldown_until;
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
      checkpoint_row.last_status_id,
      cooldown_row.cooldown_until;
    return;
  end if;

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
  where gates.source_key = 'mastodon_social';
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  return query select
    true,
    null::timestamptz,
    checkpoint_row.last_status_id,
    cooldown_row.cooldown_until;
end;
$$;

alter function ingest.begin_mastodon_public_hashtag_job(uuid, text, bigint, text, text)
  owner to postgres;
revoke all on function ingest.begin_mastodon_public_hashtag_job(uuid, text, bigint, text, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_mastodon_public_hashtag_job(uuid, text, bigint, text, text)
  to service_role;

comment on function ingest.begin_mastodon_public_hashtag_job(uuid, text, bigint, text, text) is
  'Generation-fenced preflight for one fixed mastodon.social public hashtag activity slice; all seven tags share one durable request gate and cooldown.';

-- Persist only the exact, bounded completion DTO.  The transient status_id is
-- used to bind the identity hash and is never written to a durable table.
create or replace function ingest.finalize_mastodon_public_hashtag_job(
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
  checkpoint_row ingest.mastodon_public_hashtag_checkpoints%rowtype;
  cooldown_row ingest.mastodon_rate_cooldowns%rowtype;
  existing_observation ingest.mastodon_public_hashtag_observations%rowtype;
  existing_candidate ingest.mastodon_public_hashtag_candidates%rowtype;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  event_time timestamptz;
  expected_config jsonb := '{
    "instance_key":"mastodon_social",
    "instance_url":"https://mastodon.social/api/v2/instance",
    "rules_url":"https://mastodon.social/api/v1/instance/rules",
    "terms_url":"https://mastodon.social/api/v1/instance/terms_of_service",
    "hashtag_base_url":"https://mastodon.social/api/v1/timelines/tag/",
    "official_docs_url":"https://docs.joinmastodon.org/methods/timelines/",
    "policy_state":"reviewed_public_api_2026-08-31",
    "terms_effective_date":"2026-08-31",
    "required_hashtag_access":{"local":"public","remote":"public"},
    "tag_registry":"mastodon-tags-v1",
    "approved_tags":{
      "pokemontcg":"pokemontcg",
      "pokemoncards":"pokemoncards",
      "pokeca_ja":"ポケカ",
      "pokemon_card_ja":"ポケモンカード",
      "pokemon_card_ko":"포켓몬카드",
      "pokemon_card_zh_hans":"宝可梦卡牌",
      "pokemon_card_zh_hant":"寶可夢卡牌"
    },
    "limit":40,
    "max_pages_per_run":2,
    "max_items_per_run":80,
    "max_response_bytes":2097152,
    "connect_timeout_seconds":10,
    "read_timeout_seconds":15,
    "allow_redirects":false,
    "statistics_eligible":false
  }'::jsonb;
  expected_tag_keys constant text[] := array[
    'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
    'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
  ]::text[];
  result_instance_key text;
  result_tag_key text;
  result_start_status_id text;
  result_end_status_id text;
  result_incomplete boolean;
  result_requests_made bigint;
  result_statuses_seen bigint;
  result_bytes_seen bigint;
  result_rate_limit_limit bigint;
  result_rate_limit_remaining bigint;
  result_rate_limit_reset_at timestamptz;
  candidate_count integer;
  candidate_record record;
  candidate_value jsonb;
  candidate_status_id text;
  candidate_hash text;
  candidate_published_at timestamptz;
  candidate_tags text[];
  merged_tags text[];
  persisted_observation boolean;
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
  where jobs.id = finalize_mastodon_public_hashtag_job.job_id
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
    or leased_job.job_type <> 'source.mastodon.public_hashtag'
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon finalizer requires a live source.mastodon.public_hashtag job';
  end if;

  completion_time := clock_timestamp();
  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 2097152
    or not (result ?& array[
      'version', 'instance_key', 'tag_key', 'start_status_id', 'end_status_id',
      'incomplete', 'requests_made', 'statuses_seen', 'bytes_seen', 'candidates',
      'rate_limit_limit', 'rate_limit_remaining', 'rate_limit_reset_at'
    ])
    or result - array[
      'version', 'instance_key', 'tag_key', 'start_status_id', 'end_status_id',
      'incomplete', 'requests_made', 'statuses_seen', 'bytes_seen', 'candidates',
      'rate_limit_limit', 'rate_limit_remaining', 'rate_limit_reset_at'
    ] <> '{}'::jsonb
    or jsonb_typeof(result -> 'version') is distinct from 'string'
    or result ->> 'version' <> '1.0.0'
    or jsonb_typeof(result -> 'instance_key') is distinct from 'string'
    or jsonb_typeof(result -> 'tag_key') is distinct from 'string'
    or jsonb_typeof(result -> 'start_status_id') not in ('string', 'null')
    or jsonb_typeof(result -> 'end_status_id') not in ('string', 'null')
    or jsonb_typeof(result -> 'incomplete') is distinct from 'boolean'
    or jsonb_typeof(result -> 'requests_made') is distinct from 'number'
    or jsonb_typeof(result -> 'statuses_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'bytes_seen') is distinct from 'number'
    or jsonb_typeof(result -> 'candidates') is distinct from 'array'
    or jsonb_typeof(result -> 'rate_limit_limit') not in ('number', 'null')
    or jsonb_typeof(result -> 'rate_limit_remaining') not in ('number', 'null')
    or jsonb_typeof(result -> 'rate_limit_reset_at') not in ('string', 'null')
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon result must match the exact bounded v1 contract';
  end if;

  result_instance_key := result ->> 'instance_key';
  result_tag_key := result ->> 'tag_key';
  if result_instance_key <> 'mastodon_social'
    or result_tag_key not in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon result instance or tag key is not approved';
  end if;

  if (result ->> 'requests_made') !~ '^(0|[1-9][0-9]{0,2})$'
    or (result ->> 'statuses_seen') !~ '^(0|[1-9][0-9]{0,2})$'
    or (result ->> 'bytes_seen') !~ '^(0|[1-9][0-9]{0,6})$'
    or (
      result -> 'rate_limit_limit' <> 'null'::jsonb
      and (result ->> 'rate_limit_limit') !~ '^(0|[1-9][0-9]{0,5})$'
    )
    or (
      result -> 'rate_limit_remaining' <> 'null'::jsonb
      and (result ->> 'rate_limit_remaining') !~ '^(0|[1-9][0-9]{0,5})$'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon counters must be canonical bounded integers';
  end if;

  begin
    result_requests_made := (result ->> 'requests_made')::bigint;
    result_statuses_seen := (result ->> 'statuses_seen')::bigint;
    result_bytes_seen := (result ->> 'bytes_seen')::bigint;
    result_rate_limit_limit := case
      when result -> 'rate_limit_limit' = 'null'::jsonb then null
      else (result ->> 'rate_limit_limit')::bigint
    end;
    result_rate_limit_remaining := case
      when result -> 'rate_limit_remaining' = 'null'::jsonb then null
      else (result ->> 'rate_limit_remaining')::bigint
    end;
    result_start_status_id := case
      when result -> 'start_status_id' = 'null'::jsonb then null
      else ingest.mastodon_status_id_v1(result ->> 'start_status_id')
    end;
    result_end_status_id := case
      when result -> 'end_status_id' = 'null'::jsonb then null
      else ingest.mastodon_status_id_v1(result ->> 'end_status_id')
    end;
    result_rate_limit_reset_at := case
      when result -> 'rate_limit_reset_at' = 'null'::jsonb then null
      else ingest.mastodon_timestamp_v1(
        result ->> 'rate_limit_reset_at',
        '2000-01-01 00:00:00+00'::timestamptz,
        completion_time + interval '7 days'
      )
    end;
  exception
    when others then
      raise exception using
        errcode = '22023',
        message = 'Mastodon result cursor, timestamp, or counters are invalid';
  end;

  result_incomplete := (result ->> 'incomplete')::boolean;
  if result_requests_made > 2
    or result_statuses_seen > 80
    or result_bytes_seen > 2097152
    or result_rate_limit_limit > 1000000
    or result_rate_limit_remaining > result_rate_limit_limit
    or result_rate_limit_reset_at < completion_time - interval '5 minutes'
    or (
      result_rate_limit_remaining = 0
      and (
        result_rate_limit_reset_at is null
        or result_rate_limit_reset_at <= completion_time
      )
    )
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon result exceeds the fixed page, status, byte, or rate bounds';
  end if;

  candidate_count := jsonb_array_length(result -> 'candidates');
  if candidate_count > 80
    or candidate_count > result_statuses_seen
    or (result_statuses_seen = 0 and candidate_count <> 0)
    or (result_statuses_seen = 0 and result_end_status_id is distinct from result_start_status_id)
    or (result_statuses_seen > 0 and result_end_status_id is null)
  then
    raise exception using
      errcode = '22023',
      message = 'Mastodon candidate, status, or cursor bounds are invalid';
  end if;

  -- Validate the lease and the exact policy only after parsing the bounded
  -- worker result; none of the following writes can partially commit.
  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:mastodon:public_hashtag:live', 0)
  );

  if leased_job.payload <> jsonb_build_object(
    'instance_key', result_instance_key,
    'tag_key', result_tag_key
  ) then
    raise exception using
      errcode = '22023',
      message = 'Mastodon job payload and result identity must match exactly';
  end if;

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = 'mastodon_social'
    and policies.display_name = 'Mastodon public hashtag discovery'
    and policies.source_kind = 'official_api'
    and policies.domain = 'mastodon.social'
    and policies.base_url = 'https://mastodon.social/'
    and policies.enabled
    and policies.collector_type = 'mastodon_rest'
    and policies.access_mode = 'official_api'
    and policies.robots_policy = 'not_applicable'
    and policies.routes = array['mastodon_rest']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 1
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 80
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and not policies.statistics_eligible_default
    and policies.retention_days = 30
    and policies.config = expected_config
    and policies.version = 'mastodon-public-hashtag-v1'
    and policies.expected_interval_seconds = 300
    and not policies.is_demo
  for update of policies;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'mastodon_social'
  for update of gates;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon request gate is unavailable';
  end if;
  select checkpoints.*
  into checkpoint_row
  from ingest.mastodon_public_hashtag_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and checkpoints.instance_key = 'mastodon_social'
    and checkpoints.tag_key = result_tag_key
    and not checkpoints.is_demo
  for update of checkpoints;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon checkpoint is unavailable';
  end if;
  select cooldowns.*
  into cooldown_row
  from ingest.mastodon_rate_cooldowns as cooldowns
  where cooldowns.source_policy_id = policy_id
    and cooldowns.instance_key = 'mastodon_social'
    and not cooldowns.is_demo
  for update of cooldowns;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon rate cooldown is unavailable';
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
      message = 'Mastodon request gate is not owned by this job lease';
  end if;
  if result_start_status_id is distinct from checkpoint_row.last_status_id then
    raise exception using
      errcode = '40001',
      message = 'Mastodon result start cursor does not match the fenced checkpoint';
  end if;
  if request_gate.acquired_at is null
    or request_gate.acquired_at > completion_time + interval '1 second'
  then
    raise exception using
      errcode = '40001',
      message = 'Mastodon request gate acquisition timestamp is invalid';
  end if;

  -- Every candidate object has exactly six keys.  status_id is transient and
  -- is immediately reduced to the instance-bound SHA-256 identity.
  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
  loop
    candidate_value := candidate_record.value;
    if jsonb_typeof(candidate_value) is distinct from 'object'
      or not (candidate_value ?& array[
        'status_id', 'status_key_sha256', 'published_at', 'matched_tags',
        'activity_only', 'statistics_eligible'
      ])
      or candidate_value - array[
        'status_id', 'status_key_sha256', 'published_at', 'matched_tags',
        'activity_only', 'statistics_eligible'
      ] <> '{}'::jsonb
      or jsonb_typeof(candidate_value -> 'status_id') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'status_key_sha256') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'published_at') is distinct from 'string'
      or jsonb_typeof(candidate_value -> 'matched_tags') is distinct from 'array'
      or jsonb_typeof(candidate_value -> 'activity_only') is distinct from 'boolean'
      or jsonb_typeof(candidate_value -> 'statistics_eligible') is distinct from 'boolean'
      or candidate_value -> 'activity_only' <> 'true'::jsonb
      or candidate_value -> 'statistics_eligible' <> 'false'::jsonb
    then
      raise exception using
        errcode = '22023',
        message = 'Mastodon candidates must use the exact bounded activity item contract';
    end if;

    candidate_status_id := ingest.mastodon_status_id_v1(candidate_value ->> 'status_id');
    candidate_hash := candidate_value ->> 'status_key_sha256';
    if candidate_hash !~ '^[0-9a-f]{64}$'
      or candidate_hash <> encode(
        extensions.digest(
          convert_to(result_instance_key || E'\n' || candidate_status_id, 'UTF8'),
          'sha256'
        ),
        'hex'
      )
    then
      raise exception using
        errcode = '22023',
        message = 'Mastodon status identity hash is not bound to the fixed instance';
    end if;

    candidate_tags := array(
      select jsonb_array_elements_text(candidate_value -> 'matched_tags')
    );
    if not ingest.mastodon_tag_keys_v1(candidate_tags)
      or not (result_tag_key = any(candidate_tags))
    then
      raise exception using
        errcode = '22023',
        message = 'Mastodon candidate tags must be the deterministic approved key list';
    end if;
    candidate_published_at := ingest.mastodon_timestamp_v1(
      candidate_value ->> 'published_at',
      '2000-01-01 00:00:00+00'::timestamptz,
      completion_time + interval '1 day'
    );
  end loop;

  if (
    select count(*) <> count(distinct value ->> 'status_id')
    from jsonb_array_elements(result -> 'candidates') as values(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'Mastodon status identities must be unique in one result';
  end if;
  if (
    select count(*) <> count(distinct value ->> 'status_key_sha256')
    from jsonb_array_elements(result -> 'candidates') as values(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'Mastodon status hashes must be unique in one result';
  end if;

  for candidate_record in
    select elements.value
    from jsonb_array_elements(result -> 'candidates') as elements(value)
  loop
    candidate_value := candidate_record.value;
    candidate_status_id := ingest.mastodon_status_id_v1(candidate_value ->> 'status_id');
    candidate_hash := candidate_value ->> 'status_key_sha256';
    candidate_tags := array(
      select jsonb_array_elements_text(candidate_value -> 'matched_tags')
    );
    candidate_published_at := ingest.mastodon_timestamp_v1(
      candidate_value ->> 'published_at',
      '2000-01-01 00:00:00+00'::timestamptz,
      completion_time + interval '1 day'
    );
    event_time := clock_timestamp();
    persisted_observation := false;
    insert into ingest.mastodon_public_hashtag_observations as observations (
      source_policy_id,
      tag_key,
      status_key_sha256,
      matched_tags,
      published_at,
      observed_at,
      expires_at,
      activity_only,
      statistics_eligible,
      is_demo
    ) values (
      policy_id,
      result_tag_key,
      candidate_hash,
      candidate_tags,
      candidate_published_at,
      event_time,
      event_time + interval '30 days',
      true,
      false,
      false
    )
    on conflict (source_policy_id, tag_key, status_key_sha256) do nothing;

    if not found then
      select observations.*
      into existing_observation
      from ingest.mastodon_public_hashtag_observations as observations
      where observations.source_policy_id = policy_id
        and observations.tag_key = result_tag_key
        and observations.status_key_sha256 = candidate_hash
      for update of observations;
      if not found
        or existing_observation.matched_tags <> candidate_tags
        or existing_observation.published_at <> candidate_published_at
        or existing_observation.activity_only is not true
        or existing_observation.statistics_eligible is not false
        or existing_observation.is_demo is not false
      then
        raise exception using
          errcode = '22023',
          message = 'Mastodon replay observation conflicts with its stored event';
      end if;
    end if;

    select candidates.*
    into existing_candidate
    from ingest.mastodon_public_hashtag_candidates as candidates
    where candidates.source_policy_id = policy_id
      and candidates.status_key_sha256 = candidate_hash
    for update of candidates;

    if found then
      if existing_candidate.published_at <> candidate_published_at
        or existing_candidate.activity_only is not true
        or existing_candidate.statistics_eligible is not false
        or existing_candidate.is_demo is not false
        or (
          result_tag_key = any(existing_candidate.matched_tags)
          and existing_candidate.matched_tags <> candidate_tags
        )
      then
        raise exception using
          errcode = '22023',
          message = 'Mastodon replay candidate conflicts with its stored event';
      end if;
      merged_tags := array(
        select approved.tag_key
        from unnest(expected_tag_keys) with ordinality as approved(tag_key, ordinal)
        where approved.tag_key = any(existing_candidate.matched_tags || candidate_tags)
        order by approved.ordinal
      );
      event_time := clock_timestamp();
      update ingest.mastodon_public_hashtag_candidates as candidates
      set matched_tags = merged_tags,
          last_seen_at = greatest(candidates.last_seen_at, event_time),
          expires_at = greatest(candidates.expires_at, event_time + interval '30 days'),
          updated_at = event_time
      where candidates.source_policy_id = policy_id
        and candidates.status_key_sha256 = candidate_hash;
    else
      event_time := clock_timestamp();
      insert into ingest.mastodon_public_hashtag_candidates (
        source_policy_id,
        status_key_sha256,
        matched_tags,
        published_at,
        first_seen_at,
        last_seen_at,
        expires_at,
        activity_only,
        statistics_eligible,
        is_demo,
        created_at,
        updated_at
      ) values (
        policy_id,
        candidate_hash,
        candidate_tags,
        candidate_published_at,
        event_time,
        event_time,
        event_time + interval '30 days',
        true,
        false,
        false,
        event_time,
        event_time
      );
    end if;
  end loop;

  -- A status ID is opaque: equality binds the replay boundary, and no numeric
  -- or lexical ordering is ever used.  The counter guard also prevents a
  -- malformed worker result from overflowing a retained checkpoint.
  completion_time := clock_timestamp();
  update ingest.mastodon_public_hashtag_checkpoints as checkpoints
  set last_status_id = result_end_status_id,
      last_collected_at = completion_time,
      incomplete = result_incomplete,
      requests_seen_total = checkpoints.requests_seen_total + result_requests_made,
      statuses_seen_total = checkpoints.statuses_seen_total + result_statuses_seen,
      bytes_seen_total = checkpoints.bytes_seen_total + result_bytes_seen,
      candidates_seen_total = checkpoints.candidates_seen_total + candidate_count,
      updated_at = completion_time
  where checkpoints.source_policy_id = policy_id
    and checkpoints.instance_key = 'mastodon_social'
    and checkpoints.tag_key = result_tag_key
    and not checkpoints.is_demo
    and checkpoints.last_status_id is not distinct from result_start_status_id
    and checkpoints.requests_seen_total <= 9223372036854775807 - result_requests_made
    and checkpoints.statuses_seen_total <= 9223372036854775807 - result_statuses_seen
    and checkpoints.bytes_seen_total <= 9223372036854775807 - result_bytes_seen
    and checkpoints.candidates_seen_total <= 9223372036854775807 - candidate_count;
  if not found then
    raise exception using
      errcode = '40001',
      message = 'Mastodon checkpoint changed before atomic cursor advance';
  end if;

  -- A zero remaining budget creates a durable cooldown until the exact reset
  -- header.  Nonzero remaining budget clears only an already-expired cooldown.
  update ingest.mastodon_rate_cooldowns as cooldowns
  set cooldown_until = case
        when result_rate_limit_remaining = 0 then result_rate_limit_reset_at
        else greatest(cooldowns.cooldown_until, completion_time)
      end,
      updated_at = completion_time
  where cooldowns.source_policy_id = policy_id
    and cooldowns.instance_key = 'mastodon_social'
    and not cooldowns.is_demo;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Mastodon rate cooldown changed during finalization';
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
      message = 'live Mastodon source policy changed during finalization';
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
      errcode = 'P0002',
      message = 'Mastodon completion lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'mastodon_social'
    and gates.owner_job_id = job_id
    and gates.owner_lease_generation = lease_generation;
  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'Mastodon completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  to service_role;

comment on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb) is
  'Fenced atomic Mastodon public hashtag v1 finalizer. It persists only instance-bound status hashes and activity metadata; raw IDs, content, profiles, URLs, and evidence never enter durable state.';

-- Scheduled/direct enqueue is an additional boundary: only the fixed ASCII
-- scheduler identities can create Mastodon jobs.  The worker resolves these
-- keys to the raw Unicode hashtags from the reviewed policy registry.
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
    or (
      job_type = 'source.mastodon.public_hashtag'
      and payload ?& array['instance_key', 'tag_key']
      and payload - array['instance_key', 'tag_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'instance_key') = 'string'
      and jsonb_typeof(payload -> 'tag_key') = 'string'
      and payload ->> 'instance_key' = 'mastodon_social'
      and payload ->> 'tag_key' in (
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      )
      and schedule_name = ((payload ->> 'instance_key') || '_' || (payload ->> 'tag_key'))
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
    $old$    'source.nostr.relay'
  ) then$old$,
    $new$    'source.nostr.relay',
    'source.mastodon.public_hashtag'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if job_type = 'source.bluesky.jetstream' and ($old$,
    $new$  if job_type = 'source.mastodon.public_hashtag' and (
    not (payload ?& array['instance_key', 'tag_key'])
    or payload - array['instance_key', 'tag_key'] <> '{}'::jsonb
    or jsonb_typeof(payload -> 'instance_key') is distinct from 'string'
    or jsonb_typeof(payload -> 'tag_key') is distinct from 'string'
    or payload ->> 'instance_key' <> 'mastodon_social'
    or payload ->> 'tag_key' not in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
    or schedule_name <> ((payload ->> 'instance_key') || '_' || (payload ->> 'tag_key'))
  ) then
    raise exception using
      errcode = '22023',
      message = 'Mastodon jobs require one exact instance_key, tag_key, and canonical schedule name';
  end if;
  if job_type = 'source.mastodon.public_hashtag' and not exists (
    select 1
    from ingest.source_policies as policies
    where policies.source_key = 'mastodon_social'
      and policies.enabled
      and not policies.is_demo
      and policies.source_kind = 'official_api'
      and policies.domain = 'mastodon.social'
      and policies.base_url = 'https://mastodon.social/'
      and policies.collector_type = 'mastodon_rest'
      and policies.access_mode = 'official_api'
      and policies.routes = array['mastodon_rest']::text[]
      and policies.config ->> 'instance_key' = 'mastodon_social'
      and policies.config ->> 'tag_registry' = 'mastodon-tags-v1'
      and policies.config ->> 'statistics_eligible' = 'false'
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed Mastodon source policy is unavailable';
  end if;
  if job_type = 'source.bluesky.jetstream' and ($new$
  );
  if updated_definition = definition
    or position($needle$    'source.mastodon.public_hashtag'$needle$ in updated_definition) = 0
    or position($needle$  if job_type = 'source.mastodon.public_hashtag' and ($needle$ in updated_definition) = 0
    or position($needle$Mastodon jobs require one exact instance_key$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_scheduled_job_v1 no longer matches the reviewed Mastodon extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamptz,integer)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$    'source.nostr.relay'
  ) then$old$,
    $new$    'source.nostr.relay',
    'source.mastodon.public_hashtag'
  ) then$new$
  );
  updated_definition := replace(
    updated_definition,
    $old$  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then$old$,
    $new$  if p_job_type = 'source.mastodon.public_hashtag' and (
    not (p_payload ?& array['instance_key', 'tag_key'])
    or p_payload - array['instance_key', 'tag_key'] <> '{}'::jsonb
    or jsonb_typeof(p_payload -> 'instance_key') is distinct from 'string'
    or jsonb_typeof(p_payload -> 'tag_key') is distinct from 'string'
    or p_payload ->> 'instance_key' <> 'mastodon_social'
    or p_payload ->> 'tag_key' not in (
      'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
      'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'Mastodon jobs require one exact instance_key and tag_key';
  end if;
  if p_job_type = 'source.mastodon.public_hashtag' and not exists (
    select 1
    from ingest.source_policies as policies
    where policies.source_key = 'mastodon_social'
      and policies.enabled
      and not policies.is_demo
      and policies.source_kind = 'official_api'
      and policies.domain = 'mastodon.social'
      and policies.base_url = 'https://mastodon.social/'
      and policies.collector_type = 'mastodon_rest'
      and policies.access_mode = 'official_api'
      and policies.routes = array['mastodon_rest']::text[]
      and policies.config ->> 'instance_key' = 'mastodon_social'
      and policies.config ->> 'tag_registry' = 'mastodon-tags-v1'
      and policies.config ->> 'statistics_eligible' = 'false'
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed Mastodon source policy is unavailable';
  end if;
  if p_job_type = 'source.bluesky.jetstream' and p_payload <> '{}'::jsonb then$new$
  );
  if updated_definition = definition
    or position($needle$    'source.mastodon.public_hashtag'$needle$ in updated_definition) = 0
    or position($needle$  if p_job_type = 'source.mastodon.public_hashtag' and ($needle$ in updated_definition) = 0
    or position($needle$Mastodon jobs require one exact instance_key$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'enqueue_job_v1 no longer matches the reviewed Mastodon extension point';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$    'source.nostr.relay'$old$,
    $new$    'source.nostr.relay',
    'source.mastodon.public_hashtag'$new$
  );
  if updated_definition = definition
    or position($needle$    'source.mastodon.public_hashtag'$needle$ in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'complete_job_v2 no longer matches the reviewed Mastodon extension point';
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

-- Candidate and observation rows are disposable activity metadata.  The
-- opaque per-tag checkpoints and the shared cooldown are deliberately absent
-- from this function and therefore survive retention cleanup.
create or replace function ingest.prune_mastodon_public_hashtag_v1(
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
      select candidates.source_policy_id, candidates.status_key_sha256
      from ingest.mastodon_public_hashtag_candidates as candidates
      where candidates.expires_at <= cutoff
      order by candidates.expires_at,
        candidates.source_policy_id,
        candidates.status_key_sha256
      for update of candidates skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.mastodon_public_hashtag_candidates as candidates
      using locked_candidates
      where candidates.source_policy_id = locked_candidates.source_policy_id
        and candidates.status_key_sha256 = locked_candidates.status_key_sha256
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
      select observations.source_policy_id,
        observations.tag_key,
        observations.status_key_sha256
      from ingest.mastodon_public_hashtag_observations as observations
      where observations.expires_at <= cutoff
      order by observations.expires_at,
        observations.source_policy_id,
        observations.tag_key,
        observations.status_key_sha256
      for update of observations skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.mastodon_public_hashtag_observations as observations
      using locked_observations
      where observations.source_policy_id = locked_observations.source_policy_id
        and observations.tag_key = locked_observations.tag_key
        and observations.status_key_sha256 = locked_observations.status_key_sha256
      returning 1
    )
    select count(*)::integer into batch_deleted from deleted;
    deleted_observations := deleted_observations + batch_deleted;
    exit when batch_deleted < batch_limit;
  end loop;

  return query select deleted_candidates, deleted_observations;
end;
$$;

alter function ingest.prune_mastodon_public_hashtag_v1(timestamptz, integer)
  owner to postgres;
revoke all on function ingest.prune_mastodon_public_hashtag_v1(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_mastodon_public_hashtag_v1(timestamptz, integer) is
  'Owner-only bounded cleanup for private Mastodon activity candidates and observations. Per-tag checkpoints and the shared rate cooldown are retained.';

do $migration$
declare
  definition text;
  updated_definition text;
  cleanup_call constant text := $call$  perform ingest.prune_mastodon_public_hashtag_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );$call$;
begin
  select pg_get_functiondef(
    'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
  ) into definition;
  updated_definition := replace(
    definition,
    $old$  perform ingest.prune_nostr_relay_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );$old$,
    $new$  perform ingest.prune_nostr_relay_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );

$new$ || cleanup_call
  );
  if updated_definition = definition
    or position('prune_mastodon_public_hashtag_v1' in updated_definition) = 0
    or position('prune_nostr_relay_v1' in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_cleanup_job no longer matches the reviewed Mastodon cleanup extension point';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.finalize_cleanup_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.finalize_cleanup_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_cleanup_job(uuid, text, bigint)
  to service_role;

-- v3 carries forward the reviewed Bluesky and Nostr safe source objects and
-- appends one aggregate Mastodon object.  The private policy/checkpoint rows
-- are used only to compute health; no instance URL, endpoint, ID, hash, tag,
-- cursor, rate header, error, or raw field crosses this boundary.
create or replace function public.get_public_social_discovery_v3()
returns jsonb
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  with prior_sources as (
    select source.value, source.ordinality
    from jsonb_array_elements(
      public.get_public_social_discovery_v2() -> 'sources'
    ) with ordinality as source(value, ordinality)
  ),
  mastodon_registered as (
    select
      policies.id,
      policies.enabled,
      (
        policies.source_key = 'mastodon_social'
        and policies.display_name = 'Mastodon public hashtag discovery'
        and policies.source_kind = 'official_api'
        and policies.domain = 'mastodon.social'
        and policies.base_url = 'https://mastodon.social/'
        and policies.collector_type = 'mastodon_rest'
        and policies.access_mode = 'official_api'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['mastodon_rest']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 2
        and policies.max_items_per_run = 80
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.version = 'mastodon-public-hashtag-v1'
        and policies.expected_interval_seconds = 300
        and not policies.is_demo
        and policies.config = jsonb_build_object(
          'instance_key', 'mastodon_social',
          'instance_url', 'https://mastodon.social/api/v2/instance',
          'rules_url', 'https://mastodon.social/api/v1/instance/rules',
          'terms_url', 'https://mastodon.social/api/v1/instance/terms_of_service',
          'hashtag_base_url', 'https://mastodon.social/api/v1/timelines/tag/',
          'official_docs_url', 'https://docs.joinmastodon.org/methods/timelines/',
          'policy_state', 'reviewed_public_api_2026-08-31',
          'terms_effective_date', '2026-08-31',
          'required_hashtag_access', jsonb_build_object('local', 'public', 'remote', 'public'),
          'tag_registry', 'mastodon-tags-v1',
          'approved_tags', jsonb_build_object(
            'pokemontcg', 'pokemontcg',
            'pokemoncards', 'pokemoncards',
            'pokeca_ja', 'ポケカ',
            'pokemon_card_ja', 'ポケモンカード',
            'pokemon_card_ko', '포켓몬카드',
            'pokemon_card_zh_hans', '宝可梦卡牌',
            'pokemon_card_zh_hant', '寶可夢卡牌'
          ),
          'limit', 40,
          'max_pages_per_run', 2,
          'max_items_per_run', 80,
          'max_response_bytes', 2097152,
          'connect_timeout_seconds', 10,
          'read_timeout_seconds', 15,
          'allow_redirects', false,
          'statistics_eligible', false
        )
      ) as contract_valid
    from ingest.source_policies as policies
    where policies.source_key = 'mastodon_social'
  ),
  mastodon_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count,
      count(checkpoints.tag_key)::integer as checkpoint_count,
      count(checkpoints.tag_key) filter (
        where checkpoints.last_collected_at >= statement_timestamp() - interval '15 minutes'
          and checkpoints.last_collected_at <= statement_timestamp()
      )::integer as recent_count,
      min(checkpoints.last_collected_at) filter (
        where checkpoints.last_collected_at <= statement_timestamp()
      ) as last_collected_at,
      (
        select count(*)::integer
        from ingest.mastodon_public_hashtag_candidates as candidates
        where not candidates.is_demo
          and candidates.expires_at > statement_timestamp()
      ) as active_candidate_count
    from mastodon_registered as registered
    left join ingest.mastodon_public_hashtag_checkpoints as checkpoints
      on checkpoints.source_policy_id = registered.id
      and checkpoints.instance_key = 'mastodon_social'
      and checkpoints.tag_key in (
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      )
      and not checkpoints.is_demo
  ),
  mastodon_source as (
    select jsonb_build_object(
      'id', 'mastodon_public_hashtag',
      'name', 'Mastodon public hashtag discovery',
      'kind', 'social',
      'access', 'public',
      'status', case
        when mastodon_health.registered_count <> 1
          or mastodon_health.valid_count <> 1
          or mastodon_health.checkpoint_count <> 7
          then 'attention'
        when mastodon_health.enabled_count <> 1 then 'paused'
        when mastodon_health.recent_count <> 7 then 'delayed'
        else 'operational'
      end,
      'lastCollectedAt', case
        when mastodon_health.last_collected_at is null then null
        else to_char(
          mastodon_health.last_collected_at at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'url', 'https://docs.joinmastodon.org/methods/timelines/',
      'note', format(
        '%s of 7 reviewed public hashtags collected recently; %s retained activity-only rows. Coverage may be incomplete and is never opening evidence or a pull-rate denominator.',
        mastodon_health.recent_count,
        mastodon_health.active_candidate_count
      )
    ) as source
    from mastodon_health
  ),
  all_sources as (
    select prior_sources.value as source, prior_sources.ordinality
    from prior_sources
    union all
    select mastodon_source.source, 2147483647::bigint
    from mastodon_source
  )
  select jsonb_build_object(
    'schemaVersion', '3.0.0',
    'sources', (
      select jsonb_agg(all_sources.source order by all_sources.ordinality)
      from all_sources
    )
  );
$$;

alter function public.get_public_social_discovery_v3() owner to postgres;
revoke all on function public.get_public_social_discovery_v3()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v3()
  to anon, authenticated;
comment on function public.get_public_social_discovery_v3() is
  'Strict public-safe Bluesky, Nostr, and Mastodon social discovery health tuple. Mastodon coverage is incomplete and activity-only; the projection never opens evidence or a denominator and never returns private identities, hashes, tags, cursors, endpoints, rate headers, errors, or raw fields.';

commit;
