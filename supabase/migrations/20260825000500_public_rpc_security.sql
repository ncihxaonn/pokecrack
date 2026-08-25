begin;

create or replace function public.get_public_dashboard_snapshot_v1()
returns jsonb
language sql
stable
security invoker
set search_path = pg_catalog, public
as $$
with dashboard_row as (
  select d.*
  from public.dashboard_overview d
  order by d.generated_at desc, d.snapshot_key
  limit 1
),
relation_guard as (
  -- Keep the RPC auditable: it touches only the nine named public relations.
  select
    (select count(*) from public.public_signals) +
    (select count(*) from public.data_freshness) as safe_row_count
),
set_rows as (
  select coalesce(jsonb_agg(item order by updated_at desc, set_id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'slug', s.slug,
      'name', s.name,
      'series', s.series_name,
      'releaseDate', s.release_date,
      'signal', s.signal_status,
      'packsObserved', s.observed_packs,
      'openings', s.complete_openings,
      'independentSources', s.independent_source_count,
      'baselineRate', s.baseline_rate,
      'hitRate', s.observed_rate,
      'posteriorMean', s.posterior_mean,
      'credibleInterval', case when s.posterior_mean is null then null else jsonb_build_object(
        'low', s.credible_interval_low, 'high', s.credible_interval_high
      ) end,
      'deltaFromBaseline', s.delta_from_baseline,
      'state', case s.signal_status
        when 'Insufficient sample' then 'insufficient'
        when 'No significant signal' then 'ready'
        when 'Watch' then 'watch'
        when 'Possible anomaly' then 'anomaly'
      end,
      'sampleNote', case when s.signal_status = 'Insufficient sample'
        then 'Insufficient sample for a stable observed rate.'
        else format('%s observed packs across %s independent sources.', s.observed_packs, s.independent_source_count)
      end,
      'updatedAt', s.updated_at
    ) as item, s.updated_at, s.set_id
    from public.set_summaries s
    cross join dashboard_row mode_guard
    where s.is_demo = mode_guard.is_demo
    order by s.updated_at desc, s.set_id
    limit 50
  ) bounded_sets
),
region_rows as (
  select coalesce(jsonb_agg(item order by updated_at desc, region_id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'slug', r.slug,
      'name', r.name,
      'countryCode', r.country_code,
      'coverage', r.coverage,
      'packsObserved', r.observed_packs,
      'openings', r.complete_openings,
      'independentSources', r.independent_source_count,
      'baselineRate', r.baseline_rate,
      'hitRate', r.observed_rate,
      'posteriorMean', r.posterior_mean,
      'credibleInterval', case when r.posterior_mean is null then null else jsonb_build_object(
        'low', r.credible_interval_low, 'high', r.credible_interval_high
      ) end,
      'deltaFromBaseline', r.delta_from_baseline,
      'state', case r.signal_status
        when 'Insufficient sample' then 'insufficient'
        when 'No significant signal' then 'ready'
        when 'Watch' then 'watch'
        when 'Possible anomaly' then 'anomaly'
      end,
      'sampleNote', case when r.signal_status = 'Insufficient sample'
        then 'Insufficient sample for a stable observed rate.'
        else format('%s observed packs across %s independent sources.', r.observed_packs, r.independent_source_count)
      end,
      'updatedAt', r.updated_at
    ) as item, r.updated_at, r.region_id
    from public.region_summaries r
    cross join dashboard_row mode_guard
    where r.is_demo = mode_guard.is_demo
    order by r.updated_at desc, r.region_id
    limit 50
  ) bounded_regions
),
retailer_rows as (
  select coalesce(jsonb_agg(item order by updated_at desc, id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'slug', r.slug,
      'name', r.name,
      'region', r.region_name,
      'channel', case r.channel when 'mass_market' then 'mass-market' else r.channel end,
      'packsObserved', r.observed_packs,
      'openings', r.complete_openings,
      'independentSources', r.independent_source_count,
      'baselineRate', r.baseline_rate,
      'hitRate', r.observed_rate,
      'posteriorMean', r.posterior_mean,
      'credibleInterval', case when r.posterior_mean is null then null else jsonb_build_object(
        'low', r.credible_interval_low, 'high', r.credible_interval_high
      ) end,
      'deltaFromBaseline', r.delta_from_baseline,
      'state', case r.signal_status
        when 'Insufficient sample' then 'insufficient'
        when 'No significant signal' then 'ready'
        when 'Watch' then 'watch'
        when 'Possible anomaly' then 'anomaly'
      end,
      'sampleNote', case when r.signal_status = 'Insufficient sample'
        then 'Insufficient sample for a stable observed rate.'
        else format('%s observed packs across %s independent sources.', r.observed_packs, r.independent_source_count)
      end,
      'updatedAt', r.updated_at
    ) as item, r.updated_at, r.id
    from public.retailer_summaries r
    cross join dashboard_row mode_guard
    where r.is_demo = mode_guard.is_demo
    order by r.updated_at desc, r.id
    limit 50
  ) bounded_retailers
),
batch_rows as (
  select coalesce(jsonb_agg(item order by last_observed_at desc, id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'code', b.batch_code,
      'setSlug', b.set_slug,
      'setName', b.set_name,
      'region', b.region_name,
      'productType', case b.product_type
        when 'booster_box' then 'Booster Box'
        when 'etb' then 'ETB'
        when 'booster_bundle' then 'Booster Bundle'
      end,
      'firstObserved', b.first_observed_at::date,
      'lastObserved', b.last_observed_at::date,
      'packsObserved', b.observed_packs,
      'openings', b.complete_openings,
      'independentSources', b.independent_source_count,
      'baselineRate', b.baseline_rate,
      'hitRate', b.observed_rate,
      'posteriorMean', b.posterior_mean,
      'credibleInterval', case when b.posterior_mean is null then null else jsonb_build_object(
        'low', b.credible_interval_low, 'high', b.credible_interval_high
      ) end,
      'deltaFromBaseline', b.delta_from_baseline,
      'state', case b.signal_status
        when 'Insufficient sample' then 'insufficient'
        when 'No significant signal' then 'ready'
        when 'Watch' then 'watch'
        when 'Possible anomaly' then 'anomaly'
      end,
      'sampleNote', case when b.signal_status = 'Insufficient sample'
        then 'Insufficient sample for a stable observed rate.'
        else format('%s observed packs across %s independent sources.', b.observed_packs, b.independent_source_count)
      end,
      'updatedAt', b.updated_at
    ) as item, b.last_observed_at, b.id
    from public.batch_summaries b
    cross join dashboard_row mode_guard
    where b.is_demo = mode_guard.is_demo
    order by b.last_observed_at desc, b.id
    limit 50
  ) bounded_batches
),
activity_rows as (
  select coalesce(jsonb_agg(item order by observed_at desc, id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'id', a.id::text,
      'observedAt', a.observed_at,
      'platform', a.platform,
      'setName', a.set_name,
      'productType', case a.product_type
        when 'booster_box' then 'Booster Box'
        when 'etb' then 'ETB'
        when 'booster_bundle' then 'Booster Bundle'
      end,
      'packCount', a.pack_count,
      'region', a.region_name,
      'retailer', a.retailer_name,
      'evidenceTier', case when a.status = 'activity_only' then 'activity-only' else a.evidence_tier end,
      'classification', case when a.statistics_eligible then 'rate-eligible' else 'activity-only' end,
      'statisticsEligible', a.statistics_eligible,
      'published', true,
      'sourceUrl', a.source_link
    ) as item, a.observed_at, a.id
    from public.recent_activity a
    cross join dashboard_row mode_guard
    where a.is_demo = mode_guard.is_demo
      and a.country_code = 'AU'
      and a.platform is not null
      and a.source_link is not null
      and a.region_name is not null
      and a.pack_count is not null
      and a.product_type in ('booster_box', 'etb', 'booster_bundle')
      and (a.status = 'activity_only' or a.evidence_tier in ('A', 'B'))
    order by a.observed_at desc, a.id
    limit 50
  ) bounded_activity
),
service_rows as (
  select coalesce(jsonb_agg(item order by checked_at desc, component_id), '[]'::jsonb) as value
  from (
    select jsonb_build_object(
      'id', s.component_id,
      'name', s.component_name,
      'status', s.status,
      'detail', coalesce(nullif(btrim(s.public_message), ''), 'No additional public detail.'),
      'checkedAt', s.checked_at
    ) as item, s.checked_at, s.component_id
    from public.system_status s
    cross join dashboard_row mode_guard
    where s.is_demo = mode_guard.is_demo
      and s.status in ('operational', 'degraded', 'maintenance')
    order by s.checked_at desc, s.component_id
    limit 50
  ) bounded_services
)
select jsonb_build_object(
  'mode', d.mode,
  'generatedAt', coalesce(d.generated_at, now()),
  'summary', jsonb_build_object(
    'observedPacks', coalesce(d.observed_packs, 0),
    'completeOpenings', coalesce(d.complete_openings, 0),
    'aiValidatedSources', coalesce(d.verified_sources, 0),
    'trackedSets', coalesce(d.tracked_sets, 0),
    'trackedRegions', coalesce(d.tracked_regions, 0),
    'batchSightings', coalesce(d.batch_sightings, 0),
    'baselineHitRate', d.baseline_hit_rate,
    'australiaCoverage', coalesce(d.australia_coverage, 'Australia coverage is currently unavailable.'),
    'methodologyVersion', left(coalesce(d.methodology_version, 'unavailable'), 80)
  ),
  'sets', sr.value,
  'regions', rr.value,
  'retailers', tr.value,
  'batches', br.value,
  'trend', '[]'::jsonb,
  'sources', '[]'::jsonb,
  'services', svr.value,
  'recentActivity', ar.value
)
from relation_guard guard
join dashboard_row d on true
cross join set_rows sr
cross join region_rows rr
cross join retailer_rows tr
cross join batch_rows br
cross join activity_rows ar
cross join service_rows svr
where guard.safe_row_count >= 0
  and d.mode in ('demo', 'live');
