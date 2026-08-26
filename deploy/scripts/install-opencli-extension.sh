#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 022

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PREPARE_HELPER="$SCRIPT_DIR/../lib/prepare_extension.py"
PORTABILITY_HELPER="$SCRIPT_DIR/../lib/shell_portability.sh"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"
DEFAULT_INSTALL_ROOT=${OPENCLI_EXTENSION_DIR:-/opt/pokecrack/opencli-extension}

die() {
  printf 'opencli-extension: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage:
  install-opencli-extension.sh install --version VERSION --sha256 SHA256 \
    (--url HTTPS_URL | --url-template HTTPS_TEMPLATE_WITH_{version}) \
    [--install-root ABSOLUTE_PATH]
  install-opencli-extension.sh rollback [--install-root ABSOLUTE_PATH]

The version and checksum are mandatory. Floating "latest" versions/URLs are rejected.
USAGE
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

validate_install_root() {
  local root=$1
  [[ $root == /* ]] || die "install root must be an absolute path"
  [[ ! -L $root ]] || die "install root must not be a symbolic link"
}

validate_version() {
  local value=$1 normalized
  normalized=$(pokecrack_lowercase "$value")
  [[ $value =~ ^[0-9]+([.][0-9]+){0,3}$ ]] || die "version must match Chromium's numeric extension version format"
  [[ $normalized != *latest* ]] || die "floating latest versions are forbidden"
}

validate_url() {
  local value=$1 authority normalized
  normalized=$(pokecrack_lowercase "$value")
  [[ $value == https://* ]] || die "artifact URL must use HTTPS"
  [[ $value != *[$'\r\n\t ']* ]] || die "artifact URL must not contain whitespace"
  [[ $normalized != *latest* ]] || die "floating latest URLs are forbidden"
  [[ $value != *'?'* && $value != *'#'* ]] || die "artifact URL must not contain a query or fragment"
  authority=${value#https://}
  authority=${authority%%/*}
  [[ -n $authority ]] || die "artifact URL must contain a host"
  [[ $authority != *@* ]] || die "artifact URLs containing credentials are forbidden"
}

validate_managed_link() {
  local root=$1 link_name=$2 target version
  [[ -L $root/$link_name ]] || return 1
  target=$(readlink "$root/$link_name")
  [[ $target =~ ^releases/([0-9]+([.][0-9]+){0,3})$ ]] || die "$link_name points outside the managed releases directory"
  version=${BASH_REMATCH[1]}
  [[ -d $root/$target && ! -L $root/$target ]] || die "$link_name points to a missing or invalid release"
  python3 "$PREPARE_HELPER" validate "$root/$target" "$version" >/dev/null
  printf '%s\n' "$target"
}

atomic_link() {
  local root=$1 name=$2 target=$3 temporary
  temporary="$root/.${name}.$$.${RANDOM}"
  [[ ! -e $temporary && ! -L $temporary ]] || die "temporary link collision"
  ln -s "$target" "$temporary"
  if ! pokecrack_atomic_replace "$temporary" "$root/$name"; then
    rm -f "$temporary"
    die "could not atomically activate $name"
  fi
}

install_release() {
  local version='' checksum='' url='' template='' install_root=$DEFAULT_INSTALL_ROOT
  while (($#)); do
    case $1 in
      --version) (($# >= 2)) || die "--version requires a value"; version=$2; shift 2 ;;
      --sha256) (($# >= 2)) || die "--sha256 requires a value"; checksum=$(pokecrack_lowercase "$2"); shift 2 ;;
      --url) (($# >= 2)) || die "--url requires a value"; url=$2; shift 2 ;;
      --url-template) (($# >= 2)) || die "--url-template requires a value"; template=$2; shift 2 ;;
      --install-root) (($# >= 2)) || die "--install-root requires a value"; install_root=$2; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown install argument: $1" ;;
    esac
  done

  [[ -n $version ]] || die "--version is required"
  [[ -n $checksum ]] || die "--sha256 is required"
  [[ $checksum =~ ^[0-9a-f]{64}$ ]] || die "--sha256 must be exactly 64 hexadecimal characters"
  [[ -z $url || -z $template ]] || die "use exactly one of --url or --url-template"
  [[ -n $url || -n $template ]] || die "one of --url or --url-template is required"
  validate_version "$version"
  if [[ -n $template ]]; then
    [[ $template == *'{version}'* ]] || die "URL template must contain {version}"
    url=${template//\{version\}/$version}
  fi
  validate_url "$url"
  validate_install_root "$install_root"
  require_command curl
  require_command python3
  require_command mktemp

  local artifact prepared release_root target actual_checksum current_target=''
  temporary=''
  staging=''
  temporary=$(mktemp -d "${TMPDIR:-/tmp}/opencli-extension.XXXXXXXX")
  cleanup_install() {
    local status=$?
    if [[ -n ${staging:-} && -d $staging && ! -L $staging ]]; then
      rm -rf "$staging"
    fi
    rm -rf "$temporary" || true
    return "$status"
  }
  trap cleanup_install EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM

  artifact="$temporary/artifact"
  prepared="$temporary/prepared"
  curl --fail --show-error --silent --location \
    --proto '=https' --proto-redir '=https' --tlsv1.2 \
    --max-filesize 33554432 --connect-timeout 15 --max-time 180 \
    --speed-limit 1024 --speed-time 30 \
    --output "$artifact" "$url"
  [[ -s $artifact ]] || die "downloaded artifact is empty"
  actual_checksum=$(pokecrack_sha256_file "$artifact") || die "required SHA-256 command not found or failed"
  [[ $actual_checksum == "$checksum" ]] || die "artifact checksum mismatch"
  python3 "$PREPARE_HELPER" prepare "$artifact" "$prepared" "$version" >/dev/null

  install -d -m 0755 "$install_root"
  [[ ! -L $install_root ]] || die "install root became a symbolic link"
  release_root="$install_root/releases"
  if [[ -e $release_root || -L $release_root ]]; then
    [[ -d $release_root && ! -L $release_root ]] || die "releases path must be a real directory"
  else
    install -d -m 0755 "$release_root"
  fi
  target="$release_root/$version"
  if [[ -e $target || -L $target ]]; then
    [[ -d $target && ! -L $target ]] || die "release target already exists but is not a real directory"
    python3 "$PREPARE_HELPER" validate "$target" "$version" >/dev/null
    [[ -f $target/.artifact-sha256 && ! -L $target/.artifact-sha256 ]] || die "existing release has no checksum receipt"
    IFS= read -r installed_checksum < "$target/.artifact-sha256" || die "existing checksum receipt is unreadable"
    [[ $installed_checksum == "$checksum" ]] || die "existing release checksum receipt does not match the requested artifact"
  else
    staging=$(mktemp -d "$release_root/.staging-${version}.XXXXXXXX")
    cp -a "$prepared/." "$staging/"
    printf '%s\n' "$checksum" > "$staging/.artifact-sha256"
    python3 "$PREPARE_HELPER" validate "$staging" "$version" >/dev/null
    chmod -R u=rwX,go=rX "$staging"
    mv "$staging" "$target"
    staging=''
  fi

  if current_target=$(validate_managed_link "$install_root" current); then
    if [[ $current_target == "releases/$version" ]]; then
      printf 'OpenCLI Browser Bridge %s is already current.\n' "$version"
      trap - EXIT HUP INT TERM
      cleanup_install
      return 0
    fi
    atomic_link "$install_root" previous "$current_target"
  elif [[ -e $install_root/current || -L $install_root/current ]]; then
    die "current exists but is not a valid managed symlink"
  fi

  # This is the only activation step and is atomic on the install filesystem.
  atomic_link "$install_root" current "releases/$version"
  printf 'Installed and activated OpenCLI Browser Bridge %s.\n' "$version"
  trap - EXIT HUP INT TERM
  cleanup_install
}

rollback_release() {
  local install_root=$DEFAULT_INSTALL_ROOT current_target previous_target
  while (($#)); do
    case $1 in
      --install-root) (($# >= 2)) || die "--install-root requires a value"; install_root=$2; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown rollback argument: $1" ;;
    esac
  done
  require_command python3
  validate_install_root "$install_root"
  [[ -d $install_root && ! -L $install_root ]] || die "install root does not exist"
  current_target=$(validate_managed_link "$install_root" current) || die "current release is unavailable"
  previous_target=$(validate_managed_link "$install_root" previous) || die "previous release is unavailable"
  [[ $current_target != "$previous_target" ]] || die "current and previous resolve to the same release"

  # Activation is atomic; releases themselves are never removed by rollback.
  atomic_link "$install_root" current "$previous_target"
  atomic_link "$install_root" previous "$current_target"
  printf 'Rolled back OpenCLI Browser Bridge to %s.\n' "${previous_target#releases/}"
}

main() {
  (($# >= 1)) || { usage; exit 2; }
  local command=$1
  shift
  case $command in
    install) install_release "$@" ;;
    rollback) rollback_release "$@" ;;
    -h|--help|help) usage ;;
    *) usage; die "unknown command: $command" ;;
  esac
}

main "$@"
