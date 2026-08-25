-- RED-first browser boundary, grants/RLS, RPC, and retention contract.
-- Assumes a clean reset: migrations applied, seed not required.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(64);

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
select ok(not has_function_privilege('anon', to_regprocedure('ingest.claim_jobs(text,text[],integer,integer)'), 'execute'), 'anon cannot execute claim_jobs');
select ok(not has_function_privilege('authenticated', to_regprocedure('ingest.claim_jobs(text,text[],integer,integer)'), 'execute'), 'authenticated cannot execute claim_jobs');

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

select has_function('ingest', 'prune_expired_ephemera', array['timestamp with time zone', 'integer'], 'bounded ephemeral cleanup function exists');
select ok(coalesce((select prosecdef from pg_proc where oid = to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)')), false), 'cleanup is SECURITY DEFINER');
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)')),
  'cleanup fixes its search_path to pg_catalog only'
);
select ok(has_function_privilege('service_role', to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)'), 'execute'), 'service_role can run cleanup');
select ok(not has_function_privilege('anon', to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)'), 'execute'), 'anon cannot run cleanup');
select ok(not has_function_privilege('authenticated', to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)'), 'execute'), 'authenticated cannot run cleanup');
select doesnt_match(
  coalesce((select pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)'))), ''),
  '(?is)delete\s+from\s+ingest\.openings',
  'cleanup never deletes core openings'
);
select ok(
  (select coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)')), '') ~* 'source_items'
      and coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)')), '') ~* 'extraction_runs'
      and coalesce(pg_get_functiondef(to_regprocedure('ingest.prune_expired_ephemera(timestamp with time zone,integer)')), '') ~* 'analytics\.signals'),
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
