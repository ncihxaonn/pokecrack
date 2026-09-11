#!/usr/bin/env bash
# Process a small sequential batch of reported public volume candidates.
set -Eeuo pipefail
umask 077

script_dir=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repository_root=$(CDPATH='' cd -- "$script_dir/../.." && pwd -P)
[[ "$repository_root" == /home/codex/pokecrack ]] || {
  printf 'global-volume: unapproved_runtime_path\n' >&2
  exit 2
}
[[ $# -eq 1 && "${1:-}" =~ ^[0-9a-f]{40}$ ]] || {
  printf 'global-volume: expected_revision_required\n' >&2
  exit 2
}
expected_revision=$1
revision=$(git -C "$repository_root" rev-parse --verify HEAD)
[[ "$revision" == "$expected_revision" ]] || {
  printf 'global-volume: checkout_revision_mismatch\n' >&2
  exit 2
}
container_id=$(timeout --kill-after=5 15 docker ps -q \
  --filter label=com.docker.compose.project=pokecrack \
  --filter label=com.docker.compose.service=collector)
[[ "$container_id" =~ ^[0-9a-f]{12,64}$ ]] || {
  printf 'global-volume: collector_unavailable\n' >&2
  exit 2
}
image_id=$(timeout --kill-after=5 15 docker inspect --format '{{.Image}}' "$container_id")
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]
image_revision=$(timeout --kill-after=5 15 docker image inspect \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_id")
[[ "$image_revision" == "$revision" ]] || {
  printf 'global-volume: release_mismatch\n' >&2
  exit 2
}
exec timeout --foreground --kill-after=5 120 docker exec "$container_id" \
  pokecrack-worker process-global-volume --limit 8
