begin;

-- One reviewed denominator-only display report from Bisafans. Germany is the
-- publisher country, not an inferred physical opening location; the page's
-- 47-card yield is not a hit-pack numerator. No observation is seeded: the
-- first collector admission must pass the existing evidence-only finalizer.
do $migration$
declare
  definition text;
  previous_contracts jsonb;
  old_suffix text := $old$      array['ムニキスゼロ', '30パック']::text[]
    );$old$;
  new_suffix text := $new$      array['ムニキスゼロ', '30パック']::text[]
    ),
    (
      33, 'bisafans-flying-fists-de-36-v1'::text,
      'public_study_bisafans_de_36'::text,
      'bisafans_flying_fists_study'::text,
      'Bisafans Fliegende Fäuste 36-pack coverage'::text,
      'One complete 36-pack display documented on a German public source. Germany denotes publisher country, not physical opening location. The page reports a 47-card rare-or-below yield; that card count is not a hit-pack numerator. No numerator or rate is published.'::text,
      'Bisafans Fliegende Fäuste 36-pack coverage'::text,
      'www.bisafans.de'::text,
      'https://www.bisafans.de/sammelkarten/sets/xy/fliegende-faeuste/statistiken.php'::text,
      'public-study-bisafans-flying-fists-v1'::text,
      '{
  "study_key": "bisafans-flying-fists-de-36-v1",
  "canonical_url": "https://www.bisafans.de/sammelkarten/sets/xy/fliegende-faeuste/statistiken.php",
  "collector_version": "public-study-bisafans-flying-fists-v1",
  "parser_version": "bisafans-flying-fists-evidence-v1",
  "country_code": "DE",
  "country_name": "Germany",
  "geography_basis": "publisher_country",
  "geography_confidence": "tier_b",
  "publisher_country_url": "https://www.bisafans.de/impressum.php",
  "publisher_country_review_method": "source_business_identity_matched_to_public_site_impressum",
  "publisher_country_checked_at": "2026-09-11",
  "opening_country": null,
  "opened_at": null,
  "set_external_id": "xy3",
  "set_language": "de",
  "set_language_basis": "source_page_is_german",
  "set_name": "Fliegende Fäuste",
  "set_official_url": "https://www.pokemon.com/de/pokemon-sammelkartenspiel/pokemon-karten/series/xy3/49/",
  "product_scope": "booster_box",
  "pack_count": 36,
  "observed_at": "2026-09-11T00:00:00Z",
  "observed_at_basis": "initial_mam_verification_date_not_opening_time",
  "denominator_complete": true,
  "cohort_id": "bisafans-fliegende-faeuste-display-36",
  "robots_url": "https://www.bisafans.de/robots.txt",
  "robots_checked_at": "2026-09-11",
  "terms_checked_at": "2026-09-11",
  "terms_status": "no_separate_content_reuse_license_found",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      E'Da wir zu jeder Pokémon Sammelkartenerweiterung ein Boosterdisplay mit 36 Packungen öffnen\nIn XY Fliegende Fäuste waren in unserem Display 47 Karten der Seltenheitsstufe Rare oder seltener.'::text,
      array['Statistiken']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 32)) then
    raise exception 'Expected exact ordinal-32 reviewed-study registry';
  end if;
  select jsonb_agg(to_jsonb(c) order by ordinal) into previous_contracts
    from ingest.reviewed_public_study_contracts() c;
  execute replace(definition, old_suffix, new_suffix);
  if previous_contracts is distinct from (
    select jsonb_agg(to_jsonb(c) order by ordinal)
    from ingest.reviewed_public_study_contracts() c where ordinal <= 32
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
where ordinal = 33 and study_key = 'bisafans-flying-fists-de-36-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_bisafans_de_36');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_tekemero_jp_30'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 32' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-32 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 32', 'count(*) = 33'),
    old_tail, old_tail || ', ''public_study_bisafans_de_36''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-32 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'tekemero-munikis-zero-jp-30-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-32 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''bisafans-flying-fists-de-36-v1''::text');
end;
$migration$;

-- No observation seed: the real MAM collector must fetch the exact page and
-- pass the immutable evidence-only finalizer before Germany is public.
commit;
