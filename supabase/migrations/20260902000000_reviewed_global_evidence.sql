begin;

-- Two additional first-person, deterministic public studies. Geography remains
-- Tier-B publisher country and does not claim the physical opening location.
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
  'public_study_cardchill_gb_90',
  'CardChill Ascended Heroes 90-pack study',
  'public_web',
  'cardchill.com',
  'https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real',
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
    "study_key":"cardchill-ascended-heroes-gb-90-v1",
    "canonical_url":"https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
    "collector_version":"public-study-cardchill-ascended-heroes-v1",
    "parser_version":"cardchill-ascended-heroes-evidence-v1",
    "country_code":"GB",
    "country_name":"United Kingdom",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me02.5",
    "product_scope":"etb",
    "pack_count":90,
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-03-03T11:26:21Z",
    "denominator_complete":true
  }'::jsonb,
  'public-study-cardchill-ascended-heroes-v1',
  86400,
  false
),
(
  'public_study_bleedingcool_us_36',
  'Bleeding Cool Phantasmal Flames 36-pack study',
  'public_web',
  'bleedingcool.com',
  'https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products',
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
    "study_key":"bleedingcool-phantasmal-flames-us-36-v1",
    "canonical_url":"https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products",
    "collector_version":"public-study-bleedingcool-phantasmal-flames-v1",
    "parser_version":"bleedingcool-phantasmal-flames-evidence-v1",
    "country_code":"US",
    "country_name":"United States",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me02",
    "product_scope":"booster_box",
    "pack_count":36,
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-01-03T16:12:04Z",
    "denominator_complete":true
  }'::jsonb,
  'public-study-bleedingcool-phantasmal-flames-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_cardchill_gb_90'),
  ('public_study_bleedingcool_us_36');

