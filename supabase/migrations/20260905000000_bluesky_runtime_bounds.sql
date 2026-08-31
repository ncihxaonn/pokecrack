begin;

-- Production traffic can consume the 2 MiB slice budget before the original
-- 40-second wall clock. Keep the byte ceiling unchanged, reduce the live
-- window, and let the worker finalize only a complete prefix so the next
-- inclusive cursor replay resumes at the first omitted event.
do $migration$
declare
  changed_rows integer;
  old_config jsonb := '{
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
  }'::jsonb;
  new_config jsonb := '{
    "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
    "collection":"app.bsky.feed.post",
    "operations":["create","update","delete"],
    "kinds":["commit"],
    "subprotocol":"xrpc.v1.json",
    "stream_window_seconds":10,
    "max_events":10000,
    "max_message_bytes":262144,
    "max_stream_bytes":2097152,
    "max_candidates":100,
    "max_deletions":100,
    "max_excerpt_chars":500,
    "keyword_registry":"bluesky-keywords-v1",
    "statistics_eligible":false
  }'::jsonb;
begin
  update ingest.source_policies as policies
  set config = new_config,
      updated_at = clock_timestamp()
  where policies.source_key = 'bluesky_jetstream'
    and policies.display_name = 'Bluesky Jetstream discovery'
    and policies.source_kind = 'official_api'
    and policies.collector_type = 'bluesky_jetstream'
    and policies.version = 'bluesky-jetstream-v1'
    and policies.expected_interval_seconds = 60
    and not policies.is_demo
    and policies.config = old_config;

  get diagnostics changed_rows = row_count;
  if changed_rows <> 1 then
    raise exception using
      errcode = '55000',
      message = 'Bluesky runtime policy did not match the reviewed 40-second predecessor';
  end if;
end;
$migration$;

-- The original migration intentionally repeated the exact policy contract in
-- both fenced lifecycle functions and the public-safe status projection.
-- Replace exactly one reviewed fragment in each definition and fail closed on
-- any source drift instead of recreating three large security-definer bodies.
do $migration$
declare
  function_oid oid;
  definition text;
  updated_definition text;
  old_fragment text := '"stream_window_seconds":40';
  new_fragment text := '"stream_window_seconds":10';
  occurrence_count integer;
begin
  foreach function_oid in array array[
    'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'::regprocedure::oid,
    'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'::regprocedure::oid,
    'public.get_public_social_discovery_v1()'::regprocedure::oid
  ]
  loop
    select pg_get_functiondef(function_oid) into strict definition;
    occurrence_count := (
      char_length(definition) - char_length(replace(definition, old_fragment, ''))
    ) / char_length(old_fragment);
    if occurrence_count <> 1 or position(new_fragment in definition) <> 0 then
      raise exception using
        errcode = '55000',
        message = 'Bluesky runtime function contract drifted before bounds update',
        detail = function_oid::text;
    end if;

    updated_definition := replace(definition, old_fragment, new_fragment);
    if function_oid = 'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'::regprocedure::oid then
      updated_definition := replace(
        updated_definition,
        'A 40-second stream plus close/finalization work',
        'A 10-second stream plus close/finalization work'
      );
    end if;
    if position(old_fragment in updated_definition) <> 0
      or position(new_fragment in updated_definition) = 0
    then
      raise exception using
        errcode = '55000',
        message = 'Bluesky runtime function bounds replacement was incomplete',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

alter function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  owner to postgres;
revoke all on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  to service_role;

alter function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  to service_role;

alter function public.get_public_social_discovery_v1() owner to postgres;
revoke all on function public.get_public_social_discovery_v1()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_social_discovery_v1()
  to anon, authenticated;

commit;
