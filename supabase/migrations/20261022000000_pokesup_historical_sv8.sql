begin;

-- CLI 2.115.0 generated 20260910030029 on the isolated MAM host. Renumbered
-- forward after the already-applied 20261021000000, following this repository's
-- ledger convention; identifiers are not scheduled execution dates.
-- Source proof and bounded scope: docs/CONTINUOUS_SOURCE_FAMILY.md.
-- No observation is seeded and no source/runtime switch is changed here.

create or replace function ingest.source_family_product_name_v1(p_product text)
returns text language sql stable security invoker set search_path=pg_catalog as $$
  select case p_product when 'm2' then 'インフェルノX' when 'm3' then 'ムニキスゼロ'
    when 'sv8' then '超電ブレイカー' end;
$$;

-- Historical publication is independent of access-review expiry and recent
-- verification. Remove only the old evidence-age limit. Preserve original date
-- identity, nonfuture timestamps, 48-hour verification, tombstones and gates.
do $historical$
declare definition text; old_predicate text; replacement text; target regprocedure;
begin
  for target,old_predicate,replacement in select * from (values
    ('ingest.finalize_source_family_v1(uuid,text,bigint)'::regprocedure,
     'and published>clock_timestamp()-interval ''365 days'' and published<=clock_timestamp()',
     'and published<=clock_timestamp()'),
    ('ingest.source_family_public_rows_v1()'::regprocedure,
     'and c.state=''admitted'' and a.published_at>statement_timestamp()-interval ''365 days''',
     'and c.state=''admitted''')
  ) patches(function_oid,old_text,new_text) loop
    select pg_get_functiondef(target) into definition;
    if (length(definition)-length(replace(definition,old_predicate,'')))/length(old_predicate)<>1 then
      raise exception using errcode='55000',message='historical family predicate drift';
    end if;
    execute replace(definition,old_predicate,replacement);
  end loop;
end;
$historical$;

-- One owner-triggered, finite initial catch-up. The normal hourly producer is
-- unchanged. These are at most three collection cycles, not asserted facts or
-- URL-bearing job payloads: the existing begin gate chooses each due event.
-- Durable dedupe keys survive job completion; calling again cannot add cycles.
create function ingest.enqueue_pokesup_sv8_backfill_v1()
returns setof ingest.jobs
language plpgsql security invoker set search_path=pg_catalog as $$
declare target text; round_number integer:=0; key text;
begin
  if not ingest.source_family_access_v1() then return; end if;
  if ingest.source_family_product_name_v1('sv8') is distinct from '超電ブレイカー' then
    raise exception using errcode='55000',message='reviewed SV8 mapping unavailable';
  end if;
  perform pg_advisory_xact_lock(718180001);
  foreach target in array array[
    'https://pokesup.com/blog/unboxing-sv8/',
    'https://pokesup.com/blog/unboxing-sv8-2/',
    'https://pokesup.com/blog/unboxing-sv8-3/'
  ] loop
    round_number:=round_number+1;
    key:='source-family-backfill:pokesup-sv8-v1:'||round_number;
    if exists(select 1 from ingest.source_family_candidates c where c.url=target
        and c.state in ('pending_family','pending_evidence','quarantined')
        and not exists(select 1 from ingest.source_family_admissions a where a.url=c.url)
        and not exists(select 1 from ingest.source_family_tombstones t
          where t.url_sha256=encode(extensions.digest(c.url,'sha256'),'hex')))
      and not exists(select 1 from ingest.jobs j where j.job_type='source.family.cycle'
        and j.dedupe_key=key) then
      return query insert into ingest.jobs(job_type,payload,priority,dedupe_key,available_at,max_attempts,is_demo)
        values('source.family.cycle','{"family":"pokesup-enumerated"}',12,key,
          clock_timestamp()+(round_number-1)*interval '5 minutes',1,false) returning *;
    end if;
  end loop;
end;
$$;
alter function ingest.enqueue_pokesup_sv8_backfill_v1() owner to postgres;
revoke all on function ingest.enqueue_pokesup_sv8_backfill_v1()
  from public,anon,authenticated,service_role;
comment on function ingest.enqueue_pokesup_sv8_backfill_v1() is
  'Owner-only bounded initial SV8 catch-up: at most three idempotent cycles through existing request, lease and admission gates; no direct observations or source enablement.';

commit;
