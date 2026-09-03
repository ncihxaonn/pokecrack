begin;

-- The runtime verifier was released before the isolated Bluesky capability.
-- Reissue only its reviewed definition points after the Bluesky role/ACL
-- attestation exists. This preserves the aggregate-only return shape while
-- making the four-container deployment path fail closed on its own policy,
-- checkpoint, queue, and schedule evidence.
do $runtime_evidence_bluesky$
declare
  definition text;
  updated_definition text;
  old_service_sets constant text := $old$
    when 'tcgdex-nostr' then
      expected_worker_types := array[
        'collector', 'scheduler', 'watchdog', 'nostr-collector'
      ]::text[];
      expected_source_keys := array[
        'tcgdex_catalog',
        'nostr_relay_primal',
        'nostr_relay_nos_lol',
        'nostr_relay_nostr_net'
      ]::text[];
      expected_job_types := array[
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.nostr.relay'
      ]::text[];
    else
$old$;
  new_service_sets constant text := $new$
    when 'tcgdex-nostr' then
      expected_worker_types := array[
        'collector', 'scheduler', 'watchdog', 'nostr-collector'
      ]::text[];
      expected_source_keys := array[
        'tcgdex_catalog',
        'nostr_relay_primal',
        'nostr_relay_nos_lol',
        'nostr_relay_nostr_net'
      ]::text[];
      expected_job_types := array[
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.nostr.relay'
      ]::text[];
    when 'tcgdex-bluesky' then
      expected_worker_types := array[
        'collector', 'scheduler', 'watchdog', 'bluesky-collector'
      ]::text[];
      expected_source_keys := array[
        'tcgdex_catalog',
        'bluesky_jetstream'
      ]::text[];
      expected_job_types := array[
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.bluesky.jetstream'
      ]::text[];
      expected_schedule_names := array[
        'catalog_sync', 'cleanup', 'bluesky_jetstream'
      ]::text[];
      expected_schedule_count := 3;
    else
$new$;
  old_declaration constant text := $old$
  overall_status text;
begin
$old$;
  new_declaration constant text := $new$
  overall_status text;
  bluesky_contract_ready boolean := true;
