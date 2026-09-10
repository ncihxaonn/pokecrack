create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
select is(public.get_public_study_coverage_v4()->>'schemaVersion','4.0.0','versioned public contract');
select is(public.get_public_study_coverage_v4()->'unknownLocation','null'::jsonb,'disabled publisher exposes no aggregate');
select ok(has_function_privilege('anon','public.get_public_study_coverage_v4()','EXECUTE'),'browser can read projection');
select ok(not has_function_privilege('service_role','public.get_public_study_coverage_v4()','EXECUTE'),'worker does not gain projection permission');
-- Deterministic fixture policy clock, rolled back with this test. Production
-- expiry is not extended and no real publisher records are inserted.
create or replace function ingest.numbered_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.numbered_family_control where enabled and policy_version='kozaru-numbered-v1');
$$;
update ingest.numbered_family_control set enabled=true;
insert into ingest.numbered_family_candidates(url,state)
select 'https://www.kozaru02.com/entry/synthetic-'||n,'admitted' from generate_series(1,150)n;
insert into ingest.numbered_family_admissions
select c.url,'kozaru-numbered-v1',now()-interval '1 day',now(),10,
  repeat('a',64),array_fill(repeat('b',64),array[10])
from ingest.numbered_family_candidates c where c.url like '%/synthetic-%';
create temp table baseline as select public.get_public_study_coverage_v3() value;
create temp table projected as select public.get_public_study_coverage_v4() value;
select is((select value#>>'{unknownLocation,packsObserved}' from projected),'1500','all 150 articles count, beyond former 100-source cap');
select is((select value#>>'{unknownLocation,openings}' from projected),'150','one cohort per admitted article');
select is((select value#>>'{unknownLocation,independentSources}' from projected),'1','articles are not independent publishers');
select is((select value->'countries' from projected),(select value->'countries' from baseline),'no country is fabricated');
select is((select value->'sets' from projected),(select value->'sets' from baseline),'unknown product mapping does not fabricate a set');
select is((select jsonb_array_length(value->'sources') from projected),
  (select jsonb_array_length(value->'sources')+1 from baseline),'constant-size publisher source entry');
select is((select s#>>'{coverage,countriesObserved}' from projected,jsonb_array_elements(value->'sources')s
  where s->>'id'='kozaru_numbered_openings'),'0','publisher has no known opening countries');
select ok((select not (value::text ~ 'synthetic-|resource_sha256|evidence_sha256') from projected),'no private record identities');
select is((select array_agg(k order by k) from projected,jsonb_object_keys(value->'unknownLocation')k),
  array['independentSources','openings','packsObserved','updatedAt']::text[],'unknown aggregate has only count and freshness fields');
select is((select array_agg(k order by k) from projected,jsonb_array_elements(value->'sources')s,
  jsonb_object_keys(s->'coverage')k where s->>'id'='kozaru_numbered_openings'),
  array['completeOpenings','countriesObserved','packsObserved']::text[],'publisher coverage has no numerator or rate');
set local role anon;
select is(public.get_public_study_coverage_v4()#>>'{unknownLocation,packsObserved}','1500','actual anonymous execution returns aggregates');
reset role;
update ingest.numbered_family_candidates set state='retracted' where url like '%/synthetic-1';
select is(public.get_public_study_coverage_v4()#>>'{unknownLocation,packsObserved}','1490','retraction removes public count');
update ingest.numbered_family_candidates set state='duplicate' where url like '%/synthetic-2';
select is(public.get_public_study_coverage_v4()#>>'{unknownLocation,packsObserved}','1480','duplicate state is excluded');
update ingest.numbered_family_admissions set verified_at=now()-interval '49 hours' where url like '%/synthetic-3';
select is(public.get_public_study_coverage_v4()#>>'{unknownLocation,packsObserved}','1470','stale verification is excluded');
update ingest.numbered_family_admissions set published_at=now()+interval '1 day' where url like '%/synthetic-4';
select is(public.get_public_study_coverage_v4()#>>'{unknownLocation,packsObserved}','1460','future publications are excluded');
update ingest.numbered_family_control set enabled=false;
select is(public.get_public_study_coverage_v4()->'unknownLocation','null'::jsonb,'revocation removes projection');
select is(public.get_public_study_coverage_v4()->'sources',(select value->'sources' from baseline),'revocation removes publisher entry');
select * from finish();
rollback;
