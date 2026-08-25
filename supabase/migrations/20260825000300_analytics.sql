begin;

-- Private reproducible aggregates. These canonical columns are the worker/publication
-- contract; browser clients only read bounded copies in the public schema.
create table analytics.dashboard_daily (
  date date not null,
  country_code text not null,
  language text not null default 'en',
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  accepted_sources integer not null default 0,
  activity_only_sources integer not null default 0,
  rejected_sources integer not null default 0,
  tracked_sets integer not null default 0,
  tracked_regions integer not null default 0,
  tracked_retailers integer not null default 0,
  batch_sightings bigint not null default 0,
  data_quality_score numeric(5,4) not null default 0,
  accepted_count bigint not null default 0,
  activity_only_count bigint not null default 0,
  rejected_count bigint not null default 0,
  hit_count bigint not null default 0,
  observed_hit_rate numeric(12,10),
  posterior_mean numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  baseline numeric(12,10),
  delta_from_baseline numeric(12,10),
  baseline_scope text not null,
  window_start date not null,
  window_end date not null,
  catalog_version text not null,
  build_sha text not null,
  computed_at timestamptz not null default now(),
  methodology_version text not null,
  is_demo boolean not null default false,
  primary key (date, country_code, language, is_demo),
  constraint dashboard_daily_country_check check (country_code ~ '^[A-Z]{2}$'),
  constraint dashboard_daily_language_check check (language = 'en'),
  constraint dashboard_daily_window_check check (window_start <= window_end and window_end <= date),
  constraint dashboard_daily_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and accepted_sources >= 0 and accepted_sources <= complete_openings
    and activity_only_sources >= 0 and rejected_sources >= 0
    and tracked_sets >= 0 and tracked_regions >= 0 and tracked_retailers >= 0 and batch_sightings >= 0
    and accepted_count >= 0 and activity_only_count >= 0 and rejected_count >= 0 and hit_count >= 0
  ),
  constraint dashboard_daily_quality_check check (data_quality_score between 0 and 1),
  constraint dashboard_daily_rate_check check (
    credible_level = 0.900
    and (observed_hit_rate is null or observed_hit_rate between 0 and 1)
    and (baseline is null or baseline between 0 and 1)
    and ((posterior_mean is null and credible_interval_low is null and credible_interval_high is null)
      or (posterior_mean between 0 and 1 and credible_interval_low between 0 and posterior_mean
          and credible_interval_high between posterior_mean and 1))
    and ((delta_from_baseline is null and (posterior_mean is null or baseline is null))
      or (delta_from_baseline between -1 and 1 and posterior_mean is not null and baseline is not null))
  ),
  constraint dashboard_daily_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint dashboard_daily_catalog_version_check check (btrim(catalog_version) <> '' and char_length(catalog_version) <= 120),
  constraint dashboard_daily_build_sha_check check (build_sha ~ '^[0-9a-f]{7,64}$'),
  constraint dashboard_daily_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create index dashboard_daily_latest_idx on analytics.dashboard_daily (date desc, computed_at desc);

