begin;

-- Supabase CLI 2.116.0 generated 20260910072417 on the isolated MAM host.
-- Renumbered after the applied 20261022000000 ledger entry. Dates order
-- migrations; they do not schedule deployment. Source proof is recorded in
-- docs/SOURCE_FAMILY_VARIABLE_LAYOUTS.md. No observations or flags are seeded.
create or replace function ingest.source_family_product_name_v1(p_product text)
returns text language sql stable security invoker set search_path=pg_catalog as $$
  select case p_product when 'm2' then 'インフェルノX' when 'm3' then 'ムニキスゼロ'
    when 'sv8' then '超電ブレイカー' when 'sv11b' then 'ブラックボルト'
    when 'sv11w' then 'ホワイトフレア' when 'sv2a' then 'ポケモンカード151'
    when 'sv8a' then 'テラスタルフェスex' when 'sv9' then 'バトルパートナーズ'
    when 'sv9a' then '熱風のアリーナ' end;
$$;

create function ingest.source_family_pack_count_v1(p_product text)
returns integer language sql immutable security invoker set search_path=pg_catalog as $$
  select case when p_product in ('m2','m3','sv8','sv9','sv9a') then 30
    when p_product in ('sv11b','sv11w','sv2a') then 20 when p_product='sv8a' then 10 end;
$$;

create function ingest.source_family_expected_labels_v1(p_product text)
returns jsonb language sql immutable security invoker set search_path=pg_catalog as $$
  select case when p_product='sv8a' then
    (select jsonb_agg(n||'パック' order by n) from generate_series(1,10)n)
  else (select jsonb_agg(side||n||'パック' order by ord,n)
    from (values('左',1),('右',2)) s(side,ord)
    cross join generate_series(1,ingest.source_family_pack_count_v1(p_product)/2)n) end;
$$;

-- These positions identify illustrations, NOT packs. The SV9a source explicitly
-- enumerates consecutive three-pack ranges in each of ten captions; its labels
-- normalize to thirty distinct positions while the resource count stays ten.
create function ingest.source_family_resource_paths_v1(p_product text,p_slug text,p_width integer)
returns text[] language sql immutable security invoker set search_path=pg_catalog as $$
  select case when p_width not in (1,2) or p_width is null
    or ingest.source_family_pack_count_v1(p_product) is null
    or p_slug is null or p_slug !~ ('^unboxing-'||p_product||'(-([2-9]|[1-9][0-9]))?$') then null
  when p_product='sv8a' then (select array_agg('/assets/img/blog/'||p_slug||'/pack_'||
    (case when p_width=1 then n::text else lpad(n::text,2,'0') end)||'.jpg' order by n)
    from generate_series(1,10)n)
  else (select array_agg('/assets/img/blog/'||p_slug||'/pack_'||side||'_'||
    (case when p_width=1 then n::text else lpad(n::text,2,'0') end)||'.jpg' order by ord,n)
    from (values('l',1),('r',2))s(side,ord) cross join generate_series(1,
      case when p_product='sv9a' then 5 else ingest.source_family_pack_count_v1(p_product)/2 end)n) end;
$$;

alter table ingest.source_family_admissions drop constraint source_family_admissions_pack_count_check;
alter table ingest.source_family_admissions add constraint source_family_admissions_pack_count_check
  check (pack_count in (10,20,30));

