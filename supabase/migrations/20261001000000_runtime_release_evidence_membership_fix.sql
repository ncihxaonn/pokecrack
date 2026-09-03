begin;

-- The monitor capability is allowed to retain its owner-created self
-- membership.  Only memberships that make it a member of another role are
-- drift; treating the self edge as drift makes the verifier reject the exact
-- least-privilege role contract asserted by the pgTAP suite.
do $runtime_evidence_membership_fix$
declare
  definition text;
  old_membership_check constant text := $old$
     or exists (
       select 1
       from pg_catalog.pg_auth_members as memberships
       where memberships.member = monitor_oid
     )$old$;
  new_membership_check constant text := $new$
     or exists (
       select 1
       from pg_catalog.pg_auth_members as memberships
       where memberships.member = monitor_oid
         and not (
           memberships.roleid = monitor_oid
           and memberships.member = memberships.grantor
           and memberships.admin_option
           and not memberships.inherit_option
           and not memberships.set_option
         )
     )$new$;
begin
  if to_regprocedure(
    'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'
  ) is null then
    raise exception using
      errcode = '55000',
      message = 'runtime release membership fix prerequisites are unavailable';
  end if;

  select pg_get_functiondef(
    'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
  ) into definition;

  if definition is null
     or length(definition) - length(replace(definition, old_membership_check, ''))
       <> length(old_membership_check)
     or position(new_membership_check in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence membership check has drifted';
  end if;

  execute replace(definition, old_membership_check, new_membership_check);
end;
$runtime_evidence_membership_fix$;

alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  owner to postgres;
revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  to pokecrack_runtime_monitor;

commit;
