begin;

-- Serialize installation and backfill with the existing fenced TCGdex
-- finalizer. The same transaction lock protects one coherent checkpoint.
select pg_advisory_xact_lock(
  hashtextextended('pokecrack:catalog:tcgdex:sets:en:live', 0)
);

-- Global publication accepts only reviewed ISO 3166-1 alpha-2 codes. A
-- two-letter regex alone would also accept non-codes such as UK and ZZ.
create table catalog.iso_alpha2_codes (
  code text primary key,
  constraint iso_alpha2_codes_code_check check (code ~ '^[A-Z]{2}$')
);

insert into catalog.iso_alpha2_codes (code)
select unnest(array[
  'AD','AE','AF','AG','AI','AL','AM','AO','AQ','AR','AS','AT','AU','AW','AX','AZ',
  'BA','BB','BD','BE','BF','BG','BH','BI','BJ','BL','BM','BN','BO','BQ','BR','BS',
  'BT','BV','BW','BY','BZ','CA','CC','CD','CF','CG','CH','CI','CK','CL','CM','CN',
  'CO','CR','CU','CV','CW','CX','CY','CZ','DE','DJ','DK','DM','DO','DZ','EC','EE',
  'EG','EH','ER','ES','ET','FI','FJ','FK','FM','FO','FR','GA','GB','GD','GE','GF',
  'GG','GH','GI','GL','GM','GN','GP','GQ','GR','GS','GT','GU','GW','GY','HK','HM',
  'HN','HR','HT','HU','ID','IE','IL','IM','IN','IO','IQ','IR','IS','IT','JE','JM',
  'JO','JP','KE','KG','KH','KI','KM','KN','KP','KR','KW','KY','KZ','LA','LB','LC',
  'LI','LK','LR','LS','LT','LU','LV','LY','MA','MC','MD','ME','MF','MG','MH','MK',
  'ML','MM','MN','MO','MP','MQ','MR','MS','MT','MU','MV','MW','MX','MY','MZ','NA',
  'NC','NE','NF','NG','NI','NL','NO','NP','NR','NU','NZ','OM','PA','PE','PF','PG',
  'PH','PK','PL','PM','PN','PR','PS','PT','PW','PY','QA','RE','RO','RS','RU','RW',
  'SA','SB','SC','SD','SE','SG','SH','SI','SJ','SK','SL','SM','SN','SO','SR','SS',
  'ST','SV','SX','SY','SZ','TC','TD','TF','TG','TH','TJ','TK','TL','TM','TN','TO',
  'TR','TT','TV','TW','TZ','UA','UG','UM','US','UY','UZ','VA','VC','VE','VG','VI',
  'VN','VU','WF','WS','YE','YT','ZA','ZM','ZW'
]::text[]);

alter table catalog.iso_alpha2_codes enable row level security;
alter table catalog.iso_alpha2_codes force row level security;
create policy iso_alpha2_codes_service_role_select
  on catalog.iso_alpha2_codes for select to service_role using (true);
revoke all on table catalog.iso_alpha2_codes
  from public, anon, authenticated, service_role;
grant select on table catalog.iso_alpha2_codes to service_role;

-- Browser-safe catalog projection. It intentionally omits external IDs, raw
-- metadata, hashes, ETags, jobs, and request details. Catalog records are not
-- opening evidence and never contribute to a pull-rate denominator.
create table public.tcgdex_set_index (
  set_id uuid primary key,
  slug text not null,
  name text not null,
  series_name text,
  release_date date,
  language text not null,
  is_current boolean not null,
  refreshed_at timestamptz not null,
  is_demo boolean not null,
  constraint tcgdex_set_index_slug_mode_unique unique (slug, is_demo),
  constraint tcgdex_set_index_slug_check check (
    slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'
  ),
  constraint tcgdex_set_index_name_check check (
    btrim(name) <> '' and char_length(name) <= 160
  ),
  constraint tcgdex_set_index_series_check check (
    series_name is null or char_length(series_name) <= 120
  ),
  constraint tcgdex_set_index_language_check check (language = 'en')
);
create index tcgdex_set_index_current_release_idx
  on public.tcgdex_set_index (
    is_demo,
    is_current,
    release_date desc nulls last,
    name,
    set_id
  );

