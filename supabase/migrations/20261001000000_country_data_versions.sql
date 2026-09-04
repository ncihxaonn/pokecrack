begin;

-- Add a human-readable, source-native data version to every published country
-- coverage row. Existing reviewed studies predate explicit language/name keys,
-- so they safely default to the English catalog contract they were validated
-- against. Future reviewed contracts may provide set_language and set_name
-- without changing this public JSON shape.
create or replace function public.get_public_study_coverage_v2()
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
    contracts.policy_key,
    contracts.public_id,
    contracts.public_name,
    contracts.public_note,
    contracts.display_name,
    contracts.domain,
    contracts.canonical_url,
    contracts.policy_version,
    contracts.config,
    policies.id as policy_id,
    policies.enabled,
    policies.last_failure_at,
    studies.source_observed_at as study_observed_at,
    studies.pack_count as study_pack_count,
    studies.set_external_id as study_set_external_id,
    studies.product_scope as study_product_scope,
    studies.collector_version as study_collector_version,
    studies.parser_version as study_parser_version,
    studies.source_policy_version as study_policy_version,
    studies.evidence_sha256 as study_evidence_sha256,
    studies.last_verified_at as study_last_verified_at,
    studies.qualifying_hit_pack_count as study_hit_count,
    studies.metric_key as study_metric_key,
    studies.metric_version as study_metric_version,
    studies.is_demo as study_is_demo,
    coverage.source_observed_at as coverage_observed_at,
    coverage.pack_count as coverage_pack_count,
    coverage.set_external_id as coverage_set_external_id,
    coverage.product_scope as coverage_product_scope,
    coverage.collector_version as coverage_collector_version,
    coverage.parser_version as coverage_parser_version,
    coverage.source_policy_version as coverage_policy_version,
    coverage.evidence_sha256 as coverage_evidence_sha256,
    coverage.last_verified_at as coverage_last_verified_at,
    coverage.is_demo as coverage_is_demo,
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
      studies.study_key = contracts.study_key
      and studies.source_policy_id = policies.id
      and studies.country_code = contracts.config ->> 'country_code'
      and studies.country_name = contracts.config ->> 'country_name'
      and studies.source_observed_at
        = (contracts.config ->> 'observed_at')::timestamptz
      and studies.pack_count = (contracts.config ->> 'pack_count')::integer
      and studies.qualifying_hit_pack_count
        = (contracts.config ->> 'qualifying_hit_pack_count')::integer
      and studies.set_external_id = contracts.config ->> 'set_external_id'
      and studies.product_scope = contracts.config ->> 'product_scope'
      and studies.metric_key = 'qualifying_hit_pack_rate'
      and studies.metric_version = 'global-sir-v1'
      and studies.collector_version = contracts.config ->> 'collector_version'
      and studies.parser_version = contracts.config ->> 'parser_version'
      and studies.source_policy_version = contracts.policy_version
      and studies.evidence_sha256 = encode(
        extensions.digest(convert_to(contracts.evidence_excerpt, 'UTF8'), 'sha256'),
        'hex'
      )
      and not studies.is_demo
      and exists (
        select 1
        from ingest.openings as openings
        where openings.id = studies.opening_id
          and openings.eligible_for_statistics
          and openings.complete_opening
          and openings.validation_status = 'accepted'
          and openings.public_status = 'verified'
          and openings.duplicate_of is null
          and not openings.duplicate_suspected
          and not openings.is_demo
      ),
      false
    ) as study_valid,
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
      and contracts.config ->> 'denominator_complete' = 'true'
      and not coverage.is_demo,
      false
    ) as coverage_valid
  from ingest.reviewed_public_study_contracts() as contracts
  left join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key
    and not policies.is_demo
  left join ingest.public_study_observations as studies
    on studies.study_key = contracts.study_key
  left join ingest.public_study_coverage_observations as coverage
    on coverage.study_key = contracts.study_key
),
valid_rows as (
  select
    reviewed.ordinal,
    reviewed.study_key,
    reviewed.public_id,
    reviewed.public_name,
    reviewed.public_note,
    reviewed.domain,
    reviewed.canonical_url,
    reviewed.config ->> 'country_code' as country_code,
    reviewed.config ->> 'country_name' as country_name,
    coalesce(nullif(reviewed.config ->> 'set_language', ''), 'en')
      as set_language,
    nullif(reviewed.config ->> 'set_name', '') as configured_set_name,
    case when reviewed.study_valid then reviewed.study_observed_at
      else reviewed.coverage_observed_at end as source_observed_at,
    case when reviewed.study_valid then reviewed.study_pack_count
      else reviewed.coverage_pack_count end as pack_count,
    case when reviewed.study_valid then reviewed.study_set_external_id
      else reviewed.coverage_set_external_id end as set_external_id,
    case when reviewed.study_valid then reviewed.study_product_scope
      else reviewed.coverage_product_scope end as product_scope,
    case when reviewed.study_valid then reviewed.study_last_verified_at
      else reviewed.coverage_last_verified_at end as last_verified_at
  from reviewed
  cross join selected_period as period
  where reviewed.policy_valid
    and (reviewed.study_valid or reviewed.coverage_valid)
    and exists (
      select 1
      from catalog.iso_alpha2_codes as iso_codes
      where iso_codes.code = reviewed.config ->> 'country_code'
    )
    and (
      (case when reviewed.study_valid then reviewed.study_observed_at
        else reviewed.coverage_observed_at end) at time zone 'UTC'
    )::date between period.period_start and period.period_end
    and (case when reviewed.study_valid then reviewed.study_observed_at
      else reviewed.coverage_observed_at end) <= statement_timestamp()
),
data_version_rows as (
  select distinct
    rows.country_code,
    left(
      concat_ws(
        ' · ',
        case
          when rows.set_language ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$'
            then rows.set_language
          else 'und'
        end,
        rows.set_external_id,
        coalesce(
          rows.configured_set_name,
          catalog_sets.name,
          rows.set_external_id
        ),
        case rows.product_scope
          when 'booster_box' then 'booster box'
          when 'booster_bundle' then 'booster bundle'
          when 'etb' then 'ETB'
          when 'all' then 'all products'
          else replace(rows.product_scope, '_', ' ')
        end
      ),
      240
    ) as data_version
  from valid_rows as rows
  left join catalog.sets as catalog_sets
    on catalog_sets.external_source = 'tcgdex'
    and catalog_sets.external_id = rows.set_external_id
    and catalog_sets.language = rows.set_language
    and catalog_sets.is_active
    and not catalog_sets.is_demo
),
country_data_versions as (
  select
    rows.country_code,
    jsonb_agg(rows.data_version order by rows.data_version) as value
  from data_version_rows as rows
  group by rows.country_code
),
source_coverage as (
  select
    rows.public_id,
    sum(rows.pack_count)::bigint as packs_observed,
    count(distinct rows.country_code)::integer as countries_observed,
    count(*)::bigint as complete_openings
  from valid_rows as rows
  group by rows.public_id
),
countries as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'countryCode', rows.country_code,
        'countryName', rows.country_name,
        'dataVersions', versions.value,
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
      rows.country_code,
      min(rows.country_name) as country_name,
      sum(rows.pack_count)::bigint as packs_observed,
      count(*)::bigint as openings,
      count(distinct rows.domain)::integer as independent_sources,
      max(rows.last_verified_at) as updated_at
    from valid_rows as rows
    group by rows.country_code
  ) as rows
  join country_data_versions as versions
    on versions.country_code = rows.country_code
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
      sum(rows.pack_count)::bigint as packs_observed,
      count(*)::bigint as openings,
      count(distinct rows.domain)::integer as independent_sources,
      max(rows.last_verified_at) as updated_at
    from valid_rows as rows
    join catalog.sets as catalog_sets
      on catalog_sets.external_source = 'tcgdex'
      and catalog_sets.external_id = rows.set_external_id
      and catalog_sets.language = rows.set_language
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
          when not (reviewed.study_valid or reviewed.coverage_valid)
            then 'attention'
          when reviewed.last_failure_at is not null
            and reviewed.last_failure_at > case
              when reviewed.study_valid then reviewed.study_last_verified_at
              when reviewed.coverage_valid then reviewed.coverage_last_verified_at
              else '-infinity'::timestamptz
            end then 'attention'
          when case
              when reviewed.study_valid then reviewed.study_last_verified_at
              when reviewed.coverage_valid then reviewed.coverage_last_verified_at
              else null
            end < statement_timestamp() - interval '48 hours' then 'delayed'
          else 'operational'
        end,
        'lastCollectedAt', case
          when reviewed.study_valid then reviewed.study_last_verified_at
          when reviewed.coverage_valid then reviewed.coverage_last_verified_at
          else null
        end,
        'url', reviewed.canonical_url,
        'note', reviewed.public_note
      ) || case
        when source_coverage.public_id is null then '{}'::jsonb
        else jsonb_build_object(
          'coverage', jsonb_build_object(
            'packsObserved', source_coverage.packs_observed,
            'countriesObserved', source_coverage.countries_observed,
            'completeOpenings', source_coverage.complete_openings
          )
        )
      end order by reviewed.ordinal
    ),
    '[]'::jsonb
  ) as value
  from reviewed
  left join source_coverage
    on source_coverage.public_id = reviewed.public_id
)
select jsonb_build_object(
  'schemaVersion', '2.0.0',
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

alter function public.get_public_study_coverage_v2() owner to postgres;
revoke all on function public.get_public_study_coverage_v2()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_study_coverage_v2()
  to anon, authenticated;

comment on function public.get_public_study_coverage_v2() is
  'Registry-driven denominator-safe coverage with per-country source-native language, set, and product data versions; never returns evidence, numerator, policy, job, gate, or inference fields.';

commit;
