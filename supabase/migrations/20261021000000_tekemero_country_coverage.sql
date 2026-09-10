begin;

-- Scaffold generated on MAM with Supabase CLI 2.115.0:
-- /tmp/pokecrack-intake-tools.6VZMmqqb/supabase migration new tekemero_country_coverage
-- generated 20260910000630_tekemero_country_coverage.sql; ordered after
-- immutable 20261020000000_hitpack_country_coverage.sql.
-- Fixed reviewed cohort only; no observation seed or source-family enablement.
do $migration$
declare
  definition text;
  previous_contracts jsonb;
  old_suffix text := $old$      array['Pokémon Pitch Black pull rates: co padlo z 36 boosterů?']::text[]
    );$old$;
  new_suffix text := $new$      array['Pokémon Pitch Black pull rates: co padlo z 36 boosterů?']::text[]
    ),
    (
      32, 'tekemero-munikis-zero-jp-30-v1'::text,
      'public_study_tekemero_jp_30'::text,
      'tekemero_munikis_zero_study'::text,
      'Tekemero M3 30-pack coverage'::text,
      'One complete 30-pack cohort. Japan denotes product market, not physical opening location. Publication time is not opening time. Comparison articles are not additive; no numerator or rate is published.'::text,
      'Tekemero M3 30-pack coverage'::text,
      'tekemero.com'::text,
      'https://tekemero.com/260715-02/'::text,
      'public-study-tekemero-munikis-zero-v1'::text,
      '{
  "study_key": "tekemero-munikis-zero-jp-30-v1",
  "canonical_url": "https://tekemero.com/260715-02/",
  "collector_version": "public-study-tekemero-munikis-zero-v1",
  "parser_version": "tekemero-munikis-zero-30-evidence-v1",
  "country_code": "JP",
  "country_name": "Japan",
  "geography_basis": "product_market",
  "geography_confidence": "tier_b",
  "opening_country": null,
  "opened_at": null,
  "set_external_id": "M3",
  "set_language": "ja",
  "set_name": "ムニキスゼロ",
  "set_official_url": "https://www.pokemon-card.com/ex/m3/",
  "product_scope": "booster_box",
  "pack_count": 30,
  "observed_at": "2026-07-15T06:48:03Z",
  "observed_at_basis": "original_article_publication_not_opening_time",
  "denominator_complete": true,
  "cohort_id": "tekemero-post-447-m3-complete-box",
  "robots_url": "https://tekemero.com/robots.txt",
  "robots_checked_at": "2026-09-09",
  "terms_url": "https://tekemero.com/privacy-policy/",
  "terms_checked_at": "2026-09-09",
  "terms_status": "privacy_policy_reviewed_no_separate_terms_found",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      '30パック'::text,
      array['ムニキスゼロ', '30パック']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 31)) then
    raise exception 'Expected exact ordinal-31 reviewed-study registry';
  end if;
  select jsonb_agg(to_jsonb(c) order by ordinal) into previous_contracts
    from ingest.reviewed_public_study_contracts() c;
  execute replace(definition, old_suffix, new_suffix);
  if previous_contracts is distinct from (
    select jsonb_agg(to_jsonb(c) order by ordinal)
    from ingest.reviewed_public_study_contracts() c where ordinal <= 31
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
where ordinal = 32 and study_key = 'tekemero-munikis-zero-jp-30-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_tekemero_jp_30');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_hitpack_cz_36'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 31' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-31 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 31', 'count(*) = 32'),
    old_tail, old_tail || ', ''public_study_tekemero_jp_30''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-31 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'hitpack-pitch-black-cz-36-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-31 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''tekemero-munikis-zero-jp-30-v1''::text');
end;
$migration$;

-- Existing native ja/M3 official-set validation and all RPC signatures remain unchanged.
commit;
