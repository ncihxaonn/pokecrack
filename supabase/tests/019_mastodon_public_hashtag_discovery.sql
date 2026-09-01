-- Fixed mastodon.social public hashtag discovery: policy, private state,
-- fencing, exact DTO validation, replay safety, cooldown, cleanup, and
-- public redaction.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create function pg_temp.sqlstate_of(statement text)
returns text
language plpgsql
volatile
as $$
begin
  execute statement;
  return null;
exception
  when others then
    return sqlstate;
end;
$$;

select has_table('ingest', 'mastodon_public_hashtag_candidates',
  'private Mastodon candidate ledger exists');
select has_table('ingest', 'mastodon_public_hashtag_observations',
  'private Mastodon observation ledger exists');
select has_table('ingest', 'mastodon_public_hashtag_checkpoints',
  'private Mastodon checkpoint ledger exists');
select has_table('ingest', 'mastodon_rate_cooldowns',
  'private durable Mastodon cooldown exists');

select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'mastodon_public_hashtag_candidates'$$,
  $$values
    ('source_policy_id'::text), ('status_key_sha256'), ('matched_tags'),
    ('published_at'), ('first_seen_at'), ('last_seen_at'), ('expires_at'),
    ('activity_only'), ('statistics_eligible'), ('is_demo'), ('created_at'),
    ('updated_at')$$,
  'candidate ledger contains only hashed activity metadata'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'mastodon_public_hashtag_observations'$$,
  $$values
    ('source_policy_id'::text), ('tag_key'), ('status_key_sha256'),
    ('matched_tags'), ('published_at'), ('observed_at'), ('expires_at'),
    ('activity_only'), ('statistics_eligible'), ('is_demo')$$,
  'observation ledger contains no raw status or profile fields'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'mastodon_public_hashtag_checkpoints'$$,
  $$values
    ('source_policy_id'::text), ('instance_key'), ('tag_key'), ('last_status_id'),
    ('last_collected_at'), ('incomplete'), ('requests_seen_total'),
    ('statuses_seen_total'), ('bytes_seen_total'), ('candidates_seen_total'),
    ('is_demo'), ('created_at'), ('updated_at')$$,
  'checkpoint retains only the bounded opaque cursor and counters'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'mastodon_rate_cooldowns'$$,
  $$values
    ('source_policy_id'::text), ('instance_key'), ('cooldown_until'), ('is_demo'),
    ('created_at'), ('updated_at')$$,
  'cooldown retains only source-level retry state'
);

select ok(
  (select bool_and(relrowsecurity and relforcerowsecurity)
   from pg_class
   where oid in (
     'ingest.mastodon_public_hashtag_candidates'::regclass,
     'ingest.mastodon_public_hashtag_observations'::regclass,
     'ingest.mastodon_public_hashtag_checkpoints'::regclass,
     'ingest.mastodon_rate_cooldowns'::regclass
   )),
  'all Mastodon state tables enable and force RLS'
);
select ok(
  (select bool_and(
      has_table_privilege('service_role', table_name, 'select')
      and not has_table_privilege('service_role', table_name, 'insert')
      and not has_table_privilege('service_role', table_name, 'update')
      and not has_table_privilege('service_role', table_name, 'delete')
    )
   from unnest(array[
     'ingest.mastodon_public_hashtag_candidates'::text,
     'ingest.mastodon_public_hashtag_observations'::text,
     'ingest.mastodon_public_hashtag_checkpoints'::text,
     'ingest.mastodon_rate_cooldowns'::text
   ]) as tables(table_name)),
  'service_role has SELECT-only access to private Mastodon state'
);
select ok(
  not has_table_privilege('anon', 'ingest.mastodon_public_hashtag_candidates', 'select')
    and not has_table_privilege('anon', 'ingest.mastodon_public_hashtag_observations', 'select')
    and not has_table_privilege('anon', 'ingest.mastodon_public_hashtag_checkpoints', 'select')
    and not has_table_privilege('anon', 'ingest.mastodon_rate_cooldowns', 'select')
    and not has_table_privilege('authenticated', 'ingest.mastodon_public_hashtag_candidates', 'select')
    and not has_table_privilege('authenticated', 'ingest.mastodon_public_hashtag_observations', 'select')
    and not has_table_privilege('authenticated', 'ingest.mastodon_public_hashtag_checkpoints', 'select')
    and not has_table_privilege('authenticated', 'ingest.mastodon_rate_cooldowns', 'select')
    and not has_table_privilege('public', 'ingest.mastodon_public_hashtag_candidates', 'select')
    and not has_table_privilege('public', 'ingest.mastodon_public_hashtag_observations', 'select')
    and not has_table_privilege('public', 'ingest.mastodon_public_hashtag_checkpoints', 'select')
    and not has_table_privilege('public', 'ingest.mastodon_rate_cooldowns', 'select'),
  'browser roles cannot inspect private Mastodon state'
);

