begin;

-- PostgreSQL searches a caller's temporary schema before an unlisted schema,
-- even when pg_catalog is implicitly searched.  Pin every existing
-- authorized-opening SECURITY DEFINER RPC to an explicit, ordered path.  The
-- application schemas used by these functions are all schema-qualified.
alter function ingest.submit_authorized_opening_v1(jsonb)
  set search_path = pg_catalog, pg_temp;
alter function ingest.list_authorized_opening_reviews_v1(text, integer)
  set search_path = pg_catalog, pg_temp;
alter function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)
  set search_path = pg_catalog, pg_temp;
alter function ingest.retract_authorized_opening_v1(uuid, text, text)
  set search_path = pg_catalog, pg_temp;
alter function ingest.reject_authorized_opening_immutable_mutation_v1()
  set search_path = pg_catalog, pg_temp;

-- Keep the historical service-role submit RPC available for existing callers,
-- but expose a separate capability-bound wrapper to the local submitter.  The
-- wrapper is SECURITY DEFINER so the submitter never needs the broad core
-- function grant; its direct-only check runs before the core RPC can persist
-- anything.  Social candidates therefore cannot be promoted through the
-- submitter capability by SET ROLE or a direct database call, even if the CLI
-- is bypassed; service_role retains its separate historical contract below.
create or replace function ingest.submit_authorized_opening_direct_v1(
  payload jsonb
)
returns table(
  submission_id uuid,
  revision bigint,
  state text
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog, pg_temp
as $direct$
begin
  if payload is null
    or jsonb_typeof(payload) is distinct from 'object'
  then
    raise exception using
      errcode = '22023',
      message = 'authorized opening payload must match the exact bounded v1 contract';
  end if;

  if jsonb_typeof(payload -> 'discoveryPlatform') is distinct from 'string'
    or payload ->> 'discoveryPlatform' <> 'direct'
    or jsonb_typeof(payload -> 'discoveryCandidateSha256') is distinct from 'null'
  then
    raise exception using
      errcode = '22023',
      message = 'authorized opening operator accepts direct submissions only';
  end if;

  return query
  select submitted.submission_id, submitted.revision, submitted.state
  from ingest.submit_authorized_opening_v1(payload) as submitted;
end;
$direct$;

alter function ingest.submit_authorized_opening_direct_v1(jsonb)
  owner to postgres;
revoke all on function ingest.submit_authorized_opening_direct_v1(jsonb)
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer,
    pokecrack_authorized_opening_submitter;
grant execute on function ingest.submit_authorized_opening_direct_v1(jsonb)
  to pokecrack_authorized_opening_submitter;

-- The submitter must not retain the historical core grant: that would permit
-- a caller to bypass the direct-only wrapper.  service_role remains the only
-- role allowed to use that broader, backwards-compatible RPC.
revoke execute on function ingest.submit_authorized_opening_v1(jsonb)
  from pokecrack_authorized_opening_submitter;

do $authorized_opening_operator_attestation$
declare
  submitter_oid oid;
  submit_function oid :=
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure;
  direct_submit_function oid :=
    'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure;
  expected_functions constant oid[] := array[
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
    'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
    'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
  ];
begin
  select roles.oid
  into submitter_oid
  from pg_catalog.pg_roles as roles
  where roles.rolname = 'pokecrack_authorized_opening_submitter';
  if submitter_oid is null then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter capability role is missing';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_proc as functions
    where functions.oid = any(expected_functions)
      and (
        functions.proowner <> 'postgres'::regrole
        or not functions.prosecdef
        or functions.proconfig is distinct from array['search_path=pg_catalog, pg_temp']::text[]
      )
  )
  or exists (
    select 1
    from pg_catalog.pg_proc as functions
    where functions.oid = direct_submit_function
      and (
        functions.proowner <> 'postgres'::regrole
        or not functions.prosecdef
        or functions.proconfig is distinct from array['search_path=pg_catalog, pg_temp']::text[]
      )
  )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening SECURITY DEFINER search-path contract drifted';
  end if;

  if not pg_catalog.has_function_privilege(
       'service_role', submit_function, 'EXECUTE'
     )
     or pg_catalog.has_function_privilege(
       'pokecrack_authorized_opening_submitter', submit_function, 'EXECUTE'
     )
     or not pg_catalog.has_function_privilege(
       'pokecrack_authorized_opening_submitter', direct_submit_function, 'EXECUTE'
     )
     or pg_catalog.has_function_privilege(
       'service_role', direct_submit_function, 'EXECUTE'
     )
     or pg_catalog.has_function_privilege(
       'pokecrack_authorized_opening_reviewer', direct_submit_function, 'EXECUTE'
     )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter function capability drifted';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_proc as functions
    join pg_catalog.pg_namespace as namespaces
      on namespaces.oid = functions.pronamespace
    where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and pg_catalog.has_function_privilege(
        'pokecrack_authorized_opening_submitter', functions.oid, 'EXECUTE'
      )
      and functions.oid <> direct_submit_function
  )
  or exists (
    select 1
    from pg_catalog.pg_proc as functions
    cross join lateral pg_catalog.aclexplode(
      coalesce(
        functions.proacl,
        pg_catalog.acldefault('f'::"char", functions.proowner)
      )
    ) as grants
    where functions.oid = direct_submit_function
      and (
        grants.privilege_type <> 'EXECUTE'
        or grants.is_grantable
        or grants.grantee not in (functions.proowner, submitter_oid)
      )
  )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter function ACL drifted';
  end if;
end;
$authorized_opening_operator_attestation$;

comment on function ingest.submit_authorized_opening_direct_v1(jsonb) is
  'Submitter-capability wrapper that rejects social discovery and delegates only direct owner envelopes to the historical service-role RPC.';

commit;
