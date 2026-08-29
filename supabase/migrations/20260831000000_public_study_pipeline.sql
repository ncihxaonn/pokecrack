begin;

-- This immutable private ledger is the only bridge from a reviewed web page
-- to an opening and, when still below publication thresholds, a public map
-- count. It stores no raw HTML, media, author handle, or exact address.
create table ingest.public_study_observations (
  study_key text primary key,
  source_policy_id uuid not null
    references ingest.source_policies (id)
    on update restrict on delete restrict,
  source_item_id uuid not null unique
    references ingest.source_items (id)
    on update restrict on delete restrict,
  extraction_run_id uuid not null unique
    references ingest.extraction_runs (id)
    on update restrict on delete restrict,
  opening_id uuid not null unique
    references ingest.openings (id)
    on update restrict on delete restrict,
  country_code text not null
    references catalog.iso_alpha2_codes (code)
    on update restrict on delete restrict,
  country_name text not null,
  geography_basis text not null,
  geography_confidence text not null,
  source_observed_at timestamptz not null,
  pack_count integer not null,
  qualifying_hit_pack_count integer not null,
  set_external_id text not null,
  product_scope text not null,
  metric_key text not null,
  metric_version text not null,
  collector_version text not null,
  parser_version text not null,
  source_policy_version text not null,
  evidence_sha256 text not null,
  first_verified_at timestamptz not null,
  last_verified_at timestamptz not null,
  is_demo boolean not null default false,
  constraint public_study_observations_key_check check (
    study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'
  ),
  constraint public_study_observations_country_name_check check (
    btrim(country_name) <> '' and char_length(country_name) <= 160
  ),
  constraint public_study_observations_geography_check check (
    geography_basis in ('publisher_country', 'author_public_residence')
    and geography_confidence = 'tier_b'
  ),
  constraint public_study_observations_counts_check check (
    pack_count between 1 and 100000
    and qualifying_hit_pack_count between 0 and pack_count
  ),
  constraint public_study_observations_set_check check (
    btrim(set_external_id) <> '' and char_length(set_external_id) <= 160
  ),
  constraint public_study_observations_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint public_study_observations_metric_check check (
    metric_key = 'qualifying_hit_pack_rate'
    and metric_version = 'global-sir-v1'
  ),
  constraint public_study_observations_version_check check (
    btrim(collector_version) <> ''
    and char_length(collector_version) <= 120
    and btrim(parser_version) <> ''
    and char_length(parser_version) <= 120
    and btrim(source_policy_version) <> ''
    and char_length(source_policy_version) <= 120
  ),
  constraint public_study_observations_hash_check check (
    evidence_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint public_study_observations_time_check check (
    last_verified_at >= first_verified_at
  ),
  constraint public_study_observations_live_only_check check (not is_demo)
);

create index public_study_observations_country_time_idx
  on ingest.public_study_observations (
    country_code,
    source_observed_at desc,
    study_key
  );

alter table ingest.public_study_observations enable row level security;
alter table ingest.public_study_observations force row level security;
create policy public_study_observations_service_role_select
  on ingest.public_study_observations
  for select
  to service_role
  using (true);
revoke all on table ingest.public_study_observations
  from public, anon, authenticated, service_role;
grant select on table ingest.public_study_observations to service_role;

comment on table ingest.public_study_observations is
  'Private immutable ledger for exact reviewed public opening studies. Raw HTML and exact addresses are never retained; direct mutation is denied to service_role.';

-- Keep historical map cells for audit, but never let yesterday's rolling
-- cohort survive as the browser-visible "latest" result after a source ages
-- out. The service role retains its separate read-only audit policy.
drop policy country_period_map_cells_public_read
  on public.country_period_map_cells;
create policy country_period_map_cells_public_read
  on public.country_period_map_cells
  for select
  to anon, authenticated
  using (
    not is_demo
    and period_end = (statement_timestamp() at time zone 'UTC')::date
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
  'public_study_comicbook_us_55',
  'ComicBook Perfect Order 55-pack study',
  'public_web',
  'comicbook.com',
  'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
  true,
  'scrapling_http',
  'public',
  'respect',
  array['scrapling_http']::text[],
  false,
  30,
  2,
  1,
  1,
  true,
  730,
  '{
    "study_key":"comicbook-perfect-order-us-55-v1",
    "canonical_url":"https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
    "collector_version":"public-study-comicbook-perfect-order-v1",
    "parser_version":"comicbook-perfect-order-evidence-v1",
    "country_code":"US",
    "country_name":"United States",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me03",
    "product_scope":"all",
    "pack_count":55,
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-03-19T21:00:00Z",
    "denominator_complete":true
  }'::jsonb,
  'public-study-comicbook-perfect-order-v1',
  86400,
  false
),
(
  'public_study_wargamer_gb_17',
  'Wargamer Chaos Rising 17-pack study',
  'public_web',
  'www.wargamer.com',
  'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
  true,
  'scrapling_http',
  'public',
  'respect',
  array['scrapling_http']::text[],
  false,
  30,
  2,
  1,
  1,
  true,
  730,
  '{
    "study_key":"wargamer-chaos-rising-gb-17-v1",
    "canonical_url":"https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
    "collector_version":"public-study-wargamer-chaos-rising-v1",
    "parser_version":"wargamer-chaos-rising-evidence-v1",
    "country_code":"GB",
    "country_name":"United Kingdom",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me04",
    "product_scope":"all",
    "pack_count":17,
    "qualifying_hit_pack_count":0,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-05-11T00:00:00Z",
    "denominator_complete":true
  }'::jsonb,
  'public-study-wargamer-chaos-rising-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_comicbook_us_55'),
  ('public_study_wargamer_gb_17');

