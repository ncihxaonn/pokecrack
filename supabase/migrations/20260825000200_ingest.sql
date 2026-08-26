begin;

create table ingest.source_policies (
  id uuid primary key default gen_random_uuid(),
  source_key text not null,
  display_name text not null,
  source_kind text not null default 'public_web',
  domain text not null unique,
  base_url text,
  enabled boolean not null default false,
  collector_type text not null,
  access_mode text not null,
  robots_policy text not null default 'respect',
  routes text[] not null default '{}'::text[],
  include_subdomains boolean not null default false,
  min_delay_seconds numeric(10,3) not null default 1,
  max_pages_per_run integer not null default 10,
  max_items_per_run integer not null default 100,
  max_concurrency integer not null default 1,
  browser_profile text,
  statistics_eligible_default boolean not null default false,
  retention_days integer not null default 30,
  config jsonb not null default '{}'::jsonb,
  version text not null default '1',
  expected_interval_seconds integer not null default 3600,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_policies_key_check check (source_key ~ '^[a-z0-9][a-z0-9_-]{0,62}$'),
  constraint source_policies_display_name_check check (btrim(display_name) <> '' and char_length(display_name) <= 160),
  constraint source_policies_kind_check check (source_kind in ('official_api', 'public_web', 'authenticated_social', 'fixture', 'manual_import')),
  constraint source_policies_domain_check check (domain = lower(domain) and domain ~ '^[a-z0-9.-]+$' and char_length(domain) <= 253),
  constraint source_policies_base_url_check check (base_url is null or (base_url ~ '^https://' and char_length(base_url) <= 2048)),
  constraint source_policies_collector_type_check check (collector_type in ('official_api', 'scrapling_http', 'scrapling_dynamic', 'opencli_authenticated', 'manual_import', 'disabled')),
  constraint source_policies_access_mode_check check (access_mode in ('public', 'official_api', 'authenticated', 'manual', 'disabled')),
  constraint source_policies_robots_policy_check check (robots_policy in ('respect', 'not_applicable', 'manual_review', 'blocked')),
  constraint source_policies_routes_check check (
    array_position(routes, null) is null
    and routes <@ array['official_api', 'scrapling_http', 'scrapling_dynamic', 'opencli_authenticated', 'manual_import', 'disabled']::text[]
    and collector_type = any(routes)
  ),
  constraint source_policies_delay_check check (min_delay_seconds between 0 and 86400),
  constraint source_policies_max_pages_check check (max_pages_per_run between 1 and 10000),
  constraint source_policies_max_items_check check (max_items_per_run between 1 and 100000),
  constraint source_policies_concurrency_check check (max_concurrency between 1 and 32),
  constraint source_policies_browser_profile_check check (browser_profile is null or (btrim(browser_profile) <> '' and char_length(browser_profile) <= 160)),
  constraint source_policies_retention_days_check check (retention_days between 1 and 3650),
  constraint source_policies_config_check check (jsonb_typeof(config) = 'object'),
  constraint source_policies_version_check check (btrim(version) <> '' and char_length(version) <= 120),
  constraint source_policies_interval_check check (expected_interval_seconds between 60 and 604800)
);
create unique index source_policies_key_uidx on ingest.source_policies (source_key);
create index source_policies_enabled_idx on ingest.source_policies (enabled, collector_type);

