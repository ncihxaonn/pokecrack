begin;

-- This migration deliberately establishes private, immutable inputs and audit
-- records only.  It does not publish a country rate or touch the browser-safe
-- map.  A later, separately reviewed fenced publisher may consume these
-- contracts only after it implements and verifies exact Beta quantiles.

create table analytics.reviewed_global_aggregate_baselines (
  baseline_id text primary key,
  baseline_version text not null,
  metric_key text not null,
  metric_version text not null,
  set_external_id text not null,
  language text not null,
  product_scope text not null default 'all',
  baseline_rate numeric(12,10) not null,
  provenance_sha256 text not null,
  contract_sha256 text not null,
  valid_from date not null,
  valid_to date,
  created_at timestamptz not null default clock_timestamp(),
  constraint reviewed_global_aggregate_baselines_id_check check (
    baseline_id ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
  ),
  constraint reviewed_global_aggregate_baselines_version_check check (
    baseline_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
  ),
  constraint reviewed_global_aggregate_baselines_metric_check check (
    metric_key = 'qualifying_hit_pack_rate'
    and metric_version ~ '^[a-z0-9][a-z0-9._-]{0,79}$'
  ),
  constraint reviewed_global_aggregate_baselines_set_check check (
    btrim(set_external_id) <> '' and char_length(set_external_id) <= 160
  ),
  constraint reviewed_global_aggregate_baselines_language_check check (
    language = 'en'
  ),
  constraint reviewed_global_aggregate_baselines_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint reviewed_global_aggregate_baselines_rate_check check (
    baseline_rate > 0 and baseline_rate < 1
  ),
  constraint reviewed_global_aggregate_baselines_hash_check check (
    provenance_sha256 ~ '^[0-9a-f]{64}$'
    and contract_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint reviewed_global_aggregate_baselines_window_check check (
    valid_to is null or valid_to >= valid_from
  ),
  constraint reviewed_global_aggregate_baselines_scope_unique unique (
    baseline_version,
    set_external_id,
    language,
    product_scope,
    valid_from
  )
);

create table analytics.reviewed_global_aggregate_audit (
  id uuid primary key default gen_random_uuid(),
  aggregate_key text not null unique,
  country_code text not null
    references catalog.iso_alpha2_codes (code)
    on update restrict on delete restrict,
  period_start date not null,
  period_end date not null,
  language text not null,
  set_scope text not null,
  product_scope text not null,
  metric_key text not null,
  metric_version text not null,
  methodology_version text not null,
  publication_contract_version text not null,
  calculation_implementation_version text not null,
  source_domain_set_sha256 text not null,
  cohort_fingerprint_sha256 text not null,
  independent_source_count integer not null,
  complete_openings bigint not null,
  observed_packs bigint not null,
  qualifying_hit_pack_count bigint not null,
  baseline_id text
    references analytics.reviewed_global_aggregate_baselines (baseline_id)
    on update restrict on delete restrict,
  baseline_contract_sha256 text,
  baseline_rate numeric(12,10),
  prior_strength numeric(12,10),
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  probability_above_baseline numeric(12,10),
  probability_above_practical numeric(12,10),
  delta_from_baseline numeric(12,10),
  signal_status text,
  publication_state text not null,
  withhold_reason text,
  build_sha text not null,
  created_at timestamptz not null default clock_timestamp(),
  constraint reviewed_global_aggregate_audit_key_check check (
    aggregate_key ~ '^[a-z0-9][a-z0-9._:-]{0,239}$'
  ),
  constraint reviewed_global_aggregate_audit_period_check check (
    period_start <= period_end and period_end - period_start <= 366
  ),
  constraint reviewed_global_aggregate_audit_language_check check (language = 'en'),
  constraint reviewed_global_aggregate_audit_scope_check check (
    set_scope = 'all'
    or (
      set_scope ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'
      and char_length(set_scope) <= 160
    )
  ),
  constraint reviewed_global_aggregate_audit_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint reviewed_global_aggregate_audit_metric_check check (
    metric_key = 'qualifying_hit_pack_rate'
    and metric_version ~ '^[a-z0-9][a-z0-9._-]{0,79}$'
    and methodology_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and publication_contract_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
    and calculation_implementation_version ~ '^[a-z0-9][a-z0-9._-]{0,119}$'
  ),
  constraint reviewed_global_aggregate_audit_hash_check check (
    source_domain_set_sha256 ~ '^[0-9a-f]{64}$'
    and cohort_fingerprint_sha256 ~ '^[0-9a-f]{64}$'
    and (baseline_contract_sha256 is null or baseline_contract_sha256 ~ '^[0-9a-f]{64}$')
    and build_sha ~ '^[0-9a-f]{7,64}$'
  ),
  constraint reviewed_global_aggregate_audit_counts_check check (
    independent_source_count between 1 and complete_openings
    and complete_openings between 1 and observed_packs
    and observed_packs between 1 and 1000000000
    and qualifying_hit_pack_count between 0 and observed_packs
  ),
  constraint reviewed_global_aggregate_audit_state_check check (
    -- A later reviewed publisher may extend this constraint only after it
    -- proves every derived value from the immutable cohort and baseline
    -- contract.  This foundation must never store plausible-looking rates.
    publication_state = 'withheld'
    and withhold_reason is not null
    and withhold_reason in (
      'insufficient_sample',
      'baseline_unavailable',
      'exact_interval_unavailable',
      'contract_drift'
    )
    and num_nonnulls(
      baseline_id,
      baseline_contract_sha256,
      baseline_rate,
      prior_strength,
      observed_rate,
      posterior_mean,
      credible_interval_low,
      credible_interval_high,
      probability_above_baseline,
      probability_above_practical,
      delta_from_baseline,
      signal_status
    ) = 0
  )
);

create index reviewed_global_aggregate_audit_country_period_idx
  on analytics.reviewed_global_aggregate_audit (
    country_code,
    period_end desc,
    metric_version,
    methodology_version,
    created_at desc
  );

create function analytics.reject_reviewed_global_aggregate_mutation_v1()
returns trigger
language plpgsql
security invoker
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'reviewed global aggregate records are immutable';
end;
$$;

create trigger reviewed_global_aggregate_baselines_immutable
  before update or delete on analytics.reviewed_global_aggregate_baselines
  for each row
  execute function analytics.reject_reviewed_global_aggregate_mutation_v1();

create trigger reviewed_global_aggregate_audit_immutable
  before update or delete on analytics.reviewed_global_aggregate_audit
  for each row
  execute function analytics.reject_reviewed_global_aggregate_mutation_v1();

-- This exact-arithmetic primitive intentionally stops before an interval or
-- probability.  The public map requires a credible interval, and no caller
-- may substitute a normal/Wilson approximation while the reviewed SQL port of
-- the Beta quantile routine is absent.
create function analytics.reviewed_global_beta_parameters_v1(
  p_hits bigint,
  p_packs bigint,
  p_baseline_rate numeric,
  p_prior_strength numeric default 50
)
returns table (
  alpha numeric,
  beta numeric,
  posterior_mean numeric
)
language plpgsql
security invoker
immutable
parallel safe
set search_path = pg_catalog
as $$
begin
  if p_hits is null
    or p_packs is null
    or p_hits < 0
    or p_packs <= 0
    or p_hits > p_packs then
    raise exception using
      errcode = '22023',
      message = 'hits must satisfy 0 <= hits <= packs';
  end if;
  if p_baseline_rate is null
    or p_baseline_rate = 'NaN'::numeric
    or p_baseline_rate = 'Infinity'::numeric
    or p_baseline_rate = '-Infinity'::numeric
    or p_baseline_rate <= 0
    or p_baseline_rate >= 1 then
    raise exception using
      errcode = '22023',
      message = 'baseline rate must be strictly between zero and one';
  end if;
  if p_prior_strength is null
    or p_prior_strength = 'NaN'::numeric
    or p_prior_strength = 'Infinity'::numeric
    or p_prior_strength = '-Infinity'::numeric
    or p_prior_strength <= 0 then
    raise exception using
      errcode = '22023',
      message = 'prior strength must be positive';
  end if;

  return query
  select
    p_baseline_rate * p_prior_strength + p_hits,
    (1 - p_baseline_rate) * p_prior_strength + p_packs - p_hits,
    (p_baseline_rate * p_prior_strength + p_hits)
      / (p_prior_strength + p_packs);
end;
$$;

alter table analytics.reviewed_global_aggregate_baselines enable row level security;
alter table analytics.reviewed_global_aggregate_baselines force row level security;
alter table analytics.reviewed_global_aggregate_audit enable row level security;
alter table analytics.reviewed_global_aggregate_audit force row level security;

revoke all on table analytics.reviewed_global_aggregate_baselines
  from public, anon, authenticated, service_role;
revoke all on table analytics.reviewed_global_aggregate_audit
  from public, anon, authenticated, service_role;

alter function analytics.reject_reviewed_global_aggregate_mutation_v1()
  owner to postgres;
alter function analytics.reviewed_global_beta_parameters_v1(
  bigint,
  bigint,
  numeric,
  numeric
) owner to postgres;

revoke all on function analytics.reject_reviewed_global_aggregate_mutation_v1()
  from public, anon, authenticated, service_role;
revoke all on function analytics.reviewed_global_beta_parameters_v1(
  bigint,
  bigint,
  numeric,
  numeric
) from public, anon, authenticated, service_role;

comment on table analytics.reviewed_global_aggregate_baselines is
  'Private immutable reviewed baseline contract. No baseline is seeded until its provenance and scope are separately approved.';
comment on table analytics.reviewed_global_aggregate_audit is
  'Private immutable aggregate audit. It retains numerator and cohort fingerprints but is never a browser projection or direct worker-write surface. Absence of an audit row is not a zero-data observation.';
comment on function analytics.reviewed_global_beta_parameters_v1(
  bigint,
  bigint,
  numeric,
  numeric
) is
  'Exact posterior parameter/mean arithmetic only. It intentionally does not compute credible intervals or authorize public rate publication.';

commit;
