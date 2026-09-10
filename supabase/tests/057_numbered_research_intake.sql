create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();

create function pg_temp.manifest(p_url text,p_conflicting boolean default false)
returns jsonb language sql as $$
  select jsonb_build_object('schema_version','research-intake-v1','snapshot_sha256',repeat('a',64),
    'references',jsonb_build_array(jsonb_build_object('url',p_url,
      'report_group_sha256',repeat('b',64),'conflicting',p_conflicting)));
$$;
-- Deterministic test-only expiry policy; owner activation still applies.
create or replace function ingest.numbered_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.numbered_family_control where enabled and policy_version='kozaru-numbered-v1');
$$;
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/test-one'))->>'status','paused','intake pause preserved');
select is((select count(*)::integer from ingest.numbered_family_candidates),0,'paused intake creates no candidate');
update ingest.research_intake_control set enabled=true;
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/test-one'))->>'family_queued','0','publisher pause preserved');
update ingest.numbered_family_control set enabled=true;
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/test-one'))->>'family_queued','1','search reference enters publisher queue automatically');
select is((select state from ingest.numbered_family_candidates where url='https://www.kozaru02.com/entry/test-one'),'pending','reference is pending evidence, not admitted');
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/test-one'))->>'family_queued','0','manifest replay is idempotent');
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/conflict',true))->>'family_queued','0','conflicting reference not acquired');
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/conflict'))->>'family_queued','0','conflict cannot be erased by replay');
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/entry/test-one'))->>'family_queued','0','other publishers remain research only');
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/privacy'))->>'family_queued','0','non-article routes not acquired');
update ingest.numbered_family_candidates set state='retracted' where url='https://www.kozaru02.com/entry/test-one';
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/test-one'))->>'family_queued','0','retraction is permanent across rediscovery');
select is((select state from ingest.numbered_family_candidates where url='https://www.kozaru02.com/entry/test-one'),'retracted','retracted state unchanged');
set local role service_role;
select is(ingest.import_research_intake_v1(jsonb_build_object('schema_version','research-intake-v1','snapshot_sha256',repeat('a',64),
  'references',jsonb_build_array(jsonb_build_object('url','https://www.kozaru02.com/entry/worker',
    'report_group_sha256',repeat('b',64),'conflicting',false))))->>'family_queued','1','actual worker can use unchanged importer');
reset role;
select is((select count(*)::integer from ingest.numbered_family_admissions),0,'references alone publish no packs');
select is(public.get_public_study_coverage_v4()->'unknownLocation','null'::jsonb,'public totals unchanged until evidence is admitted');

insert into ingest.numbered_family_candidates(url)
select 'https://www.kozaru02.com/entry/capacity-'||n
from generate_series(1,10000-(select count(*)::integer from ingest.numbered_family_candidates))n;
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://www.kozaru02.com/entry/overflow'))->>'family_queued','0','full acquisition queue does not overflow');
select is((select count(*)::integer from ingest.numbered_family_candidates),10000,'shared feed capacity respected');
select ok(exists(select 1 from ingest.research_intake_references where url='https://www.kozaru02.com/entry/overflow'),'unfetched reference remains available for later import');
select * from finish();
rollback;
