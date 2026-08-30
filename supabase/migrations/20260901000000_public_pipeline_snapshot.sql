begin;

-- v2 deliberately reads only browser-visible projections. v3 keeps that
-- contract as its base, then adds bounded summaries from three exact private
-- operational sources. No caller input, raw evidence, discovery identity,
-- worker identity, job payload, provider error, or policy URL is returned.
create or replace function public.get_public_dashboard_snapshot_v3()
returns jsonb
language sql
stable
security definer
parallel restricted
set search_path = pg_catalog
as $$
with raw_base_snapshot as materialized (
  select public.get_public_dashboard_snapshot_v2() as value
),
base_snapshot as materialized (
  select case
    when (raw.value #>> '{observations,period,end}')::date is null
      or (raw.value #>> '{observations,period,end}')::date
        = (statement_timestamp() at time zone 'UTC')::date
      then raw.value
    else jsonb_set(
      jsonb_set(
        jsonb_set(
          raw.value,
          '{summary}',
          jsonb_build_object(
            'observedPacks', 0,
            'completeOpenings', 0,
            'aiValidatedSources', 0,
            'trackedSets', 0,
            'trackedRegions', 0,
            'batchSightings', 0,
            'baselineHitRate', null,
            'globalCoverage',
              'No verified current-period country observations are published yet.',
            'methodologyVersion', 'global-observation-v1'
          ),
          true
        ),
        '{observations}',
        jsonb_build_object(
          'status', 'empty',
          'period', null,
          'observedPacks', 0,
          'completeOpenings', 0,
          'independentSources', null,
          'sourceCountryContributions', 0,
          'countriesObserved', 0,
          'countriesWithPublishedRate', 0,
          'asOf', null,
          'methodologyVersion', null,
          'minimumPacks', 30,
          'minimumSources', 3,
          'watchMinimumPacks', 200,
          'metricKey', 'qualifying_hit_pack_rate'
        ),
        true
      ),
      '{mapCells}',
      '[]'::jsonb,
      true
    )
  end as value
  from raw_base_snapshot as raw
),
selected_period as (
  select
    (statement_timestamp() at time zone 'UTC')::date - 364 as period_start,
    (statement_timestamp() at time zone 'UTC')::date as period_end
),
source_definitions (
  ordinal,
  source_key,
  public_id,
  public_name,
  public_kind,
  public_access,
  public_url,
  expected_display_name,
  expected_source_kind,
  expected_domain,
  expected_base_url,
  expected_collector_type,
  expected_access_mode,
  expected_robots_policy,
  expected_routes,
  expected_include_subdomains,
  expected_min_delay_seconds,
  expected_max_pages_per_run,
  expected_max_items_per_run,
  expected_max_concurrency,
  expected_browser_profile,
  expected_statistics_eligible_default,
  expected_retention_days,
  expected_config_sha256,
  expected_version,
  expected_study_key,
  expected_interval_seconds,
  public_note
) as (
  values
    (
      1,
      'youtube_discovery'::text,
      'youtube_discovery'::text,
      'YouTube global discovery'::text,
      'video'::text,
      'api-key'::text,
      'https://developers.google.com/youtube/v3/docs/search/list'::text,
      'YouTube Global Discovery API'::text,
      'official_api'::text,
      'youtube.googleapis.com'::text,
      'https://youtube.googleapis.com/youtube/v3'::text,
      'official_api'::text,
      'official_api'::text,
      'not_applicable'::text,
      array['official_api']::text[],
      false,
      2,
      1,
      25,
      1,
      null::text,
      false,
      28,
      '69aa4c7dd29ab4fdaf97f08c310f39b2cb44bdebd345650daa6c0e0a9f53935d'::text,
      'youtube-global-discovery-v1'::text,
      null::text,
      21600,
      'Discovery metadata only; never used as opening evidence, geography, a hit, or a pull-rate denominator.'::text
    ),
    (
      2,
      'public_study_comicbook_us_55',
      'comicbook_perfect_order_study',
      'ComicBook Perfect Order study',
      'community',
      'public',
      'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
      'ComicBook Perfect Order 55-pack study',
      'public_web',
      'comicbook.com',
      'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
      'scrapling_http',
      'public',
      'respect',
      array['scrapling_http']::text[],
      false,
      30,
      2,
      1,
      1,
      null,
      true,
      730,
      'f326acc375651e94f212d57f355ad642048737aa3de0a63f66258224053f800c',
      'public-study-comicbook-perfect-order-v1',
      'comicbook-perfect-order-us-55-v1',
      86400,
      'Reviewed 55-pack public study attributed to the United States; one independent source, so its rate remains withheld.'
    ),
    (
      3,
      'public_study_wargamer_gb_17',
      'wargamer_chaos_rising_study',
      'Wargamer Chaos Rising study',
      'community',
      'public',
      'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
      'Wargamer Chaos Rising 17-pack study',
      'public_web',
      'www.wargamer.com',
      'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
      'scrapling_http',
      'public',
      'respect',
      array['scrapling_http']::text[],
      false,
      30,
      2,
      1,
      1,
      null,
      true,
      730,
      'df7c3c8591222704f7ee66ee8108fcd0527bb8e1aab5696e58f2e4287f615c7c',
      'public-study-wargamer-chaos-rising-v1',
      'wargamer-chaos-rising-gb-17-v1',
      86400,
      'Reviewed 17-pack public study attributed to the United Kingdom; one independent source, so its rate remains withheld.'
    )
),
policy_state as (
  select
    definitions.*,
    policies.id as source_policy_id,
    policies.enabled,
    policies.display_name,
    policies.source_kind,
    policies.domain,
    policies.base_url,
    policies.collector_type,
    policies.access_mode,
    policies.robots_policy,
    policies.routes,
    policies.include_subdomains,
    policies.min_delay_seconds,
    policies.max_pages_per_run,
    policies.max_items_per_run,
    policies.max_concurrency,
    policies.browser_profile,
    policies.statistics_eligible_default,
    policies.retention_days,
    policies.version,
    policies.expected_interval_seconds as policy_interval_seconds,
    policies.last_success_at,
    policies.last_failure_at,
    coalesce(
      policies.display_name is not distinct from definitions.expected_display_name
      and policies.source_kind is not distinct from definitions.expected_source_kind
      and policies.domain is not distinct from definitions.expected_domain
      and policies.base_url is not distinct from definitions.expected_base_url
      and policies.collector_type is not distinct from definitions.expected_collector_type
      and policies.access_mode is not distinct from definitions.expected_access_mode
      and policies.robots_policy is not distinct from definitions.expected_robots_policy
      and policies.routes is not distinct from definitions.expected_routes
      and policies.include_subdomains is not distinct from definitions.expected_include_subdomains
      and policies.min_delay_seconds is not distinct from definitions.expected_min_delay_seconds
      and policies.max_pages_per_run is not distinct from definitions.expected_max_pages_per_run
      and policies.max_items_per_run is not distinct from definitions.expected_max_items_per_run
      and policies.max_concurrency is not distinct from definitions.expected_max_concurrency
      and policies.browser_profile is not distinct from definitions.expected_browser_profile
      and policies.statistics_eligible_default is not distinct from definitions.expected_statistics_eligible_default
      and policies.retention_days is not distinct from definitions.expected_retention_days
      and encode(
        extensions.digest(policies.config::text, 'sha256'),
        'hex'
      ) is not distinct from definitions.expected_config_sha256
      and policies.version is not distinct from definitions.expected_version
      and policies.expected_interval_seconds is not distinct from definitions.expected_interval_seconds,
      false
    ) as policy_contract_valid
  from source_definitions as definitions
  left join ingest.source_policies as policies
    on policies.source_key = definitions.source_key
    and not policies.is_demo
),
youtube_cache_freshness as (
  select
    count(*)::bigint as current_record_count,
    max(discoveries.last_seen_at) as last_seen_at
  from ingest.youtube_discoveries as discoveries
  join policy_state as policies
    on policies.source_policy_id = discoveries.source_policy_id
  where policies.source_key = 'youtube_discovery'
    and policies.enabled
    and policies.policy_contract_valid
    and not discoveries.is_demo
    and discoveries.expires_at > statement_timestamp()
),
study_freshness as (
  select
    policies.source_key,
    max(observations.last_verified_at) as last_verified_at
  from ingest.public_study_observations as observations
  join policy_state as policies
    on policies.source_policy_id = observations.source_policy_id
    and policies.expected_study_key = observations.study_key
  where policies.expected_study_key is not null
    and policies.enabled
    and policies.policy_contract_valid
    and not observations.is_demo
  group by policies.source_key
),
source_state as (
  select
    policies.*,
    case
      when policies.policy_contract_valid then greatest(
        policies.last_success_at,
        case
          when policies.source_key = 'youtube_discovery'
            then youtube.last_seen_at
          else studies.last_verified_at
        end
      )
      else null
    end as last_collected_at,
    coalesce(youtube.current_record_count, 0) as youtube_record_count
  from policy_state as policies
  left join youtube_cache_freshness as youtube
    on policies.source_key = 'youtube_discovery'
  left join study_freshness as studies
    on studies.source_key = policies.source_key
),
public_source_rows as (
  select
    state.ordinal,
    jsonb_build_object(
      'id', state.public_id,
      'name', state.public_name,
      'kind', state.public_kind,
      'access', state.public_access,
      'status', case
        when not state.policy_contract_valid then 'attention'
        when not state.enabled then 'paused'
        when state.last_failure_at is not null
          and state.last_failure_at > coalesce(
            state.last_collected_at,
            '-infinity'::timestamptz
          )
          then 'attention'
        when state.last_collected_at is null then 'attention'
        when state.last_collected_at < statement_timestamp()
          - (state.expected_interval_seconds * interval '2 seconds')
          then 'delayed'
        else 'operational'
      end,
      'lastCollectedAt', state.last_collected_at,
      'url', state.public_url,
      'note', case
        when state.source_key = 'youtube_discovery'
          then format(
            '%s current metadata record%s. %s',
            state.youtube_record_count,
            case when state.youtube_record_count = 1 then '' else 's' end,
            state.public_note
          )
        else state.public_note
      end
    ) as item
  from source_state as state
),
public_sources as (
  select coalesce(
    jsonb_agg(rows.item order by rows.ordinal),
    '[]'::jsonb
  ) as value
  from public_source_rows as rows
),
service_definitions (
  ordinal,
  worker_type,
  public_id,
  public_name,
  operational_detail,
  degraded_detail
) as (
  values
    (
      1,
      'collector'::text,
      'collector'::text,
      'Collection worker'::text,
      'Collector heartbeat received within the last five minutes.'::text,
      'No recent collector heartbeat is available.'::text
    ),
    (
      2,
      'scheduler',
      'scheduler',
      'Collection scheduler',
      'Scheduler heartbeat received within the last five minutes.',
      'No recent scheduler heartbeat is available.'
    ),
    (
      3,
      'watchdog',
      'watchdog',
      'Retention watchdog',
      'Watchdog heartbeat received within the last five minutes.',
      'No recent watchdog heartbeat is available.'
    )
),
service_heartbeats as (
  select
    heartbeats.worker_type,
    max(heartbeats.last_seen_at) as last_seen_at
  from ingest.worker_heartbeats as heartbeats
  where heartbeats.worker_type in ('collector', 'scheduler', 'watchdog')
    and not heartbeats.is_demo
  group by heartbeats.worker_type
),
public_services as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', definitions.public_id,
        'name', definitions.public_name,
        'status', case
          when heartbeats.last_seen_at >= statement_timestamp() - interval '5 minutes'
            then 'operational'
          else 'degraded'
        end,
        'detail', case
          when heartbeats.last_seen_at >= statement_timestamp() - interval '5 minutes'
            then definitions.operational_detail
          else definitions.degraded_detail
        end,
        'checkedAt', coalesce(
          heartbeats.last_seen_at,
          statement_timestamp()
        )
      )
      order by definitions.ordinal
    ),
    '[]'::jsonb
  ) as value
  from service_definitions as definitions
  left join service_heartbeats as heartbeats
    on heartbeats.worker_type = definitions.worker_type
),
reviewed_country_metrics as (
  select
    observations.country_code,
    observations.country_name,
    period.period_start,
    period.period_end,
    sum(observations.pack_count)::bigint as observed_packs,
    count(*)::bigint as complete_openings,
    count(distinct sources.domain)::integer as independent_sources,
    max(observations.last_verified_at) as updated_at
  from ingest.public_study_observations as observations
  join source_state as sources
    on sources.source_policy_id = observations.source_policy_id
    and sources.source_key in (
      'public_study_comicbook_us_55',
      'public_study_wargamer_gb_17'
    )
  cross join selected_period as period
  where not observations.is_demo
    and sources.enabled
    and sources.policy_contract_valid
    and observations.study_key = sources.expected_study_key
    and observations.collector_version = sources.expected_version
    and observations.source_policy_version = sources.expected_version
    and observations.metric_key = 'qualifying_hit_pack_rate'
    and observations.metric_version = 'global-sir-v1'
    and observations.product_scope = 'all'
    and (observations.source_observed_at at time zone 'UTC')::date
      between period.period_start and period.period_end
  group by
    observations.country_code,
    observations.country_name,
    period.period_start,
    period.period_end
  order by observations.country_name, observations.country_code
  limit 249
),
reviewed_map_rows as (
  select
    rows.country_code,
    2 as priority,
    jsonb_build_object(
      'countryCode', rows.country_code,
      'countryName', rows.country_name,
      'periodStart', rows.period_start,
      'periodEnd', rows.period_end,
      'setScope', 'all',
      'productScope', 'all',
      'metricKey', 'qualifying_hit_pack_rate',
      'metricVersion', 'global-sir-v1',
      'packsObserved', rows.observed_packs,
      'openings', rows.complete_openings,
      'independentSources', rows.independent_sources,
      'baselineRate', null,
      'hitRate', null,
      'posteriorMean', null,
      'credibleInterval', null,
      'deltaFromBaseline', null,
      'state', case
        when rows.observed_packs < 30 or rows.independent_sources < 3
          then 'insufficient'
        else 'pending'
      end,
      'sampleNote', case
        when rows.observed_packs < 30 or rows.independent_sources < 3
          then format(
            'Rate withheld: %s observed packs across %s independent source%s. Publication requires at least 30 packs and three sources.',
            rows.observed_packs,
            rows.independent_sources,
            case when rows.independent_sources = 1 then '' else 's' end
          )
        else 'The evidence threshold is met, but the reviewed baseline and interval publisher has not completed; all inference fields remain withheld.'
      end,
      'methodologyVersion', 'global-observation-v1',
      'updatedAt', rows.updated_at
    ) as item
  from reviewed_country_metrics as rows
),
base_map_rows as (
  select
    cells.item ->> 'countryCode' as country_code,
    case when cells.item -> 'hitRate' = 'null'::jsonb then 1 else 3 end as priority,
    cells.item
  from base_snapshot as base
  cross join lateral jsonb_array_elements(base.value -> 'mapCells') as cells(item)
),
selected_map_rows as (
  select distinct on (candidates.country_code)
    candidates.country_code,
    candidates.item
  from (
    select base.country_code, base.priority, base.item
    from base_map_rows as base
    union all
    select reviewed.country_code, reviewed.priority, reviewed.item
    from reviewed_map_rows as reviewed
  ) as candidates
  where candidates.country_code is not null
  order by candidates.country_code, candidates.priority desc
),
public_map_snapshot as (
  select
    coalesce(
      jsonb_agg(rows.item order by rows.item ->> 'countryName', rows.country_code),
      '[]'::jsonb
    ) as value,
    count(*)::integer as country_count,
    count(*) filter (
      where rows.item -> 'hitRate' <> 'null'::jsonb
    )::integer as published_rate_count,
    coalesce(sum((rows.item ->> 'packsObserved')::bigint), 0)::bigint
      as observed_packs,
    coalesce(sum((rows.item ->> 'openings')::bigint), 0)::bigint
      as complete_openings,
    coalesce(sum((rows.item ->> 'independentSources')::bigint), 0)::bigint
      as source_country_contributions,
    max((rows.item ->> 'updatedAt')::timestamptz) as as_of,
    case
      when count(distinct rows.item ->> 'methodologyVersion') = 1
        then min(rows.item ->> 'methodologyVersion')
      else null
    end as methodology_version
  from selected_map_rows as rows
),
reviewed_set_metrics as (
  -- The denominator never disappears. Once both evidence thresholds are met,
  -- an explicit pending state keeps the row visible while every inference
  -- field remains withheld until the reviewed publisher supplies it.
  select
    sets.slug,
    sets.name,
    sets.series_name,
    sets.release_date,
    sum(observations.pack_count)::bigint as observed_packs,
    count(*)::bigint as complete_openings,
    count(distinct sources.domain)::integer as independent_sources,
    max(observations.last_verified_at) as updated_at
  from ingest.public_study_observations as observations
  join source_state as sources
    on sources.source_policy_id = observations.source_policy_id
    and sources.source_key in (
      'public_study_comicbook_us_55',
      'public_study_wargamer_gb_17'
    )
  join catalog.sets as sets
    on sets.external_source = 'tcgdex'
    and sets.external_id = observations.set_external_id
    and sets.language = 'en'
    and sets.is_active
    and not sets.is_demo
  cross join selected_period as period
  where not observations.is_demo
    and sources.enabled
    and sources.policy_contract_valid
    and observations.study_key = sources.expected_study_key
    and observations.collector_version = sources.expected_version
    and observations.source_policy_version = sources.expected_version
    and observations.metric_key = 'qualifying_hit_pack_rate'
    and observations.metric_version = 'global-sir-v1'
    and observations.product_scope = 'all'
    and sets.series_name is not null
    and sets.release_date is not null
    and period.period_start is not null
    and period.period_end is not null
    and (observations.source_observed_at at time zone 'UTC')::date
      between period.period_start and period.period_end
  group by sets.slug, sets.name, sets.series_name, sets.release_date
  order by sets.release_date desc, sets.name, sets.slug
  limit 100
),
public_sets as (
  select
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'slug', rows.slug,
          'name', rows.name,
          'series', rows.series_name,
          'releaseDate', rows.release_date,
          'signal', case
            when rows.observed_packs < 30 or rows.independent_sources < 3
              then 'Rate withheld; the publication threshold is not met.'
            else 'Publication pending; the reviewed baseline and interval are not available yet.'
          end,
          'packsObserved', rows.observed_packs,
          'openings', rows.complete_openings,
          'independentSources', rows.independent_sources,
          'baselineRate', null,
          'hitRate', null,
          'posteriorMean', null,
          'credibleInterval', null,
          'deltaFromBaseline', null,
          'state', case
            when rows.observed_packs < 30 or rows.independent_sources < 3
              then 'insufficient'
            else 'pending'
          end,
          'sampleNote', case
            when rows.observed_packs < 30 or rows.independent_sources < 3
              then format(
                'Rate withheld: %s observed packs across %s independent source%s. Publication requires at least 30 packs and three sources.',
                rows.observed_packs,
                rows.independent_sources,
                case when rows.independent_sources = 1 then '' else 's' end
              )
            else 'The evidence threshold is met, but the reviewed baseline and interval publisher has not completed; all inference fields remain withheld.'
          end,
          'updatedAt', rows.updated_at
        )
        order by rows.release_date desc, rows.name, rows.slug
      ),
      '[]'::jsonb
    ) as value,
    count(*)::integer as row_count
  from reviewed_set_metrics as rows
),
public_regions as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'slug', lower(cells.item ->> 'countryCode'),
        'name', cells.item ->> 'countryName',
        'countryCode', cells.item ->> 'countryCode',
        'coverage', format(
          '%s observed packs from %s independent source%s in the current global period.',
          cells.item ->> 'packsObserved',
          cells.item ->> 'independentSources',
          case
            when (cells.item ->> 'independentSources')::integer = 1 then ''
            else 's'
          end
        ),
        'packsObserved', cells.item -> 'packsObserved',
        'openings', cells.item -> 'openings',
        'independentSources', cells.item -> 'independentSources',
        'baselineRate', cells.item -> 'baselineRate',
        'hitRate', cells.item -> 'hitRate',
        'posteriorMean', cells.item -> 'posteriorMean',
        'credibleInterval', cells.item -> 'credibleInterval',
        'deltaFromBaseline', cells.item -> 'deltaFromBaseline',
        'state', cells.item ->> 'state',
        'sampleNote', cells.item ->> 'sampleNote',
        'updatedAt', cells.item ->> 'updatedAt'
      )
      order by cells.ordinality
    ),
    '[]'::jsonb
  ) as value
  from public_map_snapshot as map
  cross join lateral jsonb_array_elements(map.value)
    with ordinality as cells(item, ordinality)
),
observation_snapshot as (
  select
    jsonb_set(
      jsonb_set(
        jsonb_set(
          jsonb_set(
            base.value,
            '{generatedAt}',
            to_jsonb(statement_timestamp()),
            true
          ),
          '{summary}',
          jsonb_build_object(
            'observedPacks', map.observed_packs,
            'completeOpenings', map.complete_openings,
            'aiValidatedSources', 0,
            'trackedSets', sets.row_count,
            'trackedRegions', map.country_count,
            'batchSightings', 0,
            'baselineHitRate', null,
            'globalCoverage', case
              when map.country_count = 0
                then 'No verified current-period country observations are published yet.'
              else format(
                '%s countries have verified observations in the current global period; %s publish a rate.',
                map.country_count,
                map.published_rate_count
              )
            end,
            'methodologyVersion', coalesce(
              map.methodology_version,
              'global-observation-v1'
            )
          ),
          true
        ),
        '{observations}',
        jsonb_build_object(
          'status', case
            when map.country_count = 0 then 'empty'
            when map.published_rate_count = 0 then 'collecting'
            else 'published'
          end,
          'period', case
            when map.country_count = 0 then null
            else jsonb_build_object(
              'start', period.period_start,
              'end', period.period_end
            )
          end,
          'observedPacks', map.observed_packs,
          'completeOpenings', map.complete_openings,
          'independentSources', null,
          'sourceCountryContributions', map.source_country_contributions,
          'countriesObserved', map.country_count,
          'countriesWithPublishedRate', map.published_rate_count,
          'asOf', map.as_of,
          'methodologyVersion', map.methodology_version,
          'minimumPacks', 30,
          'minimumSources', 3,
          'watchMinimumPacks', 200,
          'metricKey', 'qualifying_hit_pack_rate'
        ),
        true
      ),
      '{mapCells}',
      map.value,
      true
    ) as value
  from base_snapshot as base
  cross join selected_period as period
  cross join public_map_snapshot as map
  cross join public_sets as sets
),
assembled as (
  select
    jsonb_set(
      jsonb_set(
        jsonb_set(
          jsonb_set(
            snapshot.value,
            '{sets}',
            sets.value,
            true
          ),
          '{regions}',
          regions.value,
          true
        ),
        '{sources}',
        coalesce(snapshot.value -> 'sources', '[]'::jsonb) || sources.value,
        true
      ),
      '{services}',
      services.value,
      true
    ) as value
  from observation_snapshot as snapshot
  cross join public_sets as sets
  cross join public_regions as regions
  cross join public_sources as sources
  cross join public_services as services
)
select assembled.value
from assembled;
$$;

alter function public.get_public_dashboard_snapshot_v3() owner to postgres;
revoke all on function public.get_public_dashboard_snapshot_v3()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_dashboard_snapshot_v3()
  to anon, authenticated;

comment on function public.get_public_dashboard_snapshot_v3() is
  'Bounded public pipeline snapshot: v2 catalog/published map plus exact reviewed-study set/country denominators, safe source freshness, and role-level worker heartbeats. Pending rows never expose inference fields.';

commit;
