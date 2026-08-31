-- Authorized opening review: strict RPC contracts, least privilege, revision
-- fencing, immutable audit, expiry, retraction and public redaction.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create function pg_temp.review_sqlstate(requested_id uuid, requested_revision bigint)
returns text
language plpgsql
volatile
as $$
begin
  perform *
  from ingest.review_authorized_opening_v1(
    requested_id,
    requested_revision,
    'rejected',
    repeat('f', 64),
    'reviewer_rejected'
  );
  return null;
exception when others then
  return sqlstate;
end;
$$;

create function pg_temp.retraction_sqlstate(
  requested_id uuid,
  requested_reason text
)
returns text
language plpgsql
volatile
as $$
begin
  perform *
  from ingest.retract_authorized_opening_v1(
    requested_id,
    repeat('f', 64),
    requested_reason
  );
  return null;
exception when others then
  return sqlstate;
end;
$$;

create function pg_temp.observation_mutation_sqlstate(requested_id uuid)
returns text
language plpgsql
volatile
as $$
begin
  update ingest.authorized_opening_observations
  set pack_count = pack_count + 1
  where id = requested_id;
  return null;
exception when others then
  return sqlstate;
end;
$$;

select has_table(
  'ingest',
  'authorized_opening_submissions',
  'authorized opening submission queue exists'
);
select has_table(
  'ingest',
  'authorized_opening_review_events',
  'authorized opening review audit exists'
);
select has_table(
  'ingest',
  'authorized_opening_observations',
  'authorized opening immutable observation ledger exists'
);
select has_table(
  'ingest',
  'authorized_opening_retractions',
  'authorized opening append-only retraction ledger exists'
);
select has_column(
  'catalog',
  'iso_alpha2_codes',
  'country_name',
  'trusted ISO catalogue stores the canonical country display name'
);
select is(
  (select count(*)::integer from catalog.iso_alpha2_codes),
  249,
  'trusted ISO catalogue contains exactly 249 codes'
);
select is(
  (select country_name from catalog.iso_alpha2_codes where code = 'JP'),
  'Japan',
  'trusted ISO catalogue derives Japan from the code'
);
select is(
  (select country_name from catalog.iso_alpha2_codes where code = 'US'),
  'United States',
  'trusted ISO catalogue uses the worker-compatible United States name'
);

select ok(
  (select not rolsuper and not rolcanlogin and not rolinherit and not rolbypassrls
   from pg_roles
   where rolname = 'pokecrack_authorized_opening_reviewer'),
  'reviewer role is NOLOGIN, NOINHERIT and cannot bypass RLS'
);
select ok(
  has_schema_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest',
    'usage'
  ),
  'reviewer role receives only ingest schema usage'
);
select ok(
  (select bool_and(relrowsecurity and relforcerowsecurity)
   from pg_class
   where oid in (
     'ingest.authorized_opening_submissions'::regclass,
     'ingest.authorized_opening_review_events'::regclass,
     'ingest.authorized_opening_observations'::regclass,
     'ingest.authorized_opening_retractions'::regclass
   )),
  'all private authorized-opening ledgers force RLS'
);
select ok(
  not has_table_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.authorized_opening_submissions',
    'select'
  )
  and not has_table_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.authorized_opening_observations',
    'insert'
  )
  and not has_table_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.authorized_opening_retractions',
    'delete'
  )
  and not has_table_privilege(
    'service_role',
    'ingest.authorized_opening_submissions',
    'insert'
  )
  and has_table_privilege(
    'service_role',
    'ingest.authorized_opening_submissions',
    'select'
  ),
  'reviewer has no direct table DML and service_role is SELECT-only'
);
select ok(
  not has_table_privilege(
    'anon',
    'ingest.authorized_opening_submissions',
    'select'
  )
  and not has_table_privilege(
    'authenticated',
    'ingest.authorized_opening_observations',
    'select'
  ),
  'browser roles cannot inspect private authorized-opening ledgers'
);

select has_function(
  'ingest',
  'submit_authorized_opening_v1',
  array['jsonb'],
  'service submit RPC has the exact JSONB signature'
);
select has_function(
  'ingest',
  'list_authorized_opening_reviews_v1',
  array['text', 'integer'],
  'review queue RPC has the exact bounded signature'
);
select has_function(
  'ingest',
  'review_authorized_opening_v1',
  array['uuid', 'bigint', 'text', 'text', 'text'],
  'review RPC has the exact revision-fenced signature'
);
select has_function(
  'ingest',
  'retract_authorized_opening_v1',
  array['uuid', 'text', 'text'],
  'retraction RPC has the exact append-only signature'
);
select has_function(
  'public',
  'get_public_dashboard_snapshot_v4',
  array[]::text[],
  'public dashboard v4 RPC exists'
);