create table public.tcgdex_catalog_status (
  source text not null,
  scope text not null,
  language text not null,
  revision bigint not null,
  set_count integer not null,
  last_checked_at timestamptz not null,
  last_changed_at timestamptz not null,
  is_current boolean not null,
  is_demo boolean not null,
  primary key (source, scope, language, is_demo),
  constraint tcgdex_catalog_status_identity_check check (
    source = 'tcgdex' and scope = 'sets' and language = 'en'
  ),
  constraint tcgdex_catalog_status_revision_check check (revision >= 1),
  constraint tcgdex_catalog_status_count_check check (
    set_count between 0 and 1000000
  ),
  constraint tcgdex_catalog_status_time_check check (
    last_changed_at <= last_checked_at
  )
);

-- This table stays empty until a separately reviewed aggregator publishes a
-- real country/time-window denominator. It cannot accept fabricated zero rows.
create table public.country_period_map_cells (
  country_code text not null
    references catalog.iso_alpha2_codes(code)
    on update restrict on delete restrict,
  country_name text not null,
  period_start date not null,
  period_end date not null,
  language text not null,
  set_scope text not null default 'all',
  product_scope text not null default 'all',
  metric_key text not null,
  metric_version text not null,
  observed_packs bigint not null,
  complete_openings bigint not null,
  independent_source_count integer not null,
  observed_rate numeric(12,10),
  posterior_mean numeric(12,10),
  baseline_rate numeric(12,10),
  credible_interval_low numeric(12,10),
  credible_interval_high numeric(12,10),
  delta_from_baseline numeric(12,10),
  signal_status text not null,
  methodology_version text not null,
  updated_at timestamptz not null,
  is_demo boolean not null default false,
  primary key (
    country_code,
    period_start,
    period_end,
    language,
    set_scope,
    product_scope,
    metric_key,
    is_demo
  ),
  constraint country_period_map_name_check check (
    btrim(country_name) <> '' and char_length(country_name) <= 160
  ),
  constraint country_period_map_period_check check (
    period_start <= period_end and period_end - period_start <= 366
  ),
  constraint country_period_map_language_check check (language = 'en'),
  constraint country_period_map_set_scope_check check (
    set_scope = 'all'
    or (
      set_scope ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'
      and char_length(set_scope) <= 160
    )
  ),
  constraint country_period_map_product_scope_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint country_period_map_metric_check check (
    metric_key = 'qualifying_hit_pack_rate'
    and metric_version ~ '^[a-z0-9][a-z0-9._-]{0,79}$'
  ),
  constraint country_period_map_counts_check check (
    observed_packs between 1 and 1000000000
    and complete_openings between 1 and observed_packs
    and independent_source_count between 1 and complete_openings
  ),
  constraint country_period_map_status_check check (
    signal_status in (
      'Insufficient sample',
      'No significant signal',
      'Watch',
      'Possible anomaly'
    )
  ),
  constraint country_period_map_publication_check check (
    (
      (observed_packs < 30 or independent_source_count < 3)
      and signal_status = 'Insufficient sample'
      and num_nonnulls(
        observed_rate,
        posterior_mean,
        baseline_rate,
        credible_interval_low,
        credible_interval_high,
        delta_from_baseline
      ) = 0
    )
    or (
      observed_packs >= 30
      and independent_source_count >= 3
      and signal_status in (
        'No significant signal',
        'Watch',
        'Possible anomaly'
      )
      and (
        signal_status = 'No significant signal'
        or observed_packs >= 200
      )
      and num_nonnulls(
        observed_rate,
        posterior_mean,
        baseline_rate,
        credible_interval_low,
        credible_interval_high,
        delta_from_baseline
      ) = 6
      and observed_rate between 0 and 1
      and posterior_mean between 0 and 1
      and baseline_rate between 0 and 1
      and credible_interval_low between 0 and posterior_mean
      and credible_interval_high between posterior_mean and 1
      and delta_from_baseline between -1 and 1
      and abs(
        delta_from_baseline - (observed_rate - baseline_rate)
      ) <= 0.0000000002
    )
  ),
  constraint country_period_map_methodology_check check (
    btrim(methodology_version) <> ''
    and char_length(methodology_version) <= 120
  )
);
create index country_period_map_latest_idx
  on public.country_period_map_cells (
    language,
    set_scope,
    product_scope,
    metric_key,
    is_demo,
    period_end desc,
    period_start desc,
    country_code
  );

