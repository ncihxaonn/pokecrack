#!/usr/bin/env bash

# Small compatibility layer for the Bash 3.2/BSD userland shipped by macOS and
# the Bash/GNU userland used by the deployment containers.

pokecrack_stat_mode() {
  local target=$1 value
  [[ $target != -* ]] || target="./$target"
  if value=$(stat -c '%a' "$target" 2>/dev/null); then
    :
  elif value=$(stat -f '%Lp' "$target" 2>/dev/null); then
    :
  else
    return 1
  fi
  printf '%s\n' "$value"
}

pokecrack_stat_uid() {
  local target=$1 value
  [[ $target != -* ]] || target="./$target"
  if value=$(stat -c '%u' "$target" 2>/dev/null); then
    :
  elif value=$(stat -f '%u' "$target" 2>/dev/null); then
    :
  else
    return 1
  fi
  printf '%s\n' "$value"
}

pokecrack_stat_size() {
  local target=$1 value
  [[ $target != -* ]] || target="./$target"
  if value=$(stat -c '%s' "$target" 2>/dev/null); then
    :
  elif value=$(stat -f '%z' "$target" 2>/dev/null); then
    :
  else
    return 1
  fi
  printf '%s\n' "$value"
}

pokecrack_lowercase() {
  LC_ALL=C tr '[:upper:]' '[:lower:]' <<EOF
$1
EOF
}

pokecrack_sha256_file() {
  local target=$1 output
  [[ $target != -* ]] || target="./$target"
  if command -v sha256sum >/dev/null 2>&1; then
    output=$(sha256sum "$target") || return
  elif command -v shasum >/dev/null 2>&1; then
    output=$(shasum -a 256 "$target") || return
  else
    return 127
  fi
  printf '%s\n' "${output%% *}"
}

pokecrack_atomic_replace() {
  python3 -c 'import os, sys; os.replace(sys.argv[1], sys.argv[2])' "$1" "$2"
}
