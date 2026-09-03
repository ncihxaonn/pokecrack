-- RED-first analytics contract. Run from a clean `supabase db reset`.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(54);

select has_table('analytics', 'dashboard_daily', 'analytics.dashboard_daily exists');
select has_table('analytics', 'set_metrics_daily', 'analytics.set_metrics_daily exists');
select has_table('analytics', 'region_metrics_daily', 'analytics.region_metrics_daily exists');
select has_table('analytics', 'retailer_metrics_daily', 'analytics.retailer_metrics_daily exists');
select has_table('analytics', 'batch_metrics_daily', 'analytics.batch_metrics_daily exists');
select has_table('analytics', 'signals', 'analytics.signals exists');

select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'dashboard_daily'$$,
  $$values
    ('date'::text), ('observed_packs'), ('complete_openings'), ('accepted_sources'),
    ('activity_only_sources'), ('rejected_sources'), ('tracked_sets'), ('tracked_regions'),
    ('tracked_retailers'), ('batch_sightings'), ('data_quality_score'), ('computed_at'),
    ('methodology_version')$$,
  'dashboard daily includes every exact canonical KPI and provenance field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'set_metrics_daily'$$,
  $$values
    ('date'::text), ('set_id'), ('product_type'), ('language'), ('observed_packs'),
    ('complete_openings'), ('independent_source_count'), ('rarity_counts'), ('observed_rates'),
    ('baseline_rates'), ('credible_intervals'), ('sample_quality_score'), ('computed_at'),
    ('methodology_version'), ('baseline_scope')$$,
  'set metrics include every exact canonical dimension, JSON aggregate, score, and provenance field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'region_metrics_daily'$$,
  $$values
    ('date'::text), ('region_id'), ('set_id'), ('product_type'), ('language'), ('observed_packs'),
    ('complete_openings'), ('independent_source_count'), ('rarity_counts'), ('observed_rates'),
    ('baseline_rates'), ('credible_intervals'), ('sample_quality_score'), ('computed_at'),
    ('methodology_version'), ('baseline_scope')$$,
  'region metrics include exact region/set/product dimensions and equivalent aggregates'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'retailer_metrics_daily'$$,
  $$values
    ('date'::text), ('retailer_id'), ('set_id'), ('product_type'), ('language'), ('observed_packs'),
    ('complete_openings'), ('independent_source_count'), ('rarity_counts'), ('observed_rates'),
    ('baseline_rates'), ('credible_intervals'), ('sample_quality_score'), ('computed_at'),
    ('methodology_version'), ('baseline_scope')$$,
  'retailer metrics include exact retailer/set/product dimensions and equivalent aggregates'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'batch_metrics_daily'$$,
  $$values
    ('date'::text), ('batch_code'), ('set_id'), ('product_id'), ('observed_packs'),
    ('complete_openings'), ('independent_source_count'), ('region_count'), ('retailer_count'),
    ('first_seen'), ('last_seen'), ('posterior_mean'), ('credible_interval_low'),
    ('credible_interval_high'), ('probability_above_baseline'),
    ('probability_above_practical_uplift'), ('signal_status'), ('computed_at'),
    ('methodology_version')$$,
  'batch metrics include every exact canonical dimension, probability, status, and provenance field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'analytics' and table_name = 'signals'$$,
  $$values
    ('id'::text), ('signal_type'), ('entity_type'), ('entity_key'), ('set_id'), ('metric'),
    ('status'), ('sample_size'), ('independent_source_count'), ('baseline'), ('observed'),
    ('posterior_mean'), ('credible_interval_low'), ('credible_interval_high'),
    ('probability_above_baseline'), ('probability_above_practical_uplift'), ('explanation'),
    ('methodology_version'), ('first_detected_at'), ('last_updated_at'), ('expires_at')$$,
  'signals include every exact canonical identity, estimate, explanation, and lifecycle field'
);

select has_pk('analytics', 'dashboard_daily', 'dashboard daily has a composite primary key');
select has_pk('analytics', 'set_metrics_daily', 'set daily metrics have a composite primary key');
select has_pk('analytics', 'region_metrics_daily', 'region daily metrics have a composite primary key');
select has_pk('analytics', 'retailer_metrics_daily', 'retailer daily metrics have a composite primary key');
select has_pk('analytics', 'batch_metrics_daily', 'batch daily metrics have a composite primary key');
select has_pk('analytics', 'signals', 'signals have a primary key');

select has_index('analytics', 'dashboard_daily', 'dashboard_daily_latest_idx', array['date', 'computed_at'], 'dashboard latest-page lookup is indexed');
select has_index('analytics', 'set_metrics_daily', 'set_metrics_daily_lookup_idx', array['set_id', 'date'], 'set pagination/detail lookup is indexed');
select has_index('analytics', 'region_metrics_daily', 'region_metrics_daily_lookup_idx', array['region_id', 'set_id', 'date'], 'region pagination/detail lookup is indexed');
select has_index('analytics', 'retailer_metrics_daily', 'retailer_metrics_daily_lookup_idx', array['retailer_id', 'set_id', 'date'], 'retailer pagination/detail lookup is indexed');
select has_index('analytics', 'batch_metrics_daily', 'batch_metrics_daily_lookup_idx', array['batch_code', 'date'], 'batch pagination/detail lookup is indexed');
select has_index('analytics', 'signals', 'signals_public_latest_idx', array['is_public', 'last_updated_at'], 'public signal lookup is indexed');

