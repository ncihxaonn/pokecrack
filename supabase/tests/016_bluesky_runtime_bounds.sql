-- Forward-only Bluesky runtime bounds and least-privilege regression coverage.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (select config ->> 'stream_window_seconds'
   from ingest.source_policies
   where source_key = 'bluesky_jetstream' and not is_demo),
  '10',
  'the reviewed Bluesky policy uses a ten-second stream window'
);
select is(
  (select config ->> 'max_stream_bytes'
   from ingest.source_policies
   where source_key = 'bluesky_jetstream' and not is_demo),
  '2097152',
  'the two-MiB aggregate stream ceiling remains unchanged'
);
select is(
  (select config ->> 'max_message_bytes'
   from ingest.source_policies
   where source_key = 'bluesky_jetstream' and not is_demo),
  '262144',
  'the per-message byte ceiling remains unchanged'
);

select ok(
  (select position('"stream_window_seconds":10' in pg_get_functiondef(oid)) > 0
      and position('"stream_window_seconds":40' in pg_get_functiondef(oid)) = 0
   from pg_proc
   where oid = 'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'::regprocedure),
  'the fenced begin function enforces only the ten-second policy contract'
);
select ok(
  (select position('"stream_window_seconds":10' in pg_get_functiondef(oid)) > 0
      and position('"stream_window_seconds":40' in pg_get_functiondef(oid)) = 0
   from pg_proc
   where oid =
     'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'::regprocedure),
  'the atomic finalizer enforces only the ten-second policy contract'
);
select ok(
  (select position('"stream_window_seconds":10' in pg_get_functiondef(oid)) > 0
      and position('"stream_window_seconds":40' in pg_get_functiondef(oid)) = 0
   from pg_proc
   where oid = 'public.get_public_social_discovery_v1()'::regprocedure),
  'the browser-safe status projection recognizes only the ten-second contract'
);

select set_eq(
  $$
    select grantee::regrole::text
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as acl
    join pg_roles as grantees on grantees.oid = acl.grantee
    where procedures.oid =
      'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('service_role')$$,
  'only postgres and service_role can execute the fenced begin function'
);
select set_eq(
  $$
    select grantee::regrole::text
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as acl
    join pg_roles as grantees on grantees.oid = acl.grantee
    where procedures.oid =
      'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('service_role')$$,
  'only postgres and service_role can execute the atomic finalizer'
);
select set_eq(
  $$
    select grantee::regrole::text
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as acl
    join pg_roles as grantees on grantees.oid = acl.grantee
    where procedures.oid = 'public.get_public_social_discovery_v1()'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('anon'), ('authenticated')$$,
  'only postgres and browser roles can execute the public social status RPC'
);

set local role anon;
select set_config(
  'pokecrack.bluesky_runtime_payload',
  public.get_public_social_discovery_v1()::text,
  true
);
reset role;
select is(
  current_setting('pokecrack.bluesky_runtime_payload')::jsonb ->> 'schemaVersion',
  '1.0.0',
  'anon can execute the browser-safe status RPC after the bounds update'
);
select set_eq(
  $$
    select jsonb_object_keys(
      current_setting('pokecrack.bluesky_runtime_payload')::jsonb
    )
  $$,
  $$values ('schemaVersion'::text), ('sources')$$,
  'the public root projection remains strictly redacted'
);
select set_eq(
  $$
    select jsonb_object_keys(
      current_setting('pokecrack.bluesky_runtime_payload')::jsonb
        #> '{sources,0}'
    )
  $$,
  $$values
    ('id'::text), ('name'), ('kind'), ('access'), ('status'),
    ('lastCollectedAt'), ('url'), ('note')$$,
  'the public source projection remains strictly redacted'
);

select * from finish();
rollback;
