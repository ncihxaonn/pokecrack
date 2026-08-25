begin;

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
        and policy.collector_type <> 'disabled'
        and (
          policy.domain = v_domain
          or (policy.include_subdomains and v_domain like '%.' || policy.domain)
        )
      order by (policy.domain = v_domain) desc, char_length(policy.domain) desc
      limit 1;

      if v_policy_id is null then
        raise exception using errcode = '42501', message = 'source policy denied';
      end if;

      insert into ingest.jobs (
        job_type, payload, status, priority, dedupe_key, available_at, max_attempts
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
        5
      )
      on conflict (job_type, dedupe_key)
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
        and status = 'failed'
        and attempts < max_attempts;
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
      where id = p_target_id::uuid and status in ('pending', 'failed');
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
      where source_key = p_target_id or id::text = p_target_id;
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
      where source_item_id = p_target_id::uuid;
      delete from ingest.batch_sightings
      where source_item_id = p_target_id::uuid;

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
        'admin-record-exclusion',
        'unavailable',
        clock_timestamp(),
        'Public statistics are unavailable pending a complete rebuild after an exclusion.',
        'admin-exclusion-pending-rebuild',
        false
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
          is_demo = false;

      v_object_id := p_target_id;

    when 'browser.refresh', 'service.restart' then
      if p_source_url is not null or p_target_id is null then
        raise exception using errcode = '22023', message = 'invalid control target';
      end if;
      insert into ingest.jobs (
        job_type, payload, status, priority, dedupe_key, available_at, max_attempts
      ) values (
        p_action,
        jsonb_build_object('target_id', p_target_id, 'requested_by', v_actor_id),
        'pending',
        100,
        'admin-control:' || p_action || ':' || p_target_id,
        clock_timestamp(),
        3
      )
      on conflict (job_type, dedupe_key)
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
    false
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