select is(
  (select count(*)::integer from ingest.source_policies
   where source_key = 'mastodon_social'),
  1,
  'exactly one Mastodon source policy is provisioned'
);
select ok(
  (select source_kind = 'official_api'
      and domain = 'mastodon.social'
      and base_url = 'https://mastodon.social/'
      and enabled
      and collector_type = 'mastodon_rest'
      and access_mode = 'official_api'
      and robots_policy = 'not_applicable'
      and routes = array['mastodon_rest']::text[]
      and not include_subdomains
      and min_delay_seconds = 2
      and max_pages_per_run = 2
      and max_items_per_run = 80
      and max_concurrency = 1
      and not statistics_eligible_default
      and retention_days = 30
      and version = 'mastodon-public-hashtag-v1'
      and expected_interval_seconds = 300
      and not is_demo
      and config ->> 'instance_key' = 'mastodon_social'
      and config ->> 'instance_url' = 'https://mastodon.social/api/v2/instance'
      and config ->> 'about_url' = 'https://mastodon.social/about'
      and config ->> 'privacy_url' = 'https://mastodon.social/api/v1/instance/privacy_policy'
      and config ->> 'robots_url' = 'https://mastodon.social/robots.txt'
      and config ->> 'rules_url' = 'https://mastodon.social/api/v1/instance/rules'
      and config ->> 'terms_url' = 'https://mastodon.social/api/v1/instance/terms_of_service'
      and config ->> 'hashtag_base_url' = 'https://mastodon.social/api/v1/timelines/tag/'
      and config ->> 'official_docs_url' = 'https://docs.joinmastodon.org/methods/timelines/'
      and config ->> 'policy_state' = 'reviewed_public_api_2026-08-31'
      and config ->> 'terms_effective_date' = '2026-08-31'
      and config ->> 'terms_checked_at' = '2026-08-31'
      and config ->> 'privacy_checked_at' = '2026-08-31'
      and config ->> 'rules_checked_at' = '2026-08-31'
      and config ->> 'robots_checked_at' = '2026-08-31'
      and config ->> 'public_access_checked_at' = '2026-08-31'
      and config ->> 'robots_decision' = 'api_route_not_disallowed'
      and config ->> 'rate_limit_basis' = 'live_x_ratelimit_headers'
      and config ->> 'rate_limit_default_per_5m' = '300'
      and config ->> 'effective_max_requests_per_5m' = '150'
      and config ->> 'operator_acknowledgment' = 'recommended_before_production'
      and config ->> 'checkpoint_retention' = 'opaque_cursor_persists_beyond_activity_ttl'
      and config ->> 'user_agent' = 'PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)'
      and config -> 'required_hashtag_access' = '{"local":"public","remote":"public"}'::jsonb
      and config ->> 'tag_registry' = 'mastodon-tags-v1'
      and config ->> 'limit' = '40'
      and config ->> 'max_pages_per_run' = '2'
      and config ->> 'max_items_per_run' = '80'
      and config ->> 'max_response_bytes' = '2097152'
      and config ->> 'connect_timeout_seconds' = '10'
      and config ->> 'read_timeout_seconds' = '15'
      and config ->> 'allow_redirects' = 'false'
      and config ->> 'statistics_eligible' = 'false'
      and config -> 'approved_tags' = jsonb_build_object(
        'pokemontcg', 'pokemontcg',
        'pokemoncards', 'pokemoncards',
        'pokeca_ja', 'ポケカ',
        'pokemon_card_ja', 'ポケモンカード',
        'pokemon_card_ko', '포켓몬카드',
        'pokemon_card_zh_hans', '宝可梦卡牌',
        'pokemon_card_zh_hant', '寶可夢卡牌'
      )
   from ingest.source_policies where source_key = 'mastodon_social'),
  'Mastodon policy has the exact official API and fixed registry contract'
);
select is(
  (select count(*)::integer
   from ingest.source_policies as policies
   cross join lateral jsonb_object_keys(policies.config -> 'approved_tags') as approved(tag_key)
   where policies.source_key = 'mastodon_social'),
  7,
  'the approved registry contains exactly seven raw hashtags'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_checkpoints),
  7,
  'one checkpoint is seeded for every ASCII tag key'
);
select is(
  (select count(*)::integer from ingest.mastodon_rate_cooldowns),
  1,
  'one shared durable cooldown is seeded'
);
select set_eq(
  $$select tag_key::text from ingest.mastodon_public_hashtag_checkpoints$$,
  $$values
    ('pokemontcg'::text), ('pokemoncards'), ('pokeca_ja'), ('pokemon_card_ja'),
    ('pokemon_card_ko'), ('pokemon_card_zh_hans'), ('pokemon_card_zh_hant')$$,
  'checkpoint identities use the exact ASCII scheduler keys'
);
select is(
  (select config #>> '{approved_tags,pokemon_card_zh_hant}'
   from ingest.source_policies where source_key = 'mastodon_social'),
  '寶可夢卡牌',
  'Traditional Chinese registry mapping retains the traditional 夢'
);

