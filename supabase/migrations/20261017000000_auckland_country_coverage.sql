begin;

-- Generated with Supabase CLI 2.115.0 on MAM as 20260908221904;
-- ordered after the existing immutable 20261016 migration ledger.
-- One complete organizer-reported event segment, no rate numerator.
do $migration$
declare
  definition text;
  previous_contracts jsonb;
  old_suffix text := $old$      array['タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。']::text[]
    );$old$;
  new_suffix text := $new$      array['タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。']::text[]
    ),
    (
      30, 'auckland-show-mighty-ape-nz-105-v1'::text,
      'public_study_auckland_nz_105'::text,
      'auckland_show_mighty_ape_study'::text,
      'Auckland Card Show 105-pack coverage'::text,
      'Organizer-reported complete 105-pack segment at the August 2025 Auckland event. Mixed expansions and unknown card language; one cohort, not 105 independent opening events. Other segments, attendance and card hits are excluded. No normalized pack-hit numerator or national total is claimed.'::text,
      'Auckland Card Show 105-pack coverage'::text,
      'www.aucklandcardshow.com'::text,
      'https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap'::text,
      'public-study-auckland-show-v1'::text,
      '{
  "study_key": "auckland-show-mighty-ape-nz-105-v1",
  "canonical_url": "https://www.aucklandcardshow.com/post/auckland-card-show-2025-recap",
  "collector_version": "public-study-auckland-show-v1",
  "parser_version": "auckland-show-105-evidence-v1",
  "country_code": "NZ",
  "country_name": "New Zealand",
  "geography_basis": "publisher_country",
  "geography_confidence": "tier_b",
  "publisher_country_url": "https://www.aucklandcardshow.com/about",
  "opening_country": "NZ",
  "opened_on": "2025-08-10",
  "set_external_id": "mixed-pokemon-tcg-2025",
  "set_language": "und",
  "set_scope": "mixed_multi_expansion",
  "set_name": "Mixed Pokémon TCG expansions",
  "product_scope": "all",
  "pack_count": 105,
  "observed_at": "2025-09-30T00:08:20.972Z",
  "denominator_complete": true,
  "cohort_id": "auckland-card-show-2025-mighty-ape-105",
  "robots_url": "https://www.aucklandcardshow.com/robots.txt",
  "robots_checked_at": "2026-09-09",
  "terms_url": "https://www.aucklandcardshow.com/terms-of-use",
  "terms_checked_at": "2026-09-09",
  "terms_status": "public_site_policy_reviewed",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      '105 packs'::text,
      array['Auckland Card Show 2025 Recap']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 29)) then
    raise exception 'Expected exact ordinal-29 reviewed-study registry';
  end if;
  select jsonb_agg(to_jsonb(c) order by ordinal) into previous_contracts
    from ingest.reviewed_public_study_contracts() c;
  execute replace(definition, old_suffix, new_suffix);
  if previous_contracts is distinct from (
    select jsonb_agg(to_jsonb(c) order by ordinal)
    from ingest.reviewed_public_study_contracts() c where ordinal <= 29
  ) then
    raise exception 'Existing reviewed contracts changed';
  end if;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;

insert into ingest.source_policies (
  source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, include_subdomains,
  min_delay_seconds, max_pages_per_run, max_items_per_run, max_concurrency,
  statistics_eligible_default, retention_days, config, version,
  expected_interval_seconds, is_demo
)
select policy_key, display_name, 'public_web', domain, canonical_url, true,
  'scrapling_http', 'public', 'respect', array['scrapling_http']::text[], false,
  30, 2, 1, 1, true, 730, config, policy_version, 86400, false
from ingest.reviewed_public_study_contracts()
where ordinal = 30 and study_key = 'auckland-show-mighty-ape-nz-105-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_auckland_nz_105');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_bokunotebook_th_1'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 29' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-29 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 29', 'count(*) = 30'),
    old_tail, old_tail || ', ''public_study_auckland_nz_105''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-29 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'bokunotebook-vstar-universe-th-1-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-29 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''auckland-show-mighty-ape-nz-105-v1''::text');
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$      reviewed.study_key = 'richards-bricks-charizard-upc-pr-18-v1'$needle$;
  replacement text := $replacement$      reviewed.study_key = 'auckland-show-mighty-ape-nz-105-v1'
      and reviewed.config ->> 'set_external_id' = 'mixed-pokemon-tcg-2025'
      and reviewed.config ->> 'set_scope' = 'mixed_multi_expansion'
      and reviewed.config ->> 'set_language' = 'und'
      and reviewed.config ->> 'product_scope' = 'all'
    )
    or (
      reviewed.study_key = 'richards-bricks-charizard-upc-pr-18-v1'$replacement$;
begin
  select pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  ) into definition;
  if position(needle in definition) = 0 or position('auckland-show-mighty-ape-nz-105-v1' in definition) > 0 then
    raise exception 'Expected exact mixed-expansion catalog boundary';
  end if;
  execute replace(definition, needle, replacement);
end;
$migration$;

do $migration$
declare
  reviewed record;
  evidence_hash text;
begin
  select contracts.*, policies.id as policy_id into strict reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key and policies.config = contracts.config
    and policies.version = contracts.policy_version and policies.enabled and not policies.is_demo
  where contracts.ordinal = 30 and study_key = 'auckland-show-mighty-ape-nz-105-v1';
  evidence_hash := encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex');
  if evidence_hash <> '2adc1fd8cfc93ee9b1208dedc19b37aab7b6a720c5ffc8ef1220a8c028c1383d'
    or reviewed.config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version'] then
    raise exception 'Auckland complete-opening evidence contract drifted';
  end if;
  insert into ingest.public_study_coverage_observations (
    study_key, source_policy_id, country_code, country_name, source_observed_at,
    pack_count, set_external_id, product_scope, collector_version, parser_version,
    source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo
  ) values (
    reviewed.study_key, reviewed.policy_id, 'NZ', 'New Zealand',
    (reviewed.config ->> 'observed_at')::timestamptz, 105, 'mixed-pokemon-tcg-2025', 'all',
    reviewed.policy_version, reviewed.config ->> 'parser_version',
    reviewed.policy_version, evidence_hash, statement_timestamp(), statement_timestamp(), false
  );
end;
$migration$;
commit;