select set_eq(
  $$select parameter_name::text
    from information_schema.parameters
    where specific_schema = 'ingest'
      and routine_name = 'list_authorized_opening_reviews_v1'
      and parameter_mode = 'OUT'$$,
  $$values
    ('submission_id'::text), ('revision'), ('state'), ('discovery_platform'),
    ('country_code'), ('geography_basis'), ('geography_confidence'),
    ('language'), ('tcgdex_set_id'), ('product_scope'), ('observed_at'),
    ('pack_count'), ('qualifying_hit_pack_count'), ('denominator_complete'),
    ('statistics_eligible_requested'), ('created_at'), ('updated_at'),
    ('expires_at')$$,
  'review queue output contains only worker-approved safe fields'
);
select set_eq(
  $$select parameter_name::text
    from information_schema.parameters
    where specific_schema = 'ingest'
      and routine_name = 'review_authorized_opening_v1'
      and parameter_mode = 'OUT'$$,
  $$values
    ('submission_id'::text), ('revision'), ('state'),
    ('accepted_observation_id')$$,
  'review output exposes only the exact worker result tuple'
);

select ok(
  (select p.prosecdef
      and pg_get_userbyid(p.proowner) = 'postgres'
      and coalesce(p.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc as p
   where p.oid = 'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure)
  and has_function_privilege(
    'service_role',
    'ingest.submit_authorized_opening_v1(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.submit_authorized_opening_v1(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'ingest.submit_authorized_opening_v1(jsonb)',
    'execute'
  ),
  'submit is postgres-owned SECURITY DEFINER and service_role-only'
);
select ok(
  (select p.prosecdef
      and pg_get_userbyid(p.proowner) = 'postgres'
      and coalesce(p.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc as p
   where p.oid = 'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure)
  and has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.list_authorized_opening_reviews_v1(text,integer)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.list_authorized_opening_reviews_v1(text,integer)',
    'execute'
  ),
  'list is postgres-owned SECURITY DEFINER and reviewer-only'
);
select ok(
  (select p.prosecdef
      and pg_get_userbyid(p.proowner) = 'postgres'
      and coalesce(p.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc as p
   where p.oid = 'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure)
  and has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)',
    'execute'
  ),
  'review is postgres-owned SECURITY DEFINER and reviewer-only'
);
select ok(
  (select p.prosecdef
      and pg_get_userbyid(p.proowner) = 'postgres'
      and coalesce(p.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc as p
   where p.oid = 'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure)
  and has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.retract_authorized_opening_v1(uuid,text,text)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.retract_authorized_opening_v1(uuid,text,text)',
    'execute'
  ),
  'retract is postgres-owned SECURITY DEFINER and reviewer-only'
);
select ok(
  (select p.prosecdef
      and pg_get_userbyid(p.proowner) = 'postgres'
      and coalesce(p.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc as p
   where p.oid = 'public.get_public_dashboard_snapshot_v4()'::regprocedure)
  and has_function_privilege(
    'anon',
    'public.get_public_dashboard_snapshot_v4()',
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.get_public_dashboard_snapshot_v4()',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.get_public_dashboard_snapshot_v4()',
    'execute'
  ),
  'public v4 is postgres-owned SECURITY DEFINER and anon/auth-only'
);

create temp table authorized_opening_fixture_set(set_id uuid primary key)
on commit drop;
with inserted as (
  insert into catalog.sets (
    external_source,
    external_id,
    name,
    slug,
    language,
    release_date,
    series_name,
    is_active,
    is_demo
  ) values (
    'tcgdex',
    'authorized-opening-pgtap-set',
    'Authorized Opening pgTAP Set',
    'authorized-opening-pgtap-set',
    'en',
    (statement_timestamp() at time zone 'UTC')::date,
    'Authorized Opening Tests',
    true,
    false
  )
  returning id
)
insert into authorized_opening_fixture_set(set_id)
select id from inserted;

create function pg_temp.authorized_opening_payload(
  opening_key text,
  token text,
  statistics_requested boolean default true
)
returns jsonb
language sql
stable
as $$
select jsonb_build_object(
  'schemaVersion', '1.0.0',
  'submissionKey', opening_key,
  'discoveryPlatform', 'direct',
  'discoveryCandidateSha256', null::text,
  'sourceIdentitySha256', repeat(substr(md5(token || ':source'), 1, 32), 2),
  'authorizationReferenceSha256', repeat(substr(md5(token || ':authorization'), 1, 32), 2),
  'evidenceSha256', repeat(substr(md5(token || ':evidence'), 1, 32), 2),
  'provenanceDedupeSha256', repeat(substr(md5(token || ':provenance'), 1, 32), 2),
  'countryCode', 'JP',
  'countryName', 'Japan',
  'geographyBasis', 'opening_location',
  'geographyConfidence', 'tier_a',
  'language', 'en',
  'tcgdexSetId', 'authorized-opening-pgtap-set',
  'productScope', 'all',
  'observedAt', to_char(
    statement_timestamp() at time zone 'UTC',
    'YYYY-MM-DD"T"HH24:MI:SS"Z"'
  ),
  'packCount', 10,
  'qualifyingHitPackCount', 2,
  'denominatorComplete', true,
  'statisticsEligible', statistics_requested
)
from authorized_opening_fixture_set
limit 1;
$$;

create temp table authorized_opening_submit_result on commit drop as
select *
from ingest.submit_authorized_opening_v1(
  pg_temp.authorized_opening_payload('opening-pgtap-stats', 'stats')
);
create temp table authorized_opening_idempotent_result on commit drop as
select *
from ingest.submit_authorized_opening_v1(
  pg_temp.authorized_opening_payload('opening-pgtap-stats', 'stats')
);
insert into authorized_opening_submit_result
select *
from ingest.submit_authorized_opening_v1(
  pg_temp.authorized_opening_payload('opening-pgtap-stats', 'stats')
);
select is(
  (select count(*)::integer from authorized_opening_submit_result),
  2,
  'exact replay returns one additional result without creating a row'
);
select is(
  (select count(distinct submission_id)::integer from authorized_opening_submit_result),
  1,
  'exact replay is idempotent on submission_id'
);
select is(
  (select submission_id::text from authorized_opening_idempotent_result),
  (select submission_id::text from authorized_opening_submit_result limit 1),
  'idempotent submit returns the original row'
);
select is(
  (select revision from authorized_opening_idempotent_result),
  1::bigint,
  'idempotent submit preserves the current revision'
);
select is(
  (select state from authorized_opening_idempotent_result),
  'queued',
  'new authorized opening enters the queued state'
);

select ok(
  (select count(*) = 1
   and bool_and(
     to_jsonb(rows) ? 'submission_id'
     and to_jsonb(rows) ? 'qualifying_hit_pack_count'
     and not (to_jsonb(rows) ?| array[
       'submission_key', 'source_identity_sha256',
       'authorization_reference_sha256', 'evidence_sha256',
       'provenance_dedupe_sha256', 'discovery_candidate_sha256',
       'country_name'
     ])
   )
   from ingest.list_authorized_opening_reviews_v1('queued', 10) as rows),
  'queue projection returns safe operational fields and omits private identifiers'
);

create temp table authorized_opening_in_review on commit drop as
select *
from ingest.review_authorized_opening_v1(
  (select submission_id from authorized_opening_submit_result limit 1),
  1,
  'in_review',
  repeat('c', 64),
  'review_started'
);
select is(
  (select revision from authorized_opening_in_review),
  2::bigint,
  'review start increments the fenced revision'
);
select is(
  (select state from authorized_opening_in_review),
  'in_review',
  'review start records in_review'
);

create temp table authorized_opening_accepted on commit drop as
select *
from ingest.review_authorized_opening_v1(
  (select submission_id from authorized_opening_submit_result limit 1),
  2,
  'accepted_statistics',
  repeat('d', 64),
  'evidence_verified'
);
select is(
  (select revision from authorized_opening_accepted),
  3::bigint,
  'statistics acceptance increments the fenced revision'
);
select is(
  (select state from authorized_opening_accepted),
  'accepted_statistics',
  'statistics acceptance records the accepted state'
);
select ok(
  (select accepted_observation_id is not null from authorized_opening_accepted),
  'statistics acceptance creates one immutable observation'
);
select is(
  (select count(*)::integer
   from ingest.authorized_opening_review_events
   where submission_id = (select submission_id from authorized_opening_submit_result limit 1)),
  3,
  'submit and both review transitions append three audit events'
);
select is(
  (select count(*)::integer from ingest.authorized_opening_observations),
  1,
  'accepted statistics produce exactly one observation ledger row'
);

create temp table authorized_opening_snapshot on commit drop as
select public.get_public_dashboard_snapshot_v4() as value;
select is(
  (select value ->> 'schemaVersion' from authorized_opening_snapshot),
  '2.0.0',
  'v4 keeps the existing public dashboard wire schema stable'
);
select ok(
  (select count(*) = 1
   and bool_and(
     item ->> 'state' = 'insufficient'
     and item ->> 'countryCode' = 'JP'
     and item -> 'hitRate' = 'null'::jsonb
     and item -> 'posteriorMean' = 'null'::jsonb
     and item -> 'credibleInterval' = 'null'::jsonb
     and item ->> 'packsObserved' = '10'
   )
   from authorized_opening_snapshot,
     jsonb_array_elements(value -> 'mapCells') as cells(item)
   where item ->> 'countryCode' = 'JP'),
  'v4 publishes a counts-only withheld country cell below the threshold'
);
select doesnt_match(
  (select value::text from authorized_opening_snapshot),
  '(?i)(submission_key|source_identity_sha256|authorization_reference_sha256|evidence_sha256|provenance_dedupe_sha256|discovery_candidate_sha256|reviewer_reference_sha256|qualifying_hit_pack_count)',
  'v4 contains no private identifiers, hashes, numerator or reviewer field'
);

create temp table authorized_opening_retraction on commit drop as
select *
from ingest.retract_authorized_opening_v1(
  (select accepted_observation_id from authorized_opening_accepted),
  repeat('e', 64),
  'privacy_request'
);
select is(
  (select count(*)::integer from ingest.authorized_opening_retractions),
  1,
  'retraction appends one ledger row'
);
select is(
  (select accepted_observation_id::text from authorized_opening_retraction),
  (select accepted_observation_id::text from authorized_opening_accepted),
  'retraction returns the accepted observation identity to the reviewer RPC only'
);
select is(
  (select pg_temp.retraction_sqlstate(
      (select accepted_observation_id from authorized_opening_accepted),
      'authorization_revoked'
    )),
  '23505',
  'a conflicting second retraction is rejected without rewriting the ledger'
);
select is(
  (select pg_temp.retraction_sqlstate(
      (select accepted_observation_id from authorized_opening_accepted),
      'privacy_request'
    )),
  null,
  'an exact retraction replay is idempotent'
);
create temp table authorized_opening_snapshot_after_retraction on commit drop as
select public.get_public_dashboard_snapshot_v4() as value;
select is(
  (select count(*)::integer
   from authorized_opening_snapshot_after_retraction,
     jsonb_array_elements(value -> 'mapCells') as cells(item)
   where item ->> 'countryCode' = 'JP'),
  0,
  'v4 excludes retracted authorized observations'
);
select is(
  (select count(*)::integer from ingest.authorized_opening_observations),
  1,
  'retraction preserves the immutable accepted observation'
);

create temp table authorized_opening_activity_submit on commit drop as
select *
from ingest.submit_authorized_opening_v1(
  pg_temp.authorized_opening_payload('opening-pgtap-activity', 'activity', false)
);
create temp table authorized_opening_activity_review on commit drop as
select *
from ingest.review_authorized_opening_v1(
  (select submission_id from authorized_opening_activity_submit),
  1,
  'in_review',
  repeat('a', 64),
  'review_started'
);
create temp table authorized_opening_activity_accepted on commit drop as
select *
from ingest.review_authorized_opening_v1(
  (select submission_id from authorized_opening_activity_submit),
  2,
  'accepted_activity_only',
  repeat('b', 64),
  'activity_only'
);
select is(
  (select accepted_observation_id from authorized_opening_activity_accepted),
  null::uuid,
  'activity-only acceptance does not create a statistics observation'
);
select is(
  (select count(*)::integer from ingest.authorized_opening_observations),
  1,
  'activity-only acceptance cannot add to the public denominator'
);

select is(
  (select pg_temp.review_sqlstate(
      (select submission_id from authorized_opening_activity_submit),
      2
    )),
  '40001',
  'stale review revisions fail closed under the row fence'
);

create temp table authorized_opening_expiry_submit on commit drop as
select *
from ingest.submit_authorized_opening_v1(
  pg_temp.authorized_opening_payload('opening-pgtap-expiry', 'expiry')
);
update ingest.authorized_opening_submissions
set created_at = statement_timestamp() - interval '31 days',
    updated_at = statement_timestamp() - interval '31 days',
    expires_at = statement_timestamp() - interval '1 second'
where id = (select submission_id from authorized_opening_expiry_submit);
create temp table authorized_opening_expired on commit drop as
select *
from ingest.review_authorized_opening_v1(
  (select submission_id from authorized_opening_expiry_submit),
  1,
  'accepted_statistics',
  repeat('9', 64),
  'evidence_verified'
);
select is(
  (select state from authorized_opening_expired),
  'expired',
  'database-clock expiry fences a late acceptance into expired'
);
select is(
  (select count(*)::integer
   from ingest.authorized_opening_review_events
   where submission_id = (select submission_id from authorized_opening_expiry_submit)
     and to_state = 'expired'
     and reason_code = 'policy_expired'),
  1,
  'expiry appends an explicit policy_expired review event'
);

select is(
  (select pg_temp.observation_mutation_sqlstate(
      (select accepted_observation_id from authorized_opening_accepted)
    )),
  '55000',
  'accepted observations reject direct update mutation'
);
select ok(
  (select count(*) = 1
   and bool_and(reviewed_at is not null)
   from ingest.authorized_opening_review_events
   where submission_id = (select submission_id from authorized_opening_submit_result limit 1)),
  'review events remain append-only with their review timestamps'
);

select finish();
rollback;
