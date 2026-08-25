-- Synthetic demonstration data only.
-- Australia-only, English, physical Pokemon TCG fixtures. No row represents a
-- real person, address, store, account, opening, source, batch, or claim.
begin;

insert into catalog.sets (
  id, external_source, external_id, name, slug, set_code, language, release_date,
  series_name, rarity_taxonomy, metadata, is_active, is_demo
) values
  ('10000000-0000-4000-8000-000000000001', 'synthetic_fixture', 'demo-au-001', 'Synthetic Southern Horizons', 'synthetic-southern-horizons', 'SSH', 'en', '2026-01-15', 'Synthetic Australia',
   '{"double_rare":"Double Rare","illustration_rare":"Illustration Rare"}', '{"franchise":"Pokemon TCG","medium":"physical","synthetic":true}', true, true),
  ('10000000-0000-4000-8000-000000000002', 'synthetic_fixture', 'demo-au-empty', 'Synthetic Empty-State Set', 'synthetic-empty-state-set', 'SES', 'en', '2026-02-15', 'Synthetic Australia',
   '{"double_rare":"Double Rare"}', '{"franchise":"Pokemon TCG","medium":"physical","synthetic":true,"purpose":"empty-state"}', true, true)
on conflict do nothing;

insert into catalog.products (
  id, set_id, name, slug, product_type, language, declared_pack_count, metadata, is_active, is_demo
) values
  ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'Synthetic Southern Horizons Booster Box', 'synthetic-southern-horizons-booster-box', 'booster_box', 'en', 36, '{"synthetic":true,"format":"physical"}', true, true),
  ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', 'Synthetic Southern Horizons ETB', 'synthetic-southern-horizons-etb', 'etb', 'en', 9, '{"synthetic":true,"format":"physical"}', true, true),
  ('20000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', 'Synthetic Southern Horizons Booster Bundle', 'synthetic-southern-horizons-booster-bundle', 'booster_bundle', 'en', 6, '{"synthetic":true,"format":"physical"}', true, true)
on conflict do nothing;

insert into catalog.cards (
  id, external_source, external_id, set_id, name, collector_number, rarity, language, metadata, is_demo
) values
  ('30000000-0000-4000-8000-000000000001', 'synthetic_fixture', 'ssh-001', '10000000-0000-4000-8000-000000000001', 'Synthetic Aurora Creature', '001/100', 'double_rare', 'en', '{"synthetic":true}', true),
  ('30000000-0000-4000-8000-000000000002', 'synthetic_fixture', 'ssh-002', '10000000-0000-4000-8000-000000000001', 'Synthetic Harbour Creature', '002/100', 'illustration_rare', 'en', '{"synthetic":true}', true)
on conflict do nothing;

insert into catalog.regions (
  id, country_code, state_code, city, name, slug, region_type, parent_id,
  latitude, longitude, metadata, is_demo
) values
  ('40000000-0000-4000-8000-000000000001', 'AU', null, null, 'Synthetic Australia', 'synthetic-australia', 'country', null, null, null, '{"synthetic":true,"coverage":"country-only"}', true)
on conflict do nothing;

insert into catalog.retailers (
  id, name, slug, country_code, website_domain, metadata, is_demo
) values
  ('50000000-0000-4000-8000-000000000001', 'Synthetic Card Shop', 'synthetic-card-shop', 'AU', 'shop.pokecrack.invalid', '{"synthetic":true,"channel":"specialty"}', true)
on conflict do nothing;

insert into catalog.stores (
  id, retailer_id, region_id, name, slug, public_address, latitude, longitude, metadata, is_demo
) values
  ('60000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001', 'Synthetic AU Online Store', 'synthetic-au-online-store', null, null, null, '{"synthetic":true,"location_precision":"country-only"}', true)
on conflict do nothing;

