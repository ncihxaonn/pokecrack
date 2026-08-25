-- Synthetic AU seed contract. Assumes a clean local reset followed by supabase/seed.sql.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(38);

select is((select count(*)::integer from public.dashboard_overview), 1, 'seed publishes one bounded dashboard snapshot row');
select ok((select mode = 'demo' and is_demo and accepted_count > 0 and activity_only_count > 0 and rejected_count > 0 from public.dashboard_overview limit 1), 'overview is visibly demo and covers every aggregate source outcome');
select ok((select count(*) > 0 and bool_and(is_demo and language = 'en' and metadata @> '{"franchise":"Pokemon TCG","medium":"physical"}'::jsonb) from catalog.sets), 'seed sets are synthetic English physical Pokemon TCG data');
select set_eq(
  $$select distinct product_type from catalog.products where is_demo$$,
  $$values ('booster_box'::text), ('etb'), ('booster_bundle')$$,
  'seed covers Booster Box, ETB, and Booster Bundle only'
);
select ok((select count(*) > 0 and bool_and(is_demo and language = 'en') from catalog.cards), 'seed cards are English demo rows');
select ok((select count(*) > 0 and bool_and(is_demo and country_code = 'AU' and city is null and latitude is null and longitude is null) from catalog.regions), 'demo regions are Australia-only and contain no exact location');
select ok((select count(*) > 0 and bool_and(is_demo and country_code = 'AU') from catalog.retailers), 'demo retailers are Australia-only');
select ok((select count(*) > 0 and bool_and(is_demo and public_address is null and latitude is null and longitude is null) from catalog.stores), 'demo stores contain no address or coordinates');
select ok((select count(*) > 0 and bool_and(is_demo and country_code = 'AU' and language = 'en') from ingest.openings), 'demo openings are Australia-only and English');
select ok((select bool_and(p.product_type in ('booster_box', 'etb', 'booster_bundle')) from ingest.openings o join catalog.products p on p.id = o.product_id), 'openings cover only the three physical product formats');
select set_eq(
  $$select distinct status from ingest.source_items where is_demo$$,
  $$values ('accepted'::text), ('activity_only'), ('rejected')$$,
  'raw source outcomes cover accepted, activity_only, and rejected'
);
select ok((select count(*) > 0 and bool_and(is_demo and source_kind = 'fixture' and domain like '%.invalid' and author_hash is null and last_error_code is null and last_error_message is null) from ingest.source_items), 'fixture sources use reserved domains and contain no author or error data');
select is((select count(*)::integer from (select 1 from analytics.dashboard_daily where is_demo union all select 1 from analytics.set_metrics_daily where is_demo union all select 1 from analytics.region_metrics_daily where is_demo union all select 1 from analytics.retailer_metrics_daily where is_demo union all select 1 from analytics.batch_metrics_daily where is_demo) rows), 5, 'all five analytics routes have a demo metric row');
select set_eq(
  $$select distinct status from analytics.signals where is_demo$$,
  $$values ('Insufficient sample'::text), ('No significant signal'), ('Watch'), ('Possible anomaly')$$,
  'private demo signals cover the exact approved labels'
);
select ok((select bool_and(baseline is null and observed is null and posterior_mean is null and credible_interval_low is null and credible_interval_high is null and probability_above_baseline is null and probability_above_practical_uplift is null) from analytics.signals where status = 'Insufficient sample' and is_demo), 'insufficient private signals do not fabricate estimates');
select ok((select bool_and(row_count > 0) from (values
  ((select count(*) from public.dashboard_overview)), ((select count(*) from public.set_summaries)),
  ((select count(*) from public.region_summaries)), ((select count(*) from public.retailer_summaries)),
  ((select count(*) from public.batch_summaries)), ((select count(*) from public.recent_activity)),
  ((select count(*) from public.public_signals)), ((select count(*) from public.data_freshness)),
  ((select count(*) from public.system_status))
) counts(row_count)), 'every named public route has demo content');
select ok((select count(*) > 0 from public.set_summaries where observed_packs = 0 and complete_openings = 0 and signal_status = 'Insufficient sample'), 'at least one set dimension intentionally demonstrates an empty state');
select set_eq(
  $$select distinct status from public.public_signals where is_demo$$,
  $$values ('Insufficient sample'::text), ('No significant signal'), ('Watch'), ('Possible anomaly')$$,
  'public demo signals cover the exact approved labels'
);
select ok((select bool_and(baseline is null and observed is null and posterior_mean is null and credible_interval_low is null and credible_interval_high is null and probability_above_baseline is null and probability_above_practical_uplift is null) from public.public_signals where status = 'Insufficient sample' and is_demo), 'insufficient public signals do not fabricate estimates');
select ok(
  not exists (
    select 1 from (
      select status, sample_size, independent_source_count, probability_above_baseline, probability_above_practical_uplift
      from analytics.signals where is_demo
      union all
      select status, sample_size, independent_source_count, probability_above_baseline, probability_above_practical_uplift
      from public.public_signals where is_demo
    ) s where
      (status = 'Insufficient sample' and sample_size >= 30 and independent_source_count >= 3)
      or (status = 'No significant signal' and (sample_size < 30 or independent_source_count < 3))
      or (status = 'Watch' and (sample_size < 200 or independent_source_count < 3 or probability_above_practical_uplift < 0.900))
      or (status = 'Possible anomaly' and (sample_size < 200 or independent_source_count < 3 or probability_above_practical_uplift < 0.950))
  ),
  'demo signals obey conservative sample, source, and probability gates'
);
select set_eq(
  $$select distinct status from public.recent_activity where is_demo$$,
  $$values ('accepted'::text), ('activity_only')$$,
  'public activity includes accepted and activity_only but no rejected row'
);
select ok((select count(*) > 0 and bool_and(source_link like 'https://%.invalid/%' and jsonb_typeof(entities) = 'object') from public.recent_activity), 'public activity source links are synthetic and entities stay structured');
select ok((select bool_and(statistics_eligible = (status = 'accepted' and evidence_tier in ('A', 'B') and activity_kind = 'opening')) from public.recent_activity), 'activity statistics eligibility is explicit and conservative');
select ok((select count(*) > 0 and bool_and(status in ('fresh', 'delayed', 'stale', 'unavailable')) and bool_or(component_id = 'overall') from public.data_freshness), 'freshness route uses the safe vocabulary and has an overall row');
select ok((select bool_or(auth_required and component_id = 'authenticated-social' and public_message = 'Authentication required to resume this synthetic collector.') from public.system_status), 'system status safely demonstrates an auth-required collector');
select ok((select status = 'auth_required' and not extension_connected and not daemon_connected and last_error is null and authenticated_sources = '{}'::jsonb from ingest.browser_sessions where profile_name = 'demo-auth-required'), 'private browser health demonstrates auth required without a session, secret, or error');
select ok((select accepted_count = 2 and activity_only_count = 1 and rejected_count = 1 from public.dashboard_overview), 'dashboard outcome aggregate counts are deterministic');
select ok((select observed_packs > 0 and complete_openings > 0 and verified_sources > 0 and coverage_days > 0 from public.dashboard_overview), 'dashboard KPI cards have non-zero demo coverage');
select ok((select jsonb_typeof(snapshot) = 'object' and jsonb_array_length(snapshot->'sets') > 0 and jsonb_array_length(snapshot->'regions') > 0 and jsonb_array_length(snapshot->'retailers') > 0 and jsonb_array_length(snapshot->'batches') > 0 and jsonb_array_length(snapshot->'recentActivity') > 0 and jsonb_array_length(snapshot->'services') > 0 and jsonb_typeof(snapshot->'trend') = 'array' and jsonb_typeof(snapshot->'sources') = 'array' from (select public.get_public_dashboard_snapshot_v1() snapshot) q), 'snapshot RPC assembles every compact Web list');
select doesnt_match((select public.get_public_dashboard_snapshot_v1()::text), '(?i)(author_hash|output_json|job_payload|last_error|browser_session|secret|token)', 'snapshot contains no private field names');
select ok((select count(*) = 0 from (select is_demo from catalog.sets union all select is_demo from catalog.products union all select is_demo from catalog.cards union all select is_demo from catalog.regions union all select is_demo from catalog.retailers union all select is_demo from catalog.stores union all select is_demo from ingest.source_items union all select is_demo from ingest.openings) demo where not is_demo), 'all seeded catalog and observation records are explicitly demo');
select ok((select count(*) > 0 and bool_and(set_name like 'Synthetic %' and region_name = 'Synthetic Australia') from public.batch_summaries), 'batch route remains visibly synthetic and Australia-scoped');

