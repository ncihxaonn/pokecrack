-- Direct database workers must not inherit the PostgREST-only Admin surface.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(12);

select matches(
  pg_get_functiondef('public.get_admin_dashboard_snapshot_v1()'::regprocedure),
  '(?is)session_user\s*<>\s*''authenticator''.*auth\.jwt\(\).*service_role',
  'Admin snapshot wrapper requires immutable PostgREST session origin and service JWT'
);

select matches(
  pg_get_functiondef(
    'public.admin_control_and_audit_v1(text,uuid,text,text,text)'::regprocedure
  ),
  '(?is)session_user\s*<>\s*''authenticator''.*auth\.jwt\(\).*service_role',
  'Admin mutation wrapper requires immutable PostgREST session origin and service JWT'
);

select ok(
  not has_function_privilege(
    'service_role',
    'ingest.get_admin_dashboard_snapshot_v1()'::regprocedure,
    'execute'
  ),
  'service_role cannot execute the private Admin snapshot implementation'
);

select ok(
  not has_function_privilege(
    'service_role',
    'ingest.admin_control_and_audit_v1(text,uuid,text,text,text)'::regprocedure,
    'execute'
  ),
  'service_role cannot execute the private Admin mutation implementation'
);

select ok(
  (select bool_and(prosecdef and proowner = 'postgres'::regrole)
   from pg_proc
   where oid = any(array[
     'ingest.get_admin_dashboard_snapshot_v1()'::regprocedure,
     'ingest.admin_control_and_audit_v1(text,uuid,text,text,text)'::regprocedure
   ])),
  'private Admin implementations remain owner-only SECURITY DEFINER functions'
);

select set_eq(
  $$select p.proname || ':' || coalesce(r.rolname, 'PUBLIC')
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
    left join pg_roles r on r.oid = acl.grantee
    where p.oid in (
      'public.get_admin_dashboard_snapshot_v1()'::regprocedure,
      'public.admin_control_and_audit_v1(text,uuid,text,text,text)'::regprocedure
    )
      and acl.privilege_type = 'EXECUTE'
      and acl.grantee <> p.proowner$$,
  $$values
    ('get_admin_dashboard_snapshot_v1:service_role'::text),
    ('admin_control_and_audit_v1:service_role')$$,
  'public Admin wrappers expose non-owner EXECUTE only to service_role'
);

create role pokecrack_direct_worker_fixture noinherit;
grant service_role to pokecrack_direct_worker_fixture;

set session authorization pokecrack_direct_worker_fixture;
set local request.jwt.claims = '{"role":"service_role"}';
set local role service_role;
do $direct_worker_denials$
begin
  begin
    perform public.get_admin_dashboard_snapshot_v1();
  exception when others then
    perform set_config('pokecrack.direct_snapshot_state', sqlstate, true);
    perform set_config('pokecrack.direct_snapshot_message', sqlerrm, true);
  end;

  begin
    perform public.admin_control_and_audit_v1(
      'not.supported',
      'a1111111-1111-4111-8111-111111111111',
      'direct-worker@example.invalid',
      null,
      null
    );
  exception when others then
    perform set_config('pokecrack.direct_control_state', sqlstate, true);
    perform set_config('pokecrack.direct_control_message', sqlerrm, true);
  end;
end;
$direct_worker_denials$;
reset role;
reset session authorization;

select is(
  current_setting('pokecrack.direct_snapshot_state'),
  '42501',
  'direct worker session cannot invoke the Admin snapshot wrapper'
);
select is(
  current_setting('pokecrack.direct_control_state'),
  '42501',
  'direct worker session cannot invoke the Admin mutation wrapper'
);
select matches(
  current_setting('pokecrack.direct_snapshot_message'),
  'PostgREST service authorization required$',
  'snapshot denial identifies the immutable session-origin boundary'
);
select matches(
  current_setting('pokecrack.direct_control_message'),
  'PostgREST service authorization required$',
  'control denial identifies the immutable session-origin boundary'
);

set session authorization authenticator;
set local request.jwt.claims = '{"role":"service_role"}';
set local role service_role;
do $postgrest_service_calls$
begin
  perform set_config(
    'pokecrack.authenticator_snapshot_label',
    public.get_admin_dashboard_snapshot_v1() ->> 'label',
    true
  );
  begin
    perform public.admin_control_and_audit_v1(
      'not.supported',
      'a1111111-1111-4111-8111-111111111111',
      'postgrest-admin@example.invalid',
      null,
      null
    );
  exception when others then
    perform set_config('pokecrack.authenticator_control_state', sqlstate, true);
  end;
end;
$postgrest_service_calls$;
reset role;
reset session authorization;

select is(
  current_setting('pokecrack.authenticator_snapshot_label'),
  'Live operational snapshot · bounded private telemetry',
  'authenticator service-role session can invoke the Admin snapshot wrapper'
);
select is(
  current_setting('pokecrack.authenticator_control_state'),
  '22023',
  'authenticator service-role session crosses the wrapper and reaches input validation'
);

select * from finish();
rollback;
