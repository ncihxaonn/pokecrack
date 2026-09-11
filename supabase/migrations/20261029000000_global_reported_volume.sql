begin;

-- Quantity-first public coverage is intentionally a separate lane from the
-- reviewed hit-rate pipeline. These rows contain only source-reported pack
-- counts, a public URL and an attribution bucket. They never carry a hit
-- numerator, an inference, an identity, or raw page content.
create table ingest.global_volume_candidates (
  url text primary key,
  report_group_sha256 text not null check (report_group_sha256 ~ '^[0-9a-f]{64}$'),
  pack_count integer not null check (pack_count between 1 and 100000000),
  pack_precision text not null check (
    pack_precision in ('exact_reported', 'lower_bound', 'title_claim')
  ),
  country_code text references catalog.iso_alpha2_codes(code),
  geography_basis text not null check (
    geography_basis in ('opening_location', 'publisher_country', 'product_market', 'unknown')
  ),
  set_external_id text check (
    set_external_id is null or set_external_id ~ '^[a-z0-9][a-z0-9_-]{0,99}$'
  ),
  product_scope text not null check (
    product_scope in ('all', 'booster_box', 'booster_bundle', 'etb', 'other')
  ),
  source_language text not null default 'und' check (
    source_language = 'und'
    or source_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8}){0,2}$'
  ),
  state text not null default 'reported' check (
    state in ('reported', 'checking', 'verified', 'rejected', 'conflicting')
  ),
  attempts integer not null default 0 check (attempts between 0 and 3),
  locked_by text,
  locked_until timestamptz,
  first_seen_at timestamptz not null default clock_timestamp(),
  last_seen_at timestamptz not null default clock_timestamp(),
  last_checked_at timestamptz,
  last_error_code text,
  evidence_sha256 text check (
    evidence_sha256 is null or evidence_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint global_volume_url_check check (
    url ~ '^https://[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]/[^?#[:space:]<>]*$'
  ),
  constraint global_volume_country_basis_check check (
    (country_code is null and geography_basis = 'unknown')
    or (country_code is not null and geography_basis <> 'unknown')
  ),
  constraint global_volume_lease_check check (
    (locked_by is null and locked_until is null)
    or (locked_by is not null and locked_until is not null)
  )
);
create index global_volume_candidates_due_idx
  on ingest.global_volume_candidates (state, last_seen_at, first_seen_at, url)
  where state in ('reported', 'checking');
create index global_volume_candidates_country_idx
  on ingest.global_volume_candidates (country_code, state, last_seen_at)
  where country_code is not null and state in ('reported', 'verified');

-- One immutable, hash-only check result per source URL. The reported row is
-- already publishable for volume; this relation records a later page check
-- without retaining HTML or matched text.
create table ingest.global_volume_observations (
  observation_key text primary key check (observation_key ~ '^[0-9a-f]{64}$'),
  source_url text not null unique references ingest.global_volume_candidates(url),
  report_group_sha256 text not null check (report_group_sha256 ~ '^[0-9a-f]{64}$'),
  pack_count integer not null check (pack_count between 1 and 100000000),
  pack_precision text not null check (
    pack_precision in ('exact_reported', 'lower_bound', 'title_claim')
  ),
  country_code text references catalog.iso_alpha2_codes(code),
  geography_basis text not null check (
    geography_basis in ('opening_location', 'publisher_country', 'product_market', 'unknown')
  ),
  set_external_id text check (
    set_external_id is null or set_external_id ~ '^[a-z0-9][a-z0-9_-]{0,99}$'
  ),
  product_scope text not null check (
    product_scope in ('all', 'booster_box', 'booster_bundle', 'etb', 'other')
  ),
  source_language text not null check (
    source_language = 'und'
    or source_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8}){0,2}$'
  ),
  collector_version text not null check (collector_version = 'global-volume-v1'),
  parser_version text not null check (parser_version = 'visible-pack-count-v1'),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  first_verified_at timestamptz not null,
  last_verified_at timestamptz not null,
  is_demo boolean not null default false,
  constraint global_volume_observation_country_basis_check check (
    (country_code is null and geography_basis = 'unknown')
    or (country_code is not null and geography_basis <> 'unknown')
  )
);