insert into ingest.source_policies (
  id, source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, statistics_eligible_default,
  retention_days, config, version, expected_interval_seconds, is_demo
) values
  ('70000000-0000-4000-8000-000000000001', 'synthetic_fixture', 'Synthetic Fixture Import', 'fixture', 'sources.pokecrack.invalid', 'https://sources.pokecrack.invalid', false,
   'manual_import', 'manual', 'not_applicable', array['manual_import'], true, 30, '{"synthetic":true}', 'demo-v1', 3600, true),
  ('70000000-0000-4000-8000-000000000002', 'synthetic_auth', 'Synthetic Authenticated Collector', 'authenticated_social', 'social.pokecrack.invalid', 'https://social.pokecrack.invalid', false,
   'opencli_authenticated', 'authenticated', 'not_applicable', array['opencli_authenticated'], false, 30, '{"synthetic":true,"auth_required":true}', 'demo-v1', 3600, true)
on conflict do nothing;

insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url, domain,
  title, text_excerpt, published_at, discovered_at, author_hash, content_hash,
  collector_type, collector_version, source_policy_version, access_mode,
  usage_classification, source_kind, language, status, metadata, expires_at, is_demo
) values
  ('71000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001', 'Synthetic Video', 'fixture-accepted-1', 'https://sources.pokecrack.invalid/accepted-1', 'https://sources.pokecrack.invalid/accepted-1', 'sources.pokecrack.invalid',
   'Synthetic Booster Box opening', 'Synthetic fixture excerpt; no real author or event.', '2026-08-20 08:00:00+00', '2026-08-20 09:00:00+00', null, repeat('1', 64),
   'manual_import', 'demo-v1', 'demo-v1', 'manual', 'statistics', 'fixture', 'en', 'accepted', '{"synthetic":true}', '2030-01-01 00:00:00+00', true),
  ('71000000-0000-4000-8000-000000000002', '70000000-0000-4000-8000-000000000001', 'Synthetic Blog', 'fixture-accepted-2', 'https://sources.pokecrack.invalid/accepted-2', 'https://sources.pokecrack.invalid/accepted-2', 'sources.pokecrack.invalid',
   'Synthetic ETB opening', 'Synthetic fixture excerpt; no real author or event.', '2026-08-21 08:00:00+00', '2026-08-21 09:00:00+00', null, repeat('2', 64),
   'manual_import', 'demo-v1', 'demo-v1', 'manual', 'statistics', 'fixture', 'en', 'accepted', '{"synthetic":true}', '2030-01-01 00:00:00+00', true),
  ('71000000-0000-4000-8000-000000000003', '70000000-0000-4000-8000-000000000001', 'Synthetic Forum', 'fixture-activity-1', 'https://sources.pokecrack.invalid/activity-1', 'https://sources.pokecrack.invalid/activity-1', 'sources.pokecrack.invalid',
   'Synthetic Booster Bundle sighting', 'Synthetic activity-only fixture excerpt.', '2026-08-22 08:00:00+00', '2026-08-22 09:00:00+00', null, repeat('3', 64),
   'manual_import', 'demo-v1', 'demo-v1', 'manual', 'activity_only', 'fixture', 'en', 'activity_only', '{"synthetic":true}', '2030-01-01 00:00:00+00', true),
  ('71000000-0000-4000-8000-000000000004', '70000000-0000-4000-8000-000000000001', 'Synthetic Forum', 'fixture-rejected-1', 'https://sources.pokecrack.invalid/rejected-1', 'https://sources.pokecrack.invalid/rejected-1', 'sources.pokecrack.invalid',
   'Synthetic rejected claim', 'Synthetic rejected fixture excerpt.', '2026-08-23 08:00:00+00', '2026-08-23 09:00:00+00', null, repeat('4', 64),
   'manual_import', 'demo-v1', 'demo-v1', 'manual', 'excluded', 'fixture', 'en', 'rejected', '{"synthetic":true,"rejection_reason":"insufficient evidence"}', '2030-01-01 00:00:00+00', true)
on conflict do nothing;

