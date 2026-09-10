create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
select ok(not has_function_privilege('anon','ingest.enqueue_pokesup_sv8_backfill_v1()','EXECUTE'),'anonymous cannot trigger backfill');
select ok(not has_function_privilege('authenticated','ingest.enqueue_pokesup_sv8_backfill_v1()','EXECUTE'),'browser users cannot trigger backfill');
select ok(not has_function_privilege('service_role','ingest.enqueue_pokesup_sv8_backfill_v1()','EXECUTE'),'worker cannot create extra backfill cycles');
set local role service_role;
select throws_ok($$select ingest.enqueue_pokesup_sv8_backfill_v1()$$,'42501',null,'actual worker invocation denied');
reset role;

create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()+interval '1 day'$$;
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'disabled family cannot trigger collection');
update ingest.source_family_control set enabled=true;
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'missing candidates are not invented');
insert into ingest.source_family_candidates(url,state,reason) values
 ('https://pokesup.com/blog/unboxing-sv8-4/','pending_family','pending_family');
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'initial catch-up cannot expand to arbitrary numbered URLs');
insert into ingest.source_family_candidates(url,state,reason) values
 ('https://pokesup.com/blog/unboxing-sv8/','pending_family','pending_family'),
 ('https://pokesup.com/blog/unboxing-sv8-2/','pending_family','pending_family'),
 ('https://pokesup.com/blog/unboxing-sv8-3/','pending_family','pending_family');
update ingest.source_policies set enabled=false where source_key='public_study_pokesup_jp_30';
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'revoked source access cannot be overridden by owner catch-up');
update ingest.source_policies set enabled=true where source_key='public_study_pokesup_jp_30';
create temp table queued as select id from ingest.enqueue_pokesup_sv8_backfill_v1();
select is((select count(*)::integer from queued),3,'exactly three bounded cycles queued');
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'trigger is idempotent while jobs are pending');
select is((select count(*)::integer from ingest.jobs j join queued q using(id)
 where j.job_type='source.family.cycle' and j.payload='{"family":"pokesup-enumerated"}'::jsonb
 and not j.is_demo and j.max_attempts=1),3,'jobs use the existing typed, non-demo collection lane');
select ok((select max(available_at)-min(available_at) between interval '10 minutes' and interval '11 minutes'
 from ingest.jobs j join queued q using(id)),'initial cycles are spaced over ten minutes');
select is((select count(distinct dedupe_key)::integer from ingest.jobs j join queued q using(id)),3,'durable idempotency identity for each cycle');
select is((select count(*)::integer from ingest.source_family_admissions),0,'enqueue writes no observed packs');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'enqueue creates no public evidence');
update ingest.jobs j set status='completed',completed_at=clock_timestamp() from queued q where j.id=q.id;
select is((select count(*)::integer from ingest.enqueue_pokesup_sv8_backfill_v1()),0,'completed cycles cannot be silently recreated');
select is((select count(*)::integer from ingest.jobs where dedupe_key like 'source-family-backfill:pokesup-sv8-v1:%'),3,'backfill is permanently bounded to three jobs');
select * from finish();
rollback;
