-- RED-first browser boundary, grants/RLS, RPC, and retention contract.
-- Assumes a clean reset: migrations applied, seed not required.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(79);

select has_table('public', 'dashboard_overview', 'public.dashboard_overview exists');
select has_table('public', 'set_summaries', 'public.set_summaries exists');
select has_table('public', 'region_summaries', 'public.region_summaries exists');
select has_table('public', 'retailer_summaries', 'public.retailer_summaries exists');
select has_table('public', 'batch_summaries', 'public.batch_summaries exists');
select has_table('public', 'recent_activity', 'public.recent_activity exists');
select has_table('public', 'public_signals', 'public.public_signals exists');
select has_table('public', 'data_freshness', 'public.data_freshness exists');
select has_table('public', 'system_status', 'public.system_status exists');

select is(
  (select count(*)::integer from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  9,
  'all nine mutable public aggregates are precomputed tables'
);
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')
      and c.relkind not in ('r', 'p')
  ),
  'named public relations are RLS-capable tables, not owner-bypassing views'
);
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind in ('v', 'm')
      and not (coalesce(c.reloptions, '{}'::text[]) @> array['security_invoker=true'])
  ),
  'every public view, if one is ever added, uses security_invoker'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'public'
     and table_name in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')
     and column_name ~* '(raw|payload|excerpt|author|hash|error|session|secret|token|cookie|email|ip_address|job|prompt|model|provider|worker|profile|latitude|longitude|public_address|city)'),
  0,
  'public relations contain no raw, personal, session, secret, worker, error, AI, or exact-location columns'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'public' and table_name = 'recent_activity'
      and column_name in ('platform', 'source_kind', 'source_title', 'source_published_at', 'source_link', 'evidence_tier', 'entities')$$,
  $$values ('platform'::text), ('source_kind'), ('source_title'), ('source_published_at'), ('source_link'), ('evidence_tier'), ('entities')$$,
  'recent activity exposes only short source descriptors, link, tier, and structured entities'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'public' and table_name = 'dashboard_overview'$$,
  $$values ('tracked_sets'::text), ('tracked_regions'), ('tracked_retailers'), ('batch_sightings'), ('australia_coverage')$$,
  'dashboard overview exposes the live six-KPI dimensions and AU coverage text'
);
select ok(
  (select count(*) = 4 and bool_and(is_nullable = 'YES' and data_type = 'numeric')
   from information_schema.columns
   where table_schema = 'public' and table_name in ('set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries')
     and column_name = 'observed_rate'),
  'every public summary keeps a nullable raw observed rate distinct from the posterior'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'public' and table_name = 'batch_summaries'$$,
  $$values ('set_slug'::text), ('product_type')$$,
  'batch summaries carry the Web set slug and canonical product type'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'public' and table_name = 'recent_activity'$$,
  $$values ('set_name'::text), ('retailer_name')$$,
  'recent activity carries only the safe display names required by Web'
);
select ok(
  (select bool_and(pg_get_constraintdef(c.oid) ilike '%' || required.label || '%')
   from pg_constraint c
   cross join (values ('Insufficient sample'), ('No significant signal'), ('Watch'), ('Possible anomaly')) as required(label)
   where c.conrelid = to_regclass('public.public_signals') and c.conname = 'public_signals_status_check'),
  'public signals enforce exactly the four approved labels'
);

