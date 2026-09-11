-- The quantity-first lane publishes bounded report facts without creating a
-- statistical observation, a numerator, or a private source profile.
create extension if not exists pgtap with schema extensions;
begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select ok(
  not has_table_privilege('anon', 'ingest.global_volume_candidates', 'SELECT')
  and not has_table_privilege('authenticated', 'ingest.global_volume_candidates', 'SELECT')
  and not has_table_privilege('service_role', 'ingest.global_volume_candidates', 'SELECT')
  and not has_table_privilege('service_role', 'ingest.global_volume_candidates', 'INSERT')
  and not has_table_privilege('service_role', 'ingest.global_volume_observations', 'SELECT')
  and has_function_privilege(
    'service_role',
    'ingest.import_global_volume_intake_v1(jsonb)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'ingest.claim_global_volume_candidates_v1(text,integer)',
    'EXECUTE'
  )
  and has_function_privilege(
    'service_role',
    'ingest.finalize_global_volume_candidate_v1(text,text,jsonb)',
    'EXECUTE'
  )
  and not has_function_privilege(
    'anon',
    'ingest.import_global_volume_intake_v1(jsonb)',
    'EXECUTE'
  ),
  'quantity-first tables stay private while the collector receives only the three bounded RPCs'
);
select is(
  (
    select count(*)::integer
    from pg_class as relations
    join pg_namespace as namespaces on namespaces.oid = relations.relnamespace
    where namespaces.nspname = 'ingest'
      and relations.relname in ('global_volume_candidates', 'global_volume_observations')
      and relations.relrowsecurity
      and relations.relforcerowsecurity
  ),
  2,
  'both quantity-first tables force RLS'
);
select ok(
  not exists (
    select 1
    from information_schema.columns
    where table_schema = 'ingest'
      and table_name in ('global_volume_candidates', 'global_volume_observations')
      and column_name in ('body', 'html', 'raw_html', 'text', 'author', 'profile', 'handle')
  ),
  'the quantity-first lane stores no page body or personal profile fields'
);

create function pg_temp.volume_manifest(p_url text, p_count integer, p_country text)
returns jsonb
language sql
as $$
  select jsonb_build_object(
    'schema_version', 'global-volume-intake-v1',
    'snapshot_sha256', repeat('c', 64),
    'candidates', jsonb_build_array(jsonb_build_object(
      'url', p_url,
      'report_group_sha256', repeat('b', 64),
      'pack_count', p_count,
      'pack_precision', 'exact_reported',
      'country_code', p_country,
      'geography_basis', case when p_country is null then 'unknown' else 'opening_location' end,
      'set_external_id', null,
      'product_scope', 'all',
      'source_language', 'und'
    ))
  );
$$;

select is(
  (ingest.import_global_volume_intake_v1(
    pg_temp.volume_manifest('https://pgtap.example/volume', 420, 'US')
  )->>'candidates_inserted')::integer,
  1,
  'a new public report count enters the bounded queue'
);
select is(
  (select count(*)::integer
   from ingest.global_volume_candidates
   where url = 'https://pgtap.example/volume' and state = 'reported'),
  1,
  'reported counts are publishable before the optional page check'
);

create temporary table claimed_global_volume as
select *
from ingest.claim_global_volume_candidates_v1('pgtap-global-volume', 1);
select is(
  (select count(*)::integer from claimed_global_volume),
  1,
  'the worker receives one leased quantity candidate'
);
select is(
  (select attempts from claimed_global_volume),
  1,
  'the lease increments the bounded attempt counter'
);
select is(
  (select ingest.finalize_global_volume_candidate_v1(
    'pgtap-global-volume',
    'https://pgtap.example/volume',
    jsonb_build_object(
      'status', 'verified',
      'error_code', null,
      'evidence_sha256', repeat('d', 64)
    )
  )->>'state'),
  'verified',
  'a hash-only page check verifies the candidate'
);
select is(
  (select pack_count from ingest.global_volume_observations
   where source_url = 'https://pgtap.example/volume'),
  420,
  'the verified observation retains only the reported quantity and bounded identity fields'
);
select ok(exists (
  select 1
  from ingest.global_volume_public_rows_v1()
  where canonical_url = 'https://pgtap.example/volume'
    and country_code = 'US'
    and pack_count = 420
), 'verified known-country volume is available to the public projection');
select ok(exists (
  select 1
  from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'countries') as country
  where country ->> 'countryCode' = 'US'
    and (country ->> 'reportedVolume')::boolean
    and country -> 'coverageAttributionBases' @> '["opening_location"]'::jsonb
), 'the public country bucket marks quantity-only volume without a rate');
select ok(not exists (
  select 1
  from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') as country
  where country ->> 'countryCode' = 'US'
    and country ? 'qualifyingHitPacks'
), 'the quantity-first row cannot create a hit numerator');

select is(
  (ingest.import_global_volume_intake_v1(
    pg_temp.volume_manifest('https://pgtap.example/rejected', 7, null)
  )->>'candidates_inserted')::integer,
  1,
  'an unknown-country report can enter without fabricated geography'
);
select is(
  (select count(*)::integer
   from ingest.claim_global_volume_candidates_v1('pgtap-global-volume', 1)),
  1,
  'the next report can be leased for the bounded check'
);
select is(
  (ingest.finalize_global_volume_candidate_v1(
    'pgtap-global-volume',
    'https://pgtap.example/rejected',
    '{"status":"rejected","error_code":"robots_denied","evidence_sha256":null}'::jsonb
  )->>'state'),
  'rejected',
  'a denied page is removed from the public quantity projection'
);
select is(
  (select count(*)::integer from ingest.global_volume_public_rows_v1()
   where canonical_url = 'https://pgtap.example/rejected'),
  0,
  'rejected sources never become public rows'
);
select is(
  (select count(*)::integer
   from jsonb_array_elements(public.get_public_study_coverage_v4() -> 'sources') as source
   where source ->> 'id' like 'global_volume_%'),
  1,
  'the public source list contains only the verified domain bucket'
);

select * from finish();
rollback;
