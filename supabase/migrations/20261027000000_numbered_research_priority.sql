begin;

-- Research references are relevance hints, not evidence or access approvals.
-- Process due research-linked articles ahead of the publisher's general feed;
-- retain the same lease, freshness, retraction and request-rate boundaries.
do $migration$
declare
  definition text;
  anchor text := 'order by n.checked_at nulls first,n.url limit 1 for update skip locked;';
  replacement text := $priority$order by exists(
        select 1 from ingest.research_intake_references r
        where r.url=n.url and not r.conflicting
      ) desc,n.checked_at nulls first,n.url limit 1 for update of n skip locked;$priority$;
begin
  definition := pg_get_functiondef('ingest.begin_numbered_family_v1(uuid,text,bigint)'::regprocedure);
  if (length(definition)-length(replace(definition,anchor,'')))/length(anchor)<>1 then
    raise exception 'numbered acquisition priority boundary changed';
  end if;
  execute replace(definition,anchor,replacement);
end;
$migration$;

commit;