create or replace function ingest.begin_public_study_job(
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
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  request_gate ingest.source_request_gates%rowtype;
  lease_checked_at timestamptz;
  request_retry_at timestamptz;
  requested_study_key text;
  policy_key text;
  expected_domain text;
  expected_url text;
  expected_display_name text;
  expected_version text;
  expected_config jsonb;
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
  where jobs.id = begin_public_study_job.job_id
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
    or leased_job.job_type <> 'source.public_study.opening'
    or jsonb_typeof(leased_job.payload) is distinct from 'object'
    or not (leased_job.payload ?& array['study_key'])
    or leased_job.payload - array['study_key'] <> '{}'::jsonb
    or jsonb_typeof(leased_job.payload -> 'study_key') is distinct from 'string'
    or leased_job.payload ->> 'study_key' not in (
      'comicbook-perfect-order-us-55-v1',
      'wargamer-chaos-rising-gb-17-v1'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'public-study begin requires one exact approved live study payload';
  end if;

  requested_study_key := leased_job.payload ->> 'study_key';
  if requested_study_key = 'comicbook-perfect-order-us-55-v1' then
    policy_key := 'public_study_comicbook_us_55';
    expected_domain := 'comicbook.com';
    expected_url := 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates';
    expected_display_name := 'ComicBook Perfect Order 55-pack study';
    expected_version := 'public-study-comicbook-perfect-order-v1';
    expected_config := '{
      "study_key":"comicbook-perfect-order-us-55-v1",
      "canonical_url":"https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
      "collector_version":"public-study-comicbook-perfect-order-v1",
      "parser_version":"comicbook-perfect-order-evidence-v1",
      "country_code":"US",
      "country_name":"United States",
      "geography_basis":"publisher_country",
      "geography_confidence":"tier_b",
      "set_external_id":"me03",
      "product_scope":"all",
      "pack_count":55,
      "qualifying_hit_pack_count":1,
      "qualifying_metric":"sir_pack",
      "metric_version":"global-sir-v1",
      "observed_at":"2026-03-19T21:00:00Z",
      "denominator_complete":true
    }'::jsonb;
  else
    policy_key := 'public_study_wargamer_gb_17';
    expected_domain := 'www.wargamer.com';
    expected_url := 'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview';
    expected_display_name := 'Wargamer Chaos Rising 17-pack study';
    expected_version := 'public-study-wargamer-chaos-rising-v1';
    expected_config := '{
      "study_key":"wargamer-chaos-rising-gb-17-v1",
      "canonical_url":"https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
      "collector_version":"public-study-wargamer-chaos-rising-v1",
      "parser_version":"wargamer-chaos-rising-evidence-v1",
      "country_code":"GB",
      "country_name":"United Kingdom",
      "geography_basis":"publisher_country",
      "geography_confidence":"tier_b",
      "set_external_id":"me04",
      "product_scope":"all",
      "pack_count":17,
      "qualifying_hit_pack_count":0,
      "qualifying_metric":"sir_pack",
      "metric_version":"global-sir-v1",
      "observed_at":"2026-05-11T00:00:00Z",
      "denominator_complete":true
    }'::jsonb;
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:public-study:' || requested_study_key, 0)
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = policy_key
    and policies.display_name = expected_display_name
    and policies.source_kind = 'public_web'
    and policies.domain = expected_domain
    and policies.base_url = expected_url
    and policies.enabled
    and policies.collector_type = 'scrapling_http'
    and policies.access_mode = 'public'
    and policies.robots_policy = 'respect'
    and policies.routes = array['scrapling_http']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 30
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 1
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and policies.statistics_eligible_default
    and policies.retention_days = 730
    and policies.config = expected_config
    and policies.version = expected_version
    and policies.expected_interval_seconds = 86400
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = policy_key
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study request gate is unavailable';
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
      lease_checked_at + interval '30 seconds'
    );
  end if;
  if policy_last_attempt_at is not null
    and lease_checked_at < policy_last_attempt_at + interval '30 seconds'
  then
    if request_retry_at is null
      or request_retry_at < policy_last_attempt_at + interval '30 seconds'
    then
      request_retry_at := policy_last_attempt_at + interval '30 seconds';
    end if;
  end if;

  if request_retry_at is not null then
    return query select false, request_retry_at;
    return;
  end if;

  -- robots.txt, a mandatory 30-second follow-up delay, and one page fetch all
  -- complete under this generation fence.
  update ingest.jobs as jobs
  set lock_expires_at = greatest(
        jobs.lock_expires_at,
        lease_checked_at + interval '150 seconds'
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
  where gates.source_key = policy_key;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study request gate is unavailable';
  end if;

  update ingest.source_policies as policies
  set last_attempt_at = lease_checked_at,
      updated_at = lease_checked_at
  where policies.id = policy_id;

  return query select true, null::timestamptz;
end;
$$;

alter function ingest.begin_public_study_job(uuid, text, bigint)
  owner to postgres;
revoke all on function ingest.begin_public_study_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_public_study_job(uuid, text, bigint)
  to service_role;
comment on function ingest.begin_public_study_job(uuid, text, bigint) is
  'Generation-fenced preflight for one exact reviewed public page, including its persistent request gate and 30-second spacing.';

create or replace function ingest.finalize_public_study_job(
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
  existing_observation ingest.public_study_observations%rowtype;
  existing_source ingest.source_items%rowtype;
  observation_exists boolean := false;
  source_exists boolean := false;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  period_start_value date;
  period_end_value date;
  requested_study_key text;
  policy_key text;
  policy_id uuid;
  expected_domain text;
  expected_url text;
  expected_display_name text;
  expected_version text;
  expected_config jsonb;
  expected_evidence text;
  expected_country_code text;
  expected_country_name text;
  expected_geography_basis text;
  expected_set_external_id text;
  expected_product_scope text;
  expected_pack_count integer;
  expected_hit_pack_count integer;
  expected_observed_at timestamptz;
  expected_collector_version text;
  expected_parser_version text;
  expected_evidence_sha256 text;
  result_title text;
  result_excerpt text;
  result_evidence_sha256 text;
  set_id_value uuid;
  source_item_id_value uuid;
  extraction_run_id_value uuid;
  opening_id_value uuid;
  cohort_pack_count bigint;
  cohort_opening_count bigint;
  cohort_source_count integer;
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
  where jobs.id = finalize_public_study_job.job_id
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
    or leased_job.job_type <> 'source.public_study.opening'
    or jsonb_typeof(leased_job.payload) is distinct from 'object'
    or not (leased_job.payload ?& array['study_key'])
    or leased_job.payload - array['study_key'] <> '{}'::jsonb
    or jsonb_typeof(leased_job.payload -> 'study_key') is distinct from 'string'
    or leased_job.payload ->> 'study_key' not in (
      'comicbook-perfect-order-us-55-v1',
      'wargamer-chaos-rising-gb-17-v1'
    )
  then
    raise exception using
      errcode = '22023',
      message = 'public-study finalizer requires one exact approved live study payload';
  end if;

  requested_study_key := leased_job.payload ->> 'study_key';
  if requested_study_key = 'comicbook-perfect-order-us-55-v1' then
    policy_key := 'public_study_comicbook_us_55';
    expected_domain := 'comicbook.com';
    expected_url := 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates';
    expected_display_name := 'ComicBook Perfect Order 55-pack study';
    expected_version := 'public-study-comicbook-perfect-order-v1';
    expected_evidence := E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare';
    expected_config := '{
      "study_key":"comicbook-perfect-order-us-55-v1",
      "canonical_url":"https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
      "collector_version":"public-study-comicbook-perfect-order-v1",
      "parser_version":"comicbook-perfect-order-evidence-v1",
      "country_code":"US",
      "country_name":"United States",
      "geography_basis":"publisher_country",
      "geography_confidence":"tier_b",
      "set_external_id":"me03",
      "product_scope":"all",
      "pack_count":55,
      "qualifying_hit_pack_count":1,
      "qualifying_metric":"sir_pack",
      "metric_version":"global-sir-v1",
      "observed_at":"2026-03-19T21:00:00Z",
      "denominator_complete":true
    }'::jsonb;
  else
    policy_key := 'public_study_wargamer_gb_17';
    expected_domain := 'www.wargamer.com';
    expected_url := 'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview';
    expected_display_name := 'Wargamer Chaos Rising 17-pack study';
    expected_version := 'public-study-wargamer-chaos-rising-v1';
    expected_evidence := E'after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.\nmissing out on any SIR mega hits.';
    expected_config := '{
      "study_key":"wargamer-chaos-rising-gb-17-v1",
      "canonical_url":"https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
      "collector_version":"public-study-wargamer-chaos-rising-v1",
      "parser_version":"wargamer-chaos-rising-evidence-v1",
      "country_code":"GB",
      "country_name":"United Kingdom",
      "geography_basis":"publisher_country",
      "geography_confidence":"tier_b",
      "set_external_id":"me04",
      "product_scope":"all",
      "pack_count":17,
      "qualifying_hit_pack_count":0,
      "qualifying_metric":"sir_pack",
      "metric_version":"global-sir-v1",
      "observed_at":"2026-05-11T00:00:00Z",
      "denominator_complete":true
    }'::jsonb;
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:public-study:' || requested_study_key, 0)
  );

  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = policy_key
    and policies.display_name = expected_display_name
    and policies.source_kind = 'public_web'
    and policies.domain = expected_domain
    and policies.base_url = expected_url
    and policies.enabled
    and policies.collector_type = 'scrapling_http'
    and policies.access_mode = 'public'
    and policies.robots_policy = 'respect'
    and policies.routes = array['scrapling_http']::text[]
    and not policies.include_subdomains
    and policies.min_delay_seconds = 30
    and policies.max_pages_per_run = 2
    and policies.max_items_per_run = 1
    and policies.max_concurrency = 1
    and policies.browser_profile is null
    and policies.statistics_eligible_default
    and policies.retention_days = 730
    and policies.config = expected_config
    and policies.version = expected_version
    and policies.expected_interval_seconds = 86400
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = policy_key
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study request gate is unavailable';
  end if;

  select observations.*
  into existing_observation
  from ingest.public_study_observations as observations
  where observations.study_key = requested_study_key
  for update of observations;
  observation_exists := found;

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
      message = 'public-study request gate is not owned by this job lease';
  end if;

  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 16384
    or not (result ?& array[
      'version',
      'study_key',
      'source_url',
      'title',
      'evidence_excerpt',
      'evidence_sha256',
      'collector_version',
      'parser_version',
      'source_policy_version'
    ])
    or result - array[
      'version',
      'study_key',
      'source_url',
      'title',
      'evidence_excerpt',
      'evidence_sha256',
      'collector_version',
      'parser_version',
      'source_policy_version'
    ] <> '{}'::jsonb
    or result -> 'version' is distinct from '1'::jsonb
    or jsonb_typeof(result -> 'study_key') is distinct from 'string'
    or jsonb_typeof(result -> 'source_url') is distinct from 'string'
    or jsonb_typeof(result -> 'title') is distinct from 'string'
    or jsonb_typeof(result -> 'evidence_excerpt') is distinct from 'string'
    or jsonb_typeof(result -> 'evidence_sha256') is distinct from 'string'
    or jsonb_typeof(result -> 'collector_version') is distinct from 'string'
    or jsonb_typeof(result -> 'parser_version') is distinct from 'string'
    or jsonb_typeof(result -> 'source_policy_version') is distinct from 'string'
  then
    raise exception using
      errcode = '22023',
      message = 'public-study result must match the exact evidence-only v1 contract';
  end if;

  result_title := result ->> 'title';
  result_excerpt := result ->> 'evidence_excerpt';
  result_evidence_sha256 := result ->> 'evidence_sha256';
  expected_country_code := expected_config ->> 'country_code';
  expected_country_name := expected_config ->> 'country_name';
  expected_geography_basis := expected_config ->> 'geography_basis';
  expected_set_external_id := expected_config ->> 'set_external_id';
  expected_product_scope := expected_config ->> 'product_scope';
  expected_pack_count := (expected_config ->> 'pack_count')::integer;
  expected_hit_pack_count :=
    (expected_config ->> 'qualifying_hit_pack_count')::integer;
  expected_observed_at := (expected_config ->> 'observed_at')::timestamptz;
  expected_collector_version := expected_config ->> 'collector_version';
  expected_parser_version := expected_config ->> 'parser_version';
  expected_evidence_sha256 := encode(
    extensions.digest(convert_to(expected_evidence, 'UTF8'), 'sha256'),
    'hex'
  );

  -- Different reviewed studies may contribute to the same country. Serialize
  -- that country's cohort recomputation so no finalizer can publish a stale
  -- count that omitted another transaction which completed concurrently.
  perform pg_advisory_xact_lock(
    hashtextextended(
      'pokecrack:public-study-country:' || expected_country_code,
      0
    )
  );

  if result ->> 'study_key' <> requested_study_key
    or result ->> 'source_url' <> expected_url
    or result ->> 'collector_version' <> expected_collector_version
    or result ->> 'parser_version' <> expected_parser_version
    or result ->> 'source_policy_version' <> expected_version
    or btrim(result_title) = ''
    or char_length(result_title) > 500
    or result_title ~ '[[:cntrl:]]'
    or btrim(result_excerpt) = ''
    or char_length(result_excerpt) > 2000
    or translate(result_excerpt, E'\n\t', '') ~ '[[:cntrl:]]'
    or result_excerpt <> expected_evidence
    or result_evidence_sha256 !~ '^[0-9a-f]{64}$'
    or result_evidence_sha256 <> expected_evidence_sha256
    or result_evidence_sha256 <> encode(
      extensions.digest(convert_to(result_excerpt, 'UTF8'), 'sha256'),
      'hex'
    )
    or (
      requested_study_key = 'comicbook-perfect-order-us-55-v1'
      and (
        position('Opened 55 Packs' in result_title) = 0
        or position('Perfect Order' in result_title) = 0
        or position('Pull Rates' in result_title) = 0
      )
    )
    or (
      requested_study_key = 'wargamer-chaos-rising-gb-17-v1'
      and (
        position('opened Pokémon Chaos Rising packs early' in result_title) = 0
        or position('blessing and a curse' in result_title) = 0
      )
    )
  then
    raise exception using
      errcode = '22023',
      message = 'public-study result identity, versions, title, evidence, or hash drifted';
  end if;

  select sets.id
  into set_id_value
  from catalog.sets as sets
  where sets.external_source = 'tcgdex'
    and sets.external_id = expected_set_external_id
    and sets.language = 'en'
    and sets.is_active
    and not sets.is_demo
  for share of sets;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'reviewed public study requires its exact live TCGdex set';
  end if;

  completion_time := clock_timestamp();
  if observation_exists then
    select source_items.*
    into existing_source
    from ingest.source_items as source_items
    where source_items.id = existing_observation.source_item_id
    for update of source_items;

    if not found
      or existing_observation.source_policy_id <> policy_id
      or existing_observation.country_code <> expected_country_code
      or existing_observation.country_name <> expected_country_name
      or existing_observation.geography_basis <> expected_geography_basis
      or existing_observation.geography_confidence <> 'tier_b'
      or existing_observation.source_observed_at <> expected_observed_at
      or existing_observation.pack_count <> expected_pack_count
      or existing_observation.qualifying_hit_pack_count <> expected_hit_pack_count
      or existing_observation.set_external_id <> expected_set_external_id
      or existing_observation.product_scope <> expected_product_scope
      or existing_observation.metric_key <> 'qualifying_hit_pack_rate'
      or existing_observation.metric_version <> 'global-sir-v1'
      or existing_observation.collector_version <> expected_collector_version
      or existing_observation.parser_version <> expected_parser_version
      or existing_observation.source_policy_version <> expected_version
      or existing_observation.evidence_sha256 <> result_evidence_sha256
      or existing_observation.is_demo
      or existing_source.source_policy_id <> policy_id
      or existing_source.source_url <> expected_url
      or existing_source.normalized_url <> expected_url
      or existing_source.domain <> expected_domain
      or existing_source.title <> result_title
      or (
        existing_source.text_excerpt is not null
        and existing_source.text_excerpt <> result_excerpt
      )
      or existing_source.content_hash <> result_evidence_sha256
      or existing_source.is_demo
      or not exists (
        select 1
        from ingest.extraction_runs as runs
        where runs.id = existing_observation.extraction_run_id
          and runs.source_item_id = existing_observation.source_item_id
          and runs.stage = 'extract'
          and runs.provider = 'deterministic-public-study'
          and runs.model = expected_parser_version
          and runs.prompt_version = 'public-study-v1'
          and runs.input_hash = result_evidence_sha256
          and runs.decision = 'accepted'
          and runs.is_demo = false
      )
      or not exists (
        select 1
        from ingest.openings as openings
        where openings.id = existing_observation.opening_id
          and openings.source_item_id = existing_observation.source_item_id
          and openings.extraction_run_id = existing_observation.extraction_run_id
          and openings.set_id = set_id_value
          and openings.product_id is null
          and openings.language = 'en'
          and openings.pack_count = expected_pack_count
          and openings.complete_opening
          and openings.country_code = expected_country_code
          and openings.opened_at = expected_observed_at
          and openings.evidence_tier = 'B'
          and openings.overall_confidence = 0.8000
          and openings.eligible_for_statistics
          and openings.methodology_version = 'public-study-global-sir-v1'
          and openings.validation_status = 'accepted'
          and openings.public_status = 'verified'
          and openings.source_kind = 'public_web'
          and openings.duplicate_of is null
          and not openings.duplicate_suspected
          and not openings.is_demo
      )
    then
      raise exception using
        errcode = '23514',
        message = 'public-study immutable observation conflicts with this verification';
    end if;

    update ingest.public_study_observations as observations
    set last_verified_at = completion_time
    where observations.study_key = requested_study_key;

    -- A successful fresh verification renews the bounded evidence retention.
    -- Cleanup may have cleared an expired excerpt during a long outage; the
    -- exact reviewed text and SHA-256 above make restoring it deterministic.
    update ingest.source_items as source_items
    set text_excerpt = result_excerpt,
        expires_at = completion_time + interval '730 days',
        updated_at = completion_time
    where source_items.id = existing_observation.source_item_id;

    update ingest.extraction_runs as runs
    set expires_at = completion_time + interval '730 days',
        updated_at = completion_time
    where runs.id = existing_observation.extraction_run_id;

    update ingest.openings as openings
    set expires_at = completion_time + interval '730 days',
        updated_at = completion_time
    where openings.id = existing_observation.opening_id;

    source_item_id_value := existing_observation.source_item_id;
    extraction_run_id_value := existing_observation.extraction_run_id;
    opening_id_value := existing_observation.opening_id;
  else
    select source_items.*
    into existing_source
    from ingest.source_items as source_items
    where source_items.platform = 'public-study'
      and source_items.external_id = requested_study_key
      and not source_items.is_demo
    for update of source_items;
    source_exists := found;

    if source_exists then
      raise exception using
        errcode = '23514',
        message = 'public-study source identity exists without its immutable ledger';
    end if;

    source_item_id_value := gen_random_uuid();
    extraction_run_id_value := gen_random_uuid();
    opening_id_value := gen_random_uuid();

    insert into ingest.source_items (
      id,
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
      content_hash,
      collector_type,
      collector_version,
      source_policy_version,
      access_mode,
      usage_classification,
      source_kind,
      language,
      status,
      metadata,
      expires_at,
      is_demo,
      created_at,
      updated_at
    ) values (
      source_item_id_value,
      policy_id,
      'public-study',
      requested_study_key,
      expected_url,
      expected_url,
      expected_domain,
      result_title,
      result_excerpt,
      expected_observed_at,
      completion_time,
      result_evidence_sha256,
      'scrapling_http',
      expected_collector_version,
      expected_version,
      'public',
      'statistics',
      'public_web',
      'en',
      'accepted',
      jsonb_build_object(
        'study_key', requested_study_key,
        'geography_basis', expected_geography_basis,
        'geography_confidence', 'tier_b',
        'raw_html_retained', false
      ),
      completion_time + interval '730 days',
      false,
      completion_time,
      completion_time
    );

    insert into ingest.extraction_runs (
      id,
      source_item_id,
      stage,
      provider,
      model,
      prompt_version,
      input_hash,
      output_json,
      decision,
      confidence,
      input_tokens,
      output_tokens,
      estimated_cost_aud,
      latency_ms,
      started_at,
      completed_at,
      expires_at,
      is_demo,
      created_at,
      updated_at
    ) values (
      extraction_run_id_value,
      source_item_id_value,
      'extract',
      'deterministic-public-study',
      expected_parser_version,
      'public-study-v1',
      result_evidence_sha256,
      jsonb_build_object(
        'study_key', requested_study_key,
        'country_code', expected_country_code,
        'country_name', expected_country_name,
        'geography_basis', expected_geography_basis,
        'geography_confidence', 'tier_b',
        'set_external_id', expected_set_external_id,
        'product_scope', expected_product_scope,
        'pack_count', expected_pack_count,
        'qualifying_hit_pack_count', expected_hit_pack_count,
        'qualifying_metric', 'sir_pack',
        'metric_version', 'global-sir-v1',
        'denominator_complete', true
      ),
      'accepted',
      0.8000,
      0,
      0,
      0,
      0,
      completion_time,
      completion_time,
      completion_time + interval '730 days',
      false,
      completion_time,
      completion_time
    );

    insert into ingest.openings (
      id,
      source_item_id,
      extraction_run_id,
      set_id,
      product_id,
      language,
      pack_count,
      complete_opening,
      country_code,
      opened_at,
      observed_at,
      evidence_tier,
      overall_confidence,
      eligible_for_statistics,
      methodology_version,
      validation_status,
      public_status,
      source_kind,
      duplicate_suspected,
      expires_at,
      is_demo,
      created_at,
      updated_at
    ) values (
      opening_id_value,
      source_item_id_value,
      extraction_run_id_value,
      set_id_value,
      null,
      'en',
      expected_pack_count,
      true,
      expected_country_code,
      expected_observed_at,
      completion_time,
      'B',
      0.8000,
      true,
      'public-study-global-sir-v1',
      'accepted',
      'verified',
      'public_web',
      false,
      completion_time + interval '730 days',
      false,
      completion_time,
      completion_time
    );

    insert into ingest.public_study_observations (
      study_key,
      source_policy_id,
      source_item_id,
      extraction_run_id,
      opening_id,
      country_code,
      country_name,
      geography_basis,
      geography_confidence,
      source_observed_at,
      pack_count,
      qualifying_hit_pack_count,
      set_external_id,
      product_scope,
      metric_key,
      metric_version,
      collector_version,
      parser_version,
      source_policy_version,
      evidence_sha256,
      first_verified_at,
      last_verified_at,
      is_demo
    ) values (
      requested_study_key,
      policy_id,
      source_item_id_value,
      extraction_run_id_value,
      opening_id_value,
      expected_country_code,
      expected_country_name,
      expected_geography_basis,
      'tier_b',
      expected_observed_at,
      expected_pack_count,
      expected_hit_pack_count,
      expected_set_external_id,
      expected_product_scope,
      'qualifying_hit_pack_rate',
      'global-sir-v1',
      expected_collector_version,
      expected_parser_version,
      expected_version,
      result_evidence_sha256,
      completion_time,
      completion_time,
      false
    );
  end if;

  -- The public map is a rolling 365-day "as fetched" snapshot. Its period
  -- therefore ends on the database completion date, while cohort membership
  -- is determined only by each reviewed source's immutable observed_at.
  period_end_value := (completion_time at time zone 'UTC')::date;
  period_start_value := period_end_value - 364;

  select
    coalesce(sum(observations.pack_count), 0)::bigint,
    count(*)::bigint,
    count(distinct policies.domain)::integer
  into cohort_pack_count, cohort_opening_count, cohort_source_count
  from ingest.public_study_observations as observations
  join ingest.source_policies as policies
    on policies.id = observations.source_policy_id
  join ingest.openings as openings
    on openings.id = observations.opening_id
  where observations.country_code = expected_country_code
    and (observations.source_observed_at at time zone 'UTC')::date
      between period_start_value and period_end_value
    and not observations.is_demo
    and not policies.is_demo
    and not openings.is_demo
    and openings.eligible_for_statistics
    and openings.complete_opening
    and openings.validation_status = 'accepted'
    and openings.public_status = 'verified'
    and openings.duplicate_of is null
    and not openings.duplicate_suspected;

  if cohort_opening_count = 0 then
    delete from public.country_period_map_cells as cells
    where cells.country_code = expected_country_code
      and cells.period_start = period_start_value
      and cells.period_end = period_end_value
      and cells.language = 'en'
      and cells.set_scope = 'all'
      and cells.product_scope = 'all'
      and cells.metric_key = 'qualifying_hit_pack_rate'
      and cells.methodology_version = 'public-study-global-sir-v1'
      and not cells.is_demo;
  elsif cohort_pack_count < 30 or cohort_source_count < 3 then
    insert into public.country_period_map_cells as cells (
      country_code,
      country_name,
      period_start,
      period_end,
      language,
      set_scope,
      product_scope,
      metric_key,
      metric_version,
      observed_packs,
      complete_openings,
      independent_source_count,
      observed_rate,
      posterior_mean,
      baseline_rate,
      credible_interval_low,
      credible_interval_high,
      delta_from_baseline,
      signal_status,
      methodology_version,
      updated_at,
      is_demo
    ) values (
      expected_country_code,
      expected_country_name,
      period_start_value,
      period_end_value,
      'en',
      'all',
      'all',
      'qualifying_hit_pack_rate',
      'global-sir-v1',
      cohort_pack_count,
      cohort_opening_count,
      cohort_source_count,
      null,
      null,
      null,
      null,
      null,
      null,
      'Insufficient sample',
      'public-study-global-sir-v1',
      completion_time,
      false
    )
    on conflict (
      country_code,
      period_start,
      period_end,
      language,
      set_scope,
      product_scope,
      metric_key,
      is_demo
    ) do update set
      country_name = excluded.country_name,
      metric_version = excluded.metric_version,
      observed_packs = excluded.observed_packs,
      complete_openings = excluded.complete_openings,
      independent_source_count = excluded.independent_source_count,
      observed_rate = null,
      posterior_mean = null,
      baseline_rate = null,
      credible_interval_low = null,
      credible_interval_high = null,
      delta_from_baseline = null,
      signal_status = 'Insufficient sample',
      methodology_version = excluded.methodology_version,
      updated_at = excluded.updated_at
    where cells.methodology_version = excluded.methodology_version;
  else
    -- This exact single-row deletion withholds an old insufficient record once
    -- the cohort crosses the display threshold. A separate reviewed aggregate
    -- publisher must calculate uncertainty before any rate can appear.
    delete from public.country_period_map_cells as cells
    where cells.country_code = expected_country_code
      and cells.period_start = period_start_value
      and cells.period_end = period_end_value
      and cells.language = 'en'
      and cells.set_scope = 'all'
      and cells.product_scope = 'all'
      and cells.metric_key = 'qualifying_hit_pack_rate'
      and cells.methodology_version = 'public-study-global-sir-v1'
      and not cells.is_demo;
  end if;

  update ingest.source_policies as policies
  set last_success_at = completion_time,
      updated_at = completion_time
  where policies.id = policy_id;

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
      errcode = '40001',
      message = 'public-study lease expired before atomic completion';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = policy_key
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'public-study completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_public_study_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_public_study_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_public_study_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_public_study_job(uuid, text, bigint, jsonb) is
  'Fenced atomic public-study persistence. Facts come only from the exact database policy; the worker supplies bounded evidence whose text and SHA-256 must match.';

