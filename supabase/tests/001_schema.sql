-- RED-first core database contract. This file preceded the production migrations.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(132);

select has_schema('catalog', 'catalog schema exists');
select has_schema('ingest', 'ingest schema exists');
select has_schema('analytics', 'analytics schema exists');
select has_schema('public', 'public schema exists');

select has_table('catalog', 'sets', 'catalog.sets exists');
select has_table('catalog', 'products', 'catalog.products exists');
select has_table('catalog', 'cards', 'catalog.cards exists');
select has_table('catalog', 'regions', 'catalog.regions exists');
select has_table('catalog', 'retailers', 'catalog.retailers exists');
select has_table('catalog', 'stores', 'catalog.stores exists');
select has_table('catalog', 'sync_state', 'catalog.sync_state exists');
select has_column('catalog', 'sync_state', 'revision', 'catalog sync checkpoints expose a monotonic revision');
select has_table('ingest', 'source_policies', 'ingest.source_policies exists');
select has_table('ingest', 'source_items', 'ingest.source_items exists');
select has_table('ingest', 'extraction_runs', 'ingest.extraction_runs exists');
select has_table('ingest', 'openings', 'ingest.openings exists');
select has_table('ingest', 'opening_hits', 'ingest.opening_hits exists');
select has_table('ingest', 'batch_sightings', 'ingest.batch_sightings exists');
select has_table('ingest', 'jobs', 'ingest.jobs exists');
select has_table('ingest', 'worker_heartbeats', 'ingest.worker_heartbeats exists');
select has_table('ingest', 'browser_sessions', 'ingest.browser_sessions exists');
select has_table('ingest', 'ai_usage_daily', 'ingest.ai_usage_daily exists');
select has_table('ingest', 'admin_audit_log', 'ingest.admin_audit_log exists');
select has_table('ingest', 'schedule_slots', 'ingest.schedule_slots exists');
select has_table('ingest', 'source_request_gates', 'ingest.source_request_gates exists');