create or replace function ingest.publish_tcgdex_set_index_v1()
returns trigger
language plpgsql
security invoker
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  published_at timestamptz := clock_timestamp();
begin
  if tg_op = 'DELETE' then
    update public.tcgdex_set_index as published
    set is_current = false,
        refreshed_at = published_at
    where published.set_id = old.id;
    return old;
  end if;

  if new.external_source <> 'tcgdex' or new.language <> 'en' then
    update public.tcgdex_set_index as published
    set is_current = false,
        refreshed_at = published_at
    where published.set_id = new.id;
    return new;
  end if;

  insert into public.tcgdex_set_index as published (
    set_id,
    slug,
    name,
    series_name,
    release_date,
    language,
    is_current,
    refreshed_at,
    is_demo
  ) values (
    new.id,
    new.slug,
    new.name,
    new.series_name,
    new.release_date,
    new.language,
    new.is_active,
    published_at,
    new.is_demo
  )
  on conflict (set_id)
  do update set
    slug = excluded.slug,
    name = excluded.name,
    series_name = excluded.series_name,
    release_date = excluded.release_date,
    language = excluded.language,
    is_current = excluded.is_current,
    refreshed_at = excluded.refreshed_at,
    is_demo = excluded.is_demo;

  return new;
end;
$$;
alter function ingest.publish_tcgdex_set_index_v1() owner to postgres;
revoke all on function ingest.publish_tcgdex_set_index_v1()
  from public, anon, authenticated, service_role;

create trigger sets_publish_tcgdex_set_index
after insert or update or delete on catalog.sets
for each row execute function ingest.publish_tcgdex_set_index_v1();

create or replace function ingest.publish_tcgdex_catalog_status_v1()
returns trigger
language plpgsql
security invoker
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  if tg_op = 'DELETE' then
    if old.source = 'tcgdex'
      and old.scope = 'sets'
      and old.language = 'en'
    then
      update public.tcgdex_catalog_status as published
      set is_current = false
      where published.source = old.source
        and published.scope = old.scope
        and published.language = old.language
        and published.is_demo = old.is_demo;
    end if;
    return old;
  end if;

  if tg_op = 'UPDATE'
    and old.source = 'tcgdex'
    and old.scope = 'sets'
    and old.language = 'en'
    and (
      old.source is distinct from new.source
      or old.scope is distinct from new.scope
      or old.language is distinct from new.language
      or old.is_demo is distinct from new.is_demo
    )
  then
    update public.tcgdex_catalog_status as published
    set is_current = false
    where published.source = old.source
      and published.scope = old.scope
      and published.language = old.language
      and published.is_demo = old.is_demo;
  end if;

  if new.source <> 'tcgdex'
    or new.scope <> 'sets'
    or new.language <> 'en'
  then
    return new;
  end if;

  if tg_op = 'INSERT'
    or new.last_changed_at > old.last_changed_at
  then
    update public.tcgdex_set_index as published
    set is_current = false
    where published.is_demo = new.is_demo
      and published.is_current
      and published.refreshed_at < new.last_changed_at;
  end if;

  insert into public.tcgdex_catalog_status as published (
    source,
    scope,
    language,
    revision,
    set_count,
    last_checked_at,
    last_changed_at,
    is_current,
    is_demo
  ) values (
    new.source,
    new.scope,
    new.language,
    new.revision,
    new.item_count,
    new.last_checked_at,
    new.last_changed_at,
    true,
    new.is_demo
  )
  on conflict (source, scope, language, is_demo)
  do update set
    revision = excluded.revision,
    set_count = excluded.set_count,
    last_checked_at = excluded.last_checked_at,
    last_changed_at = excluded.last_changed_at,
    is_current = true;

  return new;
end;
$$;
alter function ingest.publish_tcgdex_catalog_status_v1() owner to postgres;
revoke all on function ingest.publish_tcgdex_catalog_status_v1()
  from public, anon, authenticated, service_role;

create trigger sync_state_publish_tcgdex_catalog_status
after insert or update or delete on catalog.sync_state
for each row execute function ingest.publish_tcgdex_catalog_status_v1();

-- A checkpoint count mismatch means the pre-existing catalog cannot identify
-- which rows are stale. Fail closed instead of publishing an invented index.
do $$
declare
  live_checkpoint_count integer;
  live_catalog_count integer;