alter table ingest.global_volume_candidates enable row level security;
alter table ingest.global_volume_candidates force row level security;
alter table ingest.global_volume_observations enable row level security;
alter table ingest.global_volume_observations force row level security;
revoke all on table ingest.global_volume_candidates
  from public, anon, authenticated, service_role;
revoke all on table ingest.global_volume_observations
  from public, anon, authenticated, service_role;

create function ingest.import_global_volume_intake_v1(p_manifest jsonb)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  item jsonb;
  received integer := 0;
  inserted integer := 0;
  conflicts integer := 0;
  existing ingest.global_volume_candidates%rowtype;
  item_url text;
  group_hash text;
  item_country text;
  item_basis text;
  item_set text;
  item_language text;
  item_product text;
  item_precision text;
  item_pack_count integer;
begin
  if jsonb_typeof(p_manifest) <> 'object'
    or p_manifest->>'schema_version' <> 'global-volume-intake-v1'
    or p_manifest->>'snapshot_sha256' !~ '^[0-9a-f]{64}$'
    or jsonb_typeof(p_manifest->'candidates') <> 'array'
    or jsonb_array_length(p_manifest->'candidates') > 1000
  then
    raise exception 'invalid global volume manifest';
  end if;

  for item in select value from jsonb_array_elements(p_manifest->'candidates') loop
    if jsonb_typeof(item) <> 'object'
      or (select count(*) from jsonb_object_keys(item)) <> 9
      or not (item ? 'url')
      or not (item ? 'report_group_sha256')
      or not (item ? 'pack_count')
      or not (item ? 'pack_precision')
      or not (item ? 'country_code')
      or not (item ? 'geography_basis')
      or not (item ? 'set_external_id')
      or not (item ? 'product_scope')
      or not (item ? 'source_language')
    then
      raise exception 'invalid global volume candidate';
    end if;

    item_url := item->>'url';
    group_hash := item->>'report_group_sha256';
    item_pack_count := (item->>'pack_count')::integer;
    item_precision := item->>'pack_precision';
    item_country := item->>'country_code';
    item_basis := item->>'geography_basis';
    item_set := item->>'set_external_id';
    item_product := item->>'product_scope';
    item_language := coalesce(nullif(item->>'source_language', ''), 'und');

    if item_url !~ '^https://[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]/[^?#[:space:]<>]*$'
      or group_hash !~ '^[0-9a-f]{64}$'
      or item_pack_count not between 1 and 100000000
      or item_precision not in ('exact_reported', 'lower_bound', 'title_claim')
      or item_basis not in ('opening_location', 'publisher_country', 'product_market', 'unknown')
      or item_product not in ('all', 'booster_box', 'booster_bundle', 'etb', 'other')
      or item_language <> 'und' and item_language !~ '^[a-z]{2,3}(-[a-z0-9]{2,8}){0,2}$'
      or item_set is not null and item_set !~ '^[a-z0-9][a-z0-9_-]{0,99}$'
      or item_country is not null and item_country !~ '^[A-Z]{2}$'
      or (item_country is null and item_basis <> 'unknown')
      or (item_country is not null and item_basis = 'unknown')
      or item_country is not null and not exists (
        select 1 from catalog.iso_alpha2_codes where code = item_country
      )
    then
      raise exception 'invalid global volume candidate';
    end if;

    received := received + 1;
    select * into existing
    from ingest.global_volume_candidates
    where url = item_url
    for update;

    if not found then
      insert into ingest.global_volume_candidates (
        url, report_group_sha256, pack_count, pack_precision, country_code,
        geography_basis, set_external_id, product_scope, source_language
      ) values (
        item_url, group_hash, item_pack_count, item_precision, item_country,
        item_basis, item_set, item_product, item_language
      );
      inserted := inserted + 1;
    elsif existing.report_group_sha256 = group_hash
      and existing.pack_count = item_pack_count
      and existing.pack_precision = item_precision
      and existing.country_code is not distinct from item_country
      and existing.geography_basis = item_basis
      and existing.set_external_id is not distinct from item_set
      and existing.product_scope = item_product
      and existing.source_language = item_language
    then
      update ingest.global_volume_candidates
      set last_seen_at = clock_timestamp()
      where url = item_url;
    else
      update ingest.global_volume_candidates
      set state = 'conflicting', last_seen_at = clock_timestamp(),
          last_error_code = 'conflicting_report_facts',
          locked_by = null, locked_until = null
      where url = item_url;
      conflicts := conflicts + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'status', 'accepted',
    'snapshot_sha256', p_manifest->>'snapshot_sha256',
    'candidates_received', received,
    'candidates_inserted', inserted,
    'conflicting_count', conflicts
  );
