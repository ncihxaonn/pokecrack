begin;

-- Scaffold generated on MAM with node:22-bookworm-slim and
-- npx supabase@2.115.0 migration new hitpack_country_coverage as
-- 20260909224922_hitpack_country_coverage.sql; ordered after the existing
-- immutable 20261019000000 ledger.
-- One original 36-pack report, no numerator. No observation is seeded:
-- the first reviewed collector admission must pass the existing finalizer.
do $migration$
declare
  definition text;
  previous_contracts jsonb;
  old_suffix text := $old$      array['Auckland Card Show 2025 Recap']::text[]
    );$old$;
  new_suffix text := $new$      array['Auckland Card Show 2025 Recap']::text[]
    ),
    (
      31, 'hitpack-pitch-black-cz-36-v1'::text,
      'public_study_hitpack_cz_36'::text,
      'hitpack_pitch_black_study'::text,
      'Hitpack Pitch Black 36-pack coverage'::text,
      'Original complete 36-pack report. Czechia identifies publisher country, not physical opening location. Card language is unknown. Publication date is a UTC day bucket. The cited 753-pack study is not additive; no numerator or rate is published.'::text,
      'Hitpack Pitch Black 36-pack coverage'::text,
      'www.hitpack.cz'::text,
      'https://www.hitpack.cz/nase-novinky/pokemon-pitch-black-pull-rates-36-boosteru/'::text,
      'public-study-hitpack-pitch-black-v1'::text,
      '{
  "study_key": "hitpack-pitch-black-cz-36-v1",
  "canonical_url": "https://www.hitpack.cz/nase-novinky/pokemon-pitch-black-pull-rates-36-boosteru/",
  "collector_version": "public-study-hitpack-pitch-black-v1",
  "parser_version": "hitpack-pitch-black-36-evidence-v1",
  "country_code": "CZ",
  "country_name": "Czechia",
  "geography_basis": "publisher_country",
  "geography_confidence": "tier_b",
  "publisher_country_url": "https://www.hitpack.cz/obchodni-podminky/",
  "publisher_country_review_method": "source_business_identity_matched_to_official_ares_country",
  "publisher_country_checked_at": "2026-09-09",
  "opening_country": null,
  "opened_at": null,
  "set_external_id": "me05",
  "set_language": "und",
  "set_language_basis": "opening_report_does_not_state_card_language",
  "set_name": "Pitch Black",
  "product_scope": "booster_box",
  "pack_count": 36,
  "observed_at": "2026-07-28T00:00:00Z",
  "source_publication_date": "2026-07-28",
  "publication_time_precision": "day",
  "observed_at_basis": "publication_date_utc_day_bucket_not_exact_timestamp",
  "denominator_complete": true,
  "cohort_id": "hitpack-pitch-black-box-20260728",
  "robots_url": "https://www.hitpack.cz/robots.txt",
  "robots_checked_at": "2026-09-09",
  "terms_url": "https://www.hitpack.cz/obchodni-podminky/",
  "terms_checked_at": "2026-09-09",
  "terms_status": "public_site_policy_reviewed",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      '36 balíčků'::text,
      array['Pokémon Pitch Black pull rates: co padlo z 36 boosterů?']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 30)) then
    raise exception 'Expected exact ordinal-30 reviewed-study registry';
  end if;
  select jsonb_agg(to_jsonb(c) order by ordinal) into previous_contracts
    from ingest.reviewed_public_study_contracts() c;
  execute replace(definition, old_suffix, new_suffix);
  if previous_contracts is distinct from (
    select jsonb_agg(to_jsonb(c) order by ordinal)
    from ingest.reviewed_public_study_contracts() c where ordinal <= 30
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
where ordinal = 31 and study_key = 'hitpack-pitch-black-cz-36-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_hitpack_cz_36');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_auckland_nz_105'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 30' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-30 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 30', 'count(*) = 31'),
    old_tail, old_tail || ', ''public_study_hitpack_cz_36''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-30 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'auckland-show-mighty-ape-nz-105-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-30 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''hitpack-pitch-black-cz-36-v1''::text');
end;
$migration$;

-- The normal branch requires source language en; und does not qualify for
-- that branch or the two-letter non-English official-set branch. Bind only
-- this exact unknown-language report to the existing English catalog identity
-- without asserting that the opened cards were English.
do $migration$
declare
  definition text;
  needle text := $needle$      reviewed.study_key = 'auckland-show-mighty-ape-nz-105-v1'$needle$;
  replacement text := $replacement$      reviewed.study_key = 'hitpack-pitch-black-cz-36-v1'
      and reviewed.config ->> 'set_external_id' = 'me05'
      and reviewed.config ->> 'set_name' = 'Pitch Black'
      and reviewed.config ->> 'set_language' = 'und'
      and reviewed.config ->> 'product_scope' = 'booster_box'
      and exists (
        select 1 from catalog.sets as sets
        where sets.external_source = 'tcgdex'
          and sets.external_id = 'me05'
          and sets.name = 'Pitch Black'
          and sets.language = 'en'
          and sets.is_active
          and not sets.is_demo
      )
    )
    or (
      reviewed.study_key = 'auckland-show-mighty-ape-nz-105-v1'$replacement$;
begin
  select pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  ) into definition;
  if definition is null or position(needle in definition) = 0
    or position('hitpack-pitch-black-cz-36-v1' in definition) > 0 then
    raise exception 'Expected exact pre-Hitpack catalog boundary';
  end if;
  execute replace(definition, needle, replacement);
end;
$migration$;

-- All public API signatures and the preceding source exceptions are unchanged.
commit;