$$;

revoke all on function public.get_public_dashboard_snapshot_v1() from public, anon, authenticated;
grant execute on function public.get_public_dashboard_snapshot_v1() to anon, authenticated;
comment on function public.get_public_dashboard_snapshot_v1() is 'Exact strict Web publicDashboardDataSchema payload assembled only from nine RLS-protected public relations; every list is capped at 50 rows.';

create or replace function ingest.prune_expired_ephemera(
  cutoff timestamptz default now(),
  max_rows integer default 10000
)
returns jsonb
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  excerpt_count integer := 0;
  extraction_count integer := 0;
  signal_count integer := 0;
begin
  if cutoff is null then
    raise exception using errcode = '22023', message = 'cutoff must not be null';
  end if;
  if max_rows is null or max_rows < 1 or max_rows > 100000 then
    raise exception using errcode = '22023', message = 'max_rows must be between 1 and 100000';
  end if;

  with candidates as materialized (
    select s.id
    from ingest.source_items s
    where s.expires_at <= cutoff and s.text_excerpt is not null
    order by s.expires_at, s.id
    for update of s skip locked
    limit max_rows
  )
  update ingest.source_items s
  set text_excerpt = null, updated_at = clock_timestamp()
  from candidates c
  where s.id = c.id;
  get diagnostics excerpt_count = row_count;

  with candidates as materialized (
    select r.id
    from ingest.extraction_runs r
    where r.expires_at <= cutoff
      and not exists (select 1 from ingest.openings o where o.extraction_run_id = r.id)
    order by r.expires_at, r.id
    for update of r skip locked
    limit max_rows
  )
  delete from ingest.extraction_runs r
  using candidates c
  where r.id = c.id;
  get diagnostics extraction_count = row_count;

  with candidates as materialized (
    select s.id
    from analytics.signals s
    where s.expires_at <= cutoff
    order by s.expires_at, s.id
    for update of s skip locked
    limit max_rows
  )
  delete from analytics.signals s
  using candidates c
  where s.id = c.id;
  get diagnostics signal_count = row_count;

  return jsonb_build_object(
    'source_excerpts_cleared', excerpt_count,
    'extraction_runs_deleted', extraction_count,
    'signals_deleted', signal_count,
    'openings_deleted', 0
  );