select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'sets'$$,
  $$values ('external_source'::text), ('external_id'), ('name'), ('slug'), ('set_code'), ('language'), ('release_date'), ('series_name'), ('rarity_taxonomy'), ('metadata'), ('created_at'), ('updated_at')$$,
  'sets preserves its canonical interface'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'products'$$,
  $$values ('set_id'::text), ('name'), ('slug'), ('product_type'), ('language'), ('sku'), ('upc'), ('ean'), ('declared_pack_count'), ('metadata'), ('created_at'), ('updated_at')$$,
  'products preserves its canonical interface'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'cards'$$,
  $$values ('external_source'::text), ('external_id'), ('set_id'), ('name'), ('collector_number'), ('rarity'), ('language'), ('metadata'), ('created_at'), ('updated_at')$$,
  'cards preserves its canonical interface'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'regions'$$,
  $$values ('country_code'::text), ('state_code'), ('city'), ('name'), ('slug'), ('region_type'), ('parent_id'), ('latitude'), ('longitude'), ('metadata')$$,
  'regions preserves geography-only canonical fields'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'retailers'$$,
  $$values ('id'::text), ('name'), ('slug'), ('country_code'), ('website_domain'), ('metadata')$$,
  'retailers preserves its canonical interface'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'catalog' and table_name = 'stores'$$,
  $$values ('retailer_id'::text), ('region_id'), ('name'), ('slug'), ('public_address'), ('latitude'), ('longitude'), ('metadata')$$,
  'stores exposes public business location fields only'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'source_policies'$$,
  $$values ('domain'::text), ('enabled'), ('collector_type'), ('access_mode'), ('robots_policy'), ('min_delay_seconds'), ('max_pages_per_run'), ('max_concurrency'), ('browser_profile'), ('statistics_eligible_default'), ('retention_days'), ('config'), ('version'), ('created_at'), ('updated_at')$$,
  'source_policies preserves every required contract field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'source_items'$$,
  $$values ('platform'::text), ('external_id'), ('source_url'), ('normalized_url'), ('domain'), ('title'), ('text_excerpt'), ('published_at'), ('discovered_at'), ('author_hash'), ('content_hash'), ('media_hash'), ('video_fingerprint'), ('audio_fingerprint'), ('duplicate_cluster_id'), ('duplicate_suspected'), ('collector_type'), ('collector_version'), ('source_policy_version'), ('access_mode'), ('usage_classification'), ('status'), ('attempt_count'), ('last_error_code'), ('last_error_message'), ('last_error_at'), ('metadata'), ('expires_at'), ('created_at'), ('updated_at')$$,
  'source_items preserves every required normalized metadata field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'extraction_runs'$$,
  $$values ('stage'::text), ('provider'), ('model'), ('prompt_version'), ('input_hash'), ('output_json'), ('decision'), ('confidence'), ('input_tokens'), ('output_tokens'), ('estimated_cost_aud'), ('latency_ms'), ('error_code'), ('error_message'), ('expires_at')$$,
  'extraction_runs preserves the auditable execution contract'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'openings'$$,
  $$values ('set_id'::text), ('product_id'), ('language'), ('pack_count'), ('complete_opening'), ('country_code'), ('state_code'), ('city'), ('region_id'), ('retailer_id'), ('store_id'), ('batch_code'), ('lot_code'), ('purchase_date'), ('opened_at'), ('evidence_tier'), ('overall_confidence'), ('eligible_for_statistics'), ('methodology_version'), ('created_at'), ('updated_at')$$,
  'openings preserves every canonical observation field'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'opening_hits'$$,
  $$values ('opening_id'::text), ('card_id'), ('card_name'), ('collector_number'), ('rarity'), ('quantity'), ('evidence_reference'), ('confidence')$$,
  'opening_hits preserves rarity and evidence references'
);
select set_has(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'batch_sightings'$$,
  $$values ('source_item_id'::text), ('opening_id'), ('set_id'), ('product_id'), ('region_id'), ('retailer_id'), ('store_id'), ('batch_code'), ('normalized_batch_code'), ('lot_code'), ('normalized_lot_code'), ('confidence'), ('observed_at'), ('expires_at')$$,
  'batch_sightings preserves codes and all catalog foreign keys'
);
select set_eq(
  $$select column_name::text from information_schema.columns where table_schema = 'ingest' and table_name = 'jobs'$$,
  $$values ('id'::text), ('job_type'), ('payload'), ('status'), ('priority'), ('attempts'), ('max_attempts'), ('available_at'), ('locked_at'), ('lock_expires_at'), ('locked_by'), ('last_error_code'), ('last_error_message'), ('created_at'), ('updated_at'), ('completed_at'), ('dedupe_key'), ('retention_until'), ('is_demo'), ('lease_generation')$$,
  'jobs exposes the exact canonical queue interface plus approved operational extras'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'jobs'
     and column_name in ('leased_by', 'leased_at', 'lease_expires_at', 'finished_at')),
  0,
  'jobs contains none of the legacy lease or finish column names'
);
select set_eq(
  $$select column_name::text || ':' || data_type from information_schema.columns where table_schema = 'ingest' and table_name = 'worker_heartbeats'$$,
  $$values ('worker_id:text'::text), ('worker_type:text'), ('version:text'), ('last_seen_at:timestamp with time zone'), ('current_job_id:uuid'), ('metadata:jsonb'), ('is_demo:boolean')$$,
  'worker_heartbeats exposes exactly the canonical typed columns'
);
select col_is_pk('ingest', 'worker_heartbeats', 'worker_id', 'worker_id is the heartbeat primary key');
select col_is_null('ingest', 'worker_heartbeats', 'current_job_id', 'heartbeat current_job_id is nullable');
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'worker_heartbeats'
     and column_name in ('id', 'status', 'metrics', 'started_at', 'expires_at')),
  0,
  'worker_heartbeats has no substitute id, status, metrics, start, or expiry columns'
);
select set_eq(
  $$select column_name::text || ':' || data_type from information_schema.columns where table_schema = 'ingest' and table_name = 'browser_sessions'$$,
  $$values ('profile_name:text'::text), ('status:text'), ('extension_connected:boolean'), ('daemon_connected:boolean'), ('authenticated_sources:jsonb'), ('last_check_at:timestamp with time zone'), ('last_successful_command_at:timestamp with time zone'), ('last_error:text'), ('is_demo:boolean')$$,
  'browser_sessions exposes exactly the canonical health-only columns'
);
select col_is_pk('ingest', 'browser_sessions', 'profile_name', 'profile_name is the browser session primary key');
select col_is_null('ingest', 'browser_sessions', 'last_successful_command_at', 'last successful browser command is nullable');
select col_is_null('ingest', 'browser_sessions', 'last_error', 'browser session last_error is nullable');
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'browser_sessions'
     and column_name in ('cookie', 'cookies', 'session', 'session_data', 'session_ref', 'encrypted_session_ref', 'profile_key', 'secret', 'token')),
  0,
  'browser_sessions stores no cookie, session, profile-secret, or encrypted-session reference'
);
select set_eq(
  $$select column_name::text || ':' || data_type from information_schema.columns where table_schema = 'ingest' and table_name = 'ai_usage_daily'$$,
  $$values ('date:date'::text), ('provider:text'), ('model:text'), ('stage:text'), ('request_count:integer'), ('input_tokens:bigint'), ('output_tokens:bigint'), ('estimated_cost_aud:numeric'), ('is_demo:boolean')$$,
  'ai_usage_daily exposes exactly the canonical typed ledger columns'
);
select matches(
  (select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'ingest.ai_usage_daily'::regclass and contype = 'p'),
  '(?is)^primary key \(date, provider, model, stage, is_demo\)$',
  'AI usage primary key keeps live and demo ledgers independent'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'ai_usage_daily'
     and column_name in ('id', 'usage_date', 'operation')),
  0,
  'ai_usage_daily has no renamed identity or stage columns'
);

