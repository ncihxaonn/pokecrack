begin;

-- Publish direct sample arithmetic whenever a reviewed source provides both an
-- exact normalized SIR-pack numerator and its exact eligible pack denominator.
-- This projection does not publish a baseline, posterior, interval, delta, or
-- signal. Those inferential fields remain owned by the aggregate publisher and
-- its existing evidence thresholds.
create or replace function public.get_public_study_coverage_v3()
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
base as (
  select public.get_public_study_coverage_v2() as value
),
reviewed as (
  select
    contracts.study_key,
    contracts.public_id,
    contracts.display_name,
    contracts.domain,
    contracts.canonical_url,
    contracts.policy_key,
    contracts.policy_version,
    contracts.evidence_excerpt,
    contracts.config,
    policies.id as policy_id,
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
    ) as coverage_valid,
    studies.source_observed_at as study_observed_at,
    studies.pack_count as study_pack_count,
    studies.qualifying_hit_pack_count as study_hit_count,
    coverage.source_observed_at as coverage_observed_at,
    coverage.pack_count as coverage_pack_count
  from ingest.reviewed_public_study_contracts() as contracts
  left join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key
    and not policies.is_demo
  left join ingest.public_study_observations as studies
    on studies.study_key = contracts.study_key
  left join ingest.public_study_coverage_observations as coverage
    on coverage.study_key = contracts.study_key
),
rate_rows as (
  select
    reviewed.public_id,
    reviewed.domain,
    reviewed.config ->> 'country_code' as country_code,
    case when reviewed.study_valid
      then reviewed.study_pack_count
      else reviewed.coverage_pack_count
    end::bigint as pack_count,
    case when reviewed.study_valid
      then reviewed.study_hit_count
      else (reviewed.config ->> 'qualifying_hit_pack_count')::integer
    end::bigint as qualifying_hit_pack_count
  from reviewed
  cross join selected_period as period
  where reviewed.policy_valid
    and (reviewed.study_valid or reviewed.coverage_valid)
    and reviewed.config ->> 'denominator_complete' = 'true'
    and reviewed.config ->> 'qualifying_metric' = 'sir_pack'
    and reviewed.config ->> 'metric_version' = 'global-sir-v1'
    and reviewed.config ->> 'pack_count' ~ '^[1-9][0-9]{0,6}$'
    and reviewed.config ->> 'qualifying_hit_pack_count' ~ '^[0-9]{1,7}$'
    and (reviewed.config ->> 'qualifying_hit_pack_count')::bigint
      <= (reviewed.config ->> 'pack_count')::bigint
    and exists (
      select 1
      from catalog.iso_alpha2_codes as iso_codes
      where iso_codes.code = reviewed.config ->> 'country_code'
    )
    and (
      (case when reviewed.study_valid
        then reviewed.study_observed_at
        else reviewed.coverage_observed_at
      end) at time zone 'UTC'
    )::date between period.period_start and period.period_end
    and case when reviewed.study_valid
      then reviewed.study_observed_at
      else reviewed.coverage_observed_at
    end <= statement_timestamp()
),
country_rates as (
  select
    rows.country_code,
    sum(rows.pack_count)::bigint as rate_packs_observed,
    sum(rows.qualifying_hit_pack_count)::bigint as qualifying_hit_packs
  from rate_rows as rows
  group by rows.country_code
),
source_rates as (
  select
    rows.public_id,
    sum(rows.pack_count)::bigint as rate_packs_observed,
    sum(rows.qualifying_hit_pack_count)::bigint as qualifying_hit_packs
  from rate_rows as rows
  group by rows.public_id
),
countries as (
  select coalesce(
    jsonb_agg(
      case when rates.country_code is null then country.item
      else country.item || jsonb_build_object(
        'collectionClass', case
          when rates.rate_packs_observed
            = (country.item ->> 'packsObserved')::bigint
            then 'observed_sample'
          else 'mixed'
        end,
        'ratePacksObserved', rates.rate_packs_observed,
        'qualifyingHitPacks', rates.qualifying_hit_packs,
        'observedRate',
          rates.qualifying_hit_packs::numeric / rates.rate_packs_observed::numeric
      ) end
      order by country.ordinality
    ),
    '[]'::jsonb
  ) as value
  from base
  cross join lateral jsonb_array_elements(base.value -> 'countries')
    with ordinality as country(item, ordinality)
  left join country_rates as rates
    on rates.country_code = country.item ->> 'countryCode'
),
sources as (
  select coalesce(
    jsonb_agg(
      case
        when rates.public_id is null or not (source.item ? 'coverage')
          then source.item
        else jsonb_set(
          source.item || jsonb_build_object(
            'note',
            coalesce(source.item ->> 'note', '')
              || ' Exact normalized numerator and denominator are available. The observed sample rate is descriptive; baseline, posterior, interval, delta, and signal remain separately gated.'
          ),
          '{coverage}',
          source.item -> 'coverage' || jsonb_build_object(
            'ratePacksObserved', rates.rate_packs_observed,
            'qualifyingHitPacks', rates.qualifying_hit_packs,
            'observedRate',
              rates.qualifying_hit_packs::numeric / rates.rate_packs_observed::numeric
          ),
          false
        )
      end
      order by source.ordinality
    ),
    '[]'::jsonb
  ) as value
  from base
  cross join lateral jsonb_array_elements(base.value -> 'sources')
    with ordinality as source(item, ordinality)
  left join source_rates as rates
    on rates.public_id = source.item ->> 'id'
)
select jsonb_set(
  jsonb_set(
    jsonb_set(
      base.value,
      '{schemaVersion}',
      to_jsonb('3.0.0'::text),
      false
    ),
    '{countries}',
    countries.value,
    false
  ),
  '{sources}',
  sources.value,
  false
)
from base
cross join countries
cross join sources;
$$;

alter function public.get_public_study_coverage_v3() owner to postgres;
revoke all on function public.get_public_study_coverage_v3()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_study_coverage_v3()
  to anon, authenticated;

comment on function public.get_public_study_coverage_v3() is
  'Reviewed coverage plus exact descriptive SIR-pack sample arithmetic when both a normalized numerator and denominator are verified; publishes no baseline, posterior, interval, delta, signal, evidence body, or private policy identity.';

commit;