-- One owner-only, immutable contract is shared by the network gate, the
-- persistence finalizer, and the public projection. Keeping reviewed facts in
-- one definition prevents the worker, queue and dashboard allowlists from
-- drifting apart. The function is deliberately not executable by API roles:
-- it includes the private qualifying-hit numerator and exact evidence text.
create or replace function ingest.reviewed_public_study_contracts()
returns table(
  ordinal integer,
  study_key text,
  policy_key text,
  public_id text,
  public_name text,
  public_note text,
  display_name text,
  domain text,
  canonical_url text,
  policy_version text,
  config jsonb,
  evidence_excerpt text,
  title_fragments text[]
)
language sql
immutable
security invoker
parallel safe
set search_path = pg_catalog
as $$
  values
    (
      1,
      'comicbook-perfect-order-us-55-v1'::text,
      'public_study_comicbook_us_55'::text,
      'comicbook_perfect_order_study'::text,
      'ComicBook Perfect Order study'::text,
      'Reviewed 55-pack public study attributed to the United States; its rate remains withheld until the independent-source threshold is met.'::text,
      'ComicBook Perfect Order 55-pack study'::text,
      'comicbook.com'::text,
      'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates'::text,
      'public-study-comicbook-perfect-order-v1'::text,
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
      E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare'::text,
      array['Opened 55 Packs', 'Perfect Order', 'Pull Rates']::text[]
    ),
    (
      2,
      'wargamer-chaos-rising-gb-17-v1',
      'public_study_wargamer_gb_17',
      'wargamer_chaos_rising_study',
      'Wargamer Chaos Rising study',
      'Reviewed 17-pack public study attributed to the United Kingdom; its rate remains withheld until the pack and independent-source thresholds are met.',
      'Wargamer Chaos Rising 17-pack study',
      'www.wargamer.com',
      'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
      'public-study-wargamer-chaos-rising-v1',
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
      E'after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.\nmissing out on any SIR mega hits.',
      array['opened Pokémon Chaos Rising packs early', 'blessing and a curse']::text[]
    ),
    (
      3,
      'cardchill-ascended-heroes-gb-90-v1',
      'public_study_cardchill_gb_90',
      'cardchill_ascended_heroes_study',
      'CardChill Ascended Heroes study',
      'Reviewed 90-pack ETB study attributed to the United Kingdom; its rate remains withheld until the independent-source threshold is met.',
      'CardChill Ascended Heroes 90-pack study',
      'cardchill.com',
      'https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real',
      'public-study-cardchill-ascended-heroes-v1',
      '{
        "study_key":"cardchill-ascended-heroes-gb-90-v1",
        "canonical_url":"https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
        "collector_version":"public-study-cardchill-ascended-heroes-v1",
        "parser_version":"cardchill-ascended-heroes-evidence-v1",
        "country_code":"GB",
        "country_name":"United Kingdom",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me02.5",
        "product_scope":"etb",
        "pack_count":90,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-03-03T11:26:21Z",
        "denominator_complete":true
      }'::jsonb,
      E'I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes.\nOut of 90 packs, I pulled 19 Double Rare (ex) cards.\nAcross 10 ETBs, I pulled exactly one SIR.',
      array['Ripping 10 Ascended Heroes ETBs', 'Mega Attack', 'Pull Rate Real']::text[]
    ),
    (
      4,
      'bleedingcool-phantasmal-flames-us-36-v1',
      'public_study_bleedingcool_us_36',
      'bleedingcool_phantasmal_flames_study',
      'Bleeding Cool Phantasmal Flames study',
      'Reviewed 36-pack booster-box study attributed to the United States; its rate remains withheld until the independent-source threshold is met.',
      'Bleeding Cool Phantasmal Flames 36-pack study',
      'bleedingcool.com',
      'https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products',
      'public-study-bleedingcool-phantasmal-flames-v1',
      '{
        "study_key":"bleedingcool-phantasmal-flames-us-36-v1",
        "canonical_url":"https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products",
        "collector_version":"public-study-bleedingcool-phantasmal-flames-v1",
        "parser_version":"bleedingcool-phantasmal-flames-evidence-v1",
        "country_code":"US",
        "country_name":"United States",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me02",
        "product_scope":"booster_box",
        "pack_count":36,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-01-03T16:12:04Z",
        "denominator_complete":true
      }'::jsonb,
      E'Now, the meat and potatoes: the booster box.\nA booster box contains 36 packs, which essentially guarantees some fire.\nMy Secret Rare count here is a whopping eight, made up of five Illustration Rares, two Full Art Trainer Supporters, and, the biggest hit, a Special Illustration Rare ex.',
      array['Opening Pokémon TCG', 'Phantasmal Flames Products']::text[]
    );
$$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private numerator and exact evidence; never grant this function to API or worker roles.';

create or replace function ingest.begin_public_study_job_v2(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  study_key text
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
  reviewed record;
  policy_id uuid;
  policy_last_attempt_at timestamptz;
  request_gate ingest.source_request_gates%rowtype;
  lease_checked_at timestamptz;
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
  if study_key is null or study_key !~ '^[a-z0-9][a-z0-9-]{0,119}$' then
    raise exception using
      errcode = '22023',
      message = 'study_key must use the reviewed public-study format';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = begin_public_study_job_v2.job_id
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
    or leased_job.payload ->> 'study_key' <> study_key
  then
    raise exception using
      errcode = '22023',
      message = 'public-study begin requires one exact approved live study payload';
  end if;

  select contracts.*
  into reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  where contracts.study_key = begin_public_study_job_v2.study_key
    and contracts.ordinal in (3, 4);

  if not found then
    raise exception using
      errcode = '22023',
      message = 'public-study begin requires one exact approved live study';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:public-study:' || study_key, 0)
  );

  select policies.id, policies.last_attempt_at
  into policy_id, policy_last_attempt_at
  from ingest.source_policies as policies
  where policies.source_key = reviewed.policy_key
    and policies.display_name = reviewed.display_name
    and policies.source_kind = 'public_web'
    and policies.domain = reviewed.domain
    and policies.base_url = reviewed.canonical_url
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
    and policies.config = reviewed.config
    and policies.version = reviewed.policy_version
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
  where gates.source_key = reviewed.policy_key
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
  where gates.source_key = reviewed.policy_key;

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

