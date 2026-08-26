begin;

create or replace function public.get_admin_dashboard_snapshot_v1()
returns jsonb
language plpgsql
security definer
volatile
parallel restricted
set search_path = pg_catalog
as $$
declare
  v_snapshot jsonb;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'admin snapshot service authorization required';
  end if;

  with queue_summary as (
    select
      count(*) filter (where j.status = 'pending')::integer as queued,
      count(*) filter (where j.status = 'running')::integer as running,
      count(*) filter (where j.status in ('failed', 'dead'))::integer as dead
    from ingest.jobs j
    where not j.is_demo
  ),
  pipeline_summary as (
    select
      coalesce(max(i.updated_at)::text, 'never') as freshness,
      count(*) filter (where i.status = 'accepted')::integer as accepted,
      count(*) filter (where i.status in ('rejected', 'failed', 'excluded'))::integer as rejected,
      count(*) filter (where i.status = 'activity_only')::integer as activity_only,
      count(*) filter (where i.duplicate_suspected)::integer as duplicates
    from ingest.source_items i
    where not i.is_demo
  ),
  bounded_workers as (
    select h.worker_id, h.worker_type, h.last_seen_at, h.current_job_id
    from ingest.worker_heartbeats h
    where not h.is_demo
    order by h.last_seen_at desc, h.worker_id
    limit 50
  ),
  workers_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', w.worker_id,
          'label', w.worker_type,
          'state', case
            when w.last_seen_at >= clock_timestamp() - interval '2 minutes' then 'healthy'
            when w.last_seen_at >= clock_timestamp() - interval '15 minutes' then 'attention'
            else 'unavailable'
          end,
          'heartbeat', w.last_seen_at::text,
          'currentWork', case
            when w.current_job_id is null then 'idle'
            else 'one active leased job'
          end
        )
        order by w.last_seen_at desc, w.worker_id
      ),
      '[]'::jsonb
    ) as value
    from bounded_workers w
  ),
  bounded_sources as (
    select p.source_key, p.display_name, p.enabled, p.collector_type,
      p.last_attempt_at, p.last_success_at, p.last_failure_at,
      p.expected_interval_seconds, p.is_demo
    from ingest.source_policies p
    where not p.is_demo
    order by p.updated_at desc, p.source_key
    limit 50
  ),
  source_status_rows as (
    select s.*,
      case
        when not s.enabled or s.collector_type = 'disabled' then 'paused'
        when s.last_failure_at is not null
          and (s.last_success_at is null or s.last_failure_at > s.last_success_at) then 'attention'
        when s.last_success_at is null then 'unavailable'
        when s.last_success_at >= clock_timestamp()
          - make_interval(secs => least(604800, s.expected_interval_seconds * 2)) then 'healthy'
        else 'attention'
      end as operational_state,
      coalesce(s.last_success_at, s.last_attempt_at)::text as freshness
    from bounded_sources s
  ),
  sources_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', s.source_key,
          'label', s.display_name,
          'policy', case when s.enabled and s.collector_type <> 'disabled'
            then 'enabled' else 'disabled' end,
          'freshness', coalesce(s.freshness, 'never'),
          'adapterStatus', s.operational_state
        )
        order by s.source_key
      ),
      '[]'::jsonb
    ) as value
    from source_status_rows s
  ),
  adapters_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', s.source_key,
          'label', s.display_name,
          'mode', case
            when not s.enabled or s.collector_type = 'disabled' then 'disabled'
            when s.is_demo then 'fixture'
            else 'live'
          end,
          'status', s.operational_state,
          'freshness', coalesce(s.freshness, 'never')
        )
        order by s.source_key
      ),
      '[]'::jsonb
    ) as value
    from source_status_rows s
  ),
  bounded_jobs as (
    select j.id, j.job_type, j.status, j.attempts, j.max_attempts, j.updated_at
    from ingest.jobs j
    where not j.is_demo
    order by j.updated_at desc, j.id
    limit 100
  ),
  jobs_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', j.id::text,
          'label', j.job_type,
          'status', case j.status
            when 'pending' then 'queued'
            when 'running' then 'running'
            when 'completed' then 'completed'
            when 'cancelled' then 'cancelled'
            else 'dead'
          end,
          'attempts', j.attempts::text || ' / ' || j.max_attempts::text,
          'freshness', j.updated_at::text,
          'records', 0
        )
        order by j.updated_at desc, j.id
      ),
      '[]'::jsonb
    ) as value
    from bounded_jobs j
  ),
  bounded_sessions as (
    select s.profile_name, s.status, s.extension_connected, s.daemon_connected,
      s.last_check_at
    from ingest.browser_sessions s
    where not s.is_demo
    order by s.last_check_at desc, s.profile_name
    limit 50
  ),
  sessions_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', s.profile_name,
          'label', s.profile_name,
          'browser', case when s.daemon_connected then 'healthy' else 'attention' end,
          'extension', case when s.extension_connected then 'healthy' else 'attention' end,
          'login', case
            when s.status = 'expired' then 'expired'
            when s.status in ('ready', 'authenticated') then 'ready'
            else 'required'
          end,
          'freshness', s.last_check_at::text
        )
        order by s.last_check_at desc, s.profile_name
      ),
      '[]'::jsonb
    ) as value
    from bounded_sessions s
  ),
  ai_base as (
    select u.date, u.stage, u.request_count, u.input_tokens, u.output_tokens,
      u.estimated_cost_aud
    from ingest.ai_usage_daily u
    where not u.is_demo
      and u.date >= current_date - 90
      and u.stage in ('extract', 'validate', 'escalate')
  ),
  ai_totals as (
    select
      coalesce(sum(a.request_count), 0)::bigint as requests,
      coalesce(sum(a.input_tokens), 0)::bigint as input_tokens,
      coalesce(sum(a.output_tokens), 0)::bigint as output_tokens,
      coalesce(sum(a.estimated_cost_aud), 0)::numeric as estimated_cost_aud
    from ai_base a
  ),
  bounded_ai as (
    select a.date, a.stage,
      sum(a.request_count)::bigint as requests,
      sum(a.input_tokens)::bigint as input_tokens,
      sum(a.output_tokens)::bigint as output_tokens,
      sum(a.estimated_cost_aud)::numeric as estimated_cost_aud
    from ai_base a
    group by a.date, a.stage
    order by a.date desc, a.stage
    limit 100
  ),
  ai_rows_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'day', a.date,
          'stage', a.stage,
          'requests', a.requests,
          'inputTokens', a.input_tokens,
          'outputTokens', a.output_tokens,
          'estimatedCostAud', a.estimated_cost_aud
        )
        order by a.date desc, a.stage
      ),
      '[]'::jsonb
    ) as value
    from bounded_ai a
  ),
  database_capacity as (
    select pg_database_size(current_database())::bigint as used_bytes
  ),
  aggregate_checkpoint as (
    select max(a.computed_at) as computed_at
    from analytics.dashboard_daily a
    where not a.is_demo
  ),
  bounded_records as (
    select i.id, i.title, i.platform, i.status, i.duplicate_suspected, i.updated_at
    from ingest.source_items i
    where not i.is_demo
      and (i.duplicate_suspected or i.status in ('accepted', 'activity_only', 'rejected'))
    order by i.updated_at desc, i.id
    limit 50
  ),
  records_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', r.id::text,
          'label', left(
            coalesce(nullif(btrim(r.title), ''), r.platform, 'Source item'),
            160
          ),
          'decision', case
            when r.duplicate_suspected then 'duplicate'
            when r.status = 'activity_only' then 'activity-only'
            when r.status = 'accepted' then 'accepted'
            else 'rejected'
          end,
          'freshness', r.updated_at::text
        )
        order by r.updated_at desc, r.id
      ),
      '[]'::jsonb
    ) as value
    from bounded_records r
  ),
  service_rows as (
    select
      w.worker_id as id,
      w.worker_type as label,
      case
        when w.last_seen_at >= clock_timestamp() - interval '2 minutes' then 'healthy'
        when w.last_seen_at >= clock_timestamp() - interval '15 minutes' then 'attention'
        else 'unavailable'
      end as status,
      w.last_seen_at::text as freshness,
      w.last_seen_at as sort_at
    from bounded_workers w
    union all
    select
      case
        when char_length('browser:' || s.profile_name) <= 160
          then 'browser:' || s.profile_name
        else 'browser:' || left(s.profile_name, 119) || ':' || md5(s.profile_name)
      end,
      left('Authenticated browser ' || s.profile_name, 160),
      case when s.daemon_connected and s.extension_connected then 'healthy' else 'attention' end,
      s.last_check_at::text,
      s.last_check_at
    from bounded_sessions s
  ),
  services_json as (
    select coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', s.id,
          'label', s.label,
          'status', s.status,
          'freshness', s.freshness
        )
        order by s.sort_at desc, s.id
      ),
      '[]'::jsonb
    ) as value
    from service_rows s
  )
  select jsonb_build_object(
    'fixture', false,
    'label', 'Live operational snapshot · bounded private telemetry',
    'generatedAt', clock_timestamp(),
    'queue', jsonb_build_object(
      'queued', q.queued,
      'running', q.running,
      'dead', q.dead
    ),
    'pipeline', jsonb_build_object(
      'freshness', p.freshness,
      'accepted', p.accepted,
      'rejected', p.rejected,
      'activityOnly', p.activity_only,
      'duplicates', p.duplicates
    ),
    'workers', w.value,
    'sources', src.value,
    'jobs', j.value,
    'browserSessions', b.value,
    'adapters', ad.value,
    'ai', jsonb_build_object(
      'requests', ait.requests,
      'inputTokens', ait.input_tokens,
      'outputTokens', ait.output_tokens,
      'estimatedCostAud', ait.estimated_cost_aud,
      'budgetAud', null,
      'paused', false,
      'rows', air.value
    ),
    'capacity', jsonb_build_object(
      'database', jsonb_build_object(
        'used', pg_size_pretty(cap.used_bytes),
        'limit', '500 MB',
        'usedPercent', least(100, round(cap.used_bytes::numeric * 100 / (500 * 1024 * 1024), 1)),
        'thresholdPercent', 70,
        'status', case
          when cap.used_bytes >= 425 * 1024 * 1024 then 'paused'
          when cap.used_bytes >= 350 * 1024 * 1024 then 'attention'
          else 'healthy'
        end
      ),
      'storage', jsonb_build_object(
        'used', 'Unavailable',
        'limit', 'Not reported',
        'usedPercent', 0,
        'thresholdPercent', 80,
        'status', 'unavailable'
      )
    ),
    'backup', jsonb_build_object(
      'status', 'unavailable',
      'freshness', 'not reported',
      'detail', 'No database backup checkpoint is persisted in this schema.'
    ),
    'aggregation', jsonb_build_object(
      'status', case
        when agg.computed_at is null then 'unavailable'
        when agg.computed_at >= clock_timestamp() - interval '30 minutes' then 'healthy'
        when agg.computed_at >= clock_timestamp() - interval '2 hours' then 'attention'
        else 'paused'
      end,
      'freshness', coalesce(agg.computed_at::text, 'never'),
      'detail', case
        when agg.computed_at is null then 'No live aggregate checkpoint is available.'
        else 'Latest live analytics dashboard computation.'
      end
    ),
    'services', svc.value,
    'records', rec.value
  )
  into v_snapshot
  from queue_summary q
  cross join pipeline_summary p
  cross join workers_json w
  cross join sources_json src
  cross join jobs_json j
  cross join sessions_json b
  cross join adapters_json ad
  cross join ai_totals ait
  cross join ai_rows_json air
  cross join database_capacity cap
  cross join aggregate_checkpoint agg
  cross join services_json svc
  cross join records_json rec;

  return v_snapshot;