end;
$$;

revoke all on function ingest.prune_expired_ephemera(timestamptz, integer) from public, anon, authenticated;
grant execute on function ingest.prune_expired_ephemera(timestamptz, integer) to service_role;
comment on function ingest.prune_expired_ephemera(timestamptz, integer) is 'Bounded cleanup for expired source excerpts, unreferenced extraction runs, and expired signals. Core openings are never deleted.';

-- Reassert default-deny after every object exists. PUBLIC is the PostgreSQL
-- pseudo-role; anon/authenticated receive only the explicit safe reads below.
revoke all on schema catalog, ingest, analytics from public, anon, authenticated;
revoke create on schema public from public, anon, authenticated;
grant usage on schema public to anon, authenticated, service_role;
grant usage on schema catalog, ingest, analytics to service_role;

revoke all on all tables in schema catalog, ingest, analytics from public, anon, authenticated;
revoke all on all sequences in schema catalog, ingest, analytics from public, anon, authenticated;
revoke all on all functions in schema catalog, ingest, analytics from public, anon, authenticated;
revoke all on all tables in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
revoke all on all functions in schema public from public, anon, authenticated;

alter default privileges in schema catalog revoke all on tables from public, anon, authenticated;
alter default privileges in schema ingest revoke all on tables from public, anon, authenticated;
alter default privileges in schema analytics revoke all on tables from public, anon, authenticated;
alter default privileges in schema public revoke all on tables from public, anon, authenticated;
alter default privileges in schema catalog revoke all on sequences from public, anon, authenticated;
alter default privileges in schema ingest revoke all on sequences from public, anon, authenticated;
alter default privileges in schema analytics revoke all on sequences from public, anon, authenticated;
alter default privileges in schema public revoke all on sequences from public, anon, authenticated;
alter default privileges in schema catalog revoke execute on functions from public, anon, authenticated;
alter default privileges in schema ingest revoke execute on functions from public, anon, authenticated;
alter default privileges in schema analytics revoke execute on functions from public, anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;

revoke all on function ingest.claim_jobs(text, text[], integer, integer) from public, anon, authenticated;
grant execute on function ingest.claim_jobs(text, text[], integer, integer) to service_role;
grant execute on function ingest.prune_expired_ephemera(timestamptz, integer) to service_role;
grant execute on function public.get_public_dashboard_snapshot_v1() to anon, authenticated;

grant select on public.dashboard_overview, public.set_summaries, public.region_summaries,
  public.retailer_summaries, public.batch_summaries, public.recent_activity,
  public.public_signals, public.data_freshness, public.system_status
  to anon, authenticated;
grant select, insert, update, delete on public.dashboard_overview, public.set_summaries,
  public.region_summaries, public.retailer_summaries, public.batch_summaries,
  public.recent_activity, public.public_signals, public.data_freshness, public.system_status
  to service_role;

commit;