alter function ingest.begin_public_study_job_v2(uuid, text, bigint, text)
  owner to postgres;
revoke all on function ingest.begin_public_study_job_v2(uuid, text, bigint, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_public_study_job_v2(uuid, text, bigint, text)
  to service_role;
comment on function ingest.begin_public_study_job_v2(uuid, text, bigint, text) is
  'Generation-fenced preflight for the immutable reviewed-study contract, including its persistent request gate and 30-second spacing.';

-- Newly reviewed pages first enter a deliberately denominator-only ledger.
-- It cannot publish a hit rate: the table has no hit numerator, posterior,
-- baseline, interval, delta, or public inference field. Promotion into the
-- immutable statistical opening ledger remains a separate reviewed migration.
create table ingest.public_study_coverage_observations (
  study_key text primary key,
  source_policy_id uuid not null unique
    references ingest.source_policies(id) on delete restrict,
  country_code text not null,
  country_name text not null,
  source_observed_at timestamptz not null,
  pack_count integer not null,
  set_external_id text not null,
  product_scope text not null,
  collector_version text not null,
  parser_version text not null,
  source_policy_version text not null,
  evidence_sha256 text not null,
  first_verified_at timestamptz not null,
  last_verified_at timestamptz not null,
  is_demo boolean not null default false,
  constraint public_study_coverage_key_check check (
    study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'
  ),
  constraint public_study_coverage_country_check check (
    country_code ~ '^[A-Z]{2}$'
    and btrim(country_name) <> ''
    and char_length(country_name) <= 160
  ),
  constraint public_study_coverage_pack_check check (
    pack_count between 1 and 100000
  ),
  constraint public_study_coverage_set_check check (
    btrim(set_external_id) <> '' and char_length(set_external_id) <= 160
  ),
  constraint public_study_coverage_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint public_study_coverage_version_check check (
    btrim(collector_version) <> '' and char_length(collector_version) <= 120
    and btrim(parser_version) <> '' and char_length(parser_version) <= 120
    and btrim(source_policy_version) <> ''
    and char_length(source_policy_version) <= 120
  ),
  constraint public_study_coverage_hash_check check (
    evidence_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint public_study_coverage_time_check check (
    last_verified_at >= first_verified_at
  ),
  constraint public_study_coverage_live_only_check check (not is_demo)
);

create index public_study_coverage_country_time_idx
  on ingest.public_study_coverage_observations (
    country_code,
    source_observed_at desc,
    study_key
  );

alter table ingest.public_study_coverage_observations enable row level security;
alter table ingest.public_study_coverage_observations force row level security;
create policy public_study_coverage_service_role_select
  on ingest.public_study_coverage_observations
  for select
  to service_role
  using (not is_demo);
revoke all on table ingest.public_study_coverage_observations
  from public, anon, authenticated, service_role;
grant select on table ingest.public_study_coverage_observations to service_role;
comment on table ingest.public_study_coverage_observations is
  'Immutable denominator-only verification ledger for reviewed pages awaiting separate statistical-ledger promotion. Contains no hit numerator or public inference.';

create or replace function ingest.finalize_public_study_coverage_job_v1(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  study_key text,
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
  reviewed record;
  request_gate ingest.source_request_gates%rowtype;
  existing_coverage ingest.public_study_coverage_observations%rowtype;
  policy_id uuid;
  lease_checked_at timestamptz;
  completion_time timestamptz;
  result_title text;
  result_excerpt text;
  result_evidence_sha256 text;
  expected_evidence_sha256 text;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null or btrim(worker_id) = '' or char_length(worker_id) > 160 then
    raise exception using errcode = '22023', message = 'worker_id is invalid';
  end if;
  if lease_generation is null or lease_generation < 1 then
    raise exception using errcode = '22023', message = 'lease_generation is invalid';
  end if;
  if study_key is null or study_key !~ '^[a-z0-9][a-z0-9-]{0,119}$' then
    raise exception using errcode = '22023', message = 'study_key is invalid';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = finalize_public_study_coverage_job_v1.job_id
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
    or leased_job.payload ->> 'study_key' <> study_key
  then
    raise exception using
      errcode = '22023',
      message = 'coverage finalizer requires one exact approved live study payload';
  end if;

  select contracts.*
  into reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  where contracts.study_key = finalize_public_study_coverage_job_v1.study_key
    and contracts.ordinal in (3, 4);

  if not found then
    raise exception using
      errcode = '22023',
      message = 'coverage finalizer accepts only the newly reviewed studies';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:public-study:' || study_key, 0)
  );

  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = reviewed.policy_key
    and policies.display_name = reviewed.display_name
    and policies.source_kind = 'public_web'
    and policies.domain = reviewed.domain
    and policies.base_url = reviewed.canonical_url
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
    and policies.config = reviewed.config
    and policies.version = reviewed.policy_version
    and policies.expected_interval_seconds = 86400
    and not policies.is_demo
  for update of policies;

  if not found then
    raise exception using errcode = '55000', message = 'reviewed policy drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = reviewed.policy_key
  for update of gates;

  if not found
    or request_gate.owner_job_id is distinct from job_id
    or request_gate.owner_lease_generation is distinct from lease_generation
    or request_gate.active_until is null
    or request_gate.active_until <= clock_timestamp()
  then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer does not own the request gate';
  end if;

  if result is null
    or jsonb_typeof(result) is distinct from 'object'
    or octet_length(result::text) > 16384
    or not (result ?& array[
      'version', 'study_key', 'source_url', 'title', 'evidence_excerpt',
      'evidence_sha256', 'collector_version', 'parser_version',
      'source_policy_version'
    ])
    or result - array[
      'version', 'study_key', 'source_url', 'title', 'evidence_excerpt',
      'evidence_sha256', 'collector_version', 'parser_version',
      'source_policy_version'
    ] <> '{}'::jsonb
    or result -> 'version' is distinct from '1'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'coverage result must match the evidence-only v1 contract';
  end if;

  result_title := result ->> 'title';
  result_excerpt := result ->> 'evidence_excerpt';
  result_evidence_sha256 := result ->> 'evidence_sha256';
  expected_evidence_sha256 := encode(
    extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'),
    'hex'
  );

  if jsonb_typeof(result -> 'study_key') is distinct from 'string'
    or jsonb_typeof(result -> 'source_url') is distinct from 'string'
    or jsonb_typeof(result -> 'title') is distinct from 'string'
    or jsonb_typeof(result -> 'evidence_excerpt') is distinct from 'string'
    or jsonb_typeof(result -> 'evidence_sha256') is distinct from 'string'
    or jsonb_typeof(result -> 'collector_version') is distinct from 'string'
    or jsonb_typeof(result -> 'parser_version') is distinct from 'string'
    or jsonb_typeof(result -> 'source_policy_version') is distinct from 'string'
    or result ->> 'study_key' <> $4
    or result ->> 'source_url' <> reviewed.canonical_url
    or (result ->> 'collector_version')
      <> (reviewed.config ->> 'collector_version')
    or (result ->> 'parser_version')
      <> (reviewed.config ->> 'parser_version')
    or result ->> 'source_policy_version' <> reviewed.policy_version
    or btrim(result_title) = ''
    or char_length(result_title) > 500
    or result_title ~ '[[:cntrl:]]'
    or exists (
      select 1
      from unnest(reviewed.title_fragments) as fragments(value)
      where position(fragments.value in result_title) = 0
    )
    or result_excerpt <> reviewed.evidence_excerpt
    or char_length(result_excerpt) > 2000
    or translate(result_excerpt, E'\n\t', '') ~ '[[:cntrl:]]'
    or result_evidence_sha256 !~ '^[0-9a-f]{64}$'
    or result_evidence_sha256 <> expected_evidence_sha256
  then
    raise exception using
      errcode = '22023',
      message = 'coverage evidence identity, title, versions, text, or hash drifted';
  end if;

  if not exists (
    select 1
    from catalog.sets as sets
    where sets.external_source = 'tcgdex'
      and sets.external_id = reviewed.config ->> 'set_external_id'
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo
  ) then
    raise exception using
      errcode = '55000',
      message = 'coverage observation requires its exact live TCGdex set';
  end if;

  select coverage.*
  into existing_coverage
  from ingest.public_study_coverage_observations as coverage
  where coverage.study_key = $4
  for update of coverage;

  completion_time := clock_timestamp();
  if found then
    if existing_coverage.source_policy_id <> policy_id
      or existing_coverage.country_code
        <> (reviewed.config ->> 'country_code')
      or existing_coverage.country_name
        <> (reviewed.config ->> 'country_name')
      or existing_coverage.source_observed_at
        <> (reviewed.config ->> 'observed_at')::timestamptz
      or existing_coverage.pack_count
        <> (reviewed.config ->> 'pack_count')::integer
      or existing_coverage.set_external_id
        <> (reviewed.config ->> 'set_external_id')
      or existing_coverage.product_scope
        <> (reviewed.config ->> 'product_scope')
      or existing_coverage.collector_version
        <> (reviewed.config ->> 'collector_version')
      or existing_coverage.parser_version
        <> (reviewed.config ->> 'parser_version')
      or existing_coverage.source_policy_version <> reviewed.policy_version
      or existing_coverage.evidence_sha256 <> result_evidence_sha256
      or existing_coverage.is_demo
    then
      raise exception using
        errcode = '23514',
        message = 'immutable coverage observation conflicts with verification';
    end if;

    update ingest.public_study_coverage_observations as coverage
    set last_verified_at = completion_time
    where coverage.study_key = $4;
  else
    insert into ingest.public_study_coverage_observations (
      study_key,
      source_policy_id,
      country_code,
      country_name,
      source_observed_at,
      pack_count,
      set_external_id,
      product_scope,
      collector_version,
      parser_version,
      source_policy_version,
      evidence_sha256,
      first_verified_at,
      last_verified_at,
      is_demo
    ) values (
      $4,
      policy_id,
      reviewed.config ->> 'country_code',
      reviewed.config ->> 'country_name',
      (reviewed.config ->> 'observed_at')::timestamptz,
      (reviewed.config ->> 'pack_count')::integer,
      reviewed.config ->> 'set_external_id',
      reviewed.config ->> 'product_scope',
      reviewed.config ->> 'collector_version',
      reviewed.config ->> 'parser_version',
      reviewed.policy_version,
      result_evidence_sha256,
      completion_time,
      completion_time,
      false
    );
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
      message = 'coverage job lease expired before completion';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = reviewed.policy_key
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'coverage completion lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) owner to postgres;
revoke all on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) to service_role;
comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for two reviewed denominator-only observations. It cannot publish hit counts or inference.';

alter table ingest.jobs
  add constraint jobs_reviewed_coverage_schedule_allowlist_check
  check (
    dedupe_key is null
    or dedupe_key !~ '^reviewed-coverage-schedule:'
    or is_demo
    or (
      job_type = 'source.public_study.opening'
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'cardchill-ascended-heroes-gb-90-v1',
        'bleedingcool-phantasmal-flames-us-36-v1'
      )
    )
  );