select has_function('ingest', 'begin_mastodon_public_hashtag_job',
  array['uuid', 'text', 'bigint', 'text', 'text'],
  'typed Mastodon begin RPC exists');
select has_function('ingest', 'finalize_mastodon_public_hashtag_job',
  array['uuid', 'text', 'bigint', 'jsonb'],
  'typed Mastodon finalizer exists');
select has_function('ingest', 'record_mastodon_rate_limit',
  array['uuid', 'text', 'bigint', 'timestamptz'],
  'typed Mastodon Retry-After recorder exists');
select has_function('ingest', 'prune_mastodon_public_hashtag_v1',
  array['timestamptz', 'integer'],
  'bounded Mastodon cleanup exists');
select has_function('public', 'get_public_social_discovery_v3',
  array[]::text[], 'Bluesky/Nostr/Mastodon public tuple exists');
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)'::regprocedure)
    and has_function_privilege(
      'service_role',
      'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)',
      'execute'
    )
    and not has_function_privilege(
      'anon',
      'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)',
      'execute'
    ),
  'only service_role receives the fenced Mastodon begin RPC'
);
select ok(
  (select bool_and(
      not has_function_privilege(role_name, function_name, 'execute')
    )
   from unnest(array['public', 'anon', 'authenticated']::text[]) as roles(role_name)
   cross join unnest(array[
     'ingest.begin_mastodon_public_hashtag_job(uuid,text,bigint,text,text)',
     'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)',
     'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)'
   ]::text[]) as functions(function_name)),
  'public browser roles cannot execute fenced Mastodon mutation RPCs'
);
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure)
    and has_function_privilege(
      'service_role',
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)',
      'execute'
    )
    and not has_function_privilege(
      'authenticated',
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)',
      'execute'
    ),
  'only service_role receives the fenced Mastodon finalizer'
);
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)'::regprocedure)
    and has_function_privilege(
      'service_role',
      'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)',
      'execute'
    )
    and not has_function_privilege(
      'anon',
      'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)',
      'execute'
    )
    and not has_function_privilege(
      'authenticated',
      'ingest.record_mastodon_rate_limit(uuid,text,bigint,timestamptz)',
      'execute'
    ),
  'only service_role receives the fenced Mastodon Retry-After recorder'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.prune_mastodon_public_hashtag_v1(timestamptz,integer)',
    'execute'
  ),
  'worker roles cannot invoke Mastodon cleanup outside maintenance fencing'
);