create table ingest.source_items (
  id uuid primary key default gen_random_uuid(),
  source_policy_id uuid not null references ingest.source_policies(id) on update cascade on delete restrict,
  platform text,
  external_id text,
  source_url text not null,
  normalized_url text not null,
  domain text not null,
  title text,
  text_excerpt text,
  published_at timestamptz,
  discovered_at timestamptz not null default now(),
  author_hash text,
  content_hash text not null,
  media_hash text,
  video_fingerprint text,
  audio_fingerprint text,
  duplicate_cluster_id uuid references ingest.source_items(id) on update cascade on delete set null,
  duplicate_suspected boolean not null default false,
  collector_type text not null,
  collector_version text not null,
  source_policy_version text not null,
  access_mode text not null,
  usage_classification text not null default 'excluded',
  source_kind text not null default 'public_web',
  language text not null default 'en',
  status text not null default 'discovered',
  attempt_count integer not null default 0,
  last_error_code text,
  last_error_message text,
  last_error_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null default (now() + interval '30 days'),
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint source_items_platform_check check (platform is null or (btrim(platform) <> '' and char_length(platform) <= 80)),
  constraint source_items_external_id_check check (external_id is null or (btrim(external_id) <> '' and char_length(external_id) <= 256)),
  constraint source_items_source_url_check check (source_url ~ '^https://' and char_length(source_url) <= 4096),
  constraint source_items_normalized_url_check check (normalized_url ~ '^https://' and char_length(normalized_url) <= 4096),
  constraint source_items_domain_check check (domain = lower(domain) and domain ~ '^[a-z0-9.-]+$' and char_length(domain) <= 253),
  constraint source_items_title_length_check check (title is null or char_length(title) <= 500),
  constraint source_items_text_excerpt_length_check check (text_excerpt is null or char_length(text_excerpt) <= 20000),
  constraint source_items_author_hash_check check (author_hash is null or author_hash ~ '^[0-9a-f]{64}$'),
  constraint source_items_content_hash_check check (content_hash ~ '^[0-9a-f]{64}$'),
  constraint source_items_media_hash_check check (media_hash is null or media_hash ~ '^[0-9a-f]{64}$'),
  constraint source_items_video_fingerprint_check check (video_fingerprint is null or char_length(video_fingerprint) between 1 and 512),
  constraint source_items_audio_fingerprint_check check (audio_fingerprint is null or char_length(audio_fingerprint) between 1 and 512),
  constraint source_items_duplicate_cluster_check check (duplicate_cluster_id is null or duplicate_cluster_id <> id),
  constraint source_items_collector_type_check check (collector_type in ('official_api', 'scrapling_http', 'scrapling_dynamic', 'opencli_authenticated', 'manual_import', 'disabled')),
  constraint source_items_collector_version_check check (btrim(collector_version) <> '' and char_length(collector_version) <= 120),
  constraint source_items_policy_version_check check (btrim(source_policy_version) <> '' and char_length(source_policy_version) <= 120),
  constraint source_items_access_mode_check check (access_mode in ('public', 'official_api', 'authenticated', 'manual', 'disabled')),
  constraint source_items_usage_check check (usage_classification in ('statistics', 'activity_only', 'catalog', 'operations', 'excluded')),
  constraint source_items_kind_check check (source_kind in ('official_api', 'public_web', 'authenticated_social', 'fixture', 'manual_import')),
  constraint source_items_language_check check (language ~ '^[a-z]{2}$'),
  constraint source_items_status_check check (status in ('discovered', 'queued', 'collected', 'extracted', 'validated', 'accepted', 'activity_only', 'rejected', 'failed', 'excluded')),
  constraint source_items_attempt_count_check check (attempt_count between 0 and 100),
  constraint source_items_last_error_code_check check (last_error_code is null or char_length(last_error_code) <= 160),
  constraint source_items_last_error_message_check check (last_error_message is null or char_length(last_error_message) <= 8000),
  constraint source_items_error_state_check check ((last_error_code is null and last_error_message is null and last_error_at is null) or last_error_at is not null),
  constraint source_items_metadata_check check (jsonb_typeof(metadata) = 'object'),
  constraint source_items_expires_check check (expires_at > discovered_at)
);
create unique index source_items_normalized_url_uidx on ingest.source_items (normalized_url);
create unique index source_items_platform_external_uidx on ingest.source_items (platform, external_id) where platform is not null and external_id is not null;
create index source_items_policy_discovered_idx on ingest.source_items (source_policy_id, discovered_at desc);
create index source_items_status_discovered_idx on ingest.source_items (status, discovered_at);
create index source_items_expires_idx on ingest.source_items (expires_at);
create index source_items_content_hash_idx on ingest.source_items (content_hash) where content_hash is not null;
create index source_items_media_hash_idx on ingest.source_items (media_hash) where media_hash is not null;
create index source_items_video_fingerprint_idx on ingest.source_items (video_fingerprint) where video_fingerprint is not null;
create index source_items_audio_fingerprint_idx on ingest.source_items (audio_fingerprint) where audio_fingerprint is not null;
create index source_items_duplicate_cluster_idx on ingest.source_items (duplicate_cluster_id) where duplicate_cluster_id is not null;

