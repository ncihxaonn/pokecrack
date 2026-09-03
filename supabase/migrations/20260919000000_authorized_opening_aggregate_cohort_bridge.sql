begin;

-- This bridge is deliberately private. An accepted reviewer observation is not
-- an aggregate input until an owner-reviewed domain binding and an immutable
-- cross-ledger admission both exist. Social discovery stays out of this path.

create table analytics.reviewed_global_aggregate_independent_sources (
  source_key text primary key,
  canonical_domain text not null unique,
  domain_contract_version text not null,
  domain_contract_sha256 text not null,
  created_at timestamptz not null default statement_timestamp(),
  constraint reviewed_global_aggregate_independent_sources_key_check check (
    source_key ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and source_key = btrim(source_key)
    and source_key = normalize(source_key, NFKC)
    and source_key !~ '[[:cntrl:]]'
  ),
  constraint reviewed_global_aggregate_independent_sources_domain_check check (
    canonical_domain = lower(canonical_domain)
    and canonical_domain = btrim(canonical_domain)
    and canonical_domain = normalize(canonical_domain, NFKC)
    and canonical_domain !~ '[[:cntrl:]]'
    and char_length(canonical_domain) between 3 and 253
    and canonical_domain ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$'
  ),
  constraint reviewed_global_aggregate_independent_sources_contract_check check (
    domain_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and domain_contract_version = btrim(domain_contract_version)
    and domain_contract_version = normalize(domain_contract_version, NFKC)
    and domain_contract_version !~ '[[:cntrl:]]'
    and domain_contract_sha256 ~ '^[0-9a-f]{64}$'
  )
);