exception
  when invalid_text_representation or numeric_value_out_of_range then
    raise exception 'invalid global volume candidate';
end;
$$;

create function ingest.claim_global_volume_candidates_v1(
  p_worker_id text,
  p_limit integer default 8
)
returns table(
  url text,
  report_group_sha256 text,
  pack_count integer,
  pack_precision text,
  country_code text,
  geography_basis text,
  set_external_id text,
  product_scope text,
  source_language text,
  state text,
  attempts integer
)
language sql
security definer
set search_path = pg_catalog
as $$
  with due as (
    select candidates.url
    from ingest.global_volume_candidates as candidates
    where p_worker_id ~ '^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}$'
      and p_limit between 1 and 25
      and candidates.attempts < 3
      and (
        candidates.state = 'reported'
        or (
          candidates.state = 'checking'
          and candidates.locked_until < clock_timestamp()
        )
      )
    order by candidates.last_checked_at nulls first,
      candidates.last_seen_at, candidates.first_seen_at, candidates.url
    limit greatest(least(p_limit, 25), 0)
    for update skip locked
  ), claimed as (
    update ingest.global_volume_candidates as candidates
    set state = 'checking', attempts = candidates.attempts + 1,
        locked_by = p_worker_id, locked_until = clock_timestamp() + interval '5 minutes'
    from due
    where candidates.url = due.url
    returning candidates.*
  )
  select claimed.url, claimed.report_group_sha256, claimed.pack_count,
    claimed.pack_precision, claimed.country_code, claimed.geography_basis,
    claimed.set_external_id, claimed.product_scope, claimed.source_language,
    claimed.state, claimed.attempts
  from claimed;
$$;