insert into ingest.extraction_runs (
  id, source_item_id, stage, provider, model, prompt_version, input_hash,
  output_json, decision, confidence, input_tokens, output_tokens,
  estimated_cost_aud, latency_ms, started_at, completed_at, expires_at, is_demo
) values
  ('72000000-0000-4000-8000-000000000001', '71000000-0000-4000-8000-000000000001', 'extract', 'synthetic-fixture', 'deterministic-v1', 'demo-v1', repeat('a',64), '{"synthetic":true}', 'accepted', 0.9900, 0, 0, 0, 1, '2026-08-20 09:00:00+00', '2026-08-20 09:00:01+00', '2030-01-01 00:00:00+00', true),
  ('72000000-0000-4000-8000-000000000002', '71000000-0000-4000-8000-000000000002', 'extract', 'synthetic-fixture', 'deterministic-v1', 'demo-v1', repeat('b',64), '{"synthetic":true}', 'accepted', 0.9800, 0, 0, 0, 1, '2026-08-21 09:00:00+00', '2026-08-21 09:00:01+00', '2030-01-01 00:00:00+00', true),
  ('72000000-0000-4000-8000-000000000003', '71000000-0000-4000-8000-000000000003', 'extract', 'synthetic-fixture', 'deterministic-v1', 'demo-v1', repeat('c',64), '{"synthetic":true}', 'activity_only', 0.9000, 0, 0, 0, 1, '2026-08-22 09:00:00+00', '2026-08-22 09:00:01+00', '2030-01-01 00:00:00+00', true),
  ('72000000-0000-4000-8000-000000000004', '71000000-0000-4000-8000-000000000004', 'extract', 'synthetic-fixture', 'deterministic-v1', 'demo-v1', repeat('d',64), '{"synthetic":true}', 'rejected', 0.9500, 0, 0, 0, 1, '2026-08-23 09:00:00+00', '2026-08-23 09:00:01+00', '2030-01-01 00:00:00+00', true)
on conflict do nothing;

