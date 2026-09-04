#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Immutable official PostgreSQL 17.6 multi-platform image. The workflow copies
# this wrapper to private files named `psql` and `pg_dump`; invocation by any
# other name is rejected.
POSTGRES_IMAGE='postgres:17.6-bookworm@sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3'
client=${0##*/}
case "$client" in
  psql | pg_dump) ;;
  *)
    printf 'PostgreSQL client wrapper: unsupported invocation\n' >&2
    exit 2
    ;;
esac

command -v docker >/dev/null 2>&1 || {
  printf 'PostgreSQL client wrapper: docker is unavailable\n' >&2
  exit 127
}

# Host filesystem paths in libpq TLS options cannot be interpreted safely
# inside this read-only container. Fail explicitly instead of silently reading
# a different in-image path. Ordinary sslmode=require/verify-* remains valid.
for variable in PGSSLCERT PGSSLCRL PGSSLCRLDIR PGSSLKEY; do
  if [[ ${!variable+x} == x ]]; then
    printf 'PostgreSQL client wrapper: file-based TLS option %s is unsupported in container mode\n' "$variable" >&2
    exit 2
  fi
done
if [[ ${PGSSLROOTCERT+x} == x && $PGSSLROOTCERT != system ]]; then
  printf 'PostgreSQL client wrapper: file-based TLS option PGSSLROOTCERT is unsupported in container mode\n' >&2
  exit 2
fi

docker_environment=()
for variable in \
  PGAPPNAME \
  PGCHANNELBINDING \
  PGCONNECT_TIMEOUT \
  PGDATABASE \
  PGGSSENCMODE \
  PGHOST \
  PGOPTIONS \
  PGPASSWORD \
  PGPORT \
  PGREQUIREAUTH \
  PGSSLMODE \
  PGSSLNEGOTIATION \
  PGSSLROOTCERT \
  PGTARGETSESSIONATTRS \
  PGUSER
do
  if [[ ${!variable+x} == x ]]; then
    docker_environment+=(--env "$variable")
  fi
done

exec docker run \
  --rm \
  --interactive \
  --pull=missing \
  --network=bridge \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777 \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp \
  "${docker_environment[@]}" \
  --entrypoint "$client" \
  "$POSTGRES_IMAGE" \
  "$@"
