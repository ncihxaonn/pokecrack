begin;

-- Generated on MAM with Supabase CLI 2.116.0 as 20260908020719,
-- ordered after the existing future-dated 20261012 ledger.
-- Japanese product market only; no physical opening location or hit rate.
do $migration$
declare
  definition text;
  old_suffix text := $old$      array['Yang Perlu Diketahui Sebelum Beli Booster Box Pokemon TCG (Bag. 1)']::text[]
    );$old$;
  new_suffix text := $new$      array['Yang Perlu Diketahui Sebelum Beli Booster Box Pokemon TCG (Bag. 1)']::text[]
    ),
    (
      27, 'nanjakorya-star-birth-jp-100-v1'::text,
      'public_study_nanjakorya_jp_100'::text,
      'nanjakorya_star_birth_study'::text,
      'Nanjakorya Star Birth 100-pack study'::text,
      'One 100-pack Star Birth cohort: 80 loose packs plus 20 premium-box packs. RR16 RRR6 SR4 HR1 are card counts, not hit-pack counts or SIR rates. Japanese product market only; physical opening place/date unknown. Observation timestamp is publication.'::text,
      'Nanjakorya Star Birth 100-pack coverage'::text,
      'nanjakorya.com'::text,
      'https://nanjakorya.com/1123'::text,
      'public-study-nanjakorya-star-birth-v1'::text,
      '{
  "study_key": "nanjakorya-star-birth-jp-100-v1",
  "canonical_url": "https://nanjakorya.com/1123",
  "collector_version": "public-study-nanjakorya-star-birth-v1",
  "parser_version": "nanjakorya-star-birth-evidence-v1",
  "country_code": "JP",
  "country_name": "Japan",
  "geography_basis": "product_market",
  "geography_confidence": "tier_b",
  "set_external_id": "s9",
  "set_language": "ja",
  "set_name": "Star Birth",
  "product_scope": "all",
  "pack_count": 100,
  "observed_at": "2022-02-21T20:40:46Z",
  "denominator_complete": true,
  "set_official_url": "https://www.pokemon-card.com/ex/s9/index.html",
  "robots_url": "https://nanjakorya.com/robots.txt",
  "robots_checked_at": "2026-09-08",
  "terms_checked_at": "2026-09-08",
  "terms_status": "no_independent_terms_page",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse",
  "rarity_card_counts": {
    "RR": 16,
    "RRR": 6,
    "SR": 4,
    "HR": 1
  },
  "loose_pack_count": 80,
  "premium_box_pack_count": 20,
  "opening_country": null,
  "opened_at": null,
  "report_evidence_sha256": "b5dc75b772fb6b63a198c72f43193e76e2fd48f332ec546dd1800062640552ad"
}'::jsonb,
      E'バラ100パック開けてみた結果【ポケカ-スターバース編】'::text,
      array['バラ100パック開けてみた結果【ポケカ-スターバース編】']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal)
        from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 26))
  then
    raise exception 'Expected exact ordinal-26 reviewed-study registry';
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
where ordinal = 27 and study_key = 'nanjakorya-star-birth-jp-100-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_nanjakorya_jp_100');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_bikuhime_id_20'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 26' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-26 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 26', 'count(*) = 27'),
    old_tail, old_tail || ', ''public_study_nanjakorya_jp_100''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-26 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'bikuhime-hantaman-pertama-a-id-20-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition
  from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-26 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''nanjakorya-star-birth-jp-100-v1''::text');
end;
$migration$;

-- Store only the independently reviewed minimal facts; live collection and
-- public projection still require separate post-deployment verification.
do $migration$
declare
  reviewed record;
  evidence_hash text;
begin
  select contracts.*, policies.id as policy_id into strict reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key
    and policies.config = contracts.config
    and policies.version = contracts.policy_version
    and policies.enabled and not policies.is_demo
  where contracts.ordinal = 27 and contracts.study_key = 'nanjakorya-star-birth-jp-100-v1';
  evidence_hash := encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex');
  if evidence_hash <> 'e9c87d754c51746c9af0cf3c85d164bfee5bf90c84e69e8c65ca46cfda2601e9'
    or reviewed.config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
  then
    raise exception 'Japanese complete-report evidence contract drifted';
  end if;
  insert into ingest.public_study_coverage_observations (
    study_key, source_policy_id, country_code, country_name, source_observed_at,
    pack_count, set_external_id, product_scope, collector_version, parser_version,
    source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo
  ) values (
    reviewed.study_key, reviewed.policy_id, 'JP', 'Japan',
    (reviewed.config ->> 'observed_at')::timestamptz, 100, 's9', 'all',
    reviewed.policy_version, reviewed.config ->> 'parser_version',
    reviewed.policy_version, evidence_hash, statement_timestamp(), statement_timestamp(), false
  );
end;
$migration$;
commit;