select col_type_is('ingest', 'source_policies', 'version', 'text', 'policy versions are text');
select col_type_is('ingest', 'source_items', 'source_policy_version', 'text', 'source policy snapshots use text versions');
select col_not_null('ingest', 'source_items', 'content_hash', 'source item content hashes remain required evidence identities');
select matches(
  (select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'ingest.source_items'::regclass and conname = 'source_items_content_hash_check'),
  '\{64\}',
  'source item content hashes are bounded SHA-256 hex digests'
);
select col_type_is('ingest', 'openings', 'purchase_date', 'date', 'purchase date is a date');
select col_type_is('ingest', 'openings', 'overall_confidence', 'numeric(5,4)', 'overall confidence has bounded precision');
select col_type_is('ingest', 'jobs', 'payload', 'jsonb', 'job payload is private jsonb');
select col_is_null('ingest', 'jobs', 'locked_at', 'job lock start is nullable');
select col_is_null('ingest', 'jobs', 'lock_expires_at', 'job lock expiry is nullable');
select col_is_null('ingest', 'jobs', 'locked_by', 'job lock owner is nullable');
select col_is_null('ingest', 'jobs', 'completed_at', 'job completion timestamp is nullable');
select col_not_null('ingest', 'openings', 'set_id', 'opening set_id is required');
select col_not_null('ingest', 'openings', 'pack_count', 'opening pack_count is required');
select col_not_null('catalog', 'cards', 'set_id', 'card set_id is required');
select col_is_null('catalog', 'products', 'set_id', 'product set_id remains nullable for multi-set products');

select col_has_check('ingest', 'source_items', 'text_excerpt', 'source excerpts have a check constraint');
select matches(
  (select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'ingest.source_items'::regclass and conname = 'source_items_text_excerpt_length_check'),
  '20000',
  'source excerpt check enforces the 20,000 character maximum'
);
select col_has_check('catalog', 'products', 'declared_pack_count', 'declared pack counts have a check constraint');
select ok(
  (select pg_get_constraintdef(oid) ilike '%''booster_box''%'
          and pg_get_constraintdef(oid) ilike '%''etb''%'
          and pg_get_constraintdef(oid) ilike '%''booster_bundle''%'
          and pg_get_constraintdef(oid) not ilike '%elite_trainer_box%'
   from pg_constraint where conrelid = 'catalog.products'::regclass and conname = 'products_type_check'),
  'product types use canonical booster_box, etb, and booster_bundle without the legacy substitute'
);
select col_has_check('ingest', 'openings', 'pack_count', 'opening pack counts have a check constraint');
select col_has_check('ingest', 'openings', 'overall_confidence', 'opening confidence has a check constraint');
select col_has_check('ingest', 'opening_hits', 'quantity', 'hit quantities have a check constraint');
select col_has_check('ingest', 'batch_sightings', 'pack_quantity', 'batch quantities have a check constraint');

select ok(
  (select condeferrable = false
      and pg_get_constraintdef(oid) ilike '%unique (slug, is_demo)%'
   from pg_constraint
   where conrelid = 'catalog.sets'::regclass
     and conname = 'sets_slug_mode_unique'),
  'set slugs are unique inside each data mode'
);
select col_is_unique('catalog', 'products', 'slug', 'product slugs are unique');
select col_is_unique('catalog', 'regions', 'slug', 'region slugs are unique');
select col_is_unique('catalog', 'retailers', 'slug', 'retailer slugs are unique');
select col_is_unique('catalog', 'stores', 'slug', 'store slugs are unique');
select col_is_unique('ingest', 'source_policies', 'domain', 'source policy domains are unique');
select index_is_unique('ingest', 'source_items', 'source_items_normalized_url_uidx', 'normalized source URLs are unique within a data mode');
select index_is_unique('ingest', 'source_items', 'source_items_platform_external_uidx', 'platform external identities are unique within a data mode');