create table ingest.extraction_runs (
  id uuid primary key default gen_random_uuid(),
  source_item_id uuid not null references ingest.source_items(id) on update cascade on delete restrict,
  stage text not null,
  provider text not null,
  model text not null,
  prompt_version text not null,
  input_hash text not null,
  output_json jsonb,
  decision text,
  confidence numeric(5,4),
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  estimated_cost_aud numeric(12,4) not null default 0,
  latency_ms integer,
  error_code text,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  expires_at timestamptz not null default (now() + interval '30 days'),
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint extraction_runs_stage_check check (stage in ('extract', 'validate', 'escalate')),
  constraint extraction_runs_provider_check check (btrim(provider) <> '' and char_length(provider) <= 120),
  constraint extraction_runs_model_check check (btrim(model) <> '' and char_length(model) <= 160),
  constraint extraction_runs_prompt_check check (btrim(prompt_version) <> '' and char_length(prompt_version) <= 120),
  constraint extraction_runs_input_hash_check check (input_hash ~ '^[0-9a-f]{64}$'),
  constraint extraction_runs_output_check check (output_json is null or jsonb_typeof(output_json) = 'object'),
  constraint extraction_runs_decision_check check (decision is null or decision in ('accepted', 'activity_only', 'rejected', 'failed')),
  constraint extraction_runs_confidence_check check (confidence is null or confidence between 0 and 1),
  constraint extraction_runs_tokens_check check (input_tokens >= 0 and output_tokens >= 0),
  constraint extraction_runs_cost_check check (estimated_cost_aud >= 0),
  constraint extraction_runs_latency_check check (latency_ms is null or latency_ms >= 0),
  constraint extraction_runs_error_code_check check (error_code is null or char_length(error_code) <= 160),
  constraint extraction_runs_error_message_check check (error_message is null or char_length(error_message) <= 8000),
  constraint extraction_runs_completion_check check ((decision is null and completed_at is null) or (decision is not null and completed_at is not null)),
  constraint extraction_runs_time_check check (completed_at is null or completed_at >= started_at),
  constraint extraction_runs_expires_check check (expires_at > started_at)
);
create index extraction_runs_source_idx on ingest.extraction_runs (source_item_id, started_at desc);
create index extraction_runs_stage_idx on ingest.extraction_runs (stage, started_at);
create index extraction_runs_expires_idx on ingest.extraction_runs (expires_at);