alter table ingest.jobs
  drop constraint jobs_live_scheduled_enqueue_allowlist_check;

alter table ingest.jobs
  add constraint jobs_live_scheduled_enqueue_allowlist_check
  check (
    is_demo
    or dedupe_key is null
    or dedupe_key !~ '^schedule:'
    or (
      job_type in ('catalog.tcgdex.sets.sync', 'maintenance.cleanup')
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
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
      )
    )
  );

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
  requested_study_key text;
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
  if job_type is null or job_type not in (
    'catalog.tcgdex.sets.sync',
    'maintenance.cleanup',
    'source.youtube.discovery',
    'source.public_study.opening'
  ) then
    raise exception using
      errcode = '22023',
      message = 'job_type is not approved for scheduled enqueue';
  end if;
  if payload is null
    or jsonb_typeof(payload) is distinct from 'object'
    or octet_length(payload::text) > 4096
  then
    raise exception using
      errcode = '22023',
      message = 'payload must be a bounded JSON object';
  end if;
  if job_type in ('catalog.tcgdex.sets.sync', 'maintenance.cleanup')
    and payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'catalog and cleanup jobs require an empty payload';
  end if;
  if job_type = 'source.youtube.discovery' and (
    not (payload ?& array['query_name'])
    or payload - array['query_name'] <> '{}'::jsonb
    or jsonb_typeof(payload -> 'query_name') is distinct from 'string'
    or payload ->> 'query_name' not in (
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
  if job_type = 'source.public_study.opening' then
    if not (payload ?& array['study_key'])
      or payload - array['study_key'] <> '{}'::jsonb
      or jsonb_typeof(payload -> 'study_key') is distinct from 'string'
      or payload ->> 'study_key' not in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
      )
    then
      raise exception using
        errcode = '22023',
        message = 'public-study jobs require one exact approved study_key';
    end if;
    requested_study_key := payload ->> 'study_key';
    if schedule_name <> 'public_study_' || requested_study_key then
      raise exception using
        errcode = '22023',
        message = 'public-study schedule_name must match its exact study_key';
    end if;
    if not exists (
      select 1
      from ingest.source_policies as policies
      where policies.enabled
        and not policies.is_demo
        and policies.collector_type = 'scrapling_http'
        and policies.config ->> 'study_key' = requested_study_key
        and policies.source_key = case requested_study_key
          when 'comicbook-perfect-order-us-55-v1'
            then 'public_study_comicbook_us_55'
          else 'public_study_wargamer_gb_17'
        end
    ) then
      raise exception using
        errcode = '55000',
        message = 'reviewed public-study source policy is unavailable';
    end if;
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
    if returned_job.job_type <> enqueue_scheduled_job_v1.job_type
      or returned_job.payload <> enqueue_scheduled_job_v1.payload
    then
      raise exception using
        errcode = '22023',
        message = 'schedule slot request must match its original job type and payload';
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
    if returned_job.job_type <> enqueue_scheduled_job_v1.job_type
      or returned_job.payload <> enqueue_scheduled_job_v1.payload
    then
      raise exception using
        errcode = '22023',
        message = 'schedule slot request must match its original job type and payload';
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
  requested_study_key text;
begin
  if p_job_type is null or p_job_type not in (
    'catalog.tcgdex.sets.sync',
    'maintenance.cleanup',
    'source.youtube.discovery',
    'source.public_study.opening'
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
  if p_job_type = 'source.public_study.opening' then
    if not (p_payload ?& array['study_key'])
      or p_payload - array['study_key'] <> '{}'::jsonb
      or jsonb_typeof(p_payload -> 'study_key') is distinct from 'string'
      or p_payload ->> 'study_key' not in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
      )
    then
      raise exception using
        errcode = '22023',
        message = 'public-study jobs require one exact approved study_key';
    end if;
    requested_study_key := p_payload ->> 'study_key';
    if not exists (
      select 1
      from ingest.source_policies as policies
      where policies.enabled
        and not policies.is_demo
        and policies.collector_type = 'scrapling_http'
        and policies.config ->> 'study_key' = requested_study_key
        and policies.source_key = case requested_study_key
          when 'comicbook-perfect-order-us-55-v1'
            then 'public_study_comicbook_us_55'
          else 'public_study_wargamer_gb_17'
        end
    ) then
      raise exception using
        errcode = '55000',
        message = 'reviewed public-study source policy is unavailable';
    end if;
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

alter function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) owner to postgres;
revoke all on function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_job_v1(
  text, jsonb, integer, text, timestamptz, integer
) to service_role;

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
  if p_worker_id is null
    or btrim(p_worker_id) = ''
    or char_length(p_worker_id) > 160
  then
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
    'source.youtube.discovery',
    'source.public_study.opening'
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

commit;
