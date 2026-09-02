-- Migration: 20260913000000_social_activity_pulse_v4
-- Publish only bounded, aggregate social activity.  The public projection is
-- deliberately separate from source provenance: it contains no text, URL/URI,
-- activity identity, hash, author, tag, cursor, or raw provider payload, and
-- it never infers country, pack, or rate information.
begin;

create or replace function public.get_public_social_discovery_v4()
returns jsonb
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  with pulse_clock as (
    select
      statement_timestamp() as observed_at,
      statement_timestamp() - interval '24 hours' as window_start
  ),
  bluesky_registered as (
    select
      policies.id,
      policies.enabled,
      (
        policies.display_name = 'Bluesky Jetstream discovery'
        and policies.source_kind = 'official_api'
        and policies.domain = 'jetstream.us-west.bsky.network'
        and policies.base_url =
          'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
        and policies.collector_type = 'bluesky_jetstream'
        and policies.access_mode = 'official_api'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['bluesky_jetstream']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 1
        and policies.max_items_per_run = 100
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.config = '{
          "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
          "collection":"app.bsky.feed.post",
          "operations":["create","update","delete"],
          "kinds":["commit"],
          "subprotocol":"xrpc.v1.json",
          "stream_window_seconds":40,
          "max_events":10000,
          "max_message_bytes":262144,
          "max_stream_bytes":2097152,
          "max_candidates":100,
          "max_deletions":100,
          "max_excerpt_chars":500,
          "keyword_registry":"bluesky-keywords-v1",
          "statistics_eligible":false
        }'::jsonb
        and policies.version = 'bluesky-jetstream-v1'
        and policies.expected_interval_seconds = 60
        and not policies.is_demo
      ) as contract_valid
    from ingest.source_policies as policies
    where policies.source_key = 'bluesky_jetstream'
  ),
  bluesky_checkpoint_health as (
    select
      count(checkpoints.source_policy_id)::integer as checkpoint_count,
      count(checkpoints.source_policy_id) filter (
        where checkpoints.last_collected_at >= pulse_clock.observed_at - interval '3 minutes'
          and checkpoints.last_collected_at <= pulse_clock.observed_at
      )::integer as recent_count,
      min(checkpoints.last_collected_at) filter (
        where checkpoints.last_collected_at <= pulse_clock.observed_at
      ) as last_collected_at
    from bluesky_registered as registered
    cross join pulse_clock
    left join ingest.bluesky_jetstream_checkpoints as checkpoints
      on checkpoints.source_policy_id = registered.id
      and not checkpoints.is_demo
      and checkpoints.endpoint =
        'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
      and checkpoints.protocol = 'xrpc.v1.json'
      and checkpoints.collection = 'app.bsky.feed.post'
  ),
  bluesky_activity_health as (
    select
      least(count(*) filter (
        where candidates.first_seen_at >= pulse_clock.window_start
          and candidates.first_seen_at < pulse_clock.observed_at
      ), 1000000)::integer as new_candidates_24h,
      least(count(*) filter (
        where candidates.deleted_at is null
          and candidates.expires_at > pulse_clock.observed_at
      ), 1000000)::integer as retained_candidates
    from bluesky_registered as registered
    cross join pulse_clock
    left join ingest.bluesky_jetstream_candidates as candidates
      on candidates.source_policy_id = registered.id
      and not candidates.is_demo
  ),
  bluesky_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count,
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
    from bluesky_registered as registered
    cross join bluesky_checkpoint_health as checkpoints
    cross join bluesky_activity_health as activity
    group by
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
  ),
  bluesky_source as (
    select jsonb_build_object(
      'id', 'bluesky_jetstream',
      'name', 'Bluesky Jetstream discovery',
      'kind', 'social',
      'access', 'public',
      'status', case
        when bluesky_health.registered_count <> 1
          or bluesky_health.valid_count <> 1
          or bluesky_health.checkpoint_count <> 1
          then 'attention'
        when bluesky_health.enabled_count <> 1 then 'paused'
        when bluesky_health.recent_count <> 1 then 'delayed'
        else 'operational'
      end,
      'freshness', case
        when bluesky_health.registered_count <> 1
          or bluesky_health.valid_count <> 1
          or bluesky_health.checkpoint_count <> 1
          then 'attention'
        when bluesky_health.enabled_count <> 1 then 'paused'
        when bluesky_health.recent_count <> 1 then 'delayed'
        else 'fresh'
      end,
      'lastCollectedAt', case
        when bluesky_health.last_collected_at is null then null
        else to_char(
          bluesky_health.last_collected_at at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'newCandidates24h', bluesky_health.new_candidates_24h,
      'retainedCandidates', bluesky_health.retained_candidates,
      'activityOnly', true,
      'statisticsEligible', false
    ) as source
    from bluesky_health
  ),
  nostr_registered as (
    select
      policies.id,
      policies.enabled,
      policies.config ->> 'relay_key' as relay_key,
      policies.config,
      (
        policies.source_key = case policies.config ->> 'relay_key'
          when 'primal' then 'nostr_relay_primal'
          when 'nos_lol' then 'nostr_relay_nos_lol'
          when 'nostr_net' then 'nostr_relay_nostr_net'
          else ''
        end
        and policies.display_name = case policies.config ->> 'relay_key'
          when 'primal' then 'Nostr relay relay.primal.net discovery'
          when 'nos_lol' then 'Nostr relay nos.lol discovery'
          when 'nostr_net' then 'Nostr relay relay.nostr.net discovery'
          else ''
        end
        and policies.source_kind = 'public_web'
        and policies.domain = case policies.config ->> 'relay_key'
          when 'primal' then 'relay.primal.net'
          when 'nos_lol' then 'nos.lol'
          when 'nostr_net' then 'relay.nostr.net'
          else ''
        end
        and policies.base_url = case policies.config ->> 'relay_key'
          when 'primal' then 'wss://relay.primal.net/'
          when 'nos_lol' then 'wss://nos.lol/'
          when 'nostr_net' then 'wss://relay.nostr.net/'
          else ''
        end
        and policies.collector_type = 'nostr_relay'
        and policies.access_mode = 'public'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['nostr_relay']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 1
        and policies.max_items_per_run = 100
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.version = 'nostr-multi-relay-v1'
        and policies.expected_interval_seconds = 60
        and not policies.is_demo
        and policies.config ->> 'protocol' = 'nip01'
        and policies.config ->> 'policy_state' = 'degraded_missing_relay_specific_terms'
        and policies.config -> 'required_nips' = jsonb_build_array(1, 9, 11)
        and policies.config -> 'approved_tags' = jsonb_build_array(
          'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
          'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
        )
        and policies.config ->> 'endpoint' = policies.base_url
        and policies.config ->> 'nip11_url' = case policies.config ->> 'relay_key'
          when 'primal' then 'https://relay.primal.net/'
          when 'nos_lol' then 'https://nos.lol/'
          when 'nostr_net' then 'https://relay.nostr.net/'
          else ''
        end
        and policies.config ->> 'replay_overlap_seconds' = '300'
        and policies.config ->> 'stream_window_seconds' = '15'
        and policies.config ->> 'max_events' = '100'
        and policies.config ->> 'max_message_bytes' = '262144'
        and policies.config ->> 'max_stream_bytes' = '2097152'
        and policies.config ->> 'max_candidates' = '100'
        and policies.config ->> 'max_deletions' = '100'
        and policies.config ->> 'max_delete_targets' = '16'
        and policies.config ->> 'statistics_eligible' = 'false'
        and policies.config = jsonb_build_object(
          'relay_key', policies.config ->> 'relay_key',
          'endpoint', policies.base_url,
          'nip11_url', policies.config ->> 'nip11_url',
          'protocol', 'nip01',
          'policy_state', 'degraded_missing_relay_specific_terms',
          'required_nips', jsonb_build_array(1, 9, 11),
          'approved_tags', jsonb_build_array(
            'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
            'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
          ),
          'replay_overlap_seconds', 300,
          'stream_window_seconds', 15,
          'max_events', 100,
          'max_message_bytes', 262144,
          'max_stream_bytes', 2097152,
          'max_candidates', 100,
          'max_deletions', 100,
          'max_delete_targets', 16,
          'statistics_eligible', false
        )
      ) as contract_valid
    from ingest.source_policies as policies
    where policies.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    )
  ),
  nostr_checkpoint_health as (
    select
      count(checkpoints.source_policy_id)::integer as checkpoint_count,
      count(checkpoints.source_policy_id) filter (
        where checkpoints.last_checkpoint >= pulse_clock.observed_at - interval '3 minutes'
          and checkpoints.last_checkpoint <= pulse_clock.observed_at
      )::integer as recent_count,
      min(checkpoints.last_checkpoint) filter (
        where checkpoints.last_checkpoint <= pulse_clock.observed_at
      ) as last_collected_at
    from nostr_registered as registered
    cross join pulse_clock
    left join ingest.nostr_relay_checkpoints as checkpoints
      on checkpoints.source_policy_id = registered.id
      and not checkpoints.is_demo
      and checkpoints.relay_key = registered.relay_key
      and checkpoints.endpoint = registered.config ->> 'endpoint'
      and checkpoints.nip11_url = registered.config ->> 'nip11_url'
      and checkpoints.protocol = registered.config ->> 'protocol'
      and checkpoints.approved_tags = array[
        'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
        'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
      ]::text[]
  ),
  nostr_activity_health as (
    select
      least(count(*) filter (
        where candidates.first_seen_at >= pulse_clock.window_start
          and candidates.first_seen_at < pulse_clock.observed_at
      ), 1000000)::integer as new_candidates_24h,
      least(count(*) filter (
        where candidates.deleted_at is null
          and candidates.expires_at > pulse_clock.observed_at
      ), 1000000)::integer as retained_candidates
    from nostr_registered as registered
    cross join pulse_clock
    left join ingest.nostr_relay_candidates as candidates
      on candidates.source_policy_id = registered.id
      and candidates.relay_key = registered.relay_key
      and not candidates.is_demo
      and candidates.activity_only
      and not candidates.statistics_eligible
  ),
  nostr_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count,
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
    from nostr_registered as registered
    cross join nostr_checkpoint_health as checkpoints
    cross join nostr_activity_health as activity
    group by
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
  ),
  nostr_source as (
    select jsonb_build_object(
      'id', 'nostr_multi_relay',
      'name', 'Nostr multi-relay discovery',
      'kind', 'social',
      'access', 'public',
      'status', case
        when nostr_health.registered_count <> 3
          or nostr_health.valid_count <> 3
          or nostr_health.checkpoint_count <> 3
          then 'attention'
        when nostr_health.enabled_count <> 3 then 'paused'
        when nostr_health.recent_count <> 3 then 'delayed'
        else 'operational'
      end,
      'freshness', case
        when nostr_health.registered_count <> 3
          or nostr_health.valid_count <> 3
          or nostr_health.checkpoint_count <> 3
          then 'attention'
        when nostr_health.enabled_count <> 3 then 'paused'
        when nostr_health.recent_count <> 3 then 'delayed'
        else 'fresh'
      end,
      'lastCollectedAt', case
        when nostr_health.last_collected_at is null then null
        else to_char(
          nostr_health.last_collected_at at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'newCandidates24h', nostr_health.new_candidates_24h,
      'retainedCandidates', nostr_health.retained_candidates,
      'activityOnly', true,
      'statisticsEligible', false
    ) as source
    from nostr_health
  ),
  mastodon_registered as (
    select
      policies.id,
      policies.enabled,
      (
        policies.source_key = 'mastodon_social'
        and policies.display_name = 'Mastodon public hashtag discovery'
        and policies.source_kind = 'official_api'
        and policies.domain = 'mastodon.social'
        and policies.base_url = 'https://mastodon.social/'
        and policies.collector_type = 'mastodon_rest'
        and policies.access_mode = 'official_api'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['mastodon_rest']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 2
        and policies.max_pages_per_run = 2
        and policies.max_items_per_run = 80
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.version = 'mastodon-public-hashtag-v1'
        and policies.expected_interval_seconds = 300
        and not policies.is_demo
        and policies.config ->> 'instance_key' = 'mastodon_social'
        and policies.config ->> 'policy_state' = 'reviewed_public_api_2026-08-31'
        and policies.config ->> 'tag_registry' = 'mastodon-tags-v1'
        and policies.config -> 'approved_tags' = jsonb_build_object(
          'pokemontcg', 'pokemontcg',
          'pokemoncards', 'pokemoncards',
          'pokeca_ja', 'ポケカ',
          'pokemon_card_ja', 'ポケモンカード',
          'pokemon_card_ko', '포켓몬카드',
          'pokemon_card_zh_hans', '宝可梦卡牌',
          'pokemon_card_zh_hant', '寶可夢卡牌'
        )
        and policies.config ->> 'statistics_eligible' = 'false'
        and policies.config = jsonb_build_object(
          'instance_key', 'mastodon_social',
          'instance_url', 'https://mastodon.social/api/v2/instance',
          'about_url', 'https://mastodon.social/about',
          'privacy_url', 'https://mastodon.social/api/v1/instance/privacy_policy',
          'robots_url', 'https://mastodon.social/robots.txt',
          'rules_url', 'https://mastodon.social/api/v1/instance/rules',
          'terms_url', 'https://mastodon.social/api/v1/instance/terms_of_service',
          'hashtag_base_url', 'https://mastodon.social/api/v1/timelines/tag/',
          'official_docs_url', 'https://docs.joinmastodon.org/methods/timelines/',
          'policy_state', 'reviewed_public_api_2026-08-31',
          'terms_effective_date', '2026-08-31',
          'terms_checked_at', '2026-08-31',
          'privacy_checked_at', '2026-08-31',
          'rules_checked_at', '2026-08-31',
          'robots_checked_at', '2026-08-31',
          'public_access_checked_at', '2026-08-31',
          'robots_decision', 'api_route_not_disallowed',
          'rate_limit_basis', 'live_x_ratelimit_headers',
          'rate_limit_default_per_5m', 300,
          'effective_max_requests_per_5m', 150,
          'operator_acknowledgment', 'recommended_before_production',
          'checkpoint_retention', 'opaque_cursor_persists_beyond_activity_ttl',
          'user_agent', 'PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)',
          'required_hashtag_access', jsonb_build_object('local', 'public', 'remote', 'public'),
          'tag_registry', 'mastodon-tags-v1',
          'approved_tags', jsonb_build_object(
            'pokemontcg', 'pokemontcg',
            'pokemoncards', 'pokemoncards',
            'pokeca_ja', 'ポケカ',
            'pokemon_card_ja', 'ポケモンカード',
            'pokemon_card_ko', '포켓몬카드',
            'pokemon_card_zh_hans', '宝可梦卡牌',
            'pokemon_card_zh_hant', '寶可夢卡牌'
          ),
          'limit', 40,
          'max_pages_per_run', 2,
          'max_items_per_run', 80,
          'max_response_bytes', 2097152,
          'connect_timeout_seconds', 10,
          'read_timeout_seconds', 15,
          'allow_redirects', false,
          'statistics_eligible', false
        )
      ) as contract_valid
    from ingest.source_policies as policies
    where policies.source_key = 'mastodon_social'
  ),
  mastodon_checkpoint_health as (
    select
      count(checkpoints.tag_key)::integer as checkpoint_count,
      count(checkpoints.tag_key) filter (
        where checkpoints.last_collected_at >= pulse_clock.observed_at - interval '15 minutes'
          and checkpoints.last_collected_at <= pulse_clock.observed_at
          and not checkpoints.incomplete
      )::integer as recent_count,
      min(checkpoints.last_collected_at) filter (
        where checkpoints.last_collected_at <= pulse_clock.observed_at
      ) as last_collected_at
    from mastodon_registered as registered
    cross join pulse_clock
    left join ingest.mastodon_public_hashtag_checkpoints as checkpoints
      on checkpoints.source_policy_id = registered.id
      and not checkpoints.is_demo
      and checkpoints.instance_key = 'mastodon_social'
      and checkpoints.tag_key in (
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      )
  ),
  mastodon_activity_health as (
    select
      least(count(*) filter (
        where candidates.first_seen_at >= pulse_clock.window_start
          and candidates.first_seen_at < pulse_clock.observed_at
      ), 1000000)::integer as new_candidates_24h,
      least(count(*) filter (
        where candidates.expires_at > pulse_clock.observed_at
      ), 1000000)::integer as retained_candidates
    from mastodon_registered as registered
    cross join pulse_clock
    left join ingest.mastodon_public_hashtag_candidates as candidates
      on candidates.source_policy_id = registered.id
      and not candidates.is_demo
      and candidates.activity_only
      and not candidates.statistics_eligible
  ),
  mastodon_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count,
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
    from mastodon_registered as registered
    cross join mastodon_checkpoint_health as checkpoints
    cross join mastodon_activity_health as activity
    group by
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.new_candidates_24h,
      activity.retained_candidates
  ),
  mastodon_source as (
    select jsonb_build_object(
      'id', 'mastodon_public_hashtag',
      'name', 'Mastodon public hashtag discovery',
      'kind', 'social',
      'access', 'public',
      'status', case
        when mastodon_health.registered_count <> 1
          or mastodon_health.valid_count <> 1
          or mastodon_health.checkpoint_count <> 7
          then 'attention'
        when mastodon_health.enabled_count <> 1 then 'paused'
        when mastodon_health.recent_count <> 7 then 'delayed'
        else 'operational'
      end,
      'freshness', case
        when mastodon_health.registered_count <> 1
          or mastodon_health.valid_count <> 1
          or mastodon_health.checkpoint_count <> 7
          then 'attention'
        when mastodon_health.enabled_count <> 1 then 'paused'
        when mastodon_health.recent_count <> 7 then 'delayed'
        else 'fresh'
      end,
      'lastCollectedAt', case
        when mastodon_health.last_collected_at is null then null
        else to_char(
          mastodon_health.last_collected_at at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'newCandidates24h', mastodon_health.new_candidates_24h,
      'retainedCandidates', mastodon_health.retained_candidates,
      'activityOnly', true,
      'statisticsEligible', false
    ) as source
    from mastodon_health
  )
  select jsonb_build_object(
    'schemaVersion', '4.0.0',
    'window', jsonb_build_object(
      'start', to_char(
        pulse_clock.window_start at time zone 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
      ),
      'end', to_char(
        pulse_clock.observed_at at time zone 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
      )
    ),
    'activityOnly', true,
    'nonEvidence', true,
    'sources', jsonb_build_array(
      bluesky_source.source,
      nostr_source.source,
      mastodon_source.source
    )
  )
  from pulse_clock
  cross join bluesky_source
  cross join nostr_source
  cross join mastodon_source;
$$;

alter function public.get_public_social_discovery_v4() owner to postgres;
revoke all on function public.get_public_social_discovery_v4()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v4()
  to anon, authenticated;
comment on function public.get_public_social_discovery_v4() is
  'Strict public-safe global social activity pulse. Returns only bounded 24-hour new and retained candidate counts plus freshness for Bluesky, Nostr, and Mastodon; never returns text, URL/URI, identities, IDs, hashes, authors, tags, cursors, rate data, geography, pack inference, evidence, or raw payloads.';

commit;
