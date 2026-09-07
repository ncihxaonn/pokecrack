# Remote release execution

The manual `backup-production-remote.yml` workflow supports an owner-managed,
single-job Linux release container with IPv6 connectivity. It is separate from
CI: never run the CI suite on the production VPS. The container must have no
production filesystem mounts, Docker socket, privileged mode, or published
ports. Use the immutable PostgreSQL image and checksummed GitHub runner in
`deploy/Dockerfile.release-runner`. The workflow derives a unique label and
runner name from its immutable GitHub run ID and attempt; callers cannot select
another runner. Before any secret-bearing step, it verifies the baked contract,
non-root UID, dropped capabilities, resource limits, and absence of production
mounts or Docker sockets. Destroy the container and confirm runner deregistration
after the one authorized main-branch job.

The protected Production environment supplies the temporary backup token and
encryption passphrase. Only the reviewed application dump is exported, encrypted,
and restored into a disposable PostgreSQL instance listening solely on a private
Unix socket. Only ciphertext, its checksum, and a non-secret restore report are
uploaded to the seven-day GitHub artifact. No application credentials are copied
from the host into the release container. Any failed backup step removes the
entire temporary run directory, and the always-run finalizer removes encrypted
staging data after the upload/identity steps.

`release-ci-evidence.yml` runs the full canonical seven-stage CI suite on a fresh
GitHub-hosted Linux runner with no production environment or credentials. It
retains the exact-SHA manifest and logs for release preflight. Database migration
continues through the existing protected workflow. VPS deployment uses the
reviewed exact-SHA deployment script, with the same target and health gates,
through the authorized operator SSH connection if hosted runner ingress fails.
