# Security model

## Protected assets and threats

Highest-risk assets are DB/service-role/provider/SSH/noVNC credentials, persistent browser cookies/2FA sessions, private source payloads, AI prompts/output, backups and deploy authority. Threats include secret commit/logging, exposed browser control ports, malicious/untrusted content, dependency/artifact compromise, account/session theft, overbroad public grants, SSRF/source-policy bypass, prompt injection and destructive operator error.

## Controls

- Unknown sources/adapters are disabled; HTTPS, domain/route, size/rate/concurrency and retention are explicit.
- Browser inputs and AI output are untrusted data. They cannot issue shell/SQL/adapter commands; strict schemas and deterministic policy decide eligibility.
- Private schemas use default-deny grants/RLS. Browser bundles get publishable values only and public-safe DTOs/relations.
- Compose drops all capabilities, uses `no-new-privileges`, read-only roots, noexec tmpfs where practical, pids/CPU/RAM limits, health checks and no Docker socket.
- Services have outbound access through a non-published bridge; a second network is internal-only. Inbound host publication is only `127.0.0.1:6080`. CDP `9222`, VNC `5900`, daemon `19825` and DB are not mapped.
- Browser profile root is `0700`, owned by uid `10001`; extension volume is read-only. Profiles/cookies never enter Git, logs, DB or ordinary backups.
- Extension install requires explicit numeric version, HTTPS URL/template and SHA-256; rejects `latest`, validates safe archive/manifest and atomically activates. Current/previous releases remain rollbackable.
- Deploy requires a clean tree and exact SHA. GitHub environments/known-host pinning protect account-bound writes. Database migration is manual, reviewed and forward-only.
- CI scans secrets and rejects tracked profiles/raw data/evidence/backups/media; it uses demo/fixture and performs no live login or paid AI.

## Secret handling

Store production env/noVNC files outside Git at mode `0600`. Prefer scoped, separate credentials; rotate on staff/device/provider changes. Do not pass DB URLs in command arguments when avoidable, paste them into chat/issues, enable shell tracing, publish Compose expansion or upload logs/artifacts containing them. GitHub secrets are account-bound; pin the VPS host key rather than `ssh-keyscan` at deploy time.

The authorized-opening operator uses two additional mode-`0600` environment
values outside the repository: `AUTHORIZED_OPENING_SUBMITTER_DB_URL` and
`AUTHORIZED_OPENING_REVIEWER_DB_URL`. They must use the named NOINHERIT logins
and fixed `options=-c role=...` settings; the CLI never falls back to a
generic database URL or service-role key. Owner evidence-envelopes are also
mode `0600` regular files, are bounded to 16 KiB, rejected when social-derived
or URL-bearing, and are not persisted after the typed RPC call. Operator
output contains only safe IDs/state/revision (plus a safe retraction reason);
opaque references, raw evidence and connection details are never logged.

## Browser/account boundary

A logged-in account remains governed by platform terms and owner authorization. Login does not authorize broad collection/republishing. CAPTCHA/2FA is completed manually through `ssh -L 6080:127.0.0.1:6080 VPS_USER@VPS_HOST`; no bypass, proxy pool or credential sharing. Disable the adapter on challenge/denial and re-review.

## Backups and recovery

DB dumps are mode `0600`, validated, retention-bounded and contain private data. Encrypt before off-host transfer with owner-managed keys. Profile backup is off by default; if business continuity later requires it, use independently reviewed encryption/key custody and test revocation. Restore only into isolated access-controlled infrastructure and sanitize after drills.

## Known limits

Static artifacts do not prove host firewall, provider RLS, terms compliance, artifact authenticity beyond the supplied checksum, account security or deployment. Base images/package repositories still require update/digest policy. Real adversarial review, dependency/SBOM scanning, key rotation, restore tests and external configuration verification are owner tasks before live operation.
