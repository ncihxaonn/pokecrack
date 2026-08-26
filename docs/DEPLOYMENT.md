# Deployment

No external deployment was performed while implementing this repository. The steps below are an operator runbook; completion must be evidenced with account-specific IDs/URLs, exact SHA and health output.

> **Current release blocker:** the single-process live composition currently supports only the scheduler's cleanup schedule and the watchdog cleanup handler. Collector, AI-worker, and aggregator roles deliberately fail closed with exit code 78. Do not perform a live VPS deployment until their persistent PostgreSQL handlers and end-to-end data path are wired and integration-tested. The steps below are an account-owner runbook, not evidence that deployment occurred.

## 1. Account-bound prerequisites

The owner must create/approve: a private GitHub repository and deploy key; protected GitHub environments; Supabase Free project and DB password; Vercel Hobby project; VPS/user/Docker access; DNS; noVNC secret; API/provider keys; a reviewed OpenCLI CLI/Bridge artifact; and platform logins/2FA. Review source/platform terms, trademark/name and privacy obligations before live collection.

Keep `DATA_MODE=demo`, `AI_PROVIDER=fixture`, `OPENCLI_ENABLED=false`, public signup off and retailer domains disabled until each corresponding live dependency is proven.

## 2. Database

1. Create a dedicated Supabase project; record region/project reference privately.
2. Test all migrations and pgTAP locally in Docker-capable CI.
3. Take/verify a backup before production changes.
4. Run `.github/workflows/migrate-database.yml` manually against a protected environment. `confirm_sha` must equal `GITHUB_SHA`; supply the fresh backup reference. Before any remote push, the workflow reads the applied migration versions, audits only pending migrations, requires an exact reasoned fingerprint for every reviewed `DELETE`, rejects `DROP`/`TRUNCATE`, builds the schema locally, and rejects generated TypeScript drift. It previews and applies forward migrations only—no automatic destructive rollback/reset.
5. Create the first admin account manually; disable public signup; configure redirect/email settings deliberately.
6. Verify private-schema grants/RLS and query the intended public-safe API as anon. Never expose DB/service-role credentials to browser variables.

## 3. Web (Vercel)

Import the private repository and use `apps/web` as the project root. Pin the production branch and Node version. Set only `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_SUPABASE_URL` and the publishable key in browser-visible variables. Keep `ADMIN_EMAILS`, `ADMIN_CONTROL_RPC_ENABLED`, and `SUPABASE_SERVICE_ROLE_KEY` as Vercel server-only variables; never prefix the service-role key with `NEXT_PUBLIC_`, place it in the VPS environment, or enable controls before the Auth claim and email allowlist are verified. Start with `ADMIN_CONTROL_RPC_ENABLED=false` and demo mode, run the production build, verify the demo label/disclaimers and no secret in built assets, then switch to live only after the database public surface and service-role-only Admin RPC grants are verified. DNS/OAuth/email-provider setup is account-bound and was not done here.

## 4. VPS

Use a patched Linux host, dedicated non-root deploy user, SSH keys only, host firewall and Docker Engine/Compose. Clone the private repo to an absolute path; keep config/secrets outside it. Follow `deploy/README.md` to create bind directories (profile root mode `0700`, uid/gid `10001`), install the noVNC secret, configure `/etc/pokecrack/production.env`, and pin the Bridge.

Deploy an exact commit:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env
```

The GitHub deploy workflow uses the same script and verifies remote `HEAD == GITHUB_SHA`; it never uses `git pull`. Protect the `worker-production` environment and configure `VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_DEPLOY_PATH`, `VPS_ENV_FILE`, `VPS_SSH_PRIVATE_KEY` and pinned `VPS_KNOWN_HOSTS`.

## 5. Authenticated browser

Install only an explicit reviewed artifact, start the service, then use exactly:

```bash
ssh -L 6080:127.0.0.1:6080 VPS_USER@VPS_HOST
```

Complete login/CAPTCHA/2FA manually, run doctor/auth/read-only adapter checks, then close the tunnel. Never publish 6080 or map CDP/VNC/daemon ports.

## 6. Acceptance record

For a real release record: exact Git SHA; CI run; migration run and backup reference; Vercel deployment URL; Supabase project reference (not secret); VPS host identifier; six healthy services; loopback-only port check; fixture/live/disabled adapters; browser doctor/auth state; restore-drill date; and known warnings. A Compose render, migration file, or successful script write alone is not deployment evidence.
