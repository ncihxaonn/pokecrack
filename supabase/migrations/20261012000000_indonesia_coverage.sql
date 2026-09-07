begin;

-- Generated on MAM with Supabase CLI 2.116.0 as 20260907232932,
-- ordered after the existing future-dated 20261011 ledger.
-- Indonesian product market only; no physical opening location or hit rate.
do $migration$
declare
  definition text;
  old_suffix text := $old$      array['Only Garbage Rips 😬 | Chinese Gem Pack Vol 2 (Eeveelutions)']::text[]
    );$old$;
  new_suffix text := $new$      array['Only Garbage Rips 😬 | Chinese Gem Pack Vol 2 (Eeveelutions)']::text[]
    ),
    (
      26, 'bikuhime-hantaman-pertama-a-id-20-v1'::text,
      'public_study_bikuhime_id_20'::text,
      'bikuhime_hantaman_pertama_a_study'::text,
      'BIKUHIME first Hantaman Pertama Set A box study'::text,
      'One complete first Set A booster box: 20 packs. Indonesian product-market coverage only, not opening location. The other Set A box and Set B box are excluded; no normalized hit numerator or rate. Publication time is used as the observation date.'::text,
      'BIKUHIME first Set A box coverage'::text,
      'bikuhime.wordpress.com'::text,
      'https://bikuhime.wordpress.com/2020/05/17/yang-perlu-diketahui-sebelum-beli-booster-box-pokemon-tcg-bag-1/'::text,
      'public-study-bikuhime-hantaman-pertama-a-v1'::text,
      '{
  "study_key": "bikuhime-hantaman-pertama-a-id-20-v1",
  "canonical_url": "https://bikuhime.wordpress.com/2020/05/17/yang-perlu-diketahui-sebelum-beli-booster-box-pokemon-tcg-bag-1/",
  "collector_version": "public-study-bikuhime-hantaman-pertama-a-v1",
  "parser_version": "bikuhime-hantaman-pertama-a-evidence-v1",
  "country_code": "ID",
  "country_name": "Indonesia",
  "geography_basis": "product_market",
  "geography_confidence": "tier_b",
  "set_external_id": "hantaman-pertama-set-a",
  "set_language": "id",
  "set_name": "Hantaman Pertama Set A",
  "product_scope": "booster_box",
  "pack_count": 20,
  "observed_at": "2020-05-17T07:23:58Z",
  "denominator_complete": true,
  "set_official_url": "https://asia.pokemon-card.com/id/archive/card/sun_moon_series/1st_booster_pack_seta.html",
  "robots_url": "https://bikuhime.wordpress.com/robots.txt",
  "robots_checked_at": "2026-09-08",
  "terms_url": "https://wordpress.com/tos/",
  "terms_checked_at": "2026-09-08",
  "terms_status": "public_site_policy_reviewed",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      E'Hantaman Pertama Set A (pembelian pertama)\n1 booster box = 20 booster pack'::text,
      array['Yang Perlu Diketahui Sebelum Beli Booster Box Pokemon TCG (Bag. 1)']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal)
        from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 25))
  then
    raise exception 'Expected exact ordinal-25 reviewed-study registry';
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
where ordinal = 26 and study_key = 'bikuhime-hantaman-pertama-a-id-20-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_bikuhime_id_20');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_garbage_rips_cn_1'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 25' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-25 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 25', 'count(*) = 26'),
    old_tail, old_tail || ', ''public_study_bikuhime_id_20''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-25 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

do $migration$
declare
  definition text;
  needle text := $needle$'garbage-rips-gem-vol2-cn-1-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition
  from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-25 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''bikuhime-hantaman-pertama-a-id-20-v1''::text');
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
  where contracts.ordinal = 26 and contracts.study_key = 'bikuhime-hantaman-pertama-a-id-20-v1';
  evidence_hash := encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex');
  if evidence_hash <> '693653031f398c3006a7aa6d3b476c968f5b3f67d6452e73d904ed1ef377b328'
    or reviewed.config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
  then
    raise exception 'Indonesian first-box evidence contract drifted';
  end if;
  insert into ingest.public_study_coverage_observations (
    study_key, source_policy_id, country_code, country_name, source_observed_at,
    pack_count, set_external_id, product_scope, collector_version, parser_version,
    source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo
  ) values (
    reviewed.study_key, reviewed.policy_id, 'ID', 'Indonesia',
    (reviewed.config ->> 'observed_at')::timestamptz, 20, 'hantaman-pertama-set-a', 'booster_box',
    reviewed.policy_version, reviewed.config ->> 'parser_version',
    reviewed.policy_version, evidence_hash, statement_timestamp(), statement_timestamp(), false
  );
end;
$migration$;
commit;