select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.source_items'::regclass and c.conname = 'source_items_status_check'),
  array['accepted', 'activity_only', 'collected', 'discovered', 'excluded', 'extracted', 'failed', 'queued', 'rejected', 'validated']::text[],
  'source items use exactly the canonical status vocabulary'
);
select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.jobs'::regclass and c.conname = 'jobs_status_check'),
  array['cancelled', 'completed', 'dead', 'failed', 'pending', 'running']::text[],
  'jobs use exactly the six canonical statuses'
);
select matches(
  (select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'ingest.jobs'::regclass and conname = 'jobs_lock_check'),
  '(?is)status = ''running''.*locked_at is not null.*lock_expires_at is not null.*locked_by is not null.*lock_expires_at > locked_at.*status <> ''running''.*locked_at is null.*lock_expires_at is null.*locked_by is null',
  'running status is equivalent to a complete valid lock'
);
select matches(
  (select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'ingest.jobs'::regclass and conname = 'jobs_completed_check'),
  '(?is)status = any.*completed.*failed.*dead.*cancelled.*completed_at is not null',
  'only terminal jobs carry completed_at and every terminal job is completed'
);
select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.source_policies'::regclass and c.conname = 'source_policies_collector_type_check'),
  array['bluesky_jetstream', 'disabled', 'manual_import', 'mastodon_rest', 'nostr_relay', 'official_api', 'opencli_authenticated', 'scrapling_dynamic', 'scrapling_http']::text[],
  'source policies use exactly the nine collector registry values'
);
select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.source_items'::regclass and c.conname = 'source_items_collector_type_check'),
  array['disabled', 'manual_import', 'official_api', 'opencli_authenticated', 'scrapling_dynamic', 'scrapling_http']::text[],
  'source items snapshot exactly the six collector registry values'
);
select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.source_policies'::regclass and c.conname = 'source_policies_access_mode_check'),
  array['authenticated', 'disabled', 'manual', 'official_api', 'public']::text[],
  'source policies accept exactly the access modes emitted by config'
);
select is(
  (select array_agg(matched.value[1] order by matched.value[1])
   from pg_constraint c
   cross join lateral regexp_matches(pg_get_constraintdef(c.oid), '''([^'']+)''', 'g') as matched(value)
   where c.conrelid = 'ingest.source_items'::regclass and c.conname = 'source_items_access_mode_check'),
  array['authenticated', 'disabled', 'manual', 'official_api', 'public']::text[],
  'source items snapshot exactly the configured access modes'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'source_items'
     and column_name in ('raw_payload', 'full_html', 'html', 'content')),
  0,
  'source_items never permanently stores raw payloads, HTML, or full content'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema = 'ingest' and table_name = 'source_items'
     and column_name in ('error_code', 'error_message')),
  0,
  'source_items uses only canonical last_error_code and last_error_message fields'
);

select ok(
  (select bool_and(c.relrowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname in ('catalog', 'ingest') and c.relkind in ('r', 'p')),
  'all core private tables have RLS enabled'
);
select ok(
  (select bool_and(c.relforcerowsecurity)
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname in ('catalog', 'ingest') and c.relkind in ('r', 'p')),
  'all core private tables force RLS'
);
select ok(not has_schema_privilege('anon', 'catalog', 'usage'), 'anon cannot use catalog');
select ok(not has_schema_privilege('anon', 'ingest', 'usage'), 'anon cannot use ingest');
select ok(not has_schema_privilege('authenticated', 'catalog', 'usage'), 'authenticated cannot use catalog');
select ok(not has_schema_privilege('authenticated', 'ingest', 'usage'), 'authenticated cannot use ingest');
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname in ('catalog', 'ingest') and c.relkind in ('r', 'p')
      and (has_table_privilege('anon', c.oid, 'select') or has_table_privilege('anon', c.oid, 'insert') or has_table_privilege('anon', c.oid, 'update') or has_table_privilege('anon', c.oid, 'delete'))
  ),
  'anon has no core private relation privileges'
);
select ok(
  not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname in ('catalog', 'ingest') and c.relkind in ('r', 'p')
      and (has_table_privilege('authenticated', c.oid, 'select') or has_table_privilege('authenticated', c.oid, 'insert') or has_table_privilege('authenticated', c.oid, 'update') or has_table_privilege('authenticated', c.oid, 'delete'))
  ),
  'authenticated has no core private relation privileges'
);
select ok(
  (select bool_and(
    has_table_privilege('service_role', c.oid, 'select')
    and not has_table_privilege('service_role', c.oid, 'insert')
    and not has_table_privilege('service_role', c.oid, 'update')
    and not has_table_privilege('service_role', c.oid, 'delete')
    and not has_table_privilege('service_role', c.oid, 'truncate')
    and not has_table_privilege('service_role', c.oid, 'references')
    and not has_table_privilege('service_role', c.oid, 'trigger'))
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname in ('catalog', 'ingest')
     and c.relkind in ('r', 'p')
     and not (n.nspname = 'ingest' and c.relname = 'source_request_gates')
     and not (
       n.nspname = 'ingest'
       and c.relname in (
         'nostr_relay_candidates',
         'nostr_relay_observations',
         'nostr_relay_checkpoints'
       )
     )),
  'service_role can read core state except the opaque gate and isolated Nostr ledgers, with no direct table mutation privileges'
);