select set_eq(
  $$select jsonb_object_keys(public.get_public_dashboard_snapshot_v1())$$,
  $$values ('mode'::text), ('generatedAt'), ('summary'), ('sets'), ('regions'), ('retailers'), ('batches'), ('trend'), ('sources'), ('services'), ('recentActivity')$$,
  'snapshot root matches the exact strict Web public dashboard shape'
);
select set_eq(
  $$select jsonb_object_keys(public.get_public_dashboard_snapshot_v1()->'summary')$$,
  $$values ('observedPacks'::text), ('completeOpenings'), ('aiValidatedSources'), ('trackedSets'), ('trackedRegions'), ('batchSightings'), ('baselineHitRate'), ('australiaCoverage'), ('methodologyVersion')$$,
  'snapshot summary matches the exact Web KPI contract'
);
select set_eq(
  $$select jsonb_object_keys(item) from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'sets') item where item->>'slug' = 'synthetic-southern-horizons'$$,
  $$values ('slug'::text), ('name'), ('series'), ('releaseDate'), ('signal'), ('packsObserved'), ('openings'), ('independentSources'), ('baselineRate'), ('hitRate'), ('posteriorMean'), ('credibleInterval'), ('deltaFromBaseline'), ('state'), ('sampleNote'), ('updatedAt')$$,
  'snapshot set rows match the strict Web metric shape'
);
select ok(
  (select (item->>'hitRate')::numeric = s.observed_rate and (item->>'hitRate')::numeric <> s.posterior_mean
   from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'sets') item
   join public.set_summaries s on s.slug = item->>'slug' where s.slug = 'synthetic-southern-horizons')
  and (select (item->>'hitRate')::numeric = r.observed_rate and (item->>'hitRate')::numeric <> r.posterior_mean
   from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'regions') item
   join public.region_summaries r on r.slug = item->>'slug')
  and (select (item->>'hitRate')::numeric = r.observed_rate and (item->>'hitRate')::numeric <> r.posterior_mean
   from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'retailers') item
   join public.retailer_summaries r on r.slug = item->>'slug')
  and (select (item->>'hitRate')::numeric = b.observed_rate and (item->>'hitRate')::numeric <> b.posterior_mean
   from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'batches') item
   join public.batch_summaries b on b.batch_code = item->>'code'),
  'Web hitRate always uses the raw observed rate rather than posterior mean'
);
select ok(
  not exists (
    select 1 from (
      select item from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'sets') item
      union all select item from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'regions') item
      union all select item from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'retailers') item
      union all select item from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'batches') item
    ) metrics where item->>'state' not in ('ready', 'watch', 'anomaly', 'insufficient')
  )
  and (select bool_and(item->>'productType' in ('Booster Box', 'ETB', 'Booster Bundle')) from jsonb_array_elements(public.get_public_dashboard_snapshot_v1()->'batches') item),
  'snapshot states and batch product labels use the strict Web vocabulary'
);
select set_eq(
  $$select jsonb_object_keys(public.get_public_dashboard_snapshot_v1()->'recentActivity'->0)$$,
  $$values ('id'::text), ('observedAt'), ('platform'), ('setName'), ('productType'), ('packCount'), ('region'), ('retailer'), ('evidenceTier'), ('classification'), ('statisticsEligible'), ('published'), ('sourceUrl')$$,
  'snapshot activity rows match the strict Web public shape'
);

select * from finish();
rollback;