create table analytics.set_metrics_daily (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  set_id uuid not null references catalog.sets(id) on update cascade on delete restrict,
  product_type text,
  language text not null default 'en',
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  rarity_counts jsonb not null default '{}'::jsonb,
  observed_rates jsonb not null default '{}'::jsonb,
  baseline_rates jsonb not null default '{}'::jsonb,
  credible_intervals jsonb not null default '{}'::jsonb,
  sample_quality_score numeric(5,4) not null default 0,
  accepted_count bigint not null default 0,
  activity_only_count bigint not null default 0,
  rejected_count bigint not null default 0,
  baseline_scope text not null,
  window_start date not null,
  window_end date not null,
  catalog_version text not null,
  computed_at timestamptz not null default now(),
  methodology_version text not null,
  is_demo boolean not null default false,
  constraint set_metrics_daily_language_check check (language = 'en'),
  constraint set_metrics_daily_product_type_check check (product_type is null or product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint set_metrics_daily_window_check check (window_start <= window_end and window_end <= date),
  constraint set_metrics_daily_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and independent_source_count >= 0 and independent_source_count <= complete_openings and accepted_count >= 0 and activity_only_count >= 0 and rejected_count >= 0
  ),
  constraint set_metrics_daily_json_check check (
    jsonb_typeof(rarity_counts) = 'object' and jsonb_typeof(observed_rates) = 'object'
    and jsonb_typeof(baseline_rates) = 'object' and jsonb_typeof(credible_intervals) = 'object'
    and octet_length(rarity_counts::text) <= 20000 and octet_length(observed_rates::text) <= 20000
    and octet_length(baseline_rates::text) <= 20000 and octet_length(credible_intervals::text) <= 40000
  ),
  constraint set_metrics_daily_quality_check check (sample_quality_score between 0 and 1),
  constraint set_metrics_daily_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint set_metrics_daily_catalog_version_check check (btrim(catalog_version) <> '' and char_length(catalog_version) <= 120),
  constraint set_metrics_daily_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create unique index set_metrics_daily_identity_uidx on analytics.set_metrics_daily (date, set_id, product_type, language, is_demo) nulls not distinct;
create index set_metrics_daily_lookup_idx on analytics.set_metrics_daily (set_id, date desc);

create table analytics.region_metrics_daily (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  region_id uuid not null references catalog.regions(id) on update cascade on delete restrict,
  set_id uuid references catalog.sets(id) on update cascade on delete restrict,
  product_id uuid references catalog.products(id) on update cascade on delete restrict,
  product_type text,
  language text not null default 'en',
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  rarity_counts jsonb not null default '{}'::jsonb,
  observed_rates jsonb not null default '{}'::jsonb,
  baseline_rates jsonb not null default '{}'::jsonb,
  credible_intervals jsonb not null default '{}'::jsonb,
  sample_quality_score numeric(5,4) not null default 0,
  accepted_count bigint not null default 0,
  activity_only_count bigint not null default 0,
  rejected_count bigint not null default 0,
  baseline_scope text not null,
  window_start date not null,
  window_end date not null,
  catalog_version text not null,
  computed_at timestamptz not null default now(),
  methodology_version text not null,
  is_demo boolean not null default false,
  constraint region_metrics_daily_language_check check (language = 'en'),
  constraint region_metrics_daily_product_type_check check (product_type is null or product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint region_metrics_daily_window_check check (window_start <= window_end and window_end <= date),
  constraint region_metrics_daily_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and independent_source_count >= 0 and independent_source_count <= complete_openings and accepted_count >= 0 and activity_only_count >= 0 and rejected_count >= 0
  ),
  constraint region_metrics_daily_json_check check (
    jsonb_typeof(rarity_counts) = 'object' and jsonb_typeof(observed_rates) = 'object'
    and jsonb_typeof(baseline_rates) = 'object' and jsonb_typeof(credible_intervals) = 'object'
    and octet_length(rarity_counts::text) <= 20000 and octet_length(observed_rates::text) <= 20000
    and octet_length(baseline_rates::text) <= 20000 and octet_length(credible_intervals::text) <= 40000
  ),
  constraint region_metrics_daily_quality_check check (sample_quality_score between 0 and 1),
  constraint region_metrics_daily_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint region_metrics_daily_catalog_version_check check (btrim(catalog_version) <> '' and char_length(catalog_version) <= 120),
  constraint region_metrics_daily_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create unique index region_metrics_daily_identity_uidx on analytics.region_metrics_daily (date, region_id, set_id, product_id, product_type, language, is_demo) nulls not distinct;
create index region_metrics_daily_lookup_idx on analytics.region_metrics_daily (region_id, set_id, date desc);

create table analytics.retailer_metrics_daily (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  retailer_id uuid not null references catalog.retailers(id) on update cascade on delete restrict,
  region_id uuid references catalog.regions(id) on update cascade on delete restrict,
  set_id uuid references catalog.sets(id) on update cascade on delete restrict,
  product_id uuid references catalog.products(id) on update cascade on delete restrict,
  product_type text,
  language text not null default 'en',
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  rarity_counts jsonb not null default '{}'::jsonb,
  observed_rates jsonb not null default '{}'::jsonb,
  baseline_rates jsonb not null default '{}'::jsonb,
  credible_intervals jsonb not null default '{}'::jsonb,
  sample_quality_score numeric(5,4) not null default 0,
  accepted_count bigint not null default 0,
  activity_only_count bigint not null default 0,
  rejected_count bigint not null default 0,
  baseline_scope text not null,
  window_start date not null,
  window_end date not null,
  catalog_version text not null,
  computed_at timestamptz not null default now(),
  methodology_version text not null,
  is_demo boolean not null default false,
  constraint retailer_metrics_daily_language_check check (language = 'en'),
  constraint retailer_metrics_daily_product_type_check check (product_type is null or product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint retailer_metrics_daily_window_check check (window_start <= window_end and window_end <= date),
  constraint retailer_metrics_daily_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and independent_source_count >= 0 and independent_source_count <= complete_openings and accepted_count >= 0 and activity_only_count >= 0 and rejected_count >= 0
  ),
  constraint retailer_metrics_daily_json_check check (
    jsonb_typeof(rarity_counts) = 'object' and jsonb_typeof(observed_rates) = 'object'
    and jsonb_typeof(baseline_rates) = 'object' and jsonb_typeof(credible_intervals) = 'object'
    and octet_length(rarity_counts::text) <= 20000 and octet_length(observed_rates::text) <= 20000
    and octet_length(baseline_rates::text) <= 20000 and octet_length(credible_intervals::text) <= 40000
  ),
  constraint retailer_metrics_daily_quality_check check (sample_quality_score between 0 and 1),
  constraint retailer_metrics_daily_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint retailer_metrics_daily_catalog_version_check check (btrim(catalog_version) <> '' and char_length(catalog_version) <= 120),
  constraint retailer_metrics_daily_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create unique index retailer_metrics_daily_identity_uidx on analytics.retailer_metrics_daily (date, retailer_id, region_id, set_id, product_id, product_type, language, is_demo) nulls not distinct;
create index retailer_metrics_daily_lookup_idx on analytics.retailer_metrics_daily (retailer_id, set_id, date desc);

create table analytics.batch_metrics_daily (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  batch_code text not null,
  normalized_batch_code text not null,
  set_id uuid not null references catalog.sets(id) on update cascade on delete restrict,
  product_id uuid references catalog.products(id) on update cascade on delete restrict,
  observed_packs bigint not null default 0,
  complete_openings bigint not null default 0,
  independent_source_count integer not null default 0,
  region_count integer not null default 0,
  retailer_count integer not null default 0,
  first_seen timestamptz not null,
  last_seen timestamptz not null,
  posterior_mean numeric(12,10) not null,
  credible_interval_low numeric(12,10) not null,
  credible_interval_high numeric(12,10) not null,
  credible_level numeric(4,3) not null default 0.900,
  baseline numeric(12,10) not null,
  baseline_scope text not null,
  probability_above_baseline numeric(12,10) not null,
  probability_above_practical_uplift numeric(12,10) not null,
  signal_status text not null,
  computed_at timestamptz not null default now(),
  methodology_version text not null,
  is_demo boolean not null default false,
  constraint batch_metrics_daily_code_check check (btrim(batch_code) <> '' and char_length(batch_code) <= 128),
  constraint batch_metrics_daily_normalized_check check (normalized_batch_code ~ '^[A-Z0-9][A-Z0-9_-]{0,127}$'),
  constraint batch_metrics_daily_counts_check check (
    observed_packs >= 0 and complete_openings >= 0 and complete_openings <= observed_packs
    and independent_source_count >= 0 and independent_source_count <= complete_openings and region_count >= 0 and retailer_count >= 0
  ),
  constraint batch_metrics_daily_seen_check check (first_seen <= last_seen and last_seen::date <= date),
  constraint batch_metrics_daily_interval_check check (
    credible_level = 0.900 and baseline between 0 and 1 and posterior_mean between 0 and 1
    and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
    and probability_above_baseline between 0 and 1 and probability_above_practical_uplift between 0 and 1
  ),
  constraint batch_metrics_daily_signal_status_check check (signal_status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint batch_metrics_daily_signal_eligibility_check check (
    (signal_status = 'Insufficient sample' and (observed_packs < 30 or independent_source_count < 3))
    or (signal_status = 'No significant signal' and observed_packs >= 30 and independent_source_count >= 3)
    or (signal_status = 'Watch' and observed_packs >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.900)
    or (signal_status = 'Possible anomaly' and observed_packs >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.950)
  ),
  constraint batch_metrics_daily_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint batch_metrics_daily_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120)
);
create unique index batch_metrics_daily_identity_uidx on analytics.batch_metrics_daily (date, normalized_batch_code, set_id, product_id, is_demo) nulls not distinct;
create index batch_metrics_daily_lookup_idx on analytics.batch_metrics_daily (batch_code, date desc);
create index batch_metrics_daily_set_idx on analytics.batch_metrics_daily (set_id, date desc);

create table analytics.signals (
  id uuid primary key default gen_random_uuid(),
  signal_type text not null,
  entity_type text not null,
  entity_key text not null,
  set_id uuid references catalog.sets(id) on update cascade on delete restrict,
  metric text not null,
  status text not null,
  sample_size bigint not null,
  independent_source_count integer not null,
  baseline numeric(12,10),
  observed numeric(12,10),
  posterior_mean numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  credible_level numeric(4,3) not null default 0.900,
  probability_above_baseline numeric(12,10),
  probability_above_practical_uplift numeric(12,10),
  explanation jsonb not null,
  baseline_scope text not null,
  evidence_tier text not null,
  methodology_version text not null,
  first_detected_at timestamptz not null,
  last_updated_at timestamptz not null,
  expires_at timestamptz not null,
  is_public boolean not null default false,
  is_demo boolean not null default false,
  constraint signals_type_check check (signal_type ~ '^[a-z][a-z0-9_]{0,79}$'),
  constraint signals_entity_type_check check (entity_type in ('global', 'set', 'product', 'region', 'retailer', 'batch')),
  constraint signals_entity_key_check check (btrim(entity_key) <> '' and char_length(entity_key) <= 160),
  constraint signals_metric_check check (metric in ('hit_rate', 'rarity_rate')),
  constraint signals_status_check check (status in ('Insufficient sample', 'No significant signal', 'Watch', 'Possible anomaly')),
  constraint signals_signal_eligibility_check check (
    (status = 'Insufficient sample' and (sample_size < 30 or independent_source_count < 3))
    or (status = 'No significant signal' and sample_size >= 30 and independent_source_count >= 3)
    or (status = 'Watch' and sample_size >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.900)
    or (status = 'Possible anomaly' and sample_size >= 200 and independent_source_count >= 3
      and probability_above_practical_uplift >= 0.950)
  ),
  constraint signals_sample_check check (sample_size >= 0 and independent_source_count >= 0 and (not is_public or (sample_size > 0 and independent_source_count > 0))),
  constraint signals_interval_check check (
    credible_level = 0.900 and (
      (status = 'Insufficient sample'
        and baseline is null and observed is null and posterior_mean is null
        and credible_interval_low is null and credible_interval_high is null
        and probability_above_baseline is null and probability_above_practical_uplift is null)
      or
      (status <> 'Insufficient sample'
        and baseline between 0 and 1 and observed between 0 and 1 and posterior_mean between 0 and 1
        and credible_interval_low between 0 and posterior_mean and credible_interval_high between posterior_mean and 1
        and probability_above_baseline between 0 and 1 and probability_above_practical_uplift between 0 and 1)
    )
  ),
  constraint signals_explanation_check check (jsonb_typeof(explanation) = 'object' and octet_length(explanation::text) <= 4000),
  constraint signals_baseline_scope_check check (btrim(baseline_scope) <> '' and char_length(baseline_scope) <= 240),
  constraint signals_evidence_tier_check check (evidence_tier in ('A', 'B')),
  constraint signals_methodology_check check (btrim(methodology_version) <> '' and char_length(methodology_version) <= 120),
  constraint signals_lifecycle_check check (first_detected_at <= last_updated_at and expires_at > last_updated_at)
);
create unique index signals_identity_uidx on analytics.signals (signal_type, entity_type, entity_key, set_id, metric, methodology_version, is_demo) nulls not distinct;
create index signals_public_latest_idx on analytics.signals (is_public, last_updated_at desc);
create index signals_entity_latest_idx on analytics.signals (entity_type, entity_key, last_updated_at desc);
create index signals_expiry_idx on analytics.signals (expires_at);

alter table analytics.dashboard_daily enable row level security;
alter table analytics.set_metrics_daily enable row level security;
alter table analytics.region_metrics_daily enable row level security;
alter table analytics.retailer_metrics_daily enable row level security;
alter table analytics.batch_metrics_daily enable row level security;
alter table analytics.signals enable row level security;
alter table analytics.dashboard_daily force row level security;
alter table analytics.set_metrics_daily force row level security;
alter table analytics.region_metrics_daily force row level security;
alter table analytics.retailer_metrics_daily force row level security;
alter table analytics.batch_metrics_daily force row level security;
alter table analytics.signals force row level security;

create policy dashboard_daily_service_role_all on analytics.dashboard_daily for all to service_role using (true) with check (true);
create policy set_metrics_daily_service_role_all on analytics.set_metrics_daily for all to service_role using (true) with check (true);
create policy region_metrics_daily_service_role_all on analytics.region_metrics_daily for all to service_role using (true) with check (true);
create policy retailer_metrics_daily_service_role_all on analytics.retailer_metrics_daily for all to service_role using (true) with check (true);
create policy batch_metrics_daily_service_role_all on analytics.batch_metrics_daily for all to service_role using (true) with check (true);
create policy signals_service_role_all on analytics.signals for all to service_role using (true) with check (true);

revoke all on all tables in schema analytics from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema analytics to service_role;

comment on table analytics.dashboard_daily is 'Private AU/locale-scoped daily observational KPIs. Complete openings supply denominators; activity-only and rejected source counts remain separate.';
comment on column analytics.set_metrics_daily.baseline_scope is 'Versioned baseline dimensions used by observed_rates/baseline_rates/credible_intervals.';
comment on table analytics.signals is 'Exploratory non-causal aggregate signals with bounded explanation and expiry; never a prediction or guarantee.';

commit;
