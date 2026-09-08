begin;

-- Created using Supabase CLI 2.115.0 on MAM as 20260908113706;
-- ordered after the existing future-dated 20261014 migration ledger.
-- One source-verified pack, not a national total or a hit-rate numerator.
do $migration$
declare
  definition text;
  old_suffix text := $old$      array['パラダイムトリガー開封結果まとめ']::text[]
    );$old$;
  new_suffix text := $new$      array['パラダイムトリガー開封結果まとめ']::text[]
    ),
    (
      29, 'bokunotebook-vstar-universe-th-1-v1'::text,
      'public_study_bokunotebook_th_1'::text,
      'bokunotebook_vstar_universe_study'::text,
      'Bokunotebook Thai VSTAR Universe opening'::text,
      'One complete Thai-language VSTAR Universe pack. Product market only, not the physical opening country. Observation timestamp is publication; actual opening date unknown. Ten cards are not ten packs or a normalized hit numerator.'::text,
      'Bokunotebook VSTAR Universe one-pack coverage'::text,
      'bokunotebook.com'::text,
      'https://bokunotebook.com/archives/13725'::text,
      'public-study-bokunotebook-vstar-universe-v1'::text,
      '{
  "study_key": "bokunotebook-vstar-universe-th-1-v1",
  "canonical_url": "https://bokunotebook.com/archives/13725",
  "collector_version": "public-study-bokunotebook-vstar-universe-v1",
  "parser_version": "bokunotebook-vstar-universe-evidence-v1",
  "country_code": "TH",
  "country_name": "Thailand",
  "geography_basis": "product_market",
  "geography_confidence": "tier_b",
  "set_external_id": "s12a",
  "set_language": "th",
  "set_name": "จักรวาลแห่ง VSTAR",
  "product_scope": "all",
  "pack_count": 1,
  "observed_at": "2026-07-01T12:01:46Z",
  "denominator_complete": true,
  "set_official_url": "https://asia.pokemon-card.com/th/archive/special/card/s12a/index.html",
  "robots_url": "https://bokunotebook.com/robots.txt",
  "robots_checked_at": "2026-09-08",
  "terms_url": "https://bokunotebook.com/privacy-policy",
  "terms_checked_at": "2026-09-08",
  "terms_status": "public_site_policy_reviewed",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
  "opening_country": null,
  "opened_at": null,
  "observed_card_count": 10
}'::jsonb,
      E'1パック\nVSTARユニバース\n全部で10枚'::text,
      array['1パック', 'VSTARユニバース', '全部で10枚']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 28)) then
    raise exception 'Expected exact ordinal-28 reviewed-study registry';
  end if;
  execute replace(definition, old_suffix, new_suffix);
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
where ordinal = 29 and study_key = 'bokunotebook-vstar-universe-th-1-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_bokunotebook_th_1');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_nanjakorya_paradigm_100'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 28' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-28 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 28', 'count(*) = 29'),
    old_tail, old_tail || ', ''public_study_bokunotebook_th_1''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-28 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'nanjakorya-paradigm-jp-100-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-28 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''bokunotebook-vstar-universe-th-1-v1''::text');
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
  where contracts.ordinal = 29 and study_key = 'bokunotebook-vstar-universe-th-1-v1';
  evidence_hash := encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex');
  if evidence_hash <> '575413295f78946c02ce9c97319f4688652a55d113df54b57c7fed3f626a9f31'
    or reviewed.config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version'] then
    raise exception 'Bokunotebook complete-opening evidence contract drifted';
  end if;
  insert into ingest.public_study_coverage_observations (
    study_key, source_policy_id, country_code, country_name, source_observed_at,
    pack_count, set_external_id, product_scope, collector_version, parser_version,
    source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo
  ) values (
    reviewed.study_key, reviewed.policy_id, 'TH', 'Thailand',
    (reviewed.config ->> 'observed_at')::timestamptz, 1, 's12a', 'all',
    reviewed.policy_version, reviewed.config ->> 'parser_version',
    reviewed.policy_version, evidence_hash, statement_timestamp(), statement_timestamp(), false
  );
end;
$migration$;
commit;