select col_is_null('analytics', 'set_metrics_daily', 'product_type', 'set product_type is nullable for all-product aggregates');
select col_is_null('analytics', 'region_metrics_daily', 'product_type', 'region product_type is nullable for all-product aggregates');
select col_is_null('analytics', 'retailer_metrics_daily', 'product_type', 'retailer product_type is nullable for all-product aggregates');
select col_is_null('analytics', 'batch_metrics_daily', 'product_id', 'batch product_id is nullable when the product is unknown');
select col_is_null('analytics', 'region_metrics_daily', 'set_id', 'region set_id is nullable for all-set aggregates');
select col_is_null('analytics', 'retailer_metrics_daily', 'set_id', 'retailer set_id is nullable for all-set aggregates');
select col_type_is('analytics', 'signals', 'explanation', 'jsonb', 'signal explanation is structured jsonb');
select col_is_null('analytics', 'signals', 'baseline', 'insufficient signals may omit the baseline');
select col_is_null('analytics', 'signals', 'observed', 'insufficient signals may omit the observed rate');
select col_is_null('analytics', 'signals', 'posterior_mean', 'insufficient signals may omit the posterior mean');
select col_is_null('analytics', 'signals', 'credible_interval_low', 'insufficient signals may omit the lower interval');
select col_is_null('analytics', 'signals', 'credible_interval_high', 'insufficient signals may omit the upper interval');
select col_is_null('analytics', 'signals', 'probability_above_baseline', 'insufficient signals may omit baseline probability');
select col_is_null('analytics', 'signals', 'probability_above_practical_uplift', 'insufficient signals may omit uplift probability');
select col_type_is('analytics', 'set_metrics_daily', 'rarity_counts', 'jsonb', 'rarity counts use structured jsonb');
select col_type_is('analytics', 'set_metrics_daily', 'observed_rates', 'jsonb', 'observed rates use structured jsonb');
select col_type_is('analytics', 'set_metrics_daily', 'baseline_rates', 'jsonb', 'baseline rates use structured jsonb');
select col_type_is('analytics', 'set_metrics_daily', 'credible_intervals', 'jsonb', 'credible intervals use structured jsonb');

select ok(
  (select bool_and(pg_get_constraintdef(c.oid) ilike '%' || required.label || '%')
   from pg_constraint c
   cross join (values ('Insufficient sample'), ('No significant signal'), ('Watch'), ('Possible anomaly')) as required(label)
   where c.conrelid = to_regclass('analytics.signals') and c.conname = 'signals_status_check'),
  'analytics signals enforce only the four approved labels'
);
select matches(
  (select pg_get_constraintdef(c.oid) from pg_constraint c
   where c.conrelid = to_regclass('analytics.signals') and c.conname = 'signals_interval_check'),
  '0\.900',
  'signals enforce the published 90 percent credible interval'
);

select ok(
  (select bool_and(c.relrowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'analytics' and c.relkind in ('r', 'p')),
  'all analytics tables have RLS enabled'
);
select ok(
  (select bool_and(c.relforcerowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'analytics' and c.relkind in ('r', 'p')),
  'all analytics tables force RLS'
);
select ok(not has_schema_privilege('anon', 'analytics', 'usage'), 'anon cannot use analytics');
select ok(not has_schema_privilege('authenticated', 'analytics', 'usage'), 'authenticated cannot use analytics');
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'analytics' and c.relkind in ('r', 'p')
      and (has_table_privilege('anon', c.oid, 'select') or has_table_privilege('anon', c.oid, 'insert')
        or has_table_privilege('anon', c.oid, 'update') or has_table_privilege('anon', c.oid, 'delete'))
  ),
  'anon has no analytics table privileges'
);
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'analytics' and c.relkind in ('r', 'p')
      and (has_table_privilege('authenticated', c.oid, 'select') or has_table_privilege('authenticated', c.oid, 'insert')
        or has_table_privilege('authenticated', c.oid, 'update') or has_table_privilege('authenticated', c.oid, 'delete'))
  ),
  'authenticated has no analytics table privileges'
);
select ok(
  (select bool_and(
     has_table_privilege('service_role', c.oid, 'select')
     and not has_table_privilege('service_role', c.oid, 'insert')
     and not has_table_privilege('service_role', c.oid, 'update')
     and not has_table_privilege('service_role', c.oid, 'delete')
     and not has_table_privilege('service_role', c.oid, 'truncate')
     and not has_table_privilege('service_role', c.oid, 'references')
     and not has_table_privilege('service_role', c.oid, 'trigger'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'analytics'
     and c.relkind in ('r', 'p')
     and c.relname not in (
       'reviewed_global_aggregate_baselines',
       'reviewed_global_aggregate_audit',
       'reviewed_global_aggregate_independent_sources',
       'reviewed_global_aggregate_authorized_source_bindings',
       'reviewed_global_aggregate_input_admissions'
     )),
  'service_role can inspect legacy analytics but can mutate only through reviewed RPCs'
);
select ok(
  (select count(*) = 12 and bool_and(is_nullable = 'NO')
   from information_schema.columns
   where table_schema = 'analytics' and (
     (table_name in ('dashboard_daily', 'set_metrics_daily', 'region_metrics_daily', 'retailer_metrics_daily', 'batch_metrics_daily')
       and column_name in ('methodology_version', 'computed_at'))
     or (table_name = 'signals' and column_name in ('methodology_version', 'last_updated_at'))
   )),
  'daily metrics and signals require their canonical methodology and computation/update timestamps'
);
select ok(
  (select count(*) = 5 from information_schema.columns
   where table_schema = 'analytics'
     and table_name in ('dashboard_daily', 'set_metrics_daily', 'region_metrics_daily', 'retailer_metrics_daily', 'batch_metrics_daily')
     and column_name = 'baseline_scope' and is_nullable = 'NO'),
  'every daily metric relation has a mandatory baseline scope'
);
select col_not_null('analytics', 'signals', 'expires_at', 'signals have a mandatory cleanup boundary');

select * from finish();
rollback;