select is(
  public.get_public_social_discovery_v3() ->> 'schemaVersion',
  '3.0.0',
  'public social v3 uses the exact schema version'
);
select is(
  jsonb_array_length(public.get_public_social_discovery_v3() -> 'sources'),
  3,
  'public social v3 exposes Bluesky, Nostr, then Mastodon'
);
select set_eq(
  $$select value ->> 'id' from jsonb_array_elements(
      public.get_public_social_discovery_v3() -> 'sources') as values(value)$$,
  $$values ('bluesky_jetstream'::text), ('nostr_multi_relay'), ('mastodon_public_hashtag')$$,
  'public social v3 returns the three fixed safe source identities'
);
select set_eq(
  $$select jsonb_object_keys(public.get_public_social_discovery_v3() #> '{sources,2}')$$,
  $$values
    ('id'::text), ('name'), ('kind'), ('access'), ('status'), ('lastCollectedAt'),
    ('url'), ('note')$$,
  'Mastodon public source has exactly the safe eight-key projection'
);
select doesnt_match(
  public.get_public_social_discovery_v3()::text,
  '(?i)(api/v[0-9]|"(instance_url|endpoint|status_id|sha256|hash|tag_key|cursor|rate_limit|error|raw|profile|handle|media|location|source_policy|gate|payload)"[[:space:]]*:)',
  'public social v3 exposes no Mastodon endpoint, identity, cursor, rate, or raw fields'
);
select matches(
  public.get_public_social_discovery_v3() #>> '{sources,2,note}',
  '^[0-9]+ of 7 reviewed mastodon[.]social public hashtag activity-only feeds collected recently; [0-9]+ retained activity-only rows[.] Coverage may be incomplete and is never opening evidence, a denominator, or rate evidence[.]$',
  'Mastodon note uses the exact public activity-only non-evidence contract'
);
select ok(
  has_function_privilege('anon', 'public.get_public_social_discovery_v3()', 'execute')
    and has_function_privilege('authenticated', 'public.get_public_social_discovery_v3()', 'execute')
    and not has_function_privilege('service_role', 'public.get_public_social_discovery_v3()', 'execute'),
  'only anon/authenticated can execute the public v3 projection'
);

select ok(ingest.mastodon_tag_keys_v1(array['pokemontcg', 'pokeca_ja']),
  'canonical Mastodon key order accepts an approved subset');
select ok(not ingest.mastodon_tag_keys_v1(array['pokeca_ja', 'pokemontcg']),
  'canonical Mastodon key order rejects reordered tags');
select ok(not ingest.mastodon_tag_keys_v1(array['pokemontcg', 'pokemontcg']),
  'canonical Mastodon key order rejects duplicate tags');

insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000001',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-1', 1, false
);
create temporary table mastodon_begin_one on commit drop as
select * from ingest.begin_mastodon_public_hashtag_job(
  'a7000000-0000-4000-8000-000000000001',
  'mastodon-worker-1', 1, 'mastodon_social', 'pokemontcg'
);
select ok(
  (select acquired and retry_at is null and start_status_id is null
   from mastodon_begin_one),
  'first Mastodon tag slice acquires from the nullable checkpoint'
);

insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000006',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemoncards"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-6', 1, false
);
select ok(
  (select not acquired and retry_at > clock_timestamp()
   from ingest.begin_mastodon_public_hashtag_job(
     'a7000000-0000-4000-8000-000000000006',
     'mastodon-worker-6', 1, 'mastodon_social', 'pokemoncards'
   )),
  'a second worker cannot pass the shared Mastodon database request gate'
);

select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_mastodon_public_hashtag_job(
      'a7000000-0000-4000-8000-000000000001', 'mastodon-worker-1', 1,
      jsonb_build_object(
        'version', '1.0.0', 'instance_key', 'mastodon_social',
        'tag_key', 'pokemontcg', 'start_status_id', null,
        'end_status_id', null, 'incomplete', false, 'requests_made', 0,
        'statuses_seen', 0, 'bytes_seen', 0, 'candidates', '[]'::jsonb,
        'rate_limit_limit', 100, 'rate_limit_remaining', 99,
        'rate_limit_reset_at', '2099-01-01T00:00:00Z', 'extra', true
      )
    )
  $sql$),
  '22023',
  'unexpected Mastodon root keys fail closed before writes'
);
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'a7000000-0000-4000-8000-000000000001')
    and (select last_status_id is null
         from ingest.mastodon_public_hashtag_checkpoints
         where tag_key = 'pokemontcg'),
  'Mastodon contract rejection leaves its lease and cursor unchanged'
);

create function pg_temp.mastodon_hash(status_id text)
returns text
language sql
immutable
as $$
  select encode(extensions.digest(
    convert_to('mastodon_social' || E'\n' || status_id, 'UTF8'), 'sha256'
  ), 'hex');
$$;

select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7000000-0000-4000-8000-000000000001', 'mastodon-worker-1', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemontcg', 'start_status_id', null,
      'end_status_id', 'opaque-z', 'incomplete', false,
      'requests_made', 1, 'statuses_seen', 1, 'bytes_seen', 128,
      'candidates', jsonb_build_array(jsonb_build_object(
        'status_id', 'opaque-z', 'status_key_sha256', pg_temp.mastodon_hash('opaque-z'),
        'published_at', '2000-01-01T00:00:00Z',
        'matched_tags', jsonb_build_array('pokemontcg'),
        'activity_only', true, 'statistics_eligible', false
      )),
      'rate_limit_limit', null, 'rate_limit_remaining', null,
      'rate_limit_reset_at', null
    )
  )$sql$,
  'valid first Mastodon slice finalizes atomically'
);
select ok(
  (select status = 'completed' and locked_by is null
   from ingest.jobs where id = 'a7000000-0000-4000-8000-000000000001')
    and (select owner_job_id is null
         from ingest.source_request_gates where source_key = 'mastodon_social')
    and (select last_status_id = 'opaque-z'
         from ingest.mastodon_public_hashtag_checkpoints where tag_key = 'pokemontcg'),
  'successful finalization advances the opaque cursor and releases the gate'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_candidates),
  1,
  'one hashed candidate is persisted'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_observations
   where tag_key = 'pokemontcg'),
  1,
  'one append-only tag observation is persisted'
);
select ok(
  (select status_key_sha256 = pg_temp.mastodon_hash('opaque-z')
      and matched_tags = array['pokemontcg']::text[]
      and activity_only and not statistics_eligible and not is_demo
   from ingest.mastodon_public_hashtag_candidates),
  'candidate persists only the instance-bound hash and activity metadata'
);
select is(
  (select count(*)::integer from information_schema.columns
   where table_schema in ('ingest')
     and table_name in (
       'mastodon_public_hashtag_candidates',
       'mastodon_public_hashtag_observations'
     )
     and column_name in (
       'status_id', 'content', 'text', 'account', 'handle', 'profile', 'media',
       'url', 'uri', 'location', 'raw_payload'
     )),
  0,
  'candidate and observation schemas contain no plaintext or raw status fields'
);

