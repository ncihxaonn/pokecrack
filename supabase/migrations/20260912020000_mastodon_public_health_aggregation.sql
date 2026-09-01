-- Migration: 20260912020000_mastodon_public_health_aggregation
-- Keep policy-cardinality checks independent from the seven per-tag
-- checkpoints. Joining before aggregation multiplied the single reviewed
-- policy into seven rows and made a fully fresh source report attention.
begin;

create or replace function public.get_public_social_discovery_v3()
returns jsonb
language sql
security definer
stable
parallel safe
set search_path = pg_catalog
as $$
  with prior_sources as (
    select source.value, source.ordinality
    from jsonb_array_elements(
      public.get_public_social_discovery_v2() -> 'sources'
    ) with ordinality as source(value, ordinality)
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
  mastodon_policy_health as (
    select
      count(*)::integer as registered_count,
      count(*) filter (where registered.contract_valid)::integer as valid_count,
      count(*) filter (where registered.enabled)::integer as enabled_count
    from mastodon_registered as registered
  ),
  mastodon_checkpoint_health as (
    select
      count(checkpoints.tag_key)::integer as checkpoint_count,
      count(checkpoints.tag_key) filter (
        where checkpoints.last_collected_at >= statement_timestamp() - interval '15 minutes'
          and checkpoints.last_collected_at <= statement_timestamp()
      )::integer as recent_count,
      min(checkpoints.last_collected_at) filter (
        where checkpoints.last_collected_at <= statement_timestamp()
      ) as last_collected_at
    from ingest.mastodon_public_hashtag_checkpoints as checkpoints
    join mastodon_registered as registered
      on registered.id = checkpoints.source_policy_id
    where checkpoints.instance_key = 'mastodon_social'
      and checkpoints.tag_key in (
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      )
      and not checkpoints.is_demo
  ),
  mastodon_activity_health as (
    select count(*)::integer as active_candidate_count
    from ingest.mastodon_public_hashtag_candidates as candidates
    where not candidates.is_demo
      and candidates.expires_at > statement_timestamp()
  ),
  mastodon_health as (
    select
      policy.registered_count,
      policy.valid_count,
      policy.enabled_count,
      checkpoints.checkpoint_count,
      checkpoints.recent_count,
      checkpoints.last_collected_at,
      activity.active_candidate_count
    from mastodon_policy_health as policy
    cross join mastodon_checkpoint_health as checkpoints
    cross join mastodon_activity_health as activity
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
      'lastCollectedAt', case
        when mastodon_health.last_collected_at is null then null
        else to_char(
          mastodon_health.last_collected_at at time zone 'UTC',
          'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
        )
      end,
      'url', 'https://docs.joinmastodon.org/methods/timelines/',
      'note', format(
        '%s of 7 reviewed mastodon.social public hashtag activity-only feeds collected recently; %s retained activity-only rows. Coverage may be incomplete and is never opening evidence, a denominator, or rate evidence.',
        mastodon_health.recent_count,
        mastodon_health.active_candidate_count
      )
    ) as source
    from mastodon_health
  ),
  all_sources as (
    select prior_sources.value as source, prior_sources.ordinality
    from prior_sources
    union all
    select mastodon_source.source, 2147483647::bigint
    from mastodon_source
  )
  select jsonb_build_object(
    'schemaVersion', '3.0.0',
    'sources', (
      select jsonb_agg(all_sources.source order by all_sources.ordinality)
      from all_sources
    )
  );
$$;

alter function public.get_public_social_discovery_v3() owner to postgres;
revoke all on function public.get_public_social_discovery_v3()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v3()
  to anon, authenticated;
comment on function public.get_public_social_discovery_v3() is
  'Strict public-safe Bluesky, Nostr, and Mastodon social discovery health tuple. Mastodon coverage is incomplete and activity-only; the projection never opens evidence or a denominator and never returns private identities, hashes, tags, cursors, endpoints, rate headers, errors, or raw fields.';

commit;