create table ingest.openings (
  id uuid primary key default gen_random_uuid(),
  source_item_id uuid not null references ingest.source_items(id) on update cascade on delete restrict,
  extraction_run_id uuid not null references ingest.extraction_runs(id) on update cascade on delete restrict,
  set_id uuid not null references catalog.sets(id) on update cascade on delete restrict,
  product_id uuid references catalog.products(id) on update cascade on delete restrict,
  language text not null default 'en',
  pack_count integer not null default 0,
  complete_opening boolean not null default false,
  country_code text,
  state_code text,
  city text,
  region_id uuid references catalog.regions(id) on update cascade on delete restrict,
  retailer_id uuid references catalog.retailers(id) on update cascade on delete restrict,
  store_id uuid references catalog.stores(id) on update cascade on delete restrict,
  batch_code text,
  lot_code text,
  purchase_date date,
  opened_at timestamptz,
  observed_at timestamptz not null default now(),
  evidence_tier text not null,
  overall_confidence numeric(5,4) not null,
  eligible_for_statistics boolean not null default false,
  methodology_version text not null,
  validation_status text not null,
  public_status text not null default 'provisional',
  source_kind text not null,
  duplicate_of uuid references ingest.openings(id) on update cascade on delete restrict,
  duplicate_suspected boolean not null default false,
  expires_at timestamptz not null default (now() + interval '730 days'),
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint openings_language_check check (language = 'en'),
  constraint openings_pack_count_check check (pack_count between 0 and 100000),
  constraint openings_country_code_check check (country_code is null or country_code ~ '^[A-Z]{2}$'),
  constraint openings_state_code_check check (state_code is null or char_length(state_code) <= 80),
  constraint openings_city_check check (city is null or char_length(city) <= 100),
  constraint openings_batch_code_check check (batch_code is null or (btrim(batch_code) <> '' and char_length(batch_code) <= 128)),
  constraint openings_lot_code_check check (lot_code is null or (btrim(lot_code) <> '' and char_length(lot_code) <= 128)),
  constraint openings_purchase_date_check check (purchase_date is null or opened_at is null or purchase_date <= opened_at::date),
  constraint openings_evidence_tier_check check (evidence_tier in ('A', 'B', 'C', 'D')),
  constraint openings_overall_confidence_check check (overall_confidence between 0 and 1),
  constraint openings_methodology_version_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120),
  constraint openings_validation_status_check check (validation_status in ('accepted', 'activity_only', 'rejected', 'excluded')),
  constraint openings_public_status_check check (public_status in ('provisional', 'verified', 'rejected')),
  constraint openings_source_kind_check check (source_kind in ('official_api', 'public_web', 'authenticated_social', 'fixture', 'manual_import')),
  constraint openings_duplicate_check check (duplicate_of is null or duplicate_of <> id),
  constraint openings_statistics_check check (
    not eligible_for_statistics
    or (pack_count > 0 and complete_opening and evidence_tier in ('A', 'B') and validation_status = 'accepted' and duplicate_of is null and not duplicate_suspected)
  ),
  constraint openings_rejected_check check (validation_status <> 'rejected' or public_status = 'rejected'),
  constraint openings_expires_check check (expires_at > observed_at)
);
create unique index openings_extraction_run_uidx on ingest.openings (extraction_run_id);
create index openings_source_item_idx on ingest.openings (source_item_id);
create index openings_observed_idx on ingest.openings (observed_at desc);
create index openings_set_observed_idx on ingest.openings (set_id, observed_at desc) where set_id is not null;
create index openings_statistics_idx on ingest.openings (set_id, opened_at desc) where eligible_for_statistics;
create index openings_region_idx on ingest.openings (region_id, observed_at desc) where region_id is not null;
create index openings_retailer_idx on ingest.openings (retailer_id, observed_at desc) where retailer_id is not null;

create table ingest.opening_hits (
  id uuid primary key default gen_random_uuid(),
  opening_id uuid not null references ingest.openings(id) on update cascade on delete cascade,
  card_id uuid references catalog.cards(id) on update cascade on delete restrict,
  card_name text not null,
  collector_number text,
  rarity text not null,
  quantity integer not null default 1,
  evidence_reference text,
  confidence numeric(5,4) not null,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  constraint opening_hits_card_name_check check (btrim(card_name) <> '' and char_length(card_name) <= 160),
  constraint opening_hits_collector_check check (collector_number is null or char_length(collector_number) <= 40),
  constraint opening_hits_rarity_check check (rarity ~ '^[a-z][a-z0-9_]{0,63}$'),
  constraint opening_hits_quantity_check check (quantity between 1 and 100000),
  constraint opening_hits_evidence_reference_check check (evidence_reference is null or char_length(evidence_reference) <= 2000),
  constraint opening_hits_confidence_check check (confidence between 0 and 1)
);
create unique index opening_hits_card_uidx on ingest.opening_hits (opening_id, card_id) where card_id is not null;
create unique index opening_hits_unmatched_uidx on ingest.opening_hits (opening_id, lower(card_name), coalesce(lower(collector_number), '')) where card_id is null;
create index opening_hits_opening_idx on ingest.opening_hits (opening_id);
create index opening_hits_rarity_idx on ingest.opening_hits (rarity);

