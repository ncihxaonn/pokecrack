# Contributing

Pokecrack is currently a private, non-commercial experimental project.

## Branches

- `main` is production.
- Use `feat/*`, `fix/*`, or `chore/*` branches.
- Do not experiment directly on `main`.
- Vercel previews and CI must pass before merge.

## Commits

Use Conventional Commits, for example:

```text
feat(worker): add source policy validation
fix(web): fail closed when live data is unavailable
chore(db): add non-destructive index migration
```

## Required checks

Run the exact commands in `README.md` and `make verify` where the local environment supports Docker. Do not skip or weaken a failing test. If infrastructure is unavailable, report the command and blocker explicitly.

## Data and security

Never commit:

- `.env` or credentials
- browser profiles, cookies, local storage, or HAR files
- database backups
- real raw scrape payloads or evidence media
- third-party full videos
- administrator exports

Run:

```bash
python3 scripts/verify_repository.py .
```

Every external adapter requires an explicit allowlisted source policy. Do not add proxy rotation, CAPTCHA solving, access-control bypasses, stealth escalation, account farms, automated purchasing, payment, ads, or affiliate behavior.

## Database

All database changes are migrations. Destructive production migrations use the manual database workflow and need an explicit rollback/restore plan.