-- Replay is idempotent when the exact persisted fields match.  The second
-- cursor is lexically smaller to prove that cursors are opaque equality keys.
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000002',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-2', 1, false
);
create temporary table mastodon_begin_two on commit drop as
select * from ingest.begin_mastodon_public_hashtag_job(
  'a7000000-0000-4000-8000-000000000002',
  'mastodon-worker-2', 1, 'mastodon_social', 'pokemontcg'
);
select ok((select acquired and start_status_id = 'opaque-z' from mastodon_begin_two),
  'replay slice starts at the exact opaque checkpoint');
select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7000000-0000-4000-8000-000000000002', 'mastodon-worker-2', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemontcg', 'start_status_id', 'opaque-z',
      'end_status_id', 'opaque-a', 'incomplete', true,
      'requests_made', 1, 'statuses_seen', 1, 'bytes_seen', 128,
      'candidates', jsonb_build_array(jsonb_build_object(
        'status_id', 'opaque-z', 'status_key_sha256', pg_temp.mastodon_hash('opaque-z'),
        'published_at', '2000-01-01T00:00:00Z',
        'matched_tags', jsonb_build_array('pokemontcg'),
        'activity_only', true, 'statistics_eligible', false
      )),
      'rate_limit_limit', 100, 'rate_limit_remaining', 99,
      'rate_limit_reset_at', to_char(
        clock_timestamp() at time zone 'UTC' + interval '1 hour',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"'
      )
    )
  )$sql$,
  'an exact replay is accepted and the opaque cursor may move lexically backward'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_observations
   where tag_key = 'pokemontcg'),
  1,
  'exact replay does not duplicate the append-only observation'
);

-- Rate-limit exhaustion persists a shared source cooldown, blocking every tag.
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000003',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemoncards"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-3', 1, false
);
create temporary table mastodon_begin_three on commit drop as
select * from ingest.begin_mastodon_public_hashtag_job(
  'a7000000-0000-4000-8000-000000000003',
  'mastodon-worker-3', 1, 'mastodon_social', 'pokemoncards'
);
select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7000000-0000-4000-8000-000000000003', 'mastodon-worker-3', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemoncards', 'start_status_id', null,
      'end_status_id', null, 'incomplete', true,
      'requests_made', 1, 'statuses_seen', 0, 'bytes_seen', 64,
      'candidates', '[]'::jsonb, 'rate_limit_limit', 100,
      'rate_limit_remaining', 0,
      'rate_limit_reset_at', to_char(
        clock_timestamp() at time zone 'UTC' + interval '1 hour',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"'
      )
    )
  )$sql$,
  'rate-limit exhaustion finalizes and records the durable cooldown'
);
select ok(
  (select cooldown_until > clock_timestamp()
   from ingest.mastodon_rate_cooldowns),
  'rate-limit exhaustion sets a future shared cooldown'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000004',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokeca_ja"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-4', 1, false
);
select ok(
  (select not acquired and retry_at > clock_timestamp()
   from ingest.begin_mastodon_public_hashtag_job(
     'a7000000-0000-4000-8000-000000000004',
     'mastodon-worker-4', 1, 'mastodon_social', 'pokeca_ja'
   )),
  'the shared cooldown defers a different tag job'
);

-- A transport-level 429 uses the dedicated fenced recorder before the runtime
-- returns the job to pending. The shared cooldown must survive that lease
-- transition and block every other tag on the same instance.
update ingest.mastodon_rate_cooldowns
set cooldown_until = clock_timestamp(),
    updated_at = clock_timestamp()