create function ingest.finalize_global_volume_candidate_v1(
  p_worker_id text,
  p_url text,
  p_result jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  candidate ingest.global_volume_candidates%rowtype;
  result_status text;
  error_code text;
  evidence text;
  observation_key text;
begin
  if p_worker_id !~ '^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}$'
    or p_url !~ '^https://[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]/[^?#[:space:]<>]*$'
    or jsonb_typeof(p_result) <> 'object'
    or (select count(*) from jsonb_object_keys(p_result)) <> 3
    or not (p_result ? 'status')
    or not (p_result ? 'error_code')
    or not (p_result ? 'evidence_sha256')
  then
    raise exception 'invalid global volume result';
  end if;
  result_status := p_result->>'status';
  error_code := p_result->>'error_code';
  evidence := p_result->>'evidence_sha256';
  if result_status not in ('verified', 'rejected', 'retry') then
    raise exception 'invalid global volume result';
  end if;
  if result_status = 'verified' then
    if error_code is not null or evidence is null
      or evidence !~ '^[0-9a-f]{64}$' then
      raise exception 'invalid global volume result';
    end if;
  elsif error_code not in (
    'robots_denied', 'robots_unavailable', 'source_challenged',
    'source_http_status', 'source_redirected', 'source_not_html',
    'source_too_large', 'source_invalid_utf8', 'page_scope_not_found',
    'pack_count_not_found', 'source_temporarily_unavailable'
  ) or evidence is not null then
    raise exception 'invalid global volume result';
  end if;

  select * into candidate
  from ingest.global_volume_candidates
  where url = p_url
  for update;
  if not found or candidate.state <> 'checking' or candidate.locked_by <> p_worker_id
    or candidate.locked_until is null or candidate.locked_until < clock_timestamp()
  then
    raise exception 'global volume lease lost';
  end if;

  if result_status = 'verified' then
    observation_key := encode(extensions.digest(
      p_url || '|' || candidate.pack_count::text || '|' || candidate.pack_precision,
      'sha256'
    ), 'hex');
    insert into ingest.global_volume_observations (
      observation_key, source_url, report_group_sha256, pack_count, pack_precision,
      country_code, geography_basis, set_external_id, product_scope, source_language,
      collector_version, parser_version, evidence_sha256, first_verified_at,
      last_verified_at
    ) values (
      observation_key, candidate.url, candidate.report_group_sha256, candidate.pack_count,
      candidate.pack_precision, candidate.country_code, candidate.geography_basis,
      candidate.set_external_id, candidate.product_scope, candidate.source_language,
      'global-volume-v1', 'visible-pack-count-v1', evidence, clock_timestamp(), clock_timestamp()
    ) on conflict (source_url) do update set
      last_verified_at = excluded.last_verified_at,
      evidence_sha256 = excluded.evidence_sha256;
    update ingest.global_volume_candidates
    set state = 'verified', locked_by = null, locked_until = null,
        last_checked_at = clock_timestamp(), last_error_code = null,
        evidence_sha256 = evidence
    where url = p_url;
  elsif result_status = 'rejected' then
    update ingest.global_volume_candidates
    set state = 'rejected', locked_by = null, locked_until = null,
        last_checked_at = clock_timestamp(), last_error_code = error_code
    where url = p_url;
  else
    update ingest.global_volume_candidates
    set state = 'reported', locked_by = null, locked_until = null,
        last_checked_at = clock_timestamp(), last_error_code = error_code
    where url = p_url;
  end if;

  return jsonb_build_object('status', result_status, 'state',
    case when result_status = 'verified' then 'verified'
      when result_status = 'rejected' then 'rejected' else 'reported' end);
end;
$$;

-- Known-country rows are the only rows that enter the v2 country projection.
-- Unknown geography is accounted for by the v4 wrapper below, so a null code
-- can never create a malformed map cell.
create function ingest.global_volume_public_rows_v1()
returns table(
  ordinal integer,
  study_key text,
  public_id text,
  public_name text,
  public_note text,
  domain text,
  publisher_identity text,
  canonical_url text,
  country_code text,
  country_name text,
  attribution_basis text,
  set_language text,
  configured_set_name text,
  source_observed_at timestamptz,
  pack_count integer,
  set_external_id text,
  product_scope text,
  last_verified_at timestamptz
)
language sql
stable
security invoker
set search_path = pg_catalog
as $$
  select
    (50000 + row_number() over (order by candidates.url))::integer,
    'global-volume-' || encode(extensions.digest(candidates.url, 'sha256'), 'hex'),
    'global_volume_' || encode(extensions.digest(candidates.url, 'sha256'), 'hex'),
    'Reported public volume · ' || split_part(split_part(candidates.url, '://', 2), '/', 1),
    'Reported public pack volume. Counts are included for quantity coverage only, '
      || 'deduplicated by report group; they may be self-reported or title-derived '
      || 'and provide no hit-rate numerator or inference.',
    split_part(split_part(candidates.url, '://', 2), '/', 1),
    split_part(split_part(candidates.url, '://', 2), '/', 1),
    candidates.url,
    candidates.country_code,
    countries.country_name,
    candidates.geography_basis,
    candidates.source_language,
    null,
    coalesce(candidates.last_checked_at, candidates.first_seen_at),
    candidates.pack_count,
    coalesce(candidates.set_external_id, 'unknown'),
    candidates.product_scope,
    coalesce(candidates.last_checked_at, candidates.first_seen_at)
  from ingest.global_volume_candidates as candidates
  join catalog.iso_alpha2_codes as countries
    on countries.code = candidates.country_code
  where candidates.country_code is not null
    and candidates.state in ('reported', 'verified')
    and candidates.first_seen_at > statement_timestamp() - interval '365 days'
    and candidates.first_seen_at <= statement_timestamp();
$$;

do $projection$
declare
  definition text;
  anchor text := E'\n),\ndata_version_rows as (';
  country_anchor text := $country_anchor$'coverageAttributionBases', bases.value,$country_anchor$;
  aggregate_anchor text := $aggregate_anchor$count(distinct rows.publisher_identity)::integer as independent_sources,$aggregate_anchor$;
begin
  select pg_get_functiondef('public.get_public_study_coverage_v2()'::regprocedure)
    into definition;
  if position(anchor in definition) = 0 then
    raise exception 'coverage projection boundary drift';
  end if;
  definition := replace(
    definition,
    anchor,
    E'\n union all select * from ingest.global_volume_public_rows_v1()' || anchor
  );
  if position('''sources'', sources.value' in definition) = 0 then
    raise exception 'coverage source boundary drift';
  end if;
  definition := replace(
    definition,
    '''sources'', sources.value',
    $sources$'sources', sources.value || coalesce((select jsonb_agg(jsonb_build_object(
      'id','global_volume_' || encode(extensions.digest(v.domain,'sha256'),'hex'),
      'name','Reported public volume · ' || v.domain,
      'kind','community','access','public',
      'status',case when v.updated_at < statement_timestamp()-interval '48 hours'
        then 'delayed' else 'operational' end,
      'lastCollectedAt',v.updated_at,'url','https://' || v.domain || '/',
      'note','Reported public pack volume for quantity coverage only; counts may be self-reported or title-derived. No hit-rate numerator or inference.',
      'coverage',jsonb_build_object('packsObserved',v.packs_observed,
        'countriesObserved',v.countries_observed,'completeOpenings',v.complete_openings)))
      from (select domain,max(last_verified_at) as updated_at,
        sum(pack_count)::bigint as packs_observed,
        count(distinct country_code)::integer as countries_observed,
        count(*)::bigint as complete_openings
        from ingest.global_volume_public_rows_v1()
        group by domain order by domain) v),'[]'::jsonb)$sources$
  );
  if position(country_anchor in definition) = 0
    or position(aggregate_anchor in definition) = 0 then
    raise exception 'coverage country aggregation boundary drift';
  end if;
  definition := replace(
    definition,
    $country_marker$'coverageAttributionBases', bases.value,$country_marker$,
    $country_replacement$'reportedVolume', rows.reported_volume,
        'coverageAttributionBases', bases.value,$country_replacement$
  );
  definition := replace(
    definition,
    aggregate_anchor,
    aggregate_anchor || E'\n      bool_or(rows.public_id like ''global_volume_%'') as reported_volume,'
  );
  execute definition;
end;
$projection$;

-- Unknown-country totals remain visible in the v4 headline without fabricating
-- a country assignment. The known-country source list is already supplied by
-- the v2 projection above.
create or replace function public.get_public_study_coverage_v4()
returns jsonb language plpgsql stable security definer
set search_path = pg_catalog as $$
declare
  base jsonb := public.get_public_study_coverage_v3();
  packs bigint;
  openings bigint;
  first_publication date;
  last_verified timestamptz;
  unknown_location jsonb := null;
  volume_packs bigint := 0;
  volume_openings bigint := 0;
  volume_sources integer := 0;
  volume_last_verified timestamptz;
begin
  select coalesce(sum(a.pack_count),0),count(*),
    min((a.published_at at time zone 'UTC')::date),max(a.verified_at)
  into packs,openings,first_publication,last_verified
  from ingest.numbered_family_admissions a
  join ingest.numbered_family_candidates c using(url)
  where ingest.numbered_family_access_v1()
    and a.policy_version='kozaru-numbered-v1' and c.state='admitted'
    and a.published_at<=statement_timestamp()
    and a.verified_at<=statement_timestamp()
    and a.verified_at>statement_timestamp()-interval '48 hours'
    and not exists(select 1 from ingest.reviewed_public_study_contracts() f
      where f.canonical_url=a.url);

  if openings>0 then
    unknown_location := jsonb_build_object(
      'packsObserved',packs,'openings',openings,'independentSources',1,
      'updatedAt',last_verified);
    base := jsonb_set(base,'{period,start}',to_jsonb(least(
      (base#>>'{period,start}')::date,first_publication)));
  end if;

  select coalesce(sum(c.pack_count),0), count(*), count(distinct
    split_part(split_part(c.url, '://', 2), '/', 1)), max(coalesce(c.last_checked_at,c.first_seen_at))
  into volume_packs, volume_openings, volume_sources, volume_last_verified
  from ingest.global_volume_candidates c
  where c.country_code is null and c.state in ('reported','verified')
    and c.first_seen_at > statement_timestamp()-interval '365 days'
    and c.first_seen_at <= statement_timestamp();

  if volume_openings > 0 then
    if unknown_location is null then
      unknown_location := jsonb_build_object(
        'packsObserved',volume_packs,'openings',volume_openings,
        'independentSources',volume_sources,'updatedAt',volume_last_verified);
    else
      unknown_location := jsonb_build_object(
        'packsObserved',(unknown_location->>'packsObserved')::bigint + volume_packs,
        'openings',(unknown_location->>'openings')::bigint + volume_openings,
        'independentSources',(unknown_location->>'independentSources')::integer + volume_sources,
        'updatedAt',greatest((unknown_location->>'updatedAt')::timestamptz,volume_last_verified));
    end if;
  end if;

  if openings>0 then
    base := jsonb_set(base,'{sources}',(base->'sources')||jsonb_build_array(
      jsonb_build_object(
        'id','kozaru_numbered_openings','name','Kozaru numbered openings',
        'kind','community','access','public','status','operational',
        'lastCollectedAt',last_verified,'url','https://www.kozaru02.com/',
        'note','Numbered pack observations; opening location is unknown. No hit-rate inference.',
        'coverage',jsonb_build_object('packsObserved',packs,'countriesObserved',0,
          'completeOpenings',openings))));
  end if;
  return base||jsonb_build_object('schemaVersion','4.0.0','unknownLocation',unknown_location);
end;
$$;
alter function public.get_public_study_coverage_v4() owner to postgres;
revoke all on function public.get_public_study_coverage_v4() from public,anon,authenticated,service_role;
grant execute on function public.get_public_study_coverage_v4() to anon,authenticated;
comment on function public.get_public_study_coverage_v4() is
  'Coverage plus a separate reported-public-volume lane; counts are deduplicated and quantity-only, with no hit-rate inference or invented geography.';

do $permissions$
declare f regprocedure;
begin
  for f in select p.oid::regprocedure
    from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='ingest' and p.proname like '%global_volume%' loop
    execute format('alter function %s owner to postgres', f);
    execute format('revoke all on function %s from public,anon,authenticated,service_role', f);
  end loop;
end;
$permissions$;
grant execute on function ingest.import_global_volume_intake_v1(jsonb) to service_role;
grant execute on function ingest.claim_global_volume_candidates_v1(text,integer) to service_role;
grant execute on function ingest.finalize_global_volume_candidate_v1(text,text,jsonb) to service_role;

commit;