create or replace function ingest.enqueue_public_study_coverage_job_v1(
  p_study_key text,
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
  reviewed record;
begin
  select contracts.*
  into reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  where contracts.study_key = p_study_key
    and contracts.ordinal in (3, 4);

  if not found then
    raise exception using
      errcode = '22023',
      message = 'coverage enqueue accepts only a newly reviewed study_key';
  end if;
  if p_priority is null or p_priority < -1000 or p_priority > 1000 then
    raise exception using errcode = '22023', message = 'priority is invalid';
  end if;
  if p_max_attempts is null or p_max_attempts < 1 or p_max_attempts > 100 then
    raise exception using errcode = '22023', message = 'max_attempts is invalid';
  end if;
  if p_dedupe_key is not null and (
    btrim(p_dedupe_key) = '' or char_length(p_dedupe_key) > 256
  ) then
    raise exception using errcode = '22023', message = 'dedupe_key is invalid';
  end if;
  if not exists (
    select 1
    from ingest.source_policies as policies
    join ingest.source_request_gates as gates
      on gates.source_key = policies.source_key
    where policies.source_key = reviewed.policy_key
      and policies.enabled
      and not policies.is_demo
      and policies.collector_type = 'scrapling_http'
      and policies.config = reviewed.config
      and policies.version = reviewed.policy_version
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed coverage policy or request gate is unavailable';
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
    'source.public_study.opening',
    jsonb_build_object('study_key', p_study_key),
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

alter function ingest.enqueue_public_study_coverage_job_v1(
  text, integer, text, timestamptz, integer
) owner to postgres;
revoke all on function ingest.enqueue_public_study_coverage_job_v1(
  text, integer, text, timestamptz, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_public_study_coverage_job_v1(
  text, integer, text, timestamptz, integer
) to service_role;

create or replace function ingest.enqueue_scheduled_public_study_coverage_job_v1(
  p_schedule_name text,
  p_scheduled_for timestamptz,
  p_study_key text,
  p_priority integer default 0,
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
  proposed_job_id uuid := gen_random_uuid();
  reserved_job_id uuid;
  legacy_created_at timestamptz;
  returned_job ingest.jobs%rowtype;
  schedule_dedupe_key text;
  reviewed record;
  expected_payload jsonb;
begin
  select contracts.*
  into reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  where contracts.study_key = p_study_key
    and contracts.ordinal in (3, 4);

  if not found then
    raise exception using
      errcode = '22023',
      message = 'scheduled coverage enqueue accepts only a newly reviewed study_key';
  end if;
  if p_schedule_name is null
    or p_schedule_name <> 'public_study_' || p_study_key
    or p_schedule_name !~ '^[a-z][a-z0-9_.-]{0,79}$'
  then
    raise exception using
      errcode = '22023',
      message = 'coverage schedule_name must match its exact study_key';
  end if;
  if p_scheduled_for is null
    or p_scheduled_for <> date_trunc('minute', p_scheduled_for)
    or p_scheduled_for < enqueue_time - interval '36 hours'
    or p_scheduled_for > enqueue_time + interval '5 minutes'
  then
    raise exception using errcode = '22023', message = 'scheduled_for is invalid';
  end if;
  if p_priority is null or p_priority < -1000 or p_priority > 1000 then
    raise exception using errcode = '22023', message = 'priority is invalid';
  end if;
  if p_max_attempts is null or p_max_attempts < 1 or p_max_attempts > 100 then
    raise exception using errcode = '22023', message = 'max_attempts is invalid';
  end if;
  if not exists (
    select 1
    from ingest.source_policies as policies
    join ingest.source_request_gates as gates
      on gates.source_key = policies.source_key
    where policies.source_key = reviewed.policy_key
      and policies.enabled
      and not policies.is_demo
      and policies.collector_type = 'scrapling_http'
      and policies.config = reviewed.config
      and policies.version = reviewed.policy_version
  ) then
    raise exception using
      errcode = '55000',
      message = 'reviewed coverage policy or request gate is unavailable';
  end if;

  expected_payload := jsonb_build_object('study_key', p_study_key);
  schedule_dedupe_key := 'reviewed-coverage-schedule:'
    || p_schedule_name || ':' || to_char(
    p_scheduled_for at time zone 'UTC',
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
      p_schedule_name, p_scheduled_for, reserved_job_id, legacy_created_at
    )
    on conflict on constraint schedule_slots_pkey do nothing;

    select slots.job_id
    into reserved_job_id
    from ingest.schedule_slots as slots
    where slots.schedule_name = p_schedule_name
      and slots.slot_at = p_scheduled_for
    for share of slots;

    select jobs.*
    into returned_job
    from ingest.jobs as jobs
    where jobs.id = reserved_job_id;

    if not found
      or returned_job.job_type <> 'source.public_study.opening'
      or returned_job.payload <> expected_payload
    then
      raise exception using
        errcode = '22023',
        message = 'coverage schedule slot conflicts with its original job';
    end if;

    return next returned_job;
    return;
  end if;

  insert into ingest.schedule_slots as slots (
    schedule_name, slot_at, job_id, created_at
  ) values (
    p_schedule_name, p_scheduled_for, proposed_job_id, enqueue_time
  )
  on conflict on constraint schedule_slots_pkey do nothing
  returning slots.job_id into reserved_job_id;

  if reserved_job_id is not null then
    insert into ingest.jobs (
      id,
      job_type,
      payload,
      status,
      priority,
      attempts,
      max_attempts,
      available_at,
      dedupe_key,
      is_demo
    ) values (
      reserved_job_id,
      'source.public_study.opening',
      expected_payload,
      'pending',
      p_priority,
      0,
      p_max_attempts,
      p_scheduled_for,
      schedule_dedupe_key,
      false
    )
    returning * into returned_job;
  else
    select slots.job_id
    into reserved_job_id
    from ingest.schedule_slots as slots
    where slots.schedule_name = p_schedule_name
      and slots.slot_at = p_scheduled_for
    for share of slots;

    select jobs.*
    into returned_job
    from ingest.jobs as jobs
    where jobs.id = reserved_job_id;

    if not found
      or returned_job.job_type <> 'source.public_study.opening'
      or returned_job.payload <> expected_payload
    then
      raise exception using
        errcode = '22023',
        message = 'coverage schedule slot conflicts with its original job';
    end if;
  end if;

  return next returned_job;
end;
$$;

alter function ingest.enqueue_scheduled_public_study_coverage_job_v1(
  text, timestamptz, text, integer, integer
) owner to postgres;
revoke all on function ingest.enqueue_scheduled_public_study_coverage_job_v1(
  text, timestamptz, text, integer, integer
) from public, anon, authenticated, service_role;
grant execute on function ingest.enqueue_scheduled_public_study_coverage_job_v1(
  text, timestamptz, text, integer, integer
) to service_role;

create or replace function public.get_public_study_coverage_v1()
returns jsonb
language sql
stable
security definer
parallel restricted
set search_path = pg_catalog
as $$
with selected_period as (
  select
    (statement_timestamp() at time zone 'UTC')::date - 364 as period_start,
    (statement_timestamp() at time zone 'UTC')::date as period_end
),
reviewed as (
  select
    contracts.ordinal,
    contracts.study_key,
    contracts.public_id,
    contracts.public_name,
    contracts.public_note,
    contracts.domain,
    contracts.canonical_url,
    contracts.config,
    policies.id as policy_id,
    policies.enabled,
    policies.last_failure_at,
    coverage.country_code,
    coverage.country_name,
    coverage.source_observed_at,
    coverage.pack_count,
    coverage.set_external_id,
    coverage.last_verified_at,
    coalesce(
      policies.source_key = contracts.policy_key
      and policies.display_name = contracts.display_name
      and policies.source_kind = 'public_web'
      and policies.domain = contracts.domain
      and policies.base_url = contracts.canonical_url
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
      and policies.config = contracts.config
      and policies.version = contracts.policy_version
      and policies.expected_interval_seconds = 86400
      and not policies.is_demo,
      false
    ) as policy_valid,
    coalesce(
      coverage.study_key = contracts.study_key
      and coverage.source_policy_id = policies.id
      and coverage.country_code = contracts.config ->> 'country_code'
      and coverage.country_name = contracts.config ->> 'country_name'
      and coverage.source_observed_at
        = (contracts.config ->> 'observed_at')::timestamptz
      and coverage.pack_count = (contracts.config ->> 'pack_count')::integer
      and coverage.set_external_id = contracts.config ->> 'set_external_id'
      and coverage.product_scope = contracts.config ->> 'product_scope'
      and coverage.collector_version = contracts.config ->> 'collector_version'
      and coverage.parser_version = contracts.config ->> 'parser_version'
      and coverage.source_policy_version = contracts.policy_version
      and coverage.evidence_sha256 = encode(
        extensions.digest(convert_to(contracts.evidence_excerpt, 'UTF8'), 'sha256'),
        'hex'
      )
      and not coverage.is_demo,
      false
    ) as coverage_valid
  from ingest.reviewed_public_study_contracts() as contracts
  left join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key
    and not policies.is_demo
  left join ingest.public_study_coverage_observations as coverage
    on coverage.study_key = contracts.study_key
  where contracts.ordinal in (3, 4)
),
valid_coverage as (
  select reviewed.*
  from reviewed
  cross join selected_period as period
  where reviewed.policy_valid
    and reviewed.coverage_valid
    and (reviewed.source_observed_at at time zone 'UTC')::date
      between period.period_start and period.period_end
),
countries as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'countryCode', rows.country_code,
        'countryName', rows.country_name,
        'packsObserved', rows.packs_observed,
        'openings', rows.openings,
        'independentSources', rows.independent_sources,
        'updatedAt', rows.updated_at
      ) order by rows.country_name, rows.country_code
    ),
    '[]'::jsonb
  ) as value
  from (
    select
      coverage.country_code,
      min(coverage.country_name) as country_name,
      sum(coverage.pack_count)::bigint as packs_observed,
      count(*)::bigint as openings,
      count(distinct coverage.domain)::integer as independent_sources,
      max(coverage.last_verified_at) as updated_at
    from valid_coverage as coverage
    group by coverage.country_code
  ) as rows
),
sets as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'slug', rows.slug,
        'name', rows.name,
        'series', rows.series_name,
        'releaseDate', rows.release_date,
        'packsObserved', rows.packs_observed,
        'openings', rows.openings,
        'independentSources', rows.independent_sources,
        'updatedAt', rows.updated_at
      ) order by rows.release_date desc, rows.name, rows.slug
    ),
    '[]'::jsonb
  ) as value
  from (
    select
      catalog_sets.slug,
      catalog_sets.name,
      catalog_sets.series_name,
      catalog_sets.release_date,
      sum(coverage.pack_count)::bigint as packs_observed,
      count(*)::bigint as openings,
      count(distinct coverage.domain)::integer as independent_sources,
      max(coverage.last_verified_at) as updated_at
    from valid_coverage as coverage
    join catalog.sets as catalog_sets
      on catalog_sets.external_source = 'tcgdex'
      and catalog_sets.external_id = coverage.set_external_id
      and catalog_sets.language = 'en'
      and catalog_sets.is_active
      and not catalog_sets.is_demo
    where catalog_sets.series_name is not null
      and btrim(catalog_sets.series_name) <> ''
      and catalog_sets.release_date is not null
    group by
      catalog_sets.slug,
      catalog_sets.name,
      catalog_sets.series_name,
      catalog_sets.release_date
  ) as rows
),
sources as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', reviewed.public_id,
        'name', reviewed.public_name,
        'kind', 'community',
        'access', 'public',
        'status', case
          when reviewed.enabled is false then 'paused'
          when not reviewed.policy_valid then 'attention'
          when reviewed.last_failure_at is not null
            and reviewed.last_failure_at > coalesce(
              reviewed.last_verified_at,
              '-infinity'::timestamptz
            ) then 'attention'
          when not reviewed.coverage_valid then 'attention'
          when reviewed.last_verified_at < statement_timestamp() - interval '48 hours'
            then 'delayed'
          else 'operational'
        end,
        'lastCollectedAt', reviewed.last_verified_at,
        'url', reviewed.canonical_url,
        'note', reviewed.public_note
      ) order by reviewed.ordinal
    ),
    '[]'::jsonb
  ) as value
  from reviewed
)
select jsonb_build_object(
  'schemaVersion', '1.0.0',
  'period', jsonb_build_object(
    'start', period.period_start,
    'end', period.period_end
  ),
  'countries', countries.value,
  'sets', sets.value,
  'sources', sources.value
)
from selected_period as period
cross join countries
cross join sets
cross join sources;
$$;

alter function public.get_public_study_coverage_v1() owner to postgres;
revoke all on function public.get_public_study_coverage_v1()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_study_coverage_v1()
  to anon, authenticated;
comment on function public.get_public_study_coverage_v1() is
  'Bounded public projection of reviewed denominator-only coverage. Returns no hit numerator, evidence text/hash, job, gate, or policy identity.';

commit;