select ok(
  (select count(*) = 9 and bool_and(c.relrowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'every exposed public table has RLS enabled'
);
select ok(
  (select count(*) = 9 and bool_and(c.relforcerowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'every exposed public table forces RLS'
);
select ok(has_schema_privilege('anon', 'public', 'usage'), 'anon can use the public API schema');
select ok(has_schema_privilege('authenticated', 'public', 'usage'), 'authenticated can use the public API schema');
select ok(
  (select count(*) = 9 and bool_and(has_table_privilege('anon', c.oid, 'select'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'anon can select every named public relation'
);
select ok(
  (select count(*) = 9 and bool_and(has_table_privilege('authenticated', c.oid, 'select'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'authenticated can select every named public relation'
);
select ok(
  (select count(*) = 9 and bool_and(not has_table_privilege('anon', c.oid, 'insert')
      and not has_table_privilege('anon', c.oid, 'update') and not has_table_privilege('anon', c.oid, 'delete'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'anon cannot insert, update, or delete any public relation'
);
select ok(
  (select count(*) = 9 and bool_and(not has_table_privilege('authenticated', c.oid, 'insert')
      and not has_table_privilege('authenticated', c.oid, 'update') and not has_table_privilege('authenticated', c.oid, 'delete'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'authenticated cannot insert, update, or delete any public relation'
);
select ok(
  not exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    cross join lateral aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
    where n.nspname = 'public' and c.relkind in ('r', 'p') and acl.grantee = 0
      and acl.privilege_type in ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
      and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')
  ),
  'the PostgreSQL PUBLIC pseudo-role has no relation grants'
);
select ok(
  (select count(*) = 9 and bool_and(has_table_privilege('service_role', c.oid, 'select,insert,update,delete'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'public' and c.relkind in ('r', 'p')
     and c.relname in ('dashboard_overview', 'set_summaries', 'region_summaries', 'retailer_summaries', 'batch_summaries', 'recent_activity', 'public_signals', 'data_freshness', 'system_status')),
  'service_role can maintain every named public relation'
);

select ok(not exists (select 1 from (values ('catalog'), ('ingest'), ('analytics')) s(name) where has_schema_privilege('anon', s.name, 'usage')), 'anon cannot use any private schema');
select ok(not exists (select 1 from (values ('catalog'), ('ingest'), ('analytics')) s(name) where has_schema_privilege('authenticated', s.name, 'usage')), 'authenticated cannot use any private schema');
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname in ('catalog', 'ingest', 'analytics') and c.relkind in ('r', 'p', 'v', 'm')
      and has_table_privilege('anon', c.oid, 'select')
  ),
  'anon cannot select any private relation'
);
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname in ('catalog', 'ingest', 'analytics') and c.relkind in ('r', 'p', 'v', 'm')
      and has_table_privilege('authenticated', c.oid, 'select')
  ),
  'authenticated cannot select any private relation'
);
select ok(not has_function_privilege('anon', to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)'), 'execute'), 'anon cannot execute claim_jobs_v2');
select ok(not has_function_privilege('authenticated', to_regprocedure('ingest.claim_jobs_v2(text,text[],integer,integer)'), 'execute'), 'authenticated cannot execute claim_jobs_v2');

select has_function('public', 'get_public_dashboard_snapshot_v1', array[]::text[], 'versioned public dashboard snapshot RPC exists');
select ok(not coalesce((select prosecdef from pg_proc where oid = to_regprocedure('public.get_public_dashboard_snapshot_v1()')), true), 'public snapshot RPC is SECURITY INVOKER');
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, public']
   from pg_proc where oid = to_regprocedure('public.get_public_dashboard_snapshot_v1()')),
  'public snapshot RPC fixes its search_path'
);
select doesnt_match(
  coalesce((select pg_get_functiondef(to_regprocedure('public.get_public_dashboard_snapshot_v1()'))), ''),
  '(?i)(catalog|ingest|analytics)\.',
  'public snapshot RPC never reads a private schema'
);
select ok(
  (select coalesce(bool_and(definition ilike '%' || relation_name || '%'), false)
   from (values ('dashboard_overview'), ('set_summaries'), ('region_summaries'), ('retailer_summaries'), ('batch_summaries'), ('recent_activity'), ('public_signals'), ('data_freshness'), ('system_status')) names(relation_name)
   cross join lateral (select coalesce(pg_get_functiondef(to_regprocedure('public.get_public_dashboard_snapshot_v1()')), '') as definition) d),
  'public snapshot is assembled only from all nine named public relations'
);
select ok(has_function_privilege('anon', to_regprocedure('public.get_public_dashboard_snapshot_v1()'), 'execute'), 'anon can execute the public snapshot RPC');
select ok(has_function_privilege('authenticated', to_regprocedure('public.get_public_dashboard_snapshot_v1()'), 'execute'), 'authenticated can execute the public snapshot RPC');
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
    where p.oid = to_regprocedure('public.get_public_dashboard_snapshot_v1()')
      and acl.grantee = 0 and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot execute the snapshot RPC'
);
select has_function(
  'public',
  'admin_control_and_audit_v1',
  array['text', 'uuid', 'text', 'text', 'text'],
  'restricted audited admin control RPC exists'
);
select ok(
  coalesce((select prosecdef from pg_proc where oid = to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)')), false),
  'admin control RPC is SECURITY DEFINER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)')),
  'admin control RPC fixes its search_path to pg_catalog only'
);
select ok(
  not has_function_privilege('anon', to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)'), 'execute'),
  'anon cannot execute admin control RPC'
);
select ok(
  not has_function_privilege('authenticated', to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)'), 'execute')
  and has_function_privilege('service_role', to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)'), 'execute'),
  'only service_role can invoke the admin control RPC'
);
select matches(
  coalesce((select pg_get_functiondef(to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)'))), ''),
  '(?is)service_role.*p_actor_id.*p_actor_email.*insert into ingest\.admin_audit_log',
  'admin RPC requires service authorization and explicit audited actor identity'
);
select ok(
  not exists (
    select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname <> 'get_public_dashboard_snapshot_v1'
      and has_function_privilege('anon', p.oid, 'execute')
  ),
  'anon can execute no other public-schema function'
);

select has_function(
  'public',
  'get_admin_dashboard_snapshot_v1',
  array[]::text[],
  'bounded Admin snapshot RPC exists'
);
select ok(
  coalesce((select prosecdef from pg_proc where oid = to_regprocedure('public.get_admin_dashboard_snapshot_v1()')), false),
  'Admin snapshot RPC is SECURITY DEFINER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = to_regprocedure('public.get_admin_dashboard_snapshot_v1()')),
  'Admin snapshot RPC fixes its search_path to pg_catalog only'
);
select ok(
  not has_function_privilege('anon', to_regprocedure('public.get_admin_dashboard_snapshot_v1()'), 'execute')
  and not has_function_privilege('authenticated', to_regprocedure('public.get_admin_dashboard_snapshot_v1()'), 'execute')
  and has_function_privilege('service_role', to_regprocedure('public.get_admin_dashboard_snapshot_v1()'), 'execute'),
  'only service_role can invoke the Admin snapshot RPC'
);
select set_eq(
  $$select p.proname || ':' || coalesce(r.rolname, 'PUBLIC')
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
    left join pg_roles r on r.oid = acl.grantee
    where p.oid in (
      to_regprocedure('public.get_admin_dashboard_snapshot_v1()'),
      to_regprocedure('public.admin_control_and_audit_v1(text,uuid,text,text,text)')
    )
      and acl.privilege_type = 'EXECUTE'
      and acl.grantee <> p.proowner$$,
  $$values
    ('get_admin_dashboard_snapshot_v1:service_role'::text),
    ('admin_control_and_audit_v1:service_role')$$,
  'both Admin RPCs grant non-owner EXECUTE only to service_role, never PUBLIC'
);
select doesnt_match(
  coalesce((select pg_get_functiondef(to_regprocedure('public.get_admin_dashboard_snapshot_v1()'))), ''),
  '(?is)payload|last_error|authenticated_sources|provider|model|prompt|source_excerpt|ip_address|cookie|secret',
  'Admin snapshot definition does not expose private payload, error, browser-auth, AI-provider, source, address or secret fields'
);

insert into ingest.jobs (
  id, job_type, payload, status, attempts, max_attempts, last_error_code,
  last_error_message, completed_at, is_demo
) values (
  'aa000000-0000-4000-8000-000000000001',
  'security.runtime',
  '{"private":"PC_JOB_PAYLOAD_MARKER"}'::jsonb,
  'failed',
  1,
  2,
  'runtime_error',
  'PC_JOB_ERROR_MARKER',
  clock_timestamp(),
  false
);

insert into ingest.worker_heartbeats (
  worker_id, worker_type, version, metadata
) values (
  'pc-live-worker-default', 'runtime', 'test', '{}'::jsonb
);
insert into ingest.worker_heartbeats (
  worker_id, worker_type, version, metadata, is_demo
) values (
  'pc-demo-worker-hidden', 'runtime', 'test', '{"private":"PC_DEMO_WORKER_MARKER"}'::jsonb, true
);

insert into ingest.browser_sessions (
  profile_name, status, extension_connected, daemon_connected, authenticated_sources,
  last_error
) values (
  'pc-runtime-browser', 'authenticated', true, true,
  '{"private":"PC_BROWSER_AUTH_MARKER"}'::jsonb,
  'PC_BROWSER_ERROR_MARKER'
);
insert into ingest.browser_sessions (
  profile_name, status, authenticated_sources, is_demo
) values (
  'pc-demo-browser-hidden', 'authenticated', '{}'::jsonb, true
);

insert into ingest.ai_usage_daily (
  date, provider, model, stage, request_count, input_tokens, output_tokens,
  estimated_cost_aud
) values (
  current_date, 'PC_AI_PROVIDER_MARKER', 'PC_AI_MODEL_MARKER', 'extract',
  7, 11, 13, 0.2500
);
insert into ingest.ai_usage_daily (
  date, provider, model, stage, request_count, input_tokens, output_tokens,
  estimated_cost_aud, is_demo
) values (
  current_date, 'PC_AI_PROVIDER_MARKER', 'PC_AI_MODEL_MARKER', 'extract',
  9000, 9000, 9000, 9000, true
);

set local request.jwt.claims = '{"role":"service_role"}';
set local role service_role;
do $admin_runtime_calls$
begin
  perform pg_catalog.set_config(
    'pokecrack.admin_snapshot_test_result',
    public.get_admin_dashboard_snapshot_v1()::text,
    true
  );
  perform pg_catalog.set_config(
    'pokecrack.admin_denial_test_result',
    public.admin_control_and_audit_v1(
      'source.enqueue',
      'a1111111-1111-4111-8111-111111111111',
      'admin-runtime-test@example.invalid',
      'https://pc-admin-denied-marker.invalid/path',
      null
    )::text,
    true
  );
end;
$admin_runtime_calls$;
reset role;

create temporary table admin_runtime_results (
  snapshot jsonb not null,
  denial jsonb not null
) on commit drop;
insert into admin_runtime_results (snapshot, denial)
values (
  pg_catalog.current_setting('pokecrack.admin_snapshot_test_result')::jsonb,
  pg_catalog.current_setting('pokecrack.admin_denial_test_result')::jsonb
);

select set_eq(
  $$select key::text
    from admin_runtime_results r
    cross join lateral jsonb_object_keys(r.snapshot) keys(key)$$,
  $$values
    ('fixture'::text), ('label'), ('generatedAt'), ('queue'), ('pipeline'),
    ('workers'), ('sources'), ('jobs'), ('browserSessions'), ('adapters'),
    ('ai'), ('capacity'), ('backup'), ('aggregation'), ('services'), ('records')$$,
  'Admin snapshot exposes the exact bounded top-level contract'
);
select set_eq(
  $$select key::text
    from admin_runtime_results r
    cross join lateral jsonb_array_elements(r.snapshot -> 'jobs') rows(item)
    cross join lateral jsonb_object_keys(rows.item) keys(key)
    where rows.item ->> 'id' = 'aa000000-0000-4000-8000-000000000001'$$,
  $$values ('id'::text), ('label'), ('status'), ('attempts'), ('freshness'), ('records')$$,
  'Admin job rows expose only the exact safe display contract'
);
select set_eq(
  $$select key::text
    from admin_runtime_results r
    cross join lateral jsonb_array_elements(r.snapshot -> 'browserSessions') rows(item)
    cross join lateral jsonb_object_keys(rows.item) keys(key)
    where rows.item ->> 'id' = 'pc-runtime-browser'$$,
  $$values ('id'::text), ('label'), ('browser'), ('extension'), ('login'), ('freshness')$$,
  'Admin browser rows expose only the exact health display contract'
);
select set_eq(
  $$select key::text
    from admin_runtime_results r
    cross join lateral jsonb_array_elements(r.snapshot #> '{ai,rows}') rows(item)
    cross join lateral jsonb_object_keys(rows.item) keys(key)
    where rows.item ->> 'day' = current_date::text and rows.item ->> 'stage' = 'extract'$$,
  $$values ('day'::text), ('stage'), ('requests'), ('inputTokens'), ('outputTokens'), ('estimatedCostAud')$$,
  'Admin AI rows expose only the exact aggregate display contract'
);
select doesnt_match(
  (select snapshot::text from admin_runtime_results),
  'PC_(JOB_PAYLOAD|JOB_ERROR|BROWSER_AUTH|BROWSER_ERROR|AI_PROVIDER|AI_MODEL)_MARKER',
  'Admin snapshot omits raw job, browser-auth, error, provider, and model markers at runtime'
);
select ok(
  (select exists (
      select 1 from jsonb_array_elements(snapshot -> 'workers') rows(item)
      where rows.item ->> 'id' = 'pc-live-worker-default'
    ) and not exists (
      select 1 from jsonb_array_elements(snapshot -> 'workers') rows(item)
      where rows.item ->> 'id' = 'pc-demo-worker-hidden'
    ) and not exists (
      select 1 from jsonb_array_elements(snapshot -> 'browserSessions') rows(item)
      where rows.item ->> 'id' = 'pc-demo-browser-hidden'
    ) from admin_runtime_results),
  'Admin snapshot includes default-live operational rows and excludes demo telemetry'
);
select is(
  (select (snapshot #>> '{ai,requests}')::bigint from admin_runtime_results),
  7::bigint,
  'Admin AI totals exclude the colliding demo ledger row'
);
select is(
  (select jsonb_build_object(
    'ok', denial -> 'ok',
    'audit_written', denial -> 'audit_written',
    'reason', denial -> 'reason'
  ) from admin_runtime_results),
  '{"ok":false,"audit_written":true,"reason":"source_policy_denied"}'::jsonb,
  'unknown source domain returns the committed structured denial contract'
);
select is(
  (select count(*)::bigint
   from ingest.admin_audit_log
   where actor_id = 'a1111111-1111-4111-8111-111111111111'
     and action = 'source.enqueue'
     and detail ->> 'source_domain' = 'pc-admin-denied-marker.invalid'
     and detail ->> 'reason' = 'source_policy_denied'
     and detail ->> 'denied' = 'true'),
  1::bigint,
  'unknown source denial audit persists in the caller transaction'
);

select has_function('ingest', 'prune_expired_ephemera_v2', array['timestamp with time zone', 'integer'], 'internal bounded ephemeral cleanup function exists');
select ok(coalesce((select prosecdef from pg_proc where oid = to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)')), false), 'internal cleanup is SECURITY DEFINER');
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)')),
  'internal cleanup fixes its search_path to pg_catalog only'
);
select ok(not has_function_privilege('service_role', to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)'), 'execute'), 'service_role cannot call the internal cleanup implementation');
select ok(not has_function_privilege('anon', to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)'), 'execute'), 'anon cannot run internal cleanup');
select ok(not has_function_privilege('authenticated', to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)'), 'execute'), 'authenticated cannot run internal cleanup');
select doesnt_match(
  coalesce((select pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)'))), ''),
  '(?is)delete\s+from\s+ingest\.openings',
  'cleanup never deletes core openings'
);
select ok(
  (select coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)')), '') ~* 'source_items'
      and coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)')), '') ~* 'extraction_runs'
      and coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)')), '') ~* 'analytics\.signals'),
  'cleanup prunes only bounded excerpts, unreferenced extraction runs, and expired signals'
);

select ok(
  (select count(*) = 8 from pg_indexes
   where schemaname = 'public' and indexname in (
     'dashboard_overview_generated_idx', 'set_summaries_page_idx', 'region_summaries_page_idx',
     'retailer_summaries_page_idx', 'batch_summaries_page_idx', 'recent_activity_page_idx',
     'public_signals_page_idx', 'data_freshness_status_idx'
   )),
  'public aggregate and activity pagination paths are indexed'
);
select ok(
  (select bool_and(pg_get_constraintdef(c.oid) ilike '%' || status_value || '%')
   from pg_constraint c
   cross join (values ('fresh'), ('delayed'), ('stale'), ('unavailable')) statuses(status_value)
   where c.conrelid = to_regclass('public.data_freshness') and c.conname = 'data_freshness_status_check'),
  'freshness uses only the safe public status vocabulary'
);
select has_column('public', 'system_status', 'auth_required', 'system status can safely report authentication required');
select ok(
  (select pg_get_constraintdef(c.oid) ilike '%accepted%' and pg_get_constraintdef(c.oid) ilike '%activity_only%'
      and pg_get_constraintdef(c.oid) not ilike '%rejected%'
   from pg_constraint c where c.conrelid = to_regclass('public.recent_activity') and c.conname = 'recent_activity_status_check'),
  'recent activity publishes accepted/activity-only rows and never rejected rows'
);
select ok(not has_schema_privilege('anon', 'public', 'create') and not has_schema_privilege('authenticated', 'public', 'create'), 'browser roles cannot create public-schema objects');
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'S'
      and (has_sequence_privilege('anon', c.oid, 'usage') or has_sequence_privilege('authenticated', c.oid, 'usage'))
  ),
  'browser roles have no public sequence privileges'
);

select * from finish();
rollback;
