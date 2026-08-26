begin;

-- The only browser-readable data layer. These are small precomputed tables so
-- mutable aggregates are protected by RLS rather than owner-rights views.
create table public.dashboard_overview (
  snapshot_key text primary key,
  schema_version text not null default '1.0.0',
  mode text not null,
  generated_at timestamptz not null,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  verified_sources integer not null default 0,
  coverage_days integer not null default 0,
  tracked_sets integer not null default 0,
  tracked_regions integer not null default 0,
  tracked_retailers integer not null default 0,
  batch_sightings bigint not null default 0,
  australia_coverage text not null,
  baseline_hit_rate numeric(12,10),
  accepted_count bigint not null default 0,
  activity_only_count bigint not null default 0,
  rejected_count bigint not null default 0,
  methodology_version text not null,
  is_demo boolean not null default false,
  constraint dashboard_overview_key_check check (snapshot_key ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
  constraint dashboard_overview_schema_check check (schema_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  constraint dashboard_overview_mode_check check (
    (mode = 'demo' and is_demo)
    or (mode = 'live' and not is_demo)
    or mode = 'unavailable'
  ),
  constraint dashboard_overview_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and verified_sources >= 0 and verified_sources <= complete_openings
    and coverage_days between 0 and 36600
    and tracked_sets >= 0 and tracked_regions >= 0 and tracked_retailers >= 0 and batch_sightings >= 0
    and accepted_count >= 0 and activity_only_count >= 0 and rejected_count >= 0
  ),
  constraint dashboard_overview_coverage_check check (btrim(australia_coverage) <> '' and char_length(australia_coverage) <= 300),
  constraint dashboard_overview_rate_check check (
    baseline_hit_rate is null
    or (observed_packs >= 30 and verified_sources >= 3 and baseline_hit_rate between 0 and 1)
  ),
  constraint dashboard_overview_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create index dashboard_overview_generated_idx on public.dashboard_overview (generated_at desc, snapshot_key);

create table public.set_summaries (
  set_id uuid primary key,
  slug text not null unique,
  name text not null,
  series_name text not null,
  release_date date not null,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  baseline_rate numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  delta_from_baseline numeric(12,10),
  signal_status text not null,
  methodology_version text not null,
  updated_at timestamptz not null,
  is_demo boolean not null default false,
  constraint set_summaries_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and char_length(slug) <= 128),
  constraint set_summaries_text_check check (btrim(name) <> '' and char_length(name) <= 160 and btrim(series_name) <> '' and char_length(series_name) <= 160),
  constraint set_summaries_counts_check check (observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs and independent_source_count >= 0 and independent_source_count <= complete_openings),
  constraint set_summaries_metric_check check (
    credible_level = 0.900 and (
      (observed_rate is null and posterior_mean is null and baseline_rate is null and credible_interval_low is null and credible_interval_high is null
        and delta_from_baseline is null and signal_status = 'Insufficient sample')
      or (observed_rate between 0 and 1 and posterior_mean between 0 and 1 and baseline_rate between 0 and 1
        and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
        and delta_from_baseline between -1 and 1
        and abs(delta_from_baseline - (observed_rate - baseline_rate)) <= 0.0000000002
        and signal_status <> 'Insufficient sample')
    )
  ),
  constraint set_summaries_status_check check (signal_status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint set_summaries_signal_eligibility_check check (
    (signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))
    or (signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)
    or (signal_status in ('Watch', 'Possible anomaly') and observed_packs >= 200 and independent_source_count >= 3)
  ),
  constraint set_summaries_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create index set_summaries_page_idx on public.set_summaries (updated_at desc, set_id);

create table public.region_summaries (
  region_id uuid primary key,
  slug text not null unique,
  name text not null,
  country_code text not null,
  coverage text not null,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  baseline_rate numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  delta_from_baseline numeric(12,10),
  signal_status text not null,
  methodology_version text not null,
  updated_at timestamptz not null,
  is_demo boolean not null default false,
  constraint region_summaries_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and char_length(slug) <= 128),
  constraint region_summaries_text_check check (btrim(name) <> '' and char_length(name) <= 160 and btrim(coverage) <> '' and char_length(coverage) <= 240),
  constraint region_summaries_country_check check (country_code = 'AU'),
  constraint region_summaries_counts_check check (observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs and independent_source_count >= 0 and independent_source_count <= complete_openings),
  constraint region_summaries_metric_check check (
    credible_level = 0.900 and (
      (observed_rate is null and posterior_mean is null and baseline_rate is null and credible_interval_low is null and credible_interval_high is null
        and delta_from_baseline is null and signal_status = 'Insufficient sample')
      or (observed_rate between 0 and 1 and posterior_mean between 0 and 1 and baseline_rate between 0 and 1
        and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
        and delta_from_baseline between -1 and 1
        and abs(delta_from_baseline - (observed_rate - baseline_rate)) <= 0.0000000002
        and signal_status <> 'Insufficient sample')
    )
  ),
  constraint region_summaries_status_check check (signal_status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint region_summaries_signal_eligibility_check check (
    (signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))
    or (signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)
    or (signal_status in ('Watch', 'Possible anomaly') and observed_packs >= 200 and independent_source_count >= 3)
  ),
  constraint region_summaries_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create index region_summaries_page_idx on public.region_summaries (updated_at desc, region_id);

create table public.retailer_summaries (
  id uuid primary key,
  retailer_id uuid not null,
  region_id uuid not null,
  slug text not null unique,
  name text not null,
  region_name text not null,
  country_code text not null,
  channel text not null,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  baseline_rate numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  delta_from_baseline numeric(12,10),
  signal_status text not null,
  methodology_version text not null,
  updated_at timestamptz not null,
  is_demo boolean not null default false,
  constraint retailer_summaries_slug_check check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and char_length(slug) <= 128),
  constraint retailer_summaries_text_check check (btrim(name) <> '' and char_length(name) <= 160 and btrim(region_name) <> '' and char_length(region_name) <= 160),
  constraint retailer_summaries_country_check check (country_code = 'AU'),
  constraint retailer_summaries_channel_check check (channel in ('specialty', 'mass_market', 'online', 'unknown')),
  constraint retailer_summaries_counts_check check (observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs and independent_source_count >= 0 and independent_source_count <= complete_openings),
  constraint retailer_summaries_metric_check check (
    credible_level = 0.900 and (
      (observed_rate is null and posterior_mean is null and baseline_rate is null and credible_interval_low is null and credible_interval_high is null
        and delta_from_baseline is null and signal_status = 'Insufficient sample')
      or (observed_rate between 0 and 1 and posterior_mean between 0 and 1 and baseline_rate between 0 and 1
        and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
        and delta_from_baseline between -1 and 1
        and abs(delta_from_baseline - (observed_rate - baseline_rate)) <= 0.0000000002
        and signal_status <> 'Insufficient sample')
    )
  ),
  constraint retailer_summaries_status_check check (signal_status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint retailer_summaries_signal_eligibility_check check (
    (signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))
    or (signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)
    or (signal_status in ('Watch', 'Possible anomaly') and observed_packs >= 200 and independent_source_count >= 3)
  ),
  constraint retailer_summaries_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120),
  constraint retailer_summaries_identity_unique unique (retailer_id, region_id)
);
create index retailer_summaries_page_idx on public.retailer_summaries (updated_at desc, id);