begin
  select states.item_count
  into live_checkpoint_count
  from catalog.sync_state as states
  where states.source = 'tcgdex'
    and states.scope = 'sets'
    and states.language = 'en'
    and not states.is_demo;

  if live_checkpoint_count is not null then
    select count(*)::integer
    into live_catalog_count
    from catalog.sets as sets
    where sets.external_source = 'tcgdex'
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo;

    if live_catalog_count <> live_checkpoint_count then
      raise exception using
        errcode = '23514',
        message = 'TCGdex checkpoint count does not match the active live catalog';
    end if;
  end if;
end;
$$;

insert into public.tcgdex_set_index (
  set_id,
  slug,
  name,
  series_name,
  release_date,
  language,
  is_current,
  refreshed_at,
  is_demo
)
select
  sets.id,
  sets.slug,
  sets.name,
  sets.series_name,
  sets.release_date,
  sets.language,
  sets.is_active,
  greatest(
    sets.updated_at,
    coalesce(states.last_changed_at, sets.updated_at)
  ),
  sets.is_demo
from catalog.sets as sets
left join catalog.sync_state as states
  on states.source = 'tcgdex'
  and states.scope = 'sets'
  and states.language = sets.language
  and states.is_demo = sets.is_demo
where sets.external_source = 'tcgdex'
  and sets.language = 'en';

insert into public.tcgdex_catalog_status (
  source,
  scope,
  language,
  revision,
  set_count,
  last_checked_at,
  last_changed_at,
  is_current,
  is_demo
)
select
  states.source,
  states.scope,
  states.language,
  states.revision,
  states.item_count,
  states.last_checked_at,
  states.last_changed_at,
  true,
  states.is_demo
from catalog.sync_state as states
where states.source = 'tcgdex'
  and states.scope = 'sets'
  and states.language = 'en';

alter table public.tcgdex_set_index enable row level security;
alter table public.tcgdex_catalog_status enable row level security;
alter table public.country_period_map_cells enable row level security;
alter table public.tcgdex_set_index force row level security;
alter table public.tcgdex_catalog_status force row level security;
alter table public.country_period_map_cells force row level security;

create policy tcgdex_set_index_public_read
  on public.tcgdex_set_index for select to anon, authenticated
  using (not is_demo and is_current);
create policy tcgdex_catalog_status_public_read
  on public.tcgdex_catalog_status for select to anon, authenticated
  using (not is_demo and is_current);
create policy country_period_map_cells_public_read
  on public.country_period_map_cells for select to anon, authenticated
  using (not is_demo);
create policy tcgdex_set_index_service_role_select
  on public.tcgdex_set_index for select to service_role using (true);
create policy tcgdex_catalog_status_service_role_select
  on public.tcgdex_catalog_status for select to service_role using (true);
create policy country_period_map_cells_service_role_select
  on public.country_period_map_cells for select to service_role using (true);

revoke all on table public.tcgdex_set_index,
  public.tcgdex_catalog_status,
  public.country_period_map_cells
  from public, anon, authenticated, service_role;
grant select on table public.tcgdex_set_index,
  public.tcgdex_catalog_status,
  public.country_period_map_cells
  to anon, authenticated, service_role;