-- Narrow, drift-checked changes preserve the existing lease, access, date,
-- dedupe, tombstone and finalization logic, including prior historical fixes.
do $layouts$
declare target regprocedure; old_text text; new_text text; definition text;
begin
  for target,old_text,new_text in select * from (values
    ('ingest.begin_source_family_v1(uuid,text,bigint)'::regprocedure,
     $old$if (select discovered_at is null or discovered_at < clock_timestamp()-interval '1 day'
      from ingest.source_family_clock) then$old$,
     $new$if j.dedupe_key like 'source-family-backfill:pokesup-variable-v1:%' then
    -- The owner-created key selects one reviewed candidate, never arbitrary
    -- worker input. It cannot redirect a catch-up to an unrelated due report.
    if j.dedupe_key !~ '^source-family-backfill:pokesup-variable-v1:unboxing-(sv11b|sv11w|sv2a|sv8a|sv9|sv9-2|sv9a):[0-9]{8}$' then return; end if;
    select c.url into target from ingest.source_family_candidates c
      where c.url='https://pokesup.com/blog/'||split_part(j.dedupe_key,':',3)||'/'
      and c.state in ('pending_family','pending_evidence','quarantined')
      and (c.checked_at is null or c.checked_at < clock_timestamp()-interval '1 day')
      and not exists(select 1 from ingest.source_family_admissions a where a.url=c.url)
      and not exists(select 1 from ingest.source_family_tombstones t
        where t.url_sha256=encode(extensions.digest(c.url,'sha256'),'hex'))
      for update skip locked;
    if target is null then return; end if;
  elsif (select discovered_at is null or discovered_at < clock_timestamp()-interval '1 day'
      from ingest.source_family_clock) then$new$),
    ('ingest.stage_source_family_v1(uuid,text,bigint,jsonb)'::regprocedure,
     $old$select jsonb_agg(side||n||'パック' order by ord,n) into expected
      from (values('左',1),('右',2)) s(side,ord) cross join generate_series(1,15) n;$old$,
     $new$expected:=ingest.source_family_expected_labels_v1(e->>'product');$new$),
    ('ingest.stage_source_family_v1(uuid,text,bigint,jsonb)'::regprocedure,
     $old$if r.requests<>3 or e->>'url' is distinct from r.target_url$old$,
     $new$if expected is null or r.requests<>3 or e->>'url' is distinct from r.target_url$new$),
    ('ingest.stage_source_family_v1(uuid,text,bigint,jsonb)'::regprocedure,
     $old$if jsonb_array_length(e->'resource_sha256s')<>30 then$old$,
     $new$if jsonb_array_length(e->'resource_sha256s') is distinct from array_length(
       ingest.source_family_resource_paths_v1(e->>'product',split_part(r.target_url,'/',5),1),1) then$new$),
    ('ingest.stage_source_family_v1(uuid,text,bigint,jsonb)'::regprocedure,
     $old$if (select count(distinct x) from jsonb_array_elements_text(e->'resource_sha256s')x)<>30$old$,
     $new$if (select count(distinct x) from jsonb_array_elements_text(e->'resource_sha256s')x)
       is distinct from array_length(ingest.source_family_resource_paths_v1(
         e->>'product',split_part(r.target_url,'/',5),1),1)$new$),
    ('ingest.stage_source_family_v1(uuid,text,bigint,jsonb)'::regprocedure,
     $old$select array_agg('/assets/img/blog/'||split_part(r.target_url,'/',5)||'/pack_'||side||'_'||
        (case when width=1 then n::text else lpad(n::text,2,'0') end)||'.jpg' order by ord,n)
        into paths from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n;$old$,
     $new$paths:=ingest.source_family_resource_paths_v1(e->>'product',split_part(r.target_url,'/',5),width);$new$),
    ('ingest.finalize_source_family_v1(uuid,text,bigint)'::regprocedure,
     $old$select jsonb_agg(side || n || 'パック' order by ord,n) into expected
        from (values('左',1),('右',2)) s(side,ord) cross join generate_series(1,15) n;$old$,
     $new$expected:=ingest.source_family_expected_labels_v1(e->>'product');$new$),
    ('ingest.source_family_public_rows_v1()'::regprocedure,
     $old$and ingest.source_family_product_name_v1(a.product) is not null$old$,
     $new$and ingest.source_family_product_name_v1(a.product) is not null
    and a.pack_count=ingest.source_family_pack_count_v1(a.product)$new$)
  ) patches(function_oid,old_value,new_value) loop
    select pg_get_functiondef(target) into definition;
    if (length(definition)-length(replace(definition,old_text,'')))/length(old_text)<>1 then
      raise exception using errcode='55000',message='source-family layout boundary drift';
    end if;
    execute replace(definition,old_text,new_text);
  end loop;
end;
$layouts$;

-- Bounded owner-triggered catch-up; no URL/count-bearing worker payload, direct
-- admissions, gate resets, flag changes or retry bypass. Normal hourly discovery
-- and repeat verification continue through the same path after this backfill.
create function ingest.enqueue_pokesup_variable_layout_backfill_v1()
returns setof ingest.jobs language plpgsql security invoker set search_path=pg_catalog as $$
declare slug text; target text; round_number integer:=0; key text; due timestamptz;
begin
  if not ingest.source_family_access_v1() then return; end if;
  perform pg_advisory_xact_lock(718180001);
  foreach slug in array array['unboxing-sv11b','unboxing-sv11w','unboxing-sv2a',
    'unboxing-sv8a','unboxing-sv9','unboxing-sv9-2','unboxing-sv9a'] loop
    round_number:=round_number+1;
    target:='https://pokesup.com/blog/'||slug||'/';
    key:='source-family-backfill:pokesup-variable-v1:'||slug||':'||to_char(clock_timestamp() at time zone 'UTC','YYYYMMDD');
    if exists(select 1 from ingest.source_family_candidates c where c.url=target
      and c.state in ('pending_family','pending_evidence','quarantined')
      and ingest.source_family_pack_count_v1(substring(c.url from '/unboxing-([a-z][a-z0-9]{0,15})')) is not null
      and not exists(select 1 from ingest.source_family_admissions a where a.url=c.url)
      and not exists(select 1 from ingest.source_family_tombstones t
        where t.url_sha256=encode(extensions.digest(c.url,'sha256'),'hex')))
      and not exists(select 1 from ingest.jobs j where j.job_type='source.family.cycle'
        and (j.dedupe_key=key or (j.dedupe_key like 'source-family-backfill:pokesup-variable-v1:'||slug||':%'
          and j.status in ('pending','running')))) then
      select greatest(clock_timestamp()+(round_number-1)*interval '5 minutes',
        c.checked_at+interval '1 day 1 second') into due
        from ingest.source_family_candidates c where c.url=target;
      return query insert into ingest.jobs(job_type,payload,priority,dedupe_key,available_at,max_attempts,is_demo)
        values('source.family.cycle','{"family":"pokesup-enumerated"}',12,key,
          due,1,false) returning *;
    end if;
  end loop;
end;
$$;

do $permissions$
declare f regprocedure;
begin
  for f in select unnest(array[
    'ingest.source_family_pack_count_v1(text)'::regprocedure,
    'ingest.source_family_expected_labels_v1(text)'::regprocedure,
    'ingest.source_family_resource_paths_v1(text,text,integer)'::regprocedure,
    'ingest.enqueue_pokesup_variable_layout_backfill_v1()'::regprocedure
  ]) loop
    execute format('alter function %s owner to postgres',f);
    execute format('revoke all on function %s from public,anon,authenticated,service_role',f);
  end loop;
end;
$permissions$;

commit;
