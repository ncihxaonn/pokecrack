#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Immutable official PostgreSQL 17.6 multi-platform image. The workflow copies
# this wrapper to private files named `psql` and `pg_dump`; invocation by any
# other name is rejected.
POSTGRES_IMAGE='postgres:17.6-bookworm@sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3'
SUPABASE_ROOT_CERT_SHA256='700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7'
CONTAINER_ROOT_CERT='/run/supabase-prod-ca-2021.crt'
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "$0")" && pwd -P)
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

network_mode=${BACKUP_POSTGRES_NETWORK_MODE:-bridge}
case "$network_mode" in
  bridge | host) ;;
  *)
    printf 'PostgreSQL client wrapper: unsupported network mode\n' >&2
    exit 2
    ;;
esac

# Host filesystem paths in libpq TLS options cannot be interpreted safely
# inside this read-only container. The only exception is the reviewed public
# Supabase root CA, mounted at one fixed in-container path after hash checking.
for variable in PGSSLCERT PGSSLCRL PGSSLCRLDIR PGSSLKEY; do
  if [[ ${!variable+x} == x ]]; then
    printf 'PostgreSQL client wrapper: file-based TLS option %s is unsupported in container mode\n' "$variable" >&2
    exit 2
  fi
done
certificate_mount=()
if [[ ${PGSSLROOTCERT+x} == x && $PGSSLROOTCERT != system ]]; then
  if [[ $PGSSLROOTCERT != "$CONTAINER_ROOT_CERT" ]]; then
    printf 'PostgreSQL client wrapper: unreviewed PGSSLROOTCERT is unsupported in container mode\n' >&2
    exit 2
  fi
  certificate_path="$SCRIPT_DIR/supabase-prod-ca-2021.crt"
  if [[ ! -f $certificate_path || -L $certificate_path ]]; then
    printf 'PostgreSQL client wrapper: reviewed Supabase root certificate is unavailable\n' >&2
    exit 2
  fi
  command -v sha256sum >/dev/null 2>&1 || {
    printf 'PostgreSQL client wrapper: sha256sum is unavailable\n' >&2
    exit 127
  }
  certificate_digest=$(sha256sum "$certificate_path")
  certificate_digest=${certificate_digest%% *}
  if [[ $certificate_digest != "$SUPABASE_ROOT_CERT_SHA256" ]]; then
    printf 'PostgreSQL client wrapper: reviewed Supabase root certificate digest mismatch\n' >&2
    exit 2
  fi
  certificate_mount+=(
    --mount
    "type=bind,src=$certificate_path,dst=$CONTAINER_ROOT_CERT,readonly"
  )
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
  "--network=$network_mode" \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777 \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp \
  "${docker_environment[@]}" \
  "${certificate_mount[@]}" \
  --entrypoint "$client" \
  "$POSTGRES_IMAGE" \
  "$@"
