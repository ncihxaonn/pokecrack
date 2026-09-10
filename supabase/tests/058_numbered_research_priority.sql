create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
-- Transaction-local deterministic policy; never extend production expiry.
create or replace function ingest.numbered_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.numbered_family_control where enabled and policy_version='kozaru-numbered-v1');
$$;
update ingest.numbered_family_control set enabled=true,discovered_at=now();
insert into ingest.numbered_family_candidates(url) values
  ('https://www.kozaru02.com/entry/a-general'),
  ('https://www.kozaru02.com/entry/b-conflicting'),
  ('https://www.kozaru02.com/entry/z-research');
insert into ingest.research_intake_references(url,report_group_sha256,snapshot_sha256,conflicting) values
  ('https://www.kozaru02.com/entry/b-conflicting',repeat('a',64),repeat('b',64),true),
  ('https://www.kozaru02.com/entry/z-research',repeat('c',64),repeat('d',64),false);
create function pg_temp.acquire() returns text language plpgsql as $$
declare j uuid; target text;
begin
  update ingest.numbered_family_control set active_until=now()-interval '1 minute';
  insert into ingest.jobs(job_type,payload,status,locked_by,locked_at,lock_expires_at,lease_generation,is_demo)
    values('source.family.cycle','{"family":"kozaru-numbered"}','running','priority-test',now(),now()+interval '5 minutes',1,false)
    returning id into j;
  select target_url into target from ingest.begin_numbered_family_v1(j,'priority-test',1);
  return target;
end;
$$;
select is(pg_temp.acquire(),'https://www.kozaru02.com/entry/z-research','relevant research precedes unrelated feed articles');
update ingest.numbered_family_candidates set checked_at=now() where url like '%/z-research';
select is(pg_temp.acquire(),'https://www.kozaru02.com/entry/a-general','fresh research does not starve unprocessed feed candidates');
update ingest.numbered_family_candidates set checked_at=null,state='retracted' where url like '%/z-research';
select is(pg_temp.acquire(),'https://www.kozaru02.com/entry/a-general','priority cannot revive a retracted cohort');
update ingest.numbered_family_candidates set state='duplicate' where url like '%/z-research';
select is(pg_temp.acquire(),'https://www.kozaru02.com/entry/a-general','duplicate research remains excluded');
update ingest.numbered_family_candidates set state='pending' where url like '%/z-research';
update ingest.research_intake_references set conflicting=true;
select is(pg_temp.acquire(),'https://www.kozaru02.com/entry/a-general','conflicting references gain no priority');
update ingest.numbered_family_control set discovered_at=null;
select is(pg_temp.acquire(),'https://www.kozaru02.com/feed','due feed discovery still runs before candidate processing');
update ingest.numbered_family_control set enabled=false;
select is(pg_temp.acquire(),null::text,'publisher pause still prevents acquisition');
select is((select count(*)::integer from ingest.numbered_family_admissions),0,'priority never creates an admission');
select * from finish();
rollback;
