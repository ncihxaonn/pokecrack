begin;

-- Requeue only the three candidates inserted by global-volume run
-- 34673922030. This is intentionally an exact, one-run window: future
-- candidates remain reported after a failed optional check through the
-- worker's retry disposition, while unrelated historical rejections stay
-- untouched.
update ingest.global_volume_candidates
set state = 'reported', attempts = 0, locked_by = null, locked_until = null
where state = 'rejected'
  and first_seen_at >= timestamptz '2026-09-12 04:47:23+00'
  and first_seen_at < timestamptz '2026-09-12 04:48:30+00'
  and last_error_code in (
    'robots_denied', 'robots_unavailable', 'source_challenged',
    'source_http_status', 'source_redirected', 'source_not_html',
    'source_too_large', 'source_invalid_utf8', 'page_scope_not_found',
    'pack_count_not_found', 'source_temporarily_unavailable'
  )
  and evidence_sha256 is null;

commit;
