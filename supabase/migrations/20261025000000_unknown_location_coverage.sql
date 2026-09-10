begin;

-- Publisher aggregation is separate from geographic buckets: publication
-- language, product market and author identity do not prove opening location.
-- Keep v3 unchanged for older web releases during the GitHub rollout.
create function public.get_public_study_coverage_v4()
returns jsonb language plpgsql stable security definer
set search_path=pg_catalog as $$
declare
  base jsonb := public.get_public_study_coverage_v3();
  packs bigint;
  openings bigint;
  first_publication date;
  last_verified timestamptz;
  unknown_location jsonb := null;
begin
  select coalesce(sum(a.pack_count),0),count(*),
    min((a.published_at at time zone 'UTC')::date),max(a.verified_at)
  into packs,openings,first_publication,last_verified
  from ingest.numbered_family_admissions a
  join ingest.numbered_family_candidates c using(url)
  where ingest.numbered_family_access_v1()
    and a.policy_version='kozaru-numbered-v1' and c.state='admitted'
    and a.published_at<=statement_timestamp()
    and a.verified_at<=statement_timestamp()
    and a.verified_at>statement_timestamp()-interval '48 hours'
    -- Fixed-contract admission must not also be counted in this lane.
    and not exists(select 1 from ingest.reviewed_public_study_contracts() f
      where f.canonical_url=a.url);

  if openings>0 then
    unknown_location := jsonb_build_object(
      'packsObserved',packs,'openings',openings,'independentSources',1,
      'updatedAt',last_verified);
    base := jsonb_set(base,'{period,start}',to_jsonb(least(
      (base#>>'{period,start}')::date,first_publication)));
    -- One publisher identity regardless of article count. No article URLs,
    -- resource hashes, author identities, raw evidence or synthetic country.
    base := jsonb_set(base,'{sources}',(base->'sources')||jsonb_build_array(
      jsonb_build_object(
        'id','kozaru_numbered_openings','name','Kozaru numbered openings',
        'kind','community','access','public','status','operational',
        'lastCollectedAt',last_verified,'url','https://www.kozaru02.com/',
        'note','Numbered pack observations; opening location is unknown. No hit-rate inference.',
        'coverage',jsonb_build_object('packsObserved',packs,'countriesObserved',0,
          'completeOpenings',openings))));
  end if;
  return base||jsonb_build_object('schemaVersion','4.0.0','unknownLocation',unknown_location);
end;
$$;
alter function public.get_public_study_coverage_v4() owner to postgres;
revoke all on function public.get_public_study_coverage_v4() from public,anon,authenticated,service_role;
grant execute on function public.get_public_study_coverage_v4() to anon,authenticated;
comment on function public.get_public_study_coverage_v4() is
  'Coverage with separately accounted unknown-location numbered openings; publisher aggregates only, no private evidence or invented geography/rates.';

commit;