create table ingest.batch_sightings (
  id uuid primary key default gen_random_uuid(),
  source_item_id uuid not null references ingest.source_items(id) on update cascade on delete restrict,
  opening_id uuid references ingest.openings(id) on update cascade on delete set null,
  set_id uuid references catalog.sets(id) on update cascade on delete restrict,
  product_id uuid references catalog.products(id) on update cascade on delete restrict,
  region_id uuid references catalog.regions(id) on update cascade on delete restrict,
  retailer_id uuid references catalog.retailers(id) on update cascade on delete restrict,
  store_id uuid references catalog.stores(id) on update cascade on delete restrict,
  batch_code text not null,
  normalized_batch_code text not null,
  lot_code text,
  normalized_lot_code text,
  pack_quantity integer,
  activity_only boolean not null default false,
  confidence numeric(5,4) not null,
  observed_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '730 days'),
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  constraint batch_sightings_code_check check (btrim(batch_code) <> '' and char_length(batch_code) <= 128),
  constraint batch_sightings_normalized_check check (normalized_batch_code ~ '^[A-Z0-9][A-Z0-9_-]{0,127}$'),
  constraint batch_sightings_lot_code_check check (lot_code is null or (btrim(lot_code) <> '' and char_length(lot_code) <= 128)),
  constraint batch_sightings_normalized_lot_check check (normalized_lot_code is null or normalized_lot_code ~ '^[A-Z0-9][A-Z0-9_-]{0,127}$'),
  constraint batch_sightings_lot_pair_check check ((lot_code is null) = (normalized_lot_code is null)),
  constraint batch_sightings_pack_quantity_check check (pack_quantity is null or pack_quantity between 1 and 100000),
  constraint batch_sightings_confidence_check check (confidence between 0 and 1),
  constraint batch_sightings_expires_check check (expires_at > observed_at)
);
create unique index batch_sightings_product_uidx on ingest.batch_sightings (source_item_id, product_id, normalized_batch_code, coalesce(normalized_lot_code, '')) where product_id is not null;
create unique index batch_sightings_unscoped_uidx on ingest.batch_sightings (source_item_id, normalized_batch_code, coalesce(normalized_lot_code, '')) where product_id is null;
create index batch_sightings_batch_idx on ingest.batch_sightings (normalized_batch_code, observed_at desc);
create index batch_sightings_set_idx on ingest.batch_sightings (set_id, observed_at desc) where set_id is not null;

create table ingest.jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending',
  priority integer not null default 0,
  attempts integer not null default 0,
  max_attempts integer not null default 5,
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  lock_expires_at timestamptz,
  locked_by text,
  last_error_code text,
  last_error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  dedupe_key text,
  retention_until timestamptz not null default (now() + interval '90 days'),
  is_demo boolean not null default false,
  constraint jobs_type_check check (job_type ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint jobs_status_check check (status in ('pending', 'running', 'completed', 'failed', 'dead', 'cancelled')),
  constraint jobs_priority_check check (priority between -1000 and 1000),
  constraint jobs_payload_check check (jsonb_typeof(payload) = 'object'),
  constraint jobs_attempts_check check (attempts >= 0 and max_attempts between 1 and 100 and attempts <= max_attempts),
  constraint jobs_lock_check check (
    (status = 'running' and locked_at is not null and lock_expires_at is not null and locked_by is not null and lock_expires_at > locked_at)
    or (status <> 'running' and locked_at is null and lock_expires_at is null and locked_by is null)
  ),
  constraint jobs_completed_check check (
    (status in ('completed', 'failed', 'dead', 'cancelled') and completed_at is not null)
    or (status not in ('completed', 'failed', 'dead', 'cancelled') and completed_at is null)
  ),
  constraint jobs_dedupe_key_check check (dedupe_key is null or (btrim(dedupe_key) <> '' and char_length(dedupe_key) <= 256)),
  constraint jobs_last_error_code_check check (last_error_code is null or char_length(last_error_code) <= 160),
  constraint jobs_last_error_message_check check (last_error_message is null or char_length(last_error_message) <= 8000),
  constraint jobs_retention_check check (retention_until > created_at)
);
create unique index jobs_active_dedupe_uidx on ingest.jobs (job_type, dedupe_key, is_demo) where dedupe_key is not null and status in ('pending', 'running');
create index jobs_claim_idx on ingest.jobs (job_type, status, priority desc, available_at, lock_expires_at);
create index jobs_retention_idx on ingest.jobs (retention_until) where status in ('completed', 'failed', 'dead', 'cancelled');

