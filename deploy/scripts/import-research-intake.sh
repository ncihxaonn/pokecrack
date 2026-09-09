#!/usr/bin/env bash
# Forward a bounded private manifest to the reviewed, already-running collector.
# No database secret is read by this script and no application code is deployed.
set -Eeuo pipefail
umask 077

script_dir=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repository_root=$(CDPATH='' cd -- "$script_dir/../.." && pwd -P)
[[ "$repository_root" == /home/codex/pokecrack ]] || {
  printf 'research-intake: unapproved_runtime_path\n' >&2
  exit 2
}
revision=$(git -C "$repository_root" rev-parse --verify HEAD)
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
container_id=$(timeout --kill-after=5 15 docker ps -q \
  --filter label=com.docker.compose.project=pokecrack \
  --filter label=com.docker.compose.service=collector)
[[ "$container_id" =~ ^[0-9a-f]{12,64}$ ]] || {
  printf 'research-intake: collector_unavailable\n' >&2
  exit 2
}
image_id=$(timeout --kill-after=5 15 docker inspect --format '{{.Image}}' "$container_id")
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]]
image_revision=$(timeout --kill-after=5 15 docker image inspect \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_id")
[[ "$image_revision" == "$revision" ]] || {
  printf 'research-intake: release_mismatch\n' >&2
  exit 2
}
exec timeout --foreground --kill-after=5 90 docker exec -i "$container_id" \
  pokecrack-worker intake-research