begin
$new$;
  old_monitor_transition constant text := $old$
      raise exception 'runtime evidence monitor login has direct application grants';
    end if;
  end if;

  with expected(worker_type) as (
$old$;
  new_monitor_transition constant text := $new$
      raise exception 'runtime evidence monitor login has direct application grants';
    end if;
  end if;

  if p_service_set = 'tcgdex-bluesky' then
    select coalesce(
      attestation = jsonb_build_object(
        'postgresql17', true,
        'ledger_210', true,
        'ledger_260', true,
        'ledger_270', true,
        'bluesky_worker_role_exact', true,
        'bluesky_policy_exact', true,
        'bluesky_acl_exact', true
      ),
      false
    )
    into bluesky_contract_ready
    from (
      select ingest.verify_bluesky_release_v1() as attestation
    ) as release_contract;

    if bluesky_contract_ready is distinct from true then
      raise exception 'runtime evidence Bluesky capability is unavailable or drifted';
    end if;
  end if;

  with expected(worker_type) as (
$new$;
  old_checkpoint_rows constant text := $old$
  with expected(source_key) as (
    select unnest(expected_source_keys)
  ), checkpoint_rows as (
    select
      expected.source_key,
      policies.expected_interval_seconds,
      case
        when expected.source_key = 'tcgdex_catalog' then catalog_state.last_checked_at
        when nostr_checkpoints.last_checkpoint is null then null
        else nostr_checkpoints.updated_at
      end as freshness_at
    from expected
    left join ingest.source_policies as policies
      on policies.source_key = expected.source_key
      and policies.is_demo = false
    left join catalog.sync_state as catalog_state
      on expected.source_key = 'tcgdex_catalog'
      and catalog_state.source = 'tcgdex'
      and catalog_state.scope = 'sets'
      and catalog_state.language = 'en'
      and catalog_state.is_demo = false
    left join ingest.nostr_relay_checkpoints as nostr_checkpoints
      on expected.source_key <> 'tcgdex_catalog'
      and nostr_checkpoints.source_policy_id = policies.id
      and nostr_checkpoints.is_demo = false
  )
$old$;
  new_checkpoint_rows constant text := $new$
  with expected(source_key) as (
    select unnest(expected_source_keys)
  ), checkpoint_rows as (
    select
      expected.source_key,
      policies.expected_interval_seconds,
      case
        when expected.source_key = 'tcgdex_catalog' then catalog_state.last_checked_at
        when expected.source_key = 'bluesky_jetstream' then bluesky_checkpoints.last_collected_at
        when nostr_checkpoints.last_checkpoint is null then null
        else nostr_checkpoints.updated_at
      end as freshness_at
    from expected
    left join ingest.source_policies as policies
      on policies.source_key = expected.source_key
      and policies.is_demo = false
    left join catalog.sync_state as catalog_state
      on expected.source_key = 'tcgdex_catalog'
      and catalog_state.source = 'tcgdex'
      and catalog_state.scope = 'sets'
      and catalog_state.language = 'en'
      and catalog_state.is_demo = false
    left join ingest.nostr_relay_checkpoints as nostr_checkpoints
      on expected.source_key <> 'tcgdex_catalog'
      and expected.source_key <> 'bluesky_jetstream'
      and nostr_checkpoints.source_policy_id = policies.id
      and nostr_checkpoints.is_demo = false
    left join ingest.bluesky_jetstream_checkpoints as bluesky_checkpoints
      on expected.source_key = 'bluesky_jetstream'
      and bluesky_checkpoints.source_policy_id = policies.id
      and bluesky_checkpoints.is_demo = false
  )
$new$;
begin
  if to_regprocedure('ingest.verify_bluesky_release_v1()') is null
     or to_regclass('ingest.bluesky_jetstream_checkpoints') is null then
    raise exception using
      errcode = '55000',
      message = 'Bluesky runtime evidence prerequisites are unavailable';
  end if;

  -- The definition replacement below deliberately preserves the hardened
  -- verifier header.  Refuse to reissue a drifted SECURITY DEFINER function:
  -- otherwise pg_get_functiondef() could faithfully carry an unsafe owner,
  -- search path, volatility, or parallel setting into this migration.
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
     or length(definition) - length(replace(definition, old_service_sets, ''))
       <> length(old_service_sets)
     or length(definition) - length(replace(definition, old_declaration, ''))
       <> length(old_declaration)
     or length(definition) - length(replace(definition, old_monitor_transition, ''))
       <> length(old_monitor_transition)
     or length(definition) - length(replace(definition, old_checkpoint_rows, ''))
       <> length(old_checkpoint_rows)
     or position(new_service_sets in definition) <> 0
     or position(new_declaration in definition) <> 0
     or position(new_monitor_transition in definition) <> 0
     or position(new_checkpoint_rows in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence no longer matches the reviewed Bluesky integration points';
  end if;

  updated_definition := replace(
    replace(
      replace(
        replace(definition, old_service_sets, new_service_sets),
        old_declaration,
        new_declaration
      ),
      old_monitor_transition,
      new_monitor_transition
    ),
    old_checkpoint_rows,
    new_checkpoint_rows
  );

  if updated_definition = definition
     or position(old_service_sets in updated_definition) <> 0
     or position(old_declaration in updated_definition) <> 0
     or position(old_monitor_transition in updated_definition) <> 0
     or position(old_checkpoint_rows in updated_definition) <> 0
     or position(new_service_sets in updated_definition) = 0
     or position(new_declaration in updated_definition) = 0
     or position(new_monitor_transition in updated_definition) = 0
     or position(new_checkpoint_rows in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'runtime release evidence Bluesky integration did not match exactly';
  end if;

  execute updated_definition;
end;
$runtime_evidence_bluesky$;

alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  owner to postgres;
revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  to pokecrack_runtime_monitor;

comment on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text) is
  'Private aggregate-only release verifier. Exact service sets require post-release non-demo worker, source, schedule, queue, checkpoint, cleanup, and isolated capability evidence; never returns identifiers, payloads, URLs, cursors, or source text.';

commit;