select has_function('ingest', 'claim_jobs_v2', array['text', 'text[]', 'integer', 'integer'], 'claim_jobs_v2 has the required signature');
select ok((select prosecdef from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure), 'claim_jobs_v2 is SECURITY DEFINER');
select ok(
  (select proretset and prorettype = 'ingest.jobs'::regtype from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'claim_jobs_v2 returns SETOF ingest.jobs'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, ingest'] from pg_proc where oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
  'claim_jobs_v2 fixes its search_path'
);
select matches(
  (select pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure)),
  '(?is)for\s+update\s+of\s+j\s+skip\s+locked',
  'claim_jobs_v2 uses FOR UPDATE SKIP LOCKED'
);
select is(
  (select count(*)::integer from regexp_matches(
    pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure),
    'update\s+ingest\.jobs',
    'gi'
  )),
  2,
  'claim_jobs_v2 dead-letters exhausted rows and performs one candidate UPDATE'
);
select ok(
  (select pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure)
      ilike '%not exhausted.is_demo%'
    and pg_get_functiondef('ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure)
      ilike '%not j.is_demo%'),
  'production job claiming never mutates or leases demo jobs'
);
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) as acl
    where p.oid = 'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure
      and acl.grantee = 0
      and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot claim jobs'
);
select ok(not has_function_privilege('anon', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'anon cannot claim jobs');
select ok(not has_function_privilege('authenticated', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'authenticated cannot claim jobs');
select ok(has_function_privilege('service_role', 'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'), 'service_role can claim jobs');
select ok(
  exists (
    select 1
    from pg_index i
    where i.indexrelid = 'ingest.jobs_active_dedupe_uidx'::regclass
      and i.indpred is not null
  ),
  'active job dedupe uses a partial index'
);
select index_is_unique('ingest', 'jobs', 'jobs_active_dedupe_uidx', 'active job dedupe index is unique');
select ok(
  (select pg_get_indexdef(indexrelid) ilike '%job_type, dedupe_key, is_demo%'
   from pg_index where indexrelid = 'ingest.jobs_active_dedupe_uidx'::regclass),
  'active job dedupe keeps live and demo modes independent'
);
select ok(
  (select pg_get_expr(i.indpred, i.indrelid) ilike '%pending%'
          and pg_get_expr(i.indpred, i.indrelid) ilike '%running%'
          and pg_get_expr(i.indpred, i.indrelid) not ilike '%leased%'
   from pg_index i where i.indexrelid = 'ingest.jobs_active_dedupe_uidx'::regclass),
  'active job dedupe index uses pending and running canonical statuses'
);
select ok(
  (select pg_get_indexdef(indexrelid) ilike '%lock_expires_at%'
          and pg_get_indexdef(indexrelid) not ilike '%lease_expires_at%'
   from pg_index where indexrelid = 'ingest.jobs_claim_idx'::regclass),
  'job claim index uses canonical lock expiry'
);

truncate table ingest.jobs cascade;
select is((select count(*)::integer from ingest.claim_jobs_v2('empty-worker', null, 10, 60)), 0, 'claiming an empty queue returns no rows');
insert into ingest.jobs (
  id, job_type, status, priority, available_at, attempts, max_attempts,
  locked_by, locked_at, lock_expires_at, completed_at, payload
) values
  ('fa000000-0000-4000-8000-000000000001', 'extract', 'pending', 20, now() - interval '1 minute', 0, 3, null, null, null, null, '{"case":"due"}'),
  ('fa000000-0000-4000-8000-000000000002', 'extract', 'pending', 100, now() + interval '1 hour', 0, 3, null, null, null, null, '{"case":"future"}'),
  ('fa000000-0000-4000-8000-000000000003', 'extract', 'running', 50, now() - interval '1 hour', 1, 3, 'active-worker', now() - interval '10 seconds', now() + interval '10 minutes', null, '{"case":"active"}'),
  ('fa000000-0000-4000-8000-000000000004', 'extract', 'running', 10, now() - interval '1 hour', 1, 3, 'dead-worker', now() - interval '10 minutes', now() - interval '5 minutes', null, '{"case":"expired"}'),
  ('fa000000-0000-4000-8000-000000000005', 'extract', 'pending', 200, now() - interval '1 hour', 3, 3, null, null, null, null, '{"case":"max-attempts"}'),
  ('fa000000-0000-4000-8000-000000000006', 'extract', 'dead', 300, now() - interval '1 hour', 3, 3, null, null, null, now() - interval '1 minute', '{"case":"dead"}'),
  ('fa000000-0000-4000-8000-000000000007', 'extract', 'running', 250, now() - interval '1 hour', 3, 3, 'crashed-worker', now() - interval '10 minutes', now() - interval '5 minutes', null, '{"case":"expired-final-attempt"}');
insert into ingest.jobs (
  id, job_type, status, priority, available_at, attempts, max_attempts, payload, is_demo
) values (
  'fa000000-0000-4000-8000-000000000008', 'extract', 'pending', 500,
  now() - interval '1 hour', 3, 3, '{"case":"demo-max-attempts"}', true
);

create temporary table claimed_first on commit drop as
select * from ingest.claim_jobs_v2('worker-alpha', array['extract'], 10, 60);
select is((select count(*)::integer from claimed_first), 2, 'due pending and expired running jobs are claimed');
select set_eq(
  $$select id from claimed_first$$,
  $$values ('fa000000-0000-4000-8000-000000000001'::uuid), ('fa000000-0000-4000-8000-000000000004'::uuid)$$,
  'only eligible jobs are returned'
);
select ok((select bool_and(status = 'running' and locked_by = 'worker-alpha') from claimed_first), 'claimed rows contain canonical running locks');
select ok(
  (select attempts = 1 from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000001')
  and (select attempts = 2 from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000004'),
  'claims and reclaims increment attempts'
);
select is((select locked_by from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000003'), 'active-worker', 'unexpired running locks are not stolen');
select is((select status from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000002'), 'pending', 'future jobs remain pending');
select set_eq(
  $$select id from ingest.jobs where id in ('fa000000-0000-4000-8000-000000000005'::uuid, 'fa000000-0000-4000-8000-000000000007'::uuid) and status = 'dead'$$,
  $$values ('fa000000-0000-4000-8000-000000000005'::uuid), ('fa000000-0000-4000-8000-000000000007'::uuid)$$,
  'due pending and expired running jobs at max attempts are dead-lettered'
);
select is((select status from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000006'), 'dead', 'dead jobs are supported and never reclaimed');
select is(
  (select status from ingest.jobs where id = 'fa000000-0000-4000-8000-000000000008'),
  'pending',
  'live claim and dead-letter paths leave demo jobs untouched'
);
select is((select count(*)::integer from ingest.claim_jobs_v2('worker-beta', array['extract'], 10, 60)), 0, 'a second claimant cannot receive active running locks');
select throws_ok($$select * from ingest.claim_jobs_v2(' ', array['extract'], 1, 60)$$, '22023', 'worker_id must contain 1 to 160 characters', 'blank worker ids are rejected');
select throws_ok($$select * from ingest.claim_jobs_v2('worker', array[]::text[], 1, 60)$$, '22023', 'job_types must be null or a non-empty array without nulls', 'empty job type arrays are rejected');
select throws_ok($$select * from ingest.claim_jobs_v2('worker', array['extract'], 0, 60)$$, '22023', 'batch_size must be between 1 and 100', 'invalid batch sizes are rejected');
select throws_ok($$select * from ingest.claim_jobs_v2('worker', array['extract'], 1, 0)$$, '22023', 'lease_seconds must be between 1 and 86400', 'invalid lease durations are rejected');

select * from finish();
rollback;