create table public.batch_summaries (
  id uuid primary key,
  batch_code text not null,
  set_id uuid not null,
  set_slug text not null,
  set_name text not null,
  product_type text not null,
  region_id uuid not null,
  region_name text not null,
  first_observed_at timestamptz not null,
  last_observed_at timestamptz not null,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  baseline_rate numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  delta_from_baseline numeric(12,10),
  signal_status text not null,
  methodology_version text not null,
  updated_at timestamptz not null,
  is_demo boolean not null default false,
  constraint batch_summaries_code_check check (btrim(batch_code) <> '' and char_length(batch_code) <= 128),
  constraint batch_summaries_set_slug_check check (set_slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' and char_length(set_slug) <= 128),
  constraint batch_summaries_product_type_check check (product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint batch_summaries_text_check check (btrim(set_name) <> '' and char_length(set_name) <= 160 and btrim(region_name) <> '' and char_length(region_name) <= 160),
  constraint batch_summaries_time_check check (first_observed_at <= last_observed_at and last_observed_at <= updated_at),
  constraint batch_summaries_counts_check check (observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs and independent_source_count >= 0 and independent_source_count <= complete_openings),
  constraint batch_summaries_metric_check check (
    credible_level = 0.900 and (
      (observed_rate is null and posterior_mean is null and baseline_rate is null and credible_interval_low is null and credible_interval_high is null
        and delta_from_baseline is null and signal_status = 'Insufficient sample')
      or (observed_rate between 0 and 1 and posterior_mean between 0 and 1 and baseline_rate between 0 and 1
        and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
        and delta_from_baseline between -1 and 1
        and abs(delta_from_baseline - (observed_rate - baseline_rate)) <= 0.0000000002
        and signal_status <> 'Insufficient sample')
    )
  ),
  constraint batch_summaries_status_check check (signal_status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint batch_summaries_signal_eligibility_check check (
    (signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))
    or (signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)
    or (signal_status in ('Watch', 'Possible anomaly') and observed_packs >= 200 and independent_source_count >= 3)
  ),
  constraint batch_summaries_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120),
  constraint batch_summaries_identity_unique unique (batch_code, set_id, region_id)
);
create index batch_summaries_page_idx on public.batch_summaries (last_observed_at desc, id);

create table public.recent_activity (
  id uuid primary key,
  activity_kind text not null,
  subject_kind text not null,
  subject_id text not null,
  subject_label text not null,
  set_name text not null,
  retailer_name text not null,
  occurred_at timestamptz not null,
  observed_at timestamptz not null,
  pack_count integer,
  product_type text,
  evidence_tier text not null,
  status text not null,
  statistics_eligible boolean not null default false,
  country_code text not null,
  region_name text,
  platform text,
  source_kind text not null,
  source_title text,
  source_published_at timestamptz,
  source_link text,
  entities jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  constraint recent_activity_kind_check check (activity_kind in ('opening', 'sighting', 'batch_mention')),
  constraint recent_activity_subject_kind_check check (subject_kind in ('set', 'product', 'region', 'retailer', 'batch')),
  constraint recent_activity_subject_check check (btrim(subject_id) <> '' and char_length(subject_id) <= 128 and btrim(subject_label) <> '' and char_length(subject_label) <= 160),
  constraint recent_activity_names_check check (btrim(set_name) <> '' and char_length(set_name) <= 160 and btrim(retailer_name) <> '' and char_length(retailer_name) <= 160),
  constraint recent_activity_time_check check (occurred_at <= observed_at and (source_published_at is null or source_published_at <= observed_at)),
  constraint recent_activity_pack_check check (pack_count is null or pack_count between 1 and 100000),
  constraint recent_activity_opening_check check (activity_kind <> 'opening' or pack_count is not null),
  constraint recent_activity_product_type_check check (product_type is null or product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint recent_activity_evidence_tier_check check (evidence_tier in ('A', 'B', 'C', 'D')),
  constraint recent_activity_status_check check (status in ('accepted', 'activity_only')),
  constraint recent_activity_statistics_check check (
    not statistics_eligible or (activity_kind = 'opening' and status = 'accepted'
      and evidence_tier in ('A', 'B') and pack_count is not null)
  ),
  constraint recent_activity_country_check check (country_code = 'AU'),
  constraint recent_activity_region_check check (region_name is null or (btrim(region_name) <> '' and char_length(region_name) <= 160)),
  constraint recent_activity_platform_check check (platform is null or (btrim(platform) <> '' and char_length(platform) <= 80)),
  constraint recent_activity_source_kind_check check (source_kind in ('official_api', 'public_web', 'authenticated_social', 'fixture', 'manual_import')),
  constraint recent_activity_title_check check (source_title is null or char_length(source_title) <= 200),
  constraint recent_activity_link_check check (source_link is null or (source_link ~ '^https://' and char_length(source_link) <= 2048)),
  constraint recent_activity_entities_check check (
    jsonb_typeof(entities) = 'object' and octet_length(entities::text) <= 2000
    and entities - array['set', 'product', 'region', 'retailer', 'batch', 'rarities']::text[] = '{}'::jsonb
  )
);
create index recent_activity_page_idx on public.recent_activity (occurred_at desc, id);
create index recent_activity_subject_idx on public.recent_activity (subject_kind, subject_id, occurred_at desc);

create table public.public_signals (
  id uuid primary key,
  entity_type text not null,
  entity_key text not null,
  entity_label text not null,
  set_id uuid,
  metric text not null,
  status text not null,
  sample_size bigint not null,
  complete_openings bigint not null,
  independent_source_count integer not null,
  baseline numeric(12,10),
  observed numeric(12,10),
  posterior_mean numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  probability_above_baseline numeric(12,10),
  probability_above_practical_uplift numeric(12,10),
  baseline_scope text not null,
  evidence_tier text not null,
  window_start date not null,
  window_end date not null,
  methodology_version text not null,
  as_of timestamptz not null,
  is_demo boolean not null default false,
  constraint public_signals_entity_type_check check (entity_type in ('global', 'set', 'product', 'region', 'retailer', 'batch')),
  constraint public_signals_entity_check check (btrim(entity_key) <> '' and char_length(entity_key) <= 128 and btrim(entity_label) <> '' and char_length(entity_label) <= 160),
  constraint public_signals_metric_check check (metric in ('hit_rate', 'rarity_rate')),
  constraint public_signals_status_check check (status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint public_signals_signal_eligibility_check check (
    (status = 'Insufficient sample' and (sample_size < 30 or independent_source_count < 3))
    or (status = 'No significant signal' and sample_size >= 30 and independent_source_count >= 3)
    or (status = 'Watch' and sample_size >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.900)
    or (status = 'Possible anomaly' and sample_size >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.950)
  ),
  constraint public_signals_counts_check check (sample_size > 0 and complete_openings > 0 and complete_openings <= sample_size and independent_source_count > 0 and independent_source_count <= complete_openings),
  constraint public_signals_interval_check check (
    credible_level = 0.900 and (
      (status = 'Insufficient sample' and baseline is null and observed is null and posterior_mean is null
        and credible_interval_low is null and credible_interval_high is null
        and probability_above_baseline is null and probability_above_practical_uplift is null)
      or (status <> 'Insufficient sample' and baseline between 0 and 1 and observed between 0 and 1
        and posterior_mean between 0 and 1 and credible_interval_low between 0 and posterior_mean
        and credible_interval_high between posterior_mean and 1 and probability_above_baseline between 0 and 1
        and probability_above_practical_uplift between 0 and 1)
    )
  ),
  constraint public_signals_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint public_signals_evidence_check check (evidence_tier in ('A', 'B')),
  constraint public_signals_window_check check (window_start <= window_end and window_end <= as_of::date),
  constraint public_signals_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create index public_signals_page_idx on public.public_signals (as_of desc, id);
create index public_signals_entity_idx on public.public_signals (entity_type, entity_key, as_of desc);

create table public.data_freshness (
  component_id text primary key,
  component_name text not null,
  status text not null,
  as_of timestamptz not null,
  last_successful_collection_at timestamptz,
  age_seconds integer,
  next_expected_at timestamptz,
  is_demo boolean not null default false,
  constraint data_freshness_component_check check (component_id ~ '^[a-z0-9][a-z0-9._-]{0,79}$' and btrim(component_name) <> '' and char_length(component_name) <= 120),
  constraint data_freshness_status_check check (status in ('fresh', 'delayed', 'stale', 'unavailable')),
  constraint data_freshness_age_check check (
    (status = 'unavailable' and last_successful_collection_at is null and age_seconds is null and next_expected_at is null)
    or (status <> 'unavailable' and last_successful_collection_at is not null and last_successful_collection_at <= as_of
      and age_seconds is not null and age_seconds between 0 and 31536000
      and (next_expected_at is null or next_expected_at >= as_of))
  )
);
create index data_freshness_status_idx on public.data_freshness (status, as_of desc);

create table public.system_status (
  component_id text primary key,
  component_name text not null,
  status text not null,
  checked_at timestamptz not null,
  public_message text,
  auth_required boolean not null default false,
  is_demo boolean not null default false,
  constraint system_status_component_check check (component_id ~ '^[a-z0-9][a-z0-9._-]{0,79}$' and btrim(component_name) <> '' and char_length(component_name) <= 120),
  constraint system_status_status_check check (status in ('operational', 'degraded', 'maintenance', 'unavailable')),
  constraint system_status_message_check check (public_message is null or char_length(public_message) <= 240)
);
create index system_status_checked_idx on public.system_status (checked_at desc, component_id);

alter table public.dashboard_overview enable row level security;
alter table public.set_summaries enable row level security;
alter table public.region_summaries enable row level security;
alter table public.retailer_summaries enable row level security;
alter table public.batch_summaries enable row level security;
alter table public.recent_activity enable row level security;
alter table public.public_signals enable row level security;
alter table public.data_freshness enable row level security;
alter table public.system_status enable row level security;
alter table public.dashboard_overview force row level security;
alter table public.set_summaries force row level security;
alter table public.region_summaries force row level security;
alter table public.retailer_summaries force row level security;
alter table public.batch_summaries force row level security;
alter table public.recent_activity force row level security;
alter table public.public_signals force row level security;
alter table public.data_freshness force row level security;
alter table public.system_status force row level security;

create policy dashboard_overview_public_read on public.dashboard_overview for select to anon, authenticated using (true);
create policy set_summaries_public_read on public.set_summaries for select to anon, authenticated using (true);
create policy region_summaries_public_read on public.region_summaries for select to anon, authenticated using (true);
create policy retailer_summaries_public_read on public.retailer_summaries for select to anon, authenticated using (true);
create policy batch_summaries_public_read on public.batch_summaries for select to anon, authenticated using (true);
create policy recent_activity_public_read on public.recent_activity for select to anon, authenticated using (true);
create policy public_signals_public_read on public.public_signals for select to anon, authenticated using (true);
create policy data_freshness_public_read on public.data_freshness for select to anon, authenticated using (true);
create policy system_status_public_read on public.system_status for select to anon, authenticated using (true);
create policy dashboard_overview_service_all on public.dashboard_overview for all to service_role using (true) with check (true);
create policy set_summaries_service_all on public.set_summaries for all to service_role using (true) with check (true);
create policy region_summaries_service_all on public.region_summaries for all to service_role using (true) with check (true);
create policy retailer_summaries_service_all on public.retailer_summaries for all to service_role using (true) with check (true);
create policy batch_summaries_service_all on public.batch_summaries for all to service_role using (true) with check (true);
create policy recent_activity_service_all on public.recent_activity for all to service_role using (true) with check (true);
create policy public_signals_service_all on public.public_signals for all to service_role using (true) with check (true);
create policy data_freshness_service_all on public.data_freshness for all to service_role using (true) with check (true);
create policy system_status_service_all on public.system_status for all to service_role using (true) with check (true);

revoke all on public.dashboard_overview, public.set_summaries, public.region_summaries,
  public.retailer_summaries, public.batch_summaries, public.recent_activity,
  public.public_signals, public.data_freshness, public.system_status
  from public, anon, authenticated;
grant select on public.dashboard_overview, public.set_summaries, public.region_summaries,
  public.retailer_summaries, public.batch_summaries, public.recent_activity,
  public.public_signals, public.data_freshness, public.system_status
  to anon, authenticated;
grant select, insert, update, delete on public.dashboard_overview, public.set_summaries,
  public.region_summaries, public.retailer_summaries, public.batch_summaries,
  public.recent_activity, public.public_signals, public.data_freshness, public.system_status
  to service_role;

comment on table public.recent_activity is 'Bounded browser-safe activity: short source descriptors/link, evidence tier, and allowlisted structured entities only.';
comment on table public.public_signals is 'Exploratory aggregate labels only; no raw evidence, AI output, authors, sessions, errors, or causal claims.';
comment on column public.system_status.auth_required is 'Safe boolean indicating that an authenticated collector needs owner action; no profile/session detail is exposed.';

commit;