where instance_key = 'mastodon_social';
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds'
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7000000-0000-4000-8000-000000000005',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemon_card_ko"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-worker-5', 1, false
);
select ok(
  (select acquired and retry_at is null
   from ingest.begin_mastodon_public_hashtag_job(
     'a7000000-0000-4000-8000-000000000005',
     'mastodon-worker-5', 1, 'mastodon_social', 'pokemon_card_ko'
   )),
  'transport-level rate-limit fixture acquires the shared Mastodon gate'
);
select is(
  (select recorded from ingest.record_mastodon_rate_limit(
    'a7000000-0000-4000-8000-000000000005',
    'mastodon-worker-5', 2, clock_timestamp() + interval '30 minutes'
  )),
  false,
  'stale lease generation cannot persist a Mastodon Retry-After boundary'
);
select lives_ok(
  $$select * from ingest.record_mastodon_rate_limit(
    'a7000000-0000-4000-8000-000000000005',
    'mastodon-worker-5', 1, clock_timestamp() + interval '30 minutes'
  )$$,
  'the owning Mastodon lease persists a bounded Retry-After boundary'
);
select ok(
  (select cooldown_until > clock_timestamp() + interval '29 minutes'
   from ingest.mastodon_rate_cooldowns where instance_key = 'mastodon_social')
    and (select owner_job_id is null and active_until is null
         from ingest.source_request_gates where source_key = 'mastodon_social')
    and (select status = 'pending'
               and attempts = 0
               and locked_by is null
               and locked_at is null
               and lock_expires_at is null
               and available_at > clock_timestamp() + interval '29 minutes'
         from ingest.jobs
         where id = 'a7000000-0000-4000-8000-000000000005'),
  'transport-level Retry-After atomically replaces the gate and pauses its job'
);
select ok(
  (select status = 'pending' and locked_by is null
   from ingest.jobs where id = 'a7000000-0000-4000-8000-000000000005')
    and (select not acquired and retry_at > clock_timestamp() + interval '29 minutes'
         from ingest.begin_mastodon_public_hashtag_job(
           'a7000000-0000-4000-8000-000000000004',
           'mastodon-worker-4', 1, 'mastodon_social', 'pokeca_ja'
         )),
  'durable 429 cooldown continues blocking another tag after lease deferral'
);

-- A malformed scheduler payload must stop before the recorder touches the
-- shared advisory lock, cooldown, or request gate.  In particular, SQL NULL
-- comparisons must not turn a missing JSONB key into an approved payload.
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values
  (
    'a7000000-0000-4000-8000-000000000007',
    'source.mastodon.public_hashtag',
    '{"tag_key":"pokemontcg"}'::jsonb,
    'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
    'mastodon-worker-malformed-instance', 1, false
  ),
  (
    'a7000000-0000-4000-8000-000000000008',
    'source.mastodon.public_hashtag',
    '{"instance_key":"mastodon_social"}'::jsonb,
    'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
    'mastodon-worker-malformed-tag', 1, false
  );
select is(
  (select recorded from ingest.record_mastodon_rate_limit(
    'a7000000-0000-4000-8000-000000000007',
    'mastodon-worker-malformed-instance', 1, clock_timestamp() + interval '30 minutes'
  )),
  false,
  'missing Mastodon instance_key fails closed before rate-limit state changes'
);
select is(
  (select recorded from ingest.record_mastodon_rate_limit(
    'a7000000-0000-4000-8000-000000000008',
    'mastodon-worker-malformed-tag', 1, clock_timestamp() + interval '30 minutes'
  )),
  false,
  'missing Mastodon tag_key fails closed before rate-limit state changes'
);
select ok(
  (select status = 'running' and locked_by = 'mastodon-worker-malformed-instance'
   from ingest.jobs where id = 'a7000000-0000-4000-8000-000000000007')
    and (select status = 'running' and locked_by = 'mastodon-worker-malformed-tag'
         from ingest.jobs where id = 'a7000000-0000-4000-8000-000000000008'),
  'malformed Mastodon payloads leave their leases untouched'
);