create table ingest.worker_heartbeats (
  worker_id text primary key,
  worker_type text not null,
  version text not null,
  last_seen_at timestamptz not null default now(),
  current_job_id uuid references ingest.jobs(id) on update cascade on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  constraint worker_heartbeats_worker_id_check check (btrim(worker_id) <> '' and char_length(worker_id) <= 160),
  constraint worker_heartbeats_type_check check (worker_type ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint worker_heartbeats_version_check check (btrim(version) <> '' and char_length(version) <= 80),
  constraint worker_heartbeats_metadata_check check (jsonb_typeof(metadata) = 'object')
);
create index worker_heartbeats_last_seen_idx on ingest.worker_heartbeats (last_seen_at desc);
create index worker_heartbeats_type_idx on ingest.worker_heartbeats (worker_type, last_seen_at desc);

create table ingest.browser_sessions (
  profile_name text primary key,
  status text not null default 'unknown',
  extension_connected boolean not null default false,
  daemon_connected boolean not null default false,
  authenticated_sources jsonb not null default '{}'::jsonb,
  last_check_at timestamptz not null default now(),
  last_successful_command_at timestamptz,
  last_error text,
  is_demo boolean not null default false,
  constraint browser_sessions_profile_name_check check (btrim(profile_name) <> '' and char_length(profile_name) <= 160),
  constraint browser_sessions_status_check check (btrim(status) <> '' and char_length(status) <= 80),
  constraint browser_sessions_authenticated_sources_check check (jsonb_typeof(authenticated_sources) = 'object'),
  constraint browser_sessions_last_error_check check (last_error is null or char_length(last_error) <= 8000)
);
create index browser_sessions_status_idx on ingest.browser_sessions (status, last_check_at desc);

create table ingest.ai_usage_daily (
  date date not null,
  provider text not null,
  model text not null,
  stage text not null,
  request_count integer not null default 0,
  input_tokens bigint not null default 0,
  output_tokens bigint not null default 0,
  estimated_cost_aud numeric(12,4) not null default 0,
  is_demo boolean not null default false,
  primary key (date, provider, model, stage, is_demo),
  constraint ai_usage_daily_provider_check check (btrim(provider) <> '' and char_length(provider) <= 120),
  constraint ai_usage_daily_model_check check (btrim(model) <> '' and char_length(model) <= 160),
  constraint ai_usage_daily_stage_check check (stage ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint ai_usage_daily_counts_check check (request_count >= 0 and input_tokens >= 0 and output_tokens >= 0),
  constraint ai_usage_daily_cost_check check (estimated_cost_aud >= 0)
);
create index ai_usage_daily_date_idx on ingest.ai_usage_daily (date desc);

create table ingest.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid,
  actor_email_hash text,
  action text not null,
  object_type text not null,
  object_id text,
  detail jsonb not null default '{}'::jsonb,
  ip_hash text,
  occurred_at timestamptz not null default now(),
  retention_until timestamptz not null default (now() + interval '730 days'),
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  constraint admin_audit_actor_hash_check check (actor_email_hash is null or actor_email_hash ~ '^[0-9a-f]{64}$'),
  constraint admin_audit_action_check check (action ~ '^[a-z][a-z0-9_.-]{0,119}$'),
  constraint admin_audit_object_type_check check (object_type ~ '^[a-z][a-z0-9_.-]{0,119}$'),
  constraint admin_audit_object_id_check check (object_id is null or char_length(object_id) <= 256),
  constraint admin_audit_detail_check check (jsonb_typeof(detail) = 'object'),
  constraint admin_audit_ip_hash_check check (ip_hash is null or ip_hash ~ '^[0-9a-f]{64}$'),
  constraint admin_audit_retention_check check (retention_until > occurred_at)
);
create index admin_audit_occurred_idx on ingest.admin_audit_log (occurred_at desc);
create index admin_audit_actor_idx on ingest.admin_audit_log (actor_id, occurred_at desc) where actor_id is not null;
create index admin_audit_retention_idx on ingest.admin_audit_log (retention_until);

create trigger source_policies_set_updated_at before update on ingest.source_policies for each row execute function ingest.set_updated_at();
create trigger source_items_set_updated_at before update on ingest.source_items for each row execute function ingest.set_updated_at();
create trigger extraction_runs_set_updated_at before update on ingest.extraction_runs for each row execute function ingest.set_updated_at();
create trigger openings_set_updated_at before update on ingest.openings for each row execute function ingest.set_updated_at();
create trigger jobs_set_updated_at before update on ingest.jobs for each row execute function ingest.set_updated_at();

alter table ingest.source_policies enable row level security;
alter table ingest.source_items enable row level security;
alter table ingest.extraction_runs enable row level security;
alter table ingest.openings enable row level security;
alter table ingest.opening_hits enable row level security;
alter table ingest.batch_sightings enable row level security;
alter table ingest.jobs enable row level security;
alter table ingest.worker_heartbeats enable row level security;
alter table ingest.browser_sessions enable row level security;
alter table ingest.ai_usage_daily enable row level security;
alter table ingest.admin_audit_log enable row level security;
alter table ingest.source_policies force row level security;
alter table ingest.source_items force row level security;
alter table ingest.extraction_runs force row level security;
alter table ingest.openings force row level security;
alter table ingest.opening_hits force row level security;
alter table ingest.batch_sightings force row level security;
alter table ingest.jobs force row level security;
alter table ingest.worker_heartbeats force row level security;
alter table ingest.browser_sessions force row level security;
alter table ingest.ai_usage_daily force row level security;
alter table ingest.admin_audit_log force row level security;

create policy source_policies_service_role_all on ingest.source_policies for all to service_role using (true) with check (true);
create policy source_items_service_role_all on ingest.source_items for all to service_role using (true) with check (true);
create policy extraction_runs_service_role_all on ingest.extraction_runs for all to service_role using (true) with check (true);
create policy openings_service_role_all on ingest.openings for all to service_role using (true) with check (true);
create policy opening_hits_service_role_all on ingest.opening_hits for all to service_role using (true) with check (true);
create policy batch_sightings_service_role_all on ingest.batch_sightings for all to service_role using (true) with check (true);
create policy jobs_service_role_all on ingest.jobs for all to service_role using (true) with check (true);
create policy worker_heartbeats_service_role_all on ingest.worker_heartbeats for all to service_role using (true) with check (true);
create policy browser_sessions_service_role_all on ingest.browser_sessions for all to service_role using (true) with check (true);
create policy ai_usage_daily_service_role_all on ingest.ai_usage_daily for all to service_role using (true) with check (true);
create policy admin_audit_log_service_role_all on ingest.admin_audit_log for all to service_role using (true) with check (true);

revoke all on all tables in schema ingest from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema ingest to service_role;

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
declare
  claim_time timestamptz := clock_timestamp();
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
      completed_at = claim_time,
      updated_at = claim_time
  where exhausted.attempts >= exhausted.max_attempts
    and not exhausted.is_demo
    and (
      (exhausted.status = 'pending' and exhausted.available_at <= claim_time)
      or (exhausted.status = 'running' and exhausted.lock_expires_at <= claim_time)
    );

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

alter function ingest.claim_jobs(text, text[], integer, integer) owner to postgres;
revoke all on function ingest.claim_jobs(text, text[], integer, integer) from public, anon, authenticated;
grant execute on function ingest.claim_jobs(text, text[], integer, integer) to service_role;
comment on function ingest.claim_jobs(text, text[], integer, integer) is
  'Atomically locks live due pending or expired running jobs via FOR UPDATE SKIP LOCKED. Demo jobs remain isolated in fixture mode. Service-role/dedicated DB workers only.';

comment on column ingest.source_items.text_excerpt is 'Private bounded excerpt; maximum 20,000 characters. Full content/HTML is never retained here.';
comment on column ingest.source_items.author_hash is 'Private pseudonymous author hash; never exposed publicly.';
comment on column ingest.extraction_runs.output_json is 'Private structured provider output; public relations must never select it.';
comment on column ingest.jobs.payload is 'Private worker payload; claim_jobs is service-role only.';
comment on table ingest.browser_sessions is 'Browser health only. Cookies, tokens, profile secrets, and session references remain outside PostgreSQL.';

commit;
