create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()+interval '1 day'$$;
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),0,'disabled catch-up stays closed');
update ingest.source_family_control set enabled=true;
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),0,'no candidate is invented');
insert into ingest.source_family_candidates(url,state,reason)
select 'https://pokesup.com/blog/'||slug||'/','pending_family','pending_family'
from unnest(array['unboxing-sv11b','unboxing-sv11w','unboxing-sv2a','unboxing-sv8a','unboxing-sv9','unboxing-sv9-2','unboxing-sv9a','unboxing-m2'])slug;
update ingest.source_family_candidates set checked_at=clock_timestamp() where url like '%/unboxing-sv9a/';
create temp table queued as select id,dedupe_key from ingest.enqueue_pokesup_variable_layout_backfill_v1();
select is((select count(*)::integer from queued),7,'bounded seven candidate jobs');
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),0,'same-day trigger is idempotent');
select ok((select available_at>now()+interval '23 hours' from ingest.jobs where dedupe_key like '%:unboxing-sv9a:%'),'recently checked candidate keeps its recheck interval');
select is((select count(*)::integer from ingest.source_family_admissions),0,'enqueue does not admit packs');
-- Other due candidates and an overdue sitemap cannot divert a targeted job.
update ingest.source_family_clock set discovered_at=null;
update ingest.jobs set status='running',locked_by='target-test',locked_at=now(),lock_expires_at=now()+interval '5 minutes',lease_generation=1
where id in(select id from queued where dedupe_key like '%:unboxing-sv11w:%');
select is((select target_url from queued q cross join lateral ingest.begin_source_family_v1(q.id,'target-test',1)
 where q.dedupe_key like '%:unboxing-sv11w:%'),'https://pokesup.com/blog/unboxing-sv11w/','target selection cannot be consumed by M2 or sitemap');
-- A prior-day active job suppresses a duplicate; a finished prior-day job
-- permits a later daily attempt, never another attempt in the same bucket.
update ingest.jobs set dedupe_key=regexp_replace(dedupe_key,':[0-9]{8}$',':20000101')
where dedupe_key like 'source-family-backfill:pokesup-variable-v1:%';
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),0,'active jobs suppress cross-day duplicates');
update ingest.jobs set status='failed',completed_at=clock_timestamp(),locked_by=null,locked_at=null,lock_expires_at=null
where dedupe_key like 'source-family-backfill:pokesup-variable-v1:%';
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),7,'finished prior-day jobs do not permanently suppress correction');
select is((select count(*)::integer from ingest.enqueue_pokesup_variable_layout_backfill_v1()),0,'replacement remains bounded in its day');
select * from finish();
rollback;