select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1(
    'mastodon_social_wrong', date_trunc('minute', clock_timestamp()),
    'source.mastodon.public_hashtag',
    '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
    0, 5
  )$$,
  '22023',
  'Mastodon jobs require one exact instance_key, tag_key, and canonical schedule name',
  'scheduled Mastodon enqueue requires canonical schedule identity'
);
select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1(
    'mastodon_social_pokemoncards', date_trunc('minute', clock_timestamp()),
    'source.mastodon.public_hashtag',
    '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
    0, 5
  )$$,
  '22023',
  'Mastodon jobs require one exact instance_key, tag_key, and canonical schedule name',
  'scheduled Mastodon enqueue rejects a schedule name for a different approved tag'
);
create temporary table mastodon_scheduled_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'mastodon_social_pokemon_card_zh_hant', date_trunc('minute', clock_timestamp()),
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemon_card_zh_hant"}'::jsonb,
  0, 5
);
select is((select count(*)::integer from mastodon_scheduled_job), 1,
  'canonical Traditional Chinese Mastodon schedule enqueues one exact job');
select throws_ok(
  $$select * from ingest.enqueue_job_v1(
    'source.mastodon.public_hashtag',
    '{"instance_key":"mastodon_social","tag_key":"pokemontcg","extra":true}'::jsonb
  )$$,
  '22023', 'Mastodon jobs require one exact instance_key and tag_key',
  'direct Mastodon enqueue rejects extra payload fields'
);

-- Expired activity rows are deleted while the per-tag cursor and cooldown stay.
insert into ingest.mastodon_public_hashtag_candidates (
  source_policy_id, status_key_sha256, matched_tags, published_at,
  first_seen_at, last_seen_at, expires_at
) select id, pg_temp.mastodon_hash('expired'), array['pokemontcg']::text[],
  '2000-01-01T00:00:00Z', statement_timestamp() - interval '31 days',
  statement_timestamp() - interval '31 days', statement_timestamp() - interval '1 day'
  from ingest.source_policies where source_key = 'mastodon_social';
insert into ingest.mastodon_public_hashtag_observations (
  source_policy_id, tag_key, status_key_sha256, matched_tags, published_at,
  observed_at, expires_at
) select id, 'pokemontcg', pg_temp.mastodon_hash('expired-observation'),
  array['pokemontcg']::text[], '2000-01-01T00:00:00Z',
  statement_timestamp() - interval '31 days', statement_timestamp() - interval '1 day'
  from ingest.source_policies where source_key = 'mastodon_social';
select lives_ok(
  $$select * from ingest.prune_mastodon_public_hashtag_v1(clock_timestamp(), 500000)$$,
  'bounded Mastodon cleanup executes for the owner'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_candidates
   where status_key_sha256 = pg_temp.mastodon_hash('expired')),
  0,
  'expired candidates are removed by cleanup'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_observations
   where status_key_sha256 = pg_temp.mastodon_hash('expired-observation')),
  0,
  'expired observations are removed by cleanup'
);
select is(
  (select count(*)::integer from ingest.mastodon_public_hashtag_checkpoints),
  7,
  'cleanup retains all seven per-tag checkpoints'
);
select is(
  (select count(*)::integer from ingest.mastodon_rate_cooldowns),
  1,
  'cleanup retains the durable shared cooldown'
);
select ok(
  -- The exact replay above is a second successful collection slice: it
  -- advances the opaque cursor and counts transport activity even though the
  -- immutable observation is deduplicated. Cleanup must preserve that current
  -- checkpoint, not the snapshot from the first slice.
  (select last_status_id = 'opaque-a'
      and requests_seen_total = 2
      and statuses_seen_total = 2
      and bytes_seen_total = 256
      and candidates_seen_total = 2
   from ingest.mastodon_public_hashtag_checkpoints
   where tag_key = 'pokemontcg'),
  'cleanup preserves the opaque cursor and checkpoint counters'
);

select * from finish();
rollback;