create or replace function public.get_public_dashboard_snapshot_v2()
returns jsonb
language sql
stable
security invoker
parallel safe
set search_path = pg_catalog, public
as $$
with catalog_status_row as (
  select status.*
  from public.tcgdex_catalog_status as status
  where status.source = 'tcgdex'
    and status.scope = 'sets'
    and status.language = 'en'
    and not status.is_demo
    and status.is_current
  limit 1
),
catalog_rows as (
  select
    coalesce(
      jsonb_agg(item order by is_current desc, release_date desc nulls last, name, set_id),
      '[]'::jsonb
    ) as value
  from (
    select
      jsonb_build_object(
        'id', sets.set_id::text,
        'slug', sets.slug,
        'name', sets.name,
        'series', sets.series_name,
        'releaseDate', sets.release_date,
        'language', sets.language,
        'current', sets.is_current,
        'refreshedAt', sets.refreshed_at
      ) as item,
      sets.is_current,
      sets.release_date,
      sets.name,
      sets.set_id
    from public.tcgdex_set_index as sets
    where not sets.is_demo and sets.is_current
    order by sets.release_date desc nulls last, sets.name, sets.set_id
    limit 1000
  ) as bounded_catalog
),
catalog_count as (
  select count(*)::integer as value
  from public.tcgdex_set_index as sets
  where not sets.is_demo and sets.is_current
),
latest_period as (
  select
    cells.period_start,
    cells.period_end
  from public.country_period_map_cells as cells
  where not cells.is_demo
    and cells.language = 'en'
    and cells.set_scope = 'all'
    and cells.product_scope = 'all'
    and cells.metric_key = 'qualifying_hit_pack_rate'
  group by cells.period_start, cells.period_end
  order by cells.period_end desc, cells.period_start desc
  limit 1
),
bounded_map_rows as (
  select cells.*
  from public.country_period_map_cells as cells
  join latest_period as period
    on period.period_start = cells.period_start
    and period.period_end = cells.period_end
  where not cells.is_demo
    and cells.language = 'en'
    and cells.set_scope = 'all'
    and cells.product_scope = 'all'
    and cells.metric_key = 'qualifying_hit_pack_rate'
  order by cells.country_name, cells.country_code
  limit 249
),
map_snapshot as (
  select
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'countryCode', rows.country_code,
          'countryName', rows.country_name,
          'periodStart', rows.period_start,
          'periodEnd', rows.period_end,
          'setScope', rows.set_scope,
          'productScope', rows.product_scope,
          'metricKey', rows.metric_key,
          'metricVersion', rows.metric_version,
          'packsObserved', rows.observed_packs,
          'openings', rows.complete_openings,
          'independentSources', rows.independent_source_count,
          'baselineRate', rows.baseline_rate,
          'hitRate', rows.observed_rate,
          'posteriorMean', rows.posterior_mean,
          'credibleInterval', case
            when rows.posterior_mean is null then null
            else jsonb_build_object(
              'low', rows.credible_interval_low,
              'high', rows.credible_interval_high
            )
          end,
          'deltaFromBaseline', rows.delta_from_baseline,
          'state', case rows.signal_status
            when 'Insufficient sample' then 'insufficient'
            when 'No significant signal' then 'ready'
            when 'Watch' then 'watch'
            when 'Possible anomaly' then 'anomaly'
          end,
          'sampleNote', case
            when rows.signal_status = 'Insufficient sample'
              then 'Rate withheld until this country has at least 30 observed packs and three independent sources.'
            else format(
              '%s observed packs across %s independent sources.',
              rows.observed_packs,
              rows.independent_source_count
            )
          end,
          'methodologyVersion', rows.methodology_version,
          'updatedAt', rows.updated_at
        )
        order by rows.country_name, rows.country_code
      ),
      '[]'::jsonb
    ) as value,
    count(*)::integer as country_count,
    count(*) filter (where rows.observed_rate is not null)::integer
      as published_rate_count,
    coalesce(sum(rows.observed_packs), 0)::bigint as observed_packs,
    coalesce(sum(rows.complete_openings), 0)::bigint as complete_openings,
    coalesce(sum(rows.independent_source_count), 0)::bigint
      as source_country_contributions,
    max(rows.updated_at) as as_of,
    case
      when count(distinct rows.methodology_version) = 1
        then min(rows.methodology_version)
      else null
    end as methodology_version
  from bounded_map_rows as rows
),
snapshot_values as (
  select
    coalesce((select value from catalog_count), 0) as catalog_count,
    (select set_count from catalog_status_row) as upstream_catalog_count,
    (select last_checked_at from catalog_status_row) as catalog_checked_at,
    (select last_changed_at from catalog_status_row) as catalog_changed_at,
    (select revision from catalog_status_row) as catalog_revision,
    coalesce((select value from catalog_rows), '[]'::jsonb) as catalog_sets,
    coalesce((select value from map_snapshot), '[]'::jsonb) as map_cells,
    coalesce((select country_count from map_snapshot), 0) as country_count,
    coalesce((select published_rate_count from map_snapshot), 0)
      as published_rate_count,
    coalesce((select observed_packs from map_snapshot), 0) as observed_packs,
    coalesce((select complete_openings from map_snapshot), 0)
      as complete_openings,
    coalesce((select source_country_contributions from map_snapshot), 0)
      as source_country_contributions,
    (select as_of from map_snapshot) as observations_as_of,
    (select methodology_version from map_snapshot) as methodology_version,
    (select period_start from latest_period) as period_start,
    (select period_end from latest_period) as period_end
)
select jsonb_build_object(
  'schemaVersion', '2.0.0',
  'mode', 'live',
  'generatedAt', coalesce(
    values.observations_as_of,
    values.catalog_checked_at,
    now()
  ),
  'summary', jsonb_build_object(
    'observedPacks', values.observed_packs,
    'completeOpenings', values.complete_openings,
    'aiValidatedSources', 0,
    'trackedSets', 0,
    'trackedRegions', values.country_count,
    'batchSightings', 0,
    'baselineHitRate', null,
    'globalCoverage', case
      when values.country_count = 0
        then 'No verified country-level opening samples are published yet.'
      else format(
        '%s countries have verified observations in the latest complete period.',
        values.country_count
      )
    end,
    'methodologyVersion', coalesce(
      values.methodology_version,
      'global-observation-v1'
    )
  ),
  'sets', '[]'::jsonb,
  'regions', '[]'::jsonb,
  'retailers', '[]'::jsonb,
  'batches', '[]'::jsonb,
  'trend', '[]'::jsonb,
  'sources', jsonb_build_array(
    jsonb_build_object(
      'id', 'tcgdex_catalog',
      'name', 'TCGdex catalog API',
      'kind', 'catalog',
      'access', 'public',
      'status', case
        when values.catalog_checked_at is null then 'attention'
        when values.upstream_catalog_count is distinct from values.catalog_count
          then 'attention'
        when values.catalog_checked_at < now() - interval '36 hours'
          then 'delayed'
        else 'operational'
      end,
      'lastCollectedAt', values.catalog_checked_at,
      'url', 'https://tcgdex.dev/',
      'note', 'Set catalog metadata only; never used as opening evidence or a pull-rate denominator.'
    )
  ),
  'services', '[]'::jsonb,
  'recentActivity', '[]'::jsonb,
  'catalog', jsonb_build_object(
    'source', 'tcgdex',
    'name', 'TCGdex',
    'language', 'en',
    'status', case
      when values.catalog_checked_at is null then 'unavailable'
      when values.upstream_catalog_count is distinct from values.catalog_count
        then 'attention'
      when values.catalog_checked_at < now() - interval '36 hours' then 'stale'
      else 'fresh'
    end,
    'setCount', values.catalog_count,
    'upstreamSetCount', values.upstream_catalog_count,
    'lastCheckedAt', values.catalog_checked_at,
    'lastChangedAt', values.catalog_changed_at,
    'revision', values.catalog_revision,
    'catalogOnly', true,
    'sets', values.catalog_sets
  ),
  'observations', jsonb_build_object(
    'status', case
      when values.country_count = 0 then 'empty'
      when values.published_rate_count = 0 then 'collecting'
      else 'published'
    end,
    'period', case
      when values.period_start is null then null
      else jsonb_build_object(
        'start', values.period_start,
        'end', values.period_end
      )
    end,
    'observedPacks', values.observed_packs,
    'completeOpenings', values.complete_openings,
    'independentSources', null,
    'sourceCountryContributions', values.source_country_contributions,
    'countriesObserved', values.country_count,
    'countriesWithPublishedRate', values.published_rate_count,
    'asOf', values.observations_as_of,
    'methodologyVersion', values.methodology_version,
    'minimumPacks', 30,
    'minimumSources', 3,
    'watchMinimumPacks', 200,
    'metricKey', 'qualifying_hit_pack_rate'
  ),
  'mapCells', values.map_cells
)
from snapshot_values as values;
$$;

revoke all on function public.get_public_dashboard_snapshot_v2()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_dashboard_snapshot_v2()
  to anon, authenticated;

comment on table catalog.iso_alpha2_codes is
  'Reviewed ISO 3166-1 alpha-2 allowlist for global public aggregation.';
comment on table public.tcgdex_set_index is
  'Browser-safe TCGdex set index. Catalog rows are never opening evidence or a denominator.';
comment on table public.tcgdex_catalog_status is
  'Browser-safe TCGdex set-catalog freshness without hashes, ETags, jobs, payloads, or errors.';
comment on table public.country_period_map_cells is
  'Country-level qualifying-hit-pack aggregates for one explicit period. Rates are withheld below 30 packs or three sources.';
comment on function public.get_public_dashboard_snapshot_v2() is
  'Global live dashboard assembled only from three browser-readable public projection tables; zero observations remain an honest empty state.';

commit;