insert into ingest.openings (
  id, source_item_id, extraction_run_id, set_id, product_id, language, pack_count,
  complete_opening, country_code, region_id, retailer_id, store_id, batch_code,
  purchase_date, opened_at, observed_at, evidence_tier, overall_confidence,
  eligible_for_statistics, methodology_version, validation_status, public_status,
  source_kind, expires_at, is_demo
) values
  ('73000000-0000-4000-8000-000000000001', '71000000-0000-4000-8000-000000000001', '72000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'en', 36, true, 'AU', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', 'SYN-AU-001', '2026-08-19', '2026-08-20 08:00:00+00', '2026-08-20 09:00:00+00', 'A', 0.9900, true, 'demo-v1', 'accepted', 'verified', 'fixture', '2030-01-01 00:00:00+00', true),
  ('73000000-0000-4000-8000-000000000002', '71000000-0000-4000-8000-000000000002', '72000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000002', 'en', 9, true, 'AU', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', 'SYN-AU-002', '2026-08-20', '2026-08-21 08:00:00+00', '2026-08-21 09:00:00+00', 'B', 0.9800, true, 'demo-v1', 'accepted', 'verified', 'fixture', '2030-01-01 00:00:00+00', true),
  ('73000000-0000-4000-8000-000000000003', '71000000-0000-4000-8000-000000000003', '72000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000003', 'en', 6, false, 'AU', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', 'SYN-AU-003', '2026-08-21', null, '2026-08-22 09:00:00+00', 'C', 0.9000, false, 'demo-v1', 'activity_only', 'provisional', 'fixture', '2030-01-01 00:00:00+00', true),
  ('73000000-0000-4000-8000-000000000004', '71000000-0000-4000-8000-000000000004', '72000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000003', 'en', 0, false, 'AU', '40000000-0000-4000-8000-000000000001', null, null, null, null, null, '2026-08-23 09:00:00+00', 'D', 0.3000, false, 'demo-v1', 'rejected', 'rejected', 'fixture', '2030-01-01 00:00:00+00', true)
on conflict do nothing;

insert into ingest.opening_hits (id, opening_id, card_id, card_name, collector_number, rarity, quantity, evidence_reference, confidence, is_demo) values
  ('74000000-0000-4000-8000-000000000001', '73000000-0000-4000-8000-000000000001', '30000000-0000-4000-8000-000000000001', 'Synthetic Aurora Creature', '001/100', 'double_rare', 1, 'synthetic-frame-001', 0.9900, true),
  ('74000000-0000-4000-8000-000000000002', '73000000-0000-4000-8000-000000000002', '30000000-0000-4000-8000-000000000002', 'Synthetic Harbour Creature', '002/100', 'illustration_rare', 1, 'synthetic-frame-002', 0.9800, true)
on conflict do nothing;

insert into ingest.batch_sightings (
  id, source_item_id, opening_id, set_id, product_id, region_id, retailer_id, store_id,
  batch_code, normalized_batch_code, pack_quantity, activity_only, confidence,
  observed_at, expires_at, is_demo
) values
  ('75000000-0000-4000-8000-000000000001', '71000000-0000-4000-8000-000000000001', '73000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', 'SYN-AU-001', 'SYN-AU-001', 36, false, 0.9900, '2026-08-20 09:00:00+00', '2030-01-01 00:00:00+00', true),
  ('75000000-0000-4000-8000-000000000002', '71000000-0000-4000-8000-000000000003', '73000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000003', '40000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '60000000-0000-4000-8000-000000000001', 'SYN-AU-003', 'SYN-AU-003', 6, true, 0.9000, '2026-08-22 09:00:00+00', '2030-01-01 00:00:00+00', true)
on conflict do nothing;

insert into ingest.browser_sessions (
  profile_name, status, extension_connected, daemon_connected, authenticated_sources,
  last_check_at, last_successful_command_at, last_error
) values ('demo-auth-required', 'auth_required', false, false, '{}'::jsonb, '2026-08-24 12:00:00+00', null, null)
on conflict do nothing;

insert into analytics.dashboard_daily (
  date, country_code, language, observed_packs, complete_openings, accepted_sources,
  activity_only_sources, rejected_sources, tracked_sets, tracked_regions,
  tracked_retailers, batch_sightings, data_quality_score, accepted_count,
  activity_only_count, rejected_count, hit_count, observed_hit_rate,
  posterior_mean, credible_interval_low, credible_interval_high, baseline,
  delta_from_baseline, baseline_scope, window_start, window_end,
  catalog_version, build_sha, computed_at, methodology_version, is_demo
) values (
  '2026-08-24', 'AU', 'en', 51, 2, 2, 1, 1, 2, 1,
  1, 2, 0.9500, 2, 1, 1, 2, 0.0392156863,
  0.0395000000, 0.0180000000, 0.0660000000, 0.0400000000,
  -0.0005000000, 'Synthetic AU physical products', '2026-08-18', '2026-08-24',
  'demo-catalog-v1', 'deadbee', '2026-08-24 12:00:00+00', 'demo-v1', true
) on conflict do nothing;

insert into analytics.set_metrics_daily (
  id, date, set_id, product_type, language, observed_packs, complete_openings,
  independent_source_count, rarity_counts, observed_rates, baseline_rates,
  credible_intervals, sample_quality_score, window_start, window_end,
  accepted_count, activity_only_count, rejected_count, baseline_scope,
  computed_at, methodology_version, catalog_version, is_demo
) values (
  '81000000-0000-4000-8000-000000000001', '2026-08-24', '10000000-0000-4000-8000-000000000001', null, 'en', 51, 3, 3,
  '{"double_rare":1,"illustration_rare":1}', '{"hit_rate":0.0392156863}', '{"hit_rate":0.0400000000}',
  '{"hit_rate":{"low":0.018,"high":0.066,"level":0.9}}', 0.9500, '2026-08-18', '2026-08-24', 2, 1, 1,
  'Synthetic AU physical products', '2026-08-24 12:00:00+00', 'demo-v1', 'demo-catalog-v1', true
) on conflict do nothing;

insert into analytics.region_metrics_daily (
  id, date, region_id, set_id, product_id, product_type, language, observed_packs,
  complete_openings, independent_source_count, rarity_counts, observed_rates,
  baseline_rates, credible_intervals, sample_quality_score, window_start, window_end,
  accepted_count, activity_only_count, rejected_count, baseline_scope,
  computed_at, methodology_version, catalog_version, is_demo
) values (
  '82000000-0000-4000-8000-000000000001', '2026-08-24', '40000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', null, null, 'en', 51, 3, 3,
  '{"double_rare":1,"illustration_rare":1}', '{"hit_rate":0.0392156863}', '{"hit_rate":0.0400000000}', '{"hit_rate":{"low":0.018,"high":0.066,"level":0.9}}',
  0.9500, '2026-08-18', '2026-08-24', 2, 1, 1, 'Synthetic national AU comparison', '2026-08-24 12:00:00+00', 'demo-v1', 'demo-catalog-v1', true
) on conflict do nothing;

insert into analytics.retailer_metrics_daily (
  id, date, retailer_id, region_id, set_id, product_id, product_type, language,
  observed_packs, complete_openings, independent_source_count, rarity_counts,
  observed_rates, baseline_rates, credible_intervals, sample_quality_score,
  window_start, window_end, accepted_count, activity_only_count, rejected_count,
  baseline_scope, computed_at, methodology_version, catalog_version, is_demo
) values (
  '83000000-0000-4000-8000-000000000001', '2026-08-24', '50000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', null, null, 'en',
  51, 3, 3, '{"double_rare":1,"illustration_rare":1}', '{"hit_rate":0.0392156863}', '{"hit_rate":0.0400000000}', '{"hit_rate":{"low":0.018,"high":0.066,"level":0.9}}',
  0.9500, '2026-08-18', '2026-08-24', 2, 1, 1, 'Synthetic AU retailer comparison', '2026-08-24 12:00:00+00', 'demo-v1', 'demo-catalog-v1', true
) on conflict do nothing;

insert into analytics.batch_metrics_daily (
  id, date, batch_code, normalized_batch_code, set_id, product_id,
  observed_packs, complete_openings, independent_source_count, region_count,
  retailer_count, first_seen, last_seen, posterior_mean, credible_interval_low,
  credible_interval_high, probability_above_baseline,
  probability_above_practical_uplift, signal_status, baseline_scope, baseline,
  credible_level, computed_at, methodology_version, is_demo
) values (
  '84000000-0000-4000-8000-000000000001', '2026-08-24', 'SYN-AU-001', 'SYN-AU-001', '10000000-0000-4000-8000-000000000001', null,
  260, 4, 4, 1, 1, '2026-08-20 08:00:00+00', '2026-08-20 09:00:00+00', 0.0620000000, 0.0360000000,
  0.0910000000, 0.9900000000, 0.9700000000, 'Possible anomaly',
  'Synthetic set baseline', 0.0400000000, 0.900,
  '2026-08-24 12:00:00+00', 'demo-v1', true
) on conflict do nothing;

insert into analytics.signals (
  id, signal_type, entity_type, entity_key, set_id, metric, status, sample_size,
  independent_source_count, baseline, observed, posterior_mean,
  credible_interval_low, credible_interval_high, probability_above_baseline,
  probability_above_practical_uplift, explanation, methodology_version,
  first_detected_at, last_updated_at, expires_at, credible_level, baseline_scope,
  evidence_tier, is_public, is_demo
) values
  ('85000000-0000-4000-8000-000000000001', 'sample_quality', 'set', 'synthetic-empty-state-set', '10000000-0000-4000-8000-000000000002', 'hit_rate', 'Insufficient sample', 4, 1, null, null, null, null, null, null, null, '{"reason":"below synthetic publication threshold"}', 'demo-v1', '2026-08-24 10:00:00+00', '2026-08-24 12:00:00+00', '2026-09-24 12:00:00+00', 0.900, 'Synthetic empty-state cohort', 'A', true, true),
  ('85000000-0000-4000-8000-000000000002', 'baseline_comparison', 'set', 'synthetic-southern-horizons', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'No significant signal', 51, 3, 0.0400000000, 0.0392156863, 0.0395000000, 0.0180000000, 0.0660000000, 0.4900000000, 0.1800000000, '{"reason":"synthetic interval overlaps baseline"}', 'demo-v1', '2026-08-24 10:00:00+00', '2026-08-24 12:00:00+00', '2026-09-24 12:00:00+00', 0.900, 'Synthetic AU physical products', 'A', true, true),
  ('85000000-0000-4000-8000-000000000003', 'baseline_comparison', 'retailer', 'synthetic-card-shop', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'Watch', 220, 3, 0.0400000000, 0.0500000000, 0.0505000000, 0.0280000000, 0.0770000000, 0.9300000000, 0.9300000000, '{"reason":"synthetic watch threshold"}', 'demo-v1', '2026-08-24 10:00:00+00', '2026-08-24 12:00:00+00', '2026-09-24 12:00:00+00', 0.900, 'Synthetic AU retailer comparison', 'A', true, true),
  ('85000000-0000-4000-8000-000000000004', 'batch_comparison', 'batch', 'SYN-AU-001', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'Possible anomaly', 260, 4, 0.0400000000, 0.0615384615, 0.0620000000, 0.0360000000, 0.0910000000, 0.9900000000, 0.9700000000, '{"reason":"synthetic anomaly demonstration only"}', 'demo-v1', '2026-08-24 10:00:00+00', '2026-08-24 12:00:00+00', '2026-09-24 12:00:00+00', 0.900, 'Synthetic set baseline', 'A', true, true)
on conflict do nothing;

insert into public.dashboard_overview (
  snapshot_key, schema_version, mode, generated_at, observed_packs,
  complete_openings, verified_sources, coverage_days, tracked_sets,
  tracked_regions, tracked_retailers, batch_sightings, australia_coverage,
  baseline_hit_rate, accepted_count, activity_only_count, rejected_count,
  methodology_version, is_demo
) values ('demo-au', '1.0.0', 'demo', '2026-08-24 12:00:00+00', 51, 3, 3, 7, 2, 1, 1, 2,
  'Australia · synthetic country-only demo coverage', 0.0400000000, 2, 1, 1, 'demo-v1', true)
on conflict do nothing;

insert into public.set_summaries (
  set_id, slug, name, series_name, release_date, observed_packs, complete_openings,
  independent_source_count, observed_rate, posterior_mean, baseline_rate, credible_interval_low,
  credible_interval_high, delta_from_baseline, signal_status,
  methodology_version, updated_at, is_demo
) values
  ('10000000-0000-4000-8000-000000000001', 'synthetic-southern-horizons', 'Synthetic Southern Horizons', 'Synthetic Australia', '2026-01-15', 51, 3, 3, 0.0392156863, 0.0395000000, 0.0400000000, 0.0180000000, 0.0660000000, -0.0007843137, 'No significant signal', 'demo-v1', '2026-08-24 12:00:00+00', true),
  ('10000000-0000-4000-8000-000000000002', 'synthetic-empty-state-set', 'Synthetic Empty-State Set', 'Synthetic Australia', '2026-02-15', 0, 0, 0, null, null, null, null, null, null, 'Insufficient sample', 'demo-v1', '2026-08-24 12:00:00+00', true)
on conflict do nothing;

insert into public.region_summaries (
  region_id, slug, name, country_code, coverage, observed_packs, complete_openings,
  independent_source_count, observed_rate, posterior_mean, baseline_rate, credible_interval_low,
  credible_interval_high, delta_from_baseline, signal_status,
  methodology_version, updated_at, is_demo
) values ('40000000-0000-4000-8000-000000000001', 'synthetic-australia', 'Synthetic Australia', 'AU', 'Synthetic country-only coverage', 51, 3, 3, 0.0392156863, 0.0395000000, 0.0400000000, 0.0180000000, 0.0660000000, -0.0007843137, 'No significant signal', 'demo-v1', '2026-08-24 12:00:00+00', true)
on conflict do nothing;

insert into public.retailer_summaries (
  id, retailer_id, region_id, slug, name, region_name, country_code, channel,
  observed_packs, complete_openings, independent_source_count, observed_rate, posterior_mean,
  baseline_rate, credible_interval_low, credible_interval_high,
  delta_from_baseline, signal_status, methodology_version, updated_at, is_demo
) values ('86000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', '40000000-0000-4000-8000-000000000001', 'synthetic-card-shop-au', 'Synthetic Card Shop', 'Synthetic Australia', 'AU', 'specialty', 220, 6, 3, 0.0500000000, 0.0505000000, 0.0400000000, 0.0280000000, 0.0770000000, 0.0100000000, 'Watch', 'demo-v1', '2026-08-24 12:00:00+00', true)
on conflict do nothing;

insert into public.batch_summaries (
  id, batch_code, set_id, set_slug, set_name, product_type, region_id, region_name, first_observed_at,
  last_observed_at, observed_packs, complete_openings, independent_source_count,
  observed_rate, posterior_mean, baseline_rate, credible_interval_low, credible_interval_high,
  delta_from_baseline, signal_status, methodology_version, updated_at, is_demo
) values ('87000000-0000-4000-8000-000000000001', 'SYN-AU-001', '10000000-0000-4000-8000-000000000001', 'synthetic-southern-horizons', 'Synthetic Southern Horizons', 'booster_box', '40000000-0000-4000-8000-000000000001', 'Synthetic Australia', '2026-08-20 08:00:00+00', '2026-08-20 09:00:00+00', 260, 4, 4, 0.0615384615, 0.0620000000, 0.0400000000, 0.0360000000, 0.0910000000, 0.0215384615, 'Possible anomaly', 'demo-v1', '2026-08-24 12:00:00+00', true)
on conflict do nothing;

insert into public.recent_activity (
  id, activity_kind, subject_kind, subject_id, subject_label, set_name, retailer_name, occurred_at,
  observed_at, pack_count, product_type, evidence_tier, status, statistics_eligible, country_code,
  region_name, platform, source_kind, source_title, source_published_at,
  source_link, entities, is_demo, created_at
) values
  ('88000000-0000-4000-8000-000000000001', 'opening', 'product', 'synthetic-southern-horizons-booster-box', 'Synthetic Southern Horizons Booster Box', 'Synthetic Southern Horizons', 'Synthetic Card Shop', '2026-08-20 08:00:00+00', '2026-08-20 09:00:00+00', 36, 'booster_box', 'A', 'accepted', true, 'AU', 'Synthetic Australia', 'Synthetic Video', 'fixture', 'Synthetic Booster Box opening', '2026-08-20 08:00:00+00', 'https://sources.pokecrack.invalid/accepted-1', '{"set":"synthetic-southern-horizons","product":"booster_box","region":"AU","batch":"SYN-AU-001"}', true, '2026-08-24 12:00:00+00'),
  ('88000000-0000-4000-8000-000000000002', 'opening', 'product', 'synthetic-southern-horizons-etb', 'Synthetic Southern Horizons ETB', 'Synthetic Southern Horizons', 'Synthetic Card Shop', '2026-08-21 08:00:00+00', '2026-08-21 09:00:00+00', 9, 'etb', 'B', 'accepted', true, 'AU', 'Synthetic Australia', 'Synthetic Blog', 'fixture', 'Synthetic ETB opening', '2026-08-21 08:00:00+00', 'https://sources.pokecrack.invalid/accepted-2', '{"set":"synthetic-southern-horizons","product":"etb","region":"AU","batch":"SYN-AU-002"}', true, '2026-08-24 12:00:00+00'),
  ('88000000-0000-4000-8000-000000000003', 'sighting', 'product', 'synthetic-southern-horizons-booster-bundle', 'Synthetic Southern Horizons Booster Bundle', 'Synthetic Southern Horizons', 'Synthetic Card Shop', '2026-08-22 08:00:00+00', '2026-08-22 09:00:00+00', 6, 'booster_bundle', 'C', 'activity_only', false, 'AU', 'Synthetic Australia', 'Synthetic Forum', 'fixture', 'Synthetic Booster Bundle sighting', '2026-08-22 08:00:00+00', 'https://sources.pokecrack.invalid/activity-1', '{"set":"synthetic-southern-horizons","product":"booster_bundle","region":"AU","batch":"SYN-AU-003"}', true, '2026-08-24 12:00:00+00')
on conflict do nothing;

insert into public.public_signals (
  id, entity_type, entity_key, entity_label, set_id, metric, status, sample_size,
  complete_openings, independent_source_count, baseline, observed, posterior_mean,
  credible_interval_low, credible_interval_high, probability_above_baseline,
  probability_above_practical_uplift, baseline_scope, evidence_tier, window_start,
  window_end, methodology_version, as_of, is_demo
) values
  ('89000000-0000-4000-8000-000000000001', 'set', 'synthetic-empty-state-set', 'Synthetic Empty-State Set', '10000000-0000-4000-8000-000000000002', 'hit_rate', 'Insufficient sample', 4, 1, 1, null, null, null, null, null, null, null, 'Synthetic empty-state cohort', 'A', '2026-08-18', '2026-08-24', 'demo-v1', '2026-08-24 12:00:00+00', true),
  ('89000000-0000-4000-8000-000000000002', 'set', 'synthetic-southern-horizons', 'Synthetic Southern Horizons', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'No significant signal', 51, 3, 3, 0.0400000000, 0.0392156863, 0.0395000000, 0.0180000000, 0.0660000000, 0.4900000000, 0.1800000000, 'Synthetic AU physical products', 'A', '2026-08-18', '2026-08-24', 'demo-v1', '2026-08-24 12:00:00+00', true),
  ('89000000-0000-4000-8000-000000000003', 'retailer', 'synthetic-card-shop', 'Synthetic Card Shop', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'Watch', 220, 6, 3, 0.0400000000, 0.0500000000, 0.0505000000, 0.0280000000, 0.0770000000, 0.9300000000, 0.9300000000, 'Synthetic AU retailer comparison', 'A', '2026-08-18', '2026-08-24', 'demo-v1', '2026-08-24 12:00:00+00', true),
  ('89000000-0000-4000-8000-000000000004', 'batch', 'SYN-AU-001', 'Synthetic batch SYN-AU-001', '10000000-0000-4000-8000-000000000001', 'hit_rate', 'Possible anomaly', 260, 4, 4, 0.0400000000, 0.0615384615, 0.0620000000, 0.0360000000, 0.0910000000, 0.9900000000, 0.9700000000, 'Synthetic set baseline', 'A', '2026-08-18', '2026-08-24', 'demo-v1', '2026-08-24 12:00:00+00', true)
on conflict do nothing;

insert into public.data_freshness (
  component_id, component_name, status, as_of, last_successful_collection_at,
  age_seconds, next_expected_at, is_demo
) values
  ('overall', 'Synthetic overall collection', 'fresh', '2026-08-24 12:00:00+00', '2026-08-24 11:55:00+00', 300, '2026-08-24 13:00:00+00', true),
  ('authenticated-social', 'Synthetic authenticated collector', 'unavailable', '2026-08-24 12:00:00+00', null, null, null, true)
on conflict do nothing;

insert into public.system_status (
  component_id, component_name, status, checked_at, public_message, auth_required, is_demo
) values
  ('overall', 'Synthetic public data system', 'operational', '2026-08-24 12:00:00+00', 'Synthetic demonstration data is available.', false, true),
  ('database', 'Synthetic database publication', 'operational', '2026-08-24 12:00:00+00', 'Synthetic public aggregates are available.', false, true),
  ('authenticated-social', 'Synthetic authenticated collector', 'degraded', '2026-08-24 12:00:00+00', 'Authentication required to resume this synthetic collector.', true, true)
on conflict do nothing;

commit;