create table analytics.reviewed_global_aggregate_authorized_source_bindings (
  binding_key text primary key,
  source_identity_sha256 text not null,
  authorization_reference_sha256 text not null,
  independent_source_key text not null,
  authorization_contract_version text not null,
  authorization_contract_sha256 text not null,
  valid_from timestamptz not null,
  valid_until timestamptz,
  created_at timestamptz not null default statement_timestamp(),
  constraint rga_asb_source_auth_key unique (
    source_identity_sha256, authorization_reference_sha256
  ),
  constraint rga_asb_source_key_fkey
    foreign key (independent_source_key)
    references analytics.reviewed_global_aggregate_independent_sources (source_key)
    on update restrict on delete restrict,
  constraint reviewed_global_aggregate_authorized_source_bindings_key_check check (
    binding_key ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and binding_key = btrim(binding_key)
    and binding_key = normalize(binding_key, NFKC)
    and binding_key !~ '[[:cntrl:]]'
  ),
  constraint reviewed_global_aggregate_authorized_source_bindings_hash_check check (
    source_identity_sha256 ~ '^[0-9a-f]{64}$'
    and authorization_reference_sha256 ~ '^[0-9a-f]{64}$'
    and authorization_contract_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint rga_asb_contract_check check (
    authorization_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and authorization_contract_version = btrim(authorization_contract_version)
    and authorization_contract_version = normalize(authorization_contract_version, NFKC)
    and authorization_contract_version !~ '[[:cntrl:]]'
  ),
  constraint rga_asb_window_check check (
    valid_until is null or valid_until >= valid_from
  )
);

-- A shared fingerprint namespace prevents an owner from admitting the same
-- opening through a reviewed public study and an authorized direct submission.
-- Public-study keys intentionally do not FK a mutable table: their immutable
-- source of truth is the owner-only reviewed-study contract function.
create table analytics.reviewed_global_aggregate_input_admissions (
  admission_key text primary key,
  input_kind text not null,
  public_study_key text,
  accepted_observation_id uuid,
  binding_key text,
  canonical_opening_fingerprint_sha256 text not null,
  admission_contract_version text not null,
  admission_contract_sha256 text not null,
  admitted_at timestamptz not null default statement_timestamp(),
  constraint rga_ia_fingerprint_key unique (
    canonical_opening_fingerprint_sha256
  ),
  constraint rga_ia_observation_fkey
    foreign key (accepted_observation_id)
    references ingest.authorized_opening_observations (id)
    on update restrict on delete restrict,
  constraint rga_ia_binding_key_fkey
    foreign key (binding_key)
    references analytics.reviewed_global_aggregate_authorized_source_bindings (binding_key)
    on update restrict on delete restrict,
  constraint reviewed_global_aggregate_input_admissions_key_check check (
    admission_key ~ '^[a-z0-9][a-z0-9._-]{0,159}$'
    and admission_key = btrim(admission_key)
    and admission_key = normalize(admission_key, NFKC)
    and admission_key !~ '[[:cntrl:]]'
  ),
  constraint reviewed_global_aggregate_input_admissions_kind_check check (
    (
      input_kind = 'public_study'
      and public_study_key is not null
      and public_study_key ~ '^[a-z0-9][a-z0-9-]{0,119}$'
      and accepted_observation_id is null
      and binding_key is null
    )
    or (
      input_kind = 'authorized_opening'
      and public_study_key is null
      and accepted_observation_id is not null
      and binding_key is not null
    )
  ),
  constraint reviewed_global_aggregate_input_admissions_hash_check check (
    canonical_opening_fingerprint_sha256 ~ '^[0-9a-f]{64}$'
    and admission_contract_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint reviewed_global_aggregate_input_admissions_contract_check check (
    admission_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and admission_contract_version = btrim(admission_contract_version)
    and admission_contract_version = normalize(admission_contract_version, NFKC)
    and admission_contract_version !~ '[[:cntrl:]]'
  )
);

create unique index reviewed_global_aggregate_input_admissions_public_study_uidx
  on analytics.reviewed_global_aggregate_input_admissions (public_study_key)
  where public_study_key is not null;
create unique index reviewed_global_aggregate_input_admissions_authorized_uidx
  on analytics.reviewed_global_aggregate_input_admissions (accepted_observation_id)
  where accepted_observation_id is not null;
create index reviewed_global_aggregate_authorized_source_bindings_source_idx
  on analytics.reviewed_global_aggregate_authorized_source_bindings (
    independent_source_key, valid_from, valid_until
  );

-- These reviewed public-study policy domains are explicit independent-source
-- identities. No SQL derives a registrable domain or silently collapses hosts.
insert into analytics.reviewed_global_aggregate_independent_sources (
  source_key,
  canonical_domain,
  domain_contract_version,
  domain_contract_sha256
)
select
  seeded.source_key,
  seeded.canonical_domain,
  seeded.domain_contract_version,
  encode(
    extensions.digest(
      convert_to(
        seeded.source_key || E'\n' || seeded.canonical_domain || E'\n'
          || seeded.domain_contract_version,
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  )
from (
  values
    ('public-study-comicbook-v1', 'comicbook.com', 'reviewed-public-study-domain-v1'),
    ('public-study-wargamer-v1', 'www.wargamer.com', 'reviewed-public-study-domain-v1'),
    ('public-study-cardchill-v1', 'cardchill.com', 'reviewed-public-study-domain-v1'),
    ('public-study-bleedingcool-v1', 'bleedingcool.com', 'reviewed-public-study-domain-v1'),
    ('public-study-tcgtalk-v1', 'tcgtalk.com', 'reviewed-public-study-domain-v1')
) as seeded(source_key, canonical_domain, domain_contract_version);

alter table analytics.reviewed_global_aggregate_independent_sources
  enable row level security;
alter table analytics.reviewed_global_aggregate_independent_sources
  force row level security;
alter table analytics.reviewed_global_aggregate_authorized_source_bindings
  enable row level security;
alter table analytics.reviewed_global_aggregate_authorized_source_bindings
  force row level security;
alter table analytics.reviewed_global_aggregate_input_admissions
  enable row level security;
alter table analytics.reviewed_global_aggregate_input_admissions
  force row level security;

revoke all on table analytics.reviewed_global_aggregate_independent_sources,
  analytics.reviewed_global_aggregate_authorized_source_bindings,
  analytics.reviewed_global_aggregate_input_admissions
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;

create trigger reviewed_global_aggregate_independent_sources_immutable
  before update or delete on analytics.reviewed_global_aggregate_independent_sources
  for each row
  execute function analytics.reject_reviewed_global_aggregate_mutation_v1();
create trigger reviewed_global_aggregate_authorized_source_bindings_immutable
  before update or delete on analytics.reviewed_global_aggregate_authorized_source_bindings
  for each row
  execute function analytics.reject_reviewed_global_aggregate_mutation_v1();
create trigger reviewed_global_aggregate_input_admissions_immutable
  before update or delete on analytics.reviewed_global_aggregate_input_admissions
  for each row
  execute function analytics.reject_reviewed_global_aggregate_mutation_v1();

create function analytics.reviewed_global_aggregate_cohort_v1(
  p_period_start date,
  p_period_end date,
  p_as_of timestamptz
)
returns table (
  input_kind text,
  input_id text,
  country_code text,
  country_name text,
  language text,
  set_external_id text,
  product_scope text,
  observed_at timestamptz,
  pack_count bigint,
  qualifying_hit_pack_count bigint,
  independent_source_key text,
  source_contract_version text,
  methodology_version text
)
language plpgsql
security definer
stable
parallel restricted
set search_path = pg_catalog
as $cohort$
begin
  if p_period_start is null
    or p_period_end is null
    or p_as_of is null
    or p_period_start > p_period_end
    or p_period_end - p_period_start > 364
    or p_period_end > (p_as_of at time zone 'UTC')::date
    or p_as_of > statement_timestamp()
  then
    raise exception using
      errcode = '22023',
      message = 'aggregate cohort window must be a nonfuture UTC period of at most 365 days';
  end if;

  return query
  with public_studies as (
    select
      'public_study'::text as input_kind,
      studies.study_key as input_id,
      studies.country_code,
      studies.country_name,
      'en'::text as language,
      studies.set_external_id,
      studies.product_scope,
      studies.source_observed_at as observed_at,
      studies.pack_count::bigint as pack_count,
      studies.qualifying_hit_pack_count::bigint as qualifying_hit_pack_count,
      sources.source_key as independent_source_key,
      policies.version as source_contract_version,
      'public-study-global-sir-v1'::text as methodology_version
    from ingest.reviewed_public_study_contracts() as contracts
    join ingest.source_policies as policies
      on policies.source_key = contracts.policy_key
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
      and not policies.is_demo
    join ingest.public_study_observations as studies
      on studies.study_key = contracts.study_key
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
    join ingest.openings as openings
      on openings.id = studies.opening_id
      and openings.eligible_for_statistics
      and openings.complete_opening
      and openings.validation_status = 'accepted'
      and openings.public_status = 'verified'
      and openings.duplicate_of is null
      and not openings.duplicate_suspected
      and not openings.is_demo
    join catalog.iso_alpha2_codes as countries
      on countries.code = studies.country_code
      and countries.country_name = studies.country_name
    join catalog.sets as sets
      on sets.external_source = 'tcgdex'
      and sets.external_id = studies.set_external_id
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo
    join public.tcgdex_set_index as set_index
      on set_index.set_id = sets.id
      and set_index.language = 'en'
      and set_index.is_current
      and not set_index.is_demo
    join analytics.reviewed_global_aggregate_independent_sources as sources
      on sources.canonical_domain = contracts.domain
    join analytics.reviewed_global_aggregate_input_admissions as admissions
      on admissions.input_kind = 'public_study'
      and admissions.public_study_key = contracts.study_key
      and admissions.admitted_at <= p_as_of
    where studies.product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
      and studies.source_observed_at <= p_as_of
      and (studies.source_observed_at at time zone 'UTC')::date
        between p_period_start and p_period_end
  ),
  authorized_openings as (
    select
      'authorized_opening'::text as input_kind,
      observations.id::text as input_id,
      observations.country_code,
      observations.country_name,
      observations.language,
      observations.tcgdex_set_id as set_external_id,
      observations.product_scope,
      observations.observed_at,
      observations.pack_count::bigint as pack_count,
      observations.qualifying_hit_pack_count::bigint as qualifying_hit_pack_count,
      sources.source_key as independent_source_key,
      bindings.authorization_contract_version as source_contract_version,
      observations.methodology_version
    from ingest.authorized_opening_observations as observations
    join analytics.reviewed_global_aggregate_input_admissions as admissions
      on admissions.input_kind = 'authorized_opening'
      and admissions.accepted_observation_id = observations.id
      and admissions.canonical_opening_fingerprint_sha256
        = observations.provenance_dedupe_sha256
      and admissions.admitted_at <= p_as_of
    join analytics.reviewed_global_aggregate_authorized_source_bindings as bindings
      on bindings.binding_key = admissions.binding_key
      and bindings.source_identity_sha256 = observations.source_identity_sha256
      and bindings.authorization_reference_sha256
        = observations.authorization_reference_sha256
      and bindings.valid_from <= observations.accepted_at
      and (bindings.valid_until is null
        or bindings.valid_until >= observations.accepted_at)
    join analytics.reviewed_global_aggregate_independent_sources as sources
      on sources.source_key = bindings.independent_source_key
    join catalog.iso_alpha2_codes as countries
      on countries.code = observations.country_code
      and countries.country_name = observations.country_name
    join catalog.sets as sets
      on sets.external_source = 'tcgdex'
      and sets.external_id = observations.tcgdex_set_id
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo
    join public.tcgdex_set_index as set_index
      on set_index.set_id = sets.id
      and set_index.language = 'en'
      and set_index.is_current
      and not set_index.is_demo
    left join ingest.authorized_opening_retractions as retractions
      on retractions.accepted_observation_id = observations.id
      and retractions.retracted_at <= p_as_of
    where observations.statistics_eligible
      and observations.denominator_complete
      and observations.methodology_version = 'authorized-opening-v1'
      and observations.language = 'en'
      and observations.product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
      and observations.accepted_at <= p_as_of
      and observations.observed_at <= p_as_of
      and (observations.observed_at at time zone 'UTC')::date
        between p_period_start and p_period_end
      and not exists (
        select 1
        from analytics.reviewed_global_aggregate_authorized_source_bindings
          as conflicting_bindings
        where conflicting_bindings.source_identity_sha256
            = bindings.source_identity_sha256
          and conflicting_bindings.independent_source_key
            is distinct from bindings.independent_source_key
      )
      and retractions.accepted_observation_id is null
  )
  select * from public_studies
  union all
  select * from authorized_openings;
end;
$cohort$;

alter function analytics.reviewed_global_aggregate_cohort_v1(
  date, date, timestamptz
) owner to postgres;
revoke all on function analytics.reviewed_global_aggregate_cohort_v1(
  date, date, timestamptz
) from public, anon, authenticated, service_role,
  pokecrack_authorized_opening_reviewer;

comment on table analytics.reviewed_global_aggregate_independent_sources is
  'Private immutable owner-reviewed identities for independent source diversity. SQL never derives or normalizes registrable domains.';
comment on table analytics.reviewed_global_aggregate_authorized_source_bindings is
  'Private immutable owner-reviewed binding from opaque authorized-source HMACs to one independent-source identity.';
comment on table analytics.reviewed_global_aggregate_input_admissions is
  'Private immutable cross-ledger admission and canonical-opening collision namespace. Reviewer acceptance alone never admits an aggregate input.';
comment on function analytics.reviewed_global_aggregate_cohort_v1(
  date, date, timestamptz
) is
  'Owner-only as-of aggregate input resolver. It returns no raw identity/evidence fields, excludes social discovery, and never writes an audit or public map cell.';

commit;
