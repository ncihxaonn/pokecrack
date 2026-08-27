begin;

-- PostgREST connects as authenticator and then assumes the JWT role. A direct
-- database worker can SET ROLE service_role and can set request.jwt.claims, but
-- it cannot forge session_user. Keep the broad Admin implementations private
-- and expose only session-origin-fenced wrappers.
alter function public.get_admin_dashboard_snapshot_v1()
  set schema ingest;
alter function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  set schema ingest;

revoke all on function ingest.get_admin_dashboard_snapshot_v1()
  from public, anon, authenticated, service_role;
revoke all on function ingest.admin_control_and_audit_v1(text, uuid, text, text, text)
  from public, anon, authenticated, service_role;

comment on function ingest.get_admin_dashboard_snapshot_v1() is
  'Private Admin snapshot implementation; callable only by its owner through the public session-origin wrapper.';
comment on function ingest.admin_control_and_audit_v1(text, uuid, text, text, text) is
  'Private audited Admin mutation implementation; callable only by its owner through the public session-origin wrapper.';

create function public.get_admin_dashboard_snapshot_v1()
returns jsonb
language plpgsql
security definer
volatile
parallel restricted
set search_path = pg_catalog
as $$
begin
  if session_user <> 'authenticator'
    or coalesce(auth.jwt() ->> 'role', '') <> 'service_role'
  then
    raise exception using
      errcode = '42501',
      message = 'admin snapshot PostgREST service authorization required';
  end if;

  return ingest.get_admin_dashboard_snapshot_v1();
end;
$$;

alter function public.get_admin_dashboard_snapshot_v1()
  owner to postgres;
revoke all on function public.get_admin_dashboard_snapshot_v1()
  from public, anon, authenticated, service_role;
grant execute on function public.get_admin_dashboard_snapshot_v1()
  to service_role;
comment on function public.get_admin_dashboard_snapshot_v1() is
  'PostgREST service-role-only Admin telemetry wrapper; direct database sessions are rejected by immutable session origin.';

create function public.admin_control_and_audit_v1(
  p_action text,
  p_actor_id uuid,
  p_actor_email text,
  p_source_url text default null,
  p_target_id text default null
)
returns jsonb
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
begin
  if session_user <> 'authenticator'
    or coalesce(auth.jwt() ->> 'role', '') <> 'service_role'
  then
    raise exception using
      errcode = '42501',
      message = 'admin control PostgREST service authorization required';
  end if;

  return ingest.admin_control_and_audit_v1(
    p_action,
    p_actor_id,
    p_actor_email,
    p_source_url,
    p_target_id
  );
end;
$$;

alter function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  owner to postgres;
revoke all on function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  to service_role;
comment on function public.admin_control_and_audit_v1(text, uuid, text, text, text) is
  'PostgREST service-role-only audited Admin controls; direct database sessions are rejected by immutable session origin.';

commit;
