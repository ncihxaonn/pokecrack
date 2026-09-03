begin;

-- PostgreSQL's empty ACL literal is zero-dimensional, while aclexplode()
-- accepts only one-dimensional arrays. Reissue the private verifier after
-- every prior runtime-evidence patch, preserving its direct-grant semantics
-- while normalising NULL catalog ACLs through their owner-aware defaults.
do $runtime_release_acl_normalization$
declare
  definition text;
  updated_definition text;
  old_namespace_acl constant text := $old$coalesce(namespaces.nspacl, '{}'::aclitem[])$old$;
  new_namespace_acl constant text := $new$coalesce(namespaces.nspacl, acldefault('n', namespaces.nspowner))$new$;
  old_relation_acl constant text := $old$coalesce(relations.relacl, '{}'::aclitem[])$old$;
  new_relation_acl constant text := $new$coalesce(relations.relacl, acldefault('r', relations.relowner))$new$;
  old_procedure_acl constant text := $old$coalesce(procedures.proacl, '{}'::aclitem[])$old$;
  new_procedure_acl constant text := $new$coalesce(procedures.proacl, acldefault('f', procedures.proowner))$new$;
begin
  if to_regprocedure(
    'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'
  ) is null then
    raise exception using
      errcode = '55000',
      message = 'runtime release ACL normalization prerequisites are unavailable';
  end if;

  if not exists (
    select 1
    from pg_catalog.pg_proc as functions
    where functions.oid =
        'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
      and pg_catalog.pg_get_userbyid(functions.proowner) = 'postgres'
      and functions.prosecdef
      and functions.provolatile = 's'
      and functions.proparallel = 'r'
      and coalesce(functions.proconfig, '{}'::text[])
        = array['search_path=pg_catalog, pg_temp']::text[]
  ) then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence no longer has the reviewed security header';
  end if;

  select pg_get_functiondef(
    'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
  ) into definition;

  if definition is null
     or length(definition) - length(replace(definition, old_namespace_acl, ''))
       <> 2 * length(old_namespace_acl)
     or length(definition) - length(replace(definition, old_relation_acl, ''))
       <> 2 * length(old_relation_acl)
     or length(definition) - length(replace(definition, old_procedure_acl, ''))
       <> 2 * length(old_procedure_acl)
     or position(new_namespace_acl in definition) <> 0
     or position(new_relation_acl in definition) <> 0
     or position(new_procedure_acl in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence no longer matches the reviewed ACL normalization points';
  end if;

  updated_definition := replace(
    replace(
      replace(definition, old_namespace_acl, new_namespace_acl),
      old_relation_acl,
      new_relation_acl
    ),
    old_procedure_acl,
    new_procedure_acl
  );

  if updated_definition = definition
     or position(old_namespace_acl in updated_definition) <> 0
     or position(old_relation_acl in updated_definition) <> 0
     or position(old_procedure_acl in updated_definition) <> 0
     or length(updated_definition) - length(replace(
       updated_definition, new_namespace_acl, ''
     )) <> 2 * length(new_namespace_acl)
     or length(updated_definition) - length(replace(
       updated_definition, new_relation_acl, ''
     )) <> 2 * length(new_relation_acl)
     or length(updated_definition) - length(replace(
       updated_definition, new_procedure_acl, ''
     )) <> 2 * length(new_procedure_acl)
  then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence ACL normalization did not match exactly';
  end if;

  execute updated_definition;
end;
$runtime_release_acl_normalization$;

alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  owner to postgres;
revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  to pokecrack_runtime_monitor;

comment on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text) is
  'Private aggregate-only release verifier. Exact service sets require post-release non-demo worker, source, schedule, queue, checkpoint, cleanup, and isolated capability evidence; never returns identifiers, payloads, URLs, cursors, or source text.';

commit;
