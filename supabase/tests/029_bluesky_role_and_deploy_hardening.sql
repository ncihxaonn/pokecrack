-- The Bluesky lane is opt-in.  Its named login is provisioned by an owner
-- outside migrations, and this test exercises the read-only drift attestation
-- after adding that exact login edge.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'true'::jsonb,
  'the capability remains ready before its separately provisioned optional login exists'
);

create role pokecrack_bluesky_worker_login
  login
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls
  connection limit 2;
grant pokecrack_bluesky_worker to pokecrack_bluesky_worker_login
  with inherit false, set true;

select has_function(
  'ingest', 'verify_bluesky_release_v1', array[]::text[],
  'the Bluesky release attestation exists'
);
select ok(
  (select prosecdef
      and coalesce(proconfig, '{}'::text[])
        = array['search_path=pg_catalog, pg_temp']::text[]
   from pg_catalog.pg_proc
   where oid = 'ingest.verify_bluesky_release_v1()'::regprocedure),
  'the Bluesky attestation is SECURITY DEFINER with a safe fixed search path'
);
select ok(
  not has_function_privilege(
      'service_role', 'ingest.verify_bluesky_release_v1()', 'execute'
    )
    and has_function_privilege(
      'pokecrack_bluesky_worker',
      'ingest.verify_bluesky_release_v1()',
      'execute'
    )
    and not has_function_privilege(
      'pokecrack_bluesky_worker_login',
      'ingest.verify_bluesky_release_v1()',
      'execute'
    ),
  'only the capability role can execute the boolean-only proof'
);
select ok(
  (select not rolsuper and not rolinherit and not rolcreaterole
      and not rolcreatedb and not rolcanlogin and not rolreplication
      and not rolbypassrls and rolconnlimit = -1
      and coalesce(rolconfig, '{}'::text[]) = '{}'::text[]
   from pg_catalog.pg_roles
   where rolname = 'pokecrack_bluesky_worker'),
  'the Bluesky capability role has the exact NOLOGIN attributes'
);
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'true'::jsonb,
  'the owner-provisioned login and exact capability surface are ready'
);
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_policy_exact',
  'true'::jsonb,
  'the Bluesky policy and idle-or-valid-active gate are ready'
);
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_acl_exact',
  'true'::jsonb,
  'the private Bluesky tables retain their reviewed ACL boundary'
);

alter role pokecrack_bluesky_worker_login set statement_timeout = '1s';
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'role-level settings fail the Bluesky contract closed'
);
alter role pokecrack_bluesky_worker_login reset statement_timeout;

grant service_role to pokecrack_bluesky_worker
  with inherit false, set false;
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'a capability membership in service_role fails closed'
);
revoke service_role from pokecrack_bluesky_worker;

grant pokecrack_bluesky_worker_login to current_user
  with inherit true, set true;
grant create on schema public to pokecrack_bluesky_worker_login;
create table public.bluesky_worker_owned_probe(id integer);
alter table public.bluesky_worker_owned_probe owner to pokecrack_bluesky_worker_login;
revoke create on schema public from pokecrack_bluesky_worker_login;
revoke pokecrack_bluesky_worker_login from current_user;
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'worker-owned catalog objects fail the Bluesky contract closed'
);
grant pokecrack_bluesky_worker_login to current_user
  with inherit true, set true;
alter table public.bluesky_worker_owned_probe owner to postgres;
revoke pokecrack_bluesky_worker_login from current_user;
drop table public.bluesky_worker_owned_probe;

grant execute on function ingest.claim_bluesky_jetstream_jobs_v1(text, integer)
  to service_role;
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'an unexpected Bluesky function ACL grantee fails closed'
);
revoke execute on function ingest.claim_bluesky_jetstream_jobs_v1(text, integer)
  from service_role;

alter function ingest.get_bluesky_worker_policy_snapshot_v1()
  set search_path = public;
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'a Bluesky worker-function search_path drift fails closed'
);
alter function ingest.get_bluesky_worker_policy_snapshot_v1()
  set search_path = pg_catalog, pg_temp;

grant select (source_key) on ingest.source_policies to pokecrack_bluesky_worker;
select is(
  ingest.verify_bluesky_release_v1() -> 'bluesky_worker_role_exact',
  'false'::jsonb,
  'a Bluesky worker column grant fails closed'
);
revoke select (source_key) on ingest.source_policies
  from pokecrack_bluesky_worker;

select ok(
  (select count(*) = 7 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_bluesky_release_v1())),
  'the exact Bluesky contract returns to ready after drift is removed'
);

select * from finish();
rollback;