end;
$$;

revoke all on function public.get_admin_dashboard_snapshot_v1()
  from public, anon, authenticated, service_role;
grant execute on function public.get_admin_dashboard_snapshot_v1()
  to service_role;
comment on function public.get_admin_dashboard_snapshot_v1() is
  'Service-role-only bounded Admin telemetry. Returns queue, freshness, usage and capacity summaries without private job, browser, AI-content, source-content, address or credential fields.';

create or replace function public.admin_control_and_audit_v1(
  p_action text,
  p_actor_id uuid,
  p_actor_email text,
  p_source_url text default null,
  p_target_id text default null
)
returns jsonb
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  v_actor_id uuid;
  v_actor_email text;
  v_actor_email_hash text;
  v_domain text;
  v_authority text;
  v_policy_id uuid;
  v_object_id text;
  v_rows integer := 0;
  v_policy_validated boolean := false;
  v_record_is_demo boolean;
begin
  if coalesce(auth.jwt() ->> 'role', '') <> 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'admin control service authorization required';
  end if;

  v_actor_id := p_actor_id;
  v_actor_email := lower(btrim(coalesce(p_actor_email, '')));
  if v_actor_id is null
    or char_length(v_actor_email) not between 3 and 320
    or v_actor_email !~ '^[^[:space:]@]+@[^[:space:]@]+$'
  then
    raise exception using
      errcode = '22023',
      message = 'verified admin actor required';
  end if;

  if p_action is null or p_action not in (
    'source.enqueue',
    'job.retry',
    'job.cancel',
    'source.disable',
    'record.exclude',
    'browser.refresh',
    'service.restart'
  ) then
    raise exception using errcode = '22023', message = 'unsupported admin action';
  end if;

  v_actor_email_hash := encode(
    extensions.digest(convert_to(v_actor_email, 'UTF8'), 'sha256'),
    'hex'
  );

  case p_action
    when 'source.enqueue' then
      if p_target_id is not null
        or p_source_url is null
        or char_length(p_source_url) > 2048
        or p_source_url !~ '^https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?(/[^?#[:space:]]*)?$'
        or p_source_url ~ '[@?#[:space:]]'
      then
        raise exception using errcode = '22023', message = 'invalid source URL';
      end if;

      v_authority := split_part(substr(p_source_url, 9), '/', 1);
      v_domain := lower(split_part(v_authority, ':', 1));
      if v_domain = '' or v_domain !~ '^[a-z0-9.-]+$' or char_length(v_domain) > 253 then
        raise exception using errcode = '22023', message = 'invalid source domain';
      end if;

      select policy.id
      into v_policy_id
      from ingest.source_policies as policy
      where policy.enabled
        and not policy.is_demo
        and policy.collector_type <> 'disabled'
        and (
          policy.domain = v_domain
          or (policy.include_subdomains and v_domain like '%.' || policy.domain)
        )
      order by (policy.domain = v_domain) desc, char_length(policy.domain) desc
      limit 1;

      if v_policy_id is null then
        -- Policy denials are expected security events. Returning a structured
        -- failure keeps the denial audit in the same committed transaction;
        -- raising here would roll the audit row back with the exception.
        insert into ingest.admin_audit_log (
          actor_id, actor_email_hash, action, object_type, object_id, detail, is_demo
        ) values (
          v_actor_id,
          v_actor_email_hash,
          p_action,
          'source',
          null,
          jsonb_build_object(
            'policy_validated', false,
            'source_domain', v_domain,
            'denied', true,
            'reason', 'source_policy_denied'
          ),
          false
        );
        return jsonb_build_object(
          'ok', false,
          'audit_written', true,
          'policy_validated', false,
          'reason', 'source_policy_denied'
        );
      end if;

      insert into ingest.jobs (
        job_type, payload, status, priority, dedupe_key, available_at, max_attempts,
        is_demo
      ) values (
        'collect.url',
        jsonb_build_object(
          'source_url', p_source_url,
          'source_policy_id', v_policy_id,
          'requested_by', v_actor_id
        ),
        'pending',
        10,
        'admin-source:' || encode(
          extensions.digest(convert_to(p_source_url, 'UTF8'), 'sha256'),
          'hex'
        ),
        clock_timestamp(),
        5,
        false
      )
      on conflict (job_type, dedupe_key, is_demo)
        where dedupe_key is not null and status in ('pending', 'running')
      do update set updated_at = ingest.jobs.updated_at
      returning id::text into v_object_id;
      v_policy_validated := true;

    when 'job.retry' then
      if p_source_url is not null
        or p_target_id is null
        or p_target_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      then
        raise exception using errcode = '22023', message = 'invalid job target';
      end if;
      update ingest.jobs
      set status = 'pending',
          available_at = clock_timestamp(),
          locked_by = null,
          locked_at = null,
          lock_expires_at = null,
          completed_at = null,
          updated_at = clock_timestamp()
      where id = p_target_id::uuid
        and not is_demo
        and status = 'failed'
        and attempts < max_attempts
      returning is_demo into v_record_is_demo;
      get diagnostics v_rows = row_count;
      if v_rows <> 1 then
        raise exception using errcode = 'P0002', message = 'retryable job not found';
      end if;
      v_object_id := p_target_id;

    when 'job.cancel' then
      if p_source_url is not null
        or p_target_id is null
        or p_target_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      then
        raise exception using errcode = '22023', message = 'invalid job target';
      end if;
      update ingest.jobs
      set status = 'cancelled',
          locked_by = null,
          locked_at = null,
          lock_expires_at = null,
          completed_at = clock_timestamp(),
          updated_at = clock_timestamp()
      where id = p_target_id::uuid
        and not is_demo
        and status in ('pending', 'failed')
      returning is_demo into v_record_is_demo;
      get diagnostics v_rows = row_count;
      if v_rows <> 1 then
        raise exception using errcode = 'P0002', message = 'cancellable job not found';
      end if;
      v_object_id := p_target_id;

    when 'source.disable' then
      if p_source_url is not null or p_target_id is null then
        raise exception using errcode = '22023', message = 'invalid source target';
      end if;
      update ingest.source_policies
      set enabled = false,
          collector_type = 'disabled',
          access_mode = 'disabled',
          routes = array['disabled']::text[],
          updated_at = clock_timestamp()
      where not is_demo
        and (source_key = p_target_id or id::text = p_target_id)
      returning is_demo into v_record_is_demo;
      get diagnostics v_rows = row_count;
      if v_rows <> 1 then
        raise exception using errcode = 'P0002', message = 'source policy not found';
      end if;
      v_object_id := p_target_id;

    when 'record.exclude' then
      if p_source_url is not null
        or p_target_id is null
        or p_target_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      then
        raise exception using errcode = '22023', message = 'invalid record target';
      end if;
      update ingest.source_items
      set usage_classification = 'excluded',
          status = 'excluded',
          updated_at = clock_timestamp()
      where id = p_target_id::uuid
        and not is_demo
      returning is_demo into v_record_is_demo;
      get diagnostics v_rows = row_count;
      if v_rows <> 1 then
        raise exception using errcode = 'P0002', message = 'record not found';
      end if;

      update ingest.openings
      set eligible_for_statistics = false,
          validation_status = 'excluded',
          public_status = 'rejected',
          updated_at = clock_timestamp()
      where source_item_id = p_target_id::uuid
        and is_demo = v_record_is_demo;
      delete from ingest.batch_sightings
      where source_item_id = p_target_id::uuid
        and is_demo = v_record_is_demo;

      -- A record may have contributed to every materialized scope. Remove all
      -- derived rows for its data mode rather than attempting an unsafe partial
      -- decrement, then make the public RPC unavailable until a full rebuild.
      delete from analytics.dashboard_daily where is_demo = v_record_is_demo;
      delete from analytics.set_metrics_daily where is_demo = v_record_is_demo;
      delete from analytics.region_metrics_daily where is_demo = v_record_is_demo;
      delete from analytics.retailer_metrics_daily where is_demo = v_record_is_demo;
      delete from analytics.batch_metrics_daily where is_demo = v_record_is_demo;
      delete from analytics.signals where is_demo = v_record_is_demo;

      delete from public.dashboard_overview where is_demo = v_record_is_demo;
      delete from public.set_summaries where is_demo = v_record_is_demo;
      delete from public.region_summaries where is_demo = v_record_is_demo;
      delete from public.retailer_summaries where is_demo = v_record_is_demo;
      delete from public.batch_summaries where is_demo = v_record_is_demo;
      delete from public.recent_activity where is_demo = v_record_is_demo;
      delete from public.public_signals where is_demo = v_record_is_demo;

      insert into public.dashboard_overview (
        snapshot_key,
        mode,
        generated_at,
        australia_coverage,
        methodology_version,
        is_demo
      ) values (
        case
          when v_record_is_demo then 'admin-record-exclusion-demo'
          else 'admin-record-exclusion-live'
        end,
        'unavailable',
        clock_timestamp(),
        'Public statistics are unavailable pending a complete rebuild after an exclusion.',
        'admin-exclusion-pending-rebuild',
        v_record_is_demo
      )
      on conflict (snapshot_key) do update
      set mode = 'unavailable',
          generated_at = excluded.generated_at,
          observed_packs = 0,
          complete_openings = 0,
          verified_sources = 0,
          coverage_days = 0,
          tracked_sets = 0,
          tracked_regions = 0,
          tracked_retailers = 0,
          batch_sightings = 0,
          australia_coverage = excluded.australia_coverage,
          baseline_hit_rate = null,
          accepted_count = 0,
          activity_only_count = 0,
          rejected_count = 0,
          methodology_version = excluded.methodology_version,
          is_demo = v_record_is_demo;

      v_object_id := p_target_id;

    when 'browser.refresh' then
      if p_source_url is not null or p_target_id is null then
        raise exception using errcode = '22023', message = 'invalid control target';
      end if;
      select s.is_demo
      into v_record_is_demo
      from ingest.browser_sessions s
      where s.profile_name = p_target_id
        and not s.is_demo;
      if not found then
        raise exception using errcode = 'P0002', message = 'live browser target not found';
      end if;
      insert into ingest.jobs (
        job_type, payload, status, priority, dedupe_key, available_at, max_attempts,
        is_demo
      ) values (
        p_action,
        jsonb_build_object('target_id', p_target_id, 'requested_by', v_actor_id),
        'pending',
        100,
        'admin-control:' || p_action || ':' || p_target_id,
        clock_timestamp(),
        3,
        false
      )
      on conflict (job_type, dedupe_key, is_demo)
        where dedupe_key is not null and status in ('pending', 'running')
      do update set updated_at = ingest.jobs.updated_at
      returning id::text into v_object_id;

    when 'service.restart' then
      if p_source_url is not null or p_target_id is null then
        raise exception using errcode = '22023', message = 'invalid control target';
      end if;
      select h.is_demo
      into v_record_is_demo
      from ingest.worker_heartbeats h
      where h.worker_id = p_target_id
        and not h.is_demo;
      if not found then
        raise exception using errcode = 'P0002', message = 'live service target not found';
      end if;
      insert into ingest.jobs (
        job_type, payload, status, priority, dedupe_key, available_at, max_attempts,
        is_demo
      ) values (
        p_action,
        jsonb_build_object('target_id', p_target_id, 'requested_by', v_actor_id),
        'pending',
        100,
        'admin-control:' || p_action || ':' || p_target_id,
        clock_timestamp(),
        3,
        false
      )
      on conflict (job_type, dedupe_key, is_demo)
        where dedupe_key is not null and status in ('pending', 'running')
      do update set updated_at = ingest.jobs.updated_at
      returning id::text into v_object_id;
  end case;

  insert into ingest.admin_audit_log (
    actor_id, actor_email_hash, action, object_type, object_id, detail, is_demo
  ) values (
    v_actor_id,
    v_actor_email_hash,
    p_action,
    split_part(p_action, '.', 1),
    v_object_id,
    jsonb_build_object(
      'policy_validated', v_policy_validated,
      'source_domain', v_domain
    ),
    coalesce(v_record_is_demo, false)
  );

  return jsonb_build_object(
    'ok', true,
    'audit_written', true,
    'policy_validated', v_policy_validated,
    'object_id', v_object_id
  );
end;
$$;

revoke all on function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_control_and_audit_v1(text, uuid, text, text, text)
  to service_role;
comment on function public.admin_control_and_audit_v1(text, uuid, text, text, text) is
  'Service-role-only Admin controls. The Web server verifies Supabase Auth, app_metadata.pokecrack_admin, ADMIN_EMAILS, and its kill switch before passing the audited actor. Every successful action writes ingest.admin_audit_log.';

commit;
