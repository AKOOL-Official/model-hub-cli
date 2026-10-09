#!/usr/bin/env bash
# Standalone installer. Keep this whole function intact so a truncated pipe cannot install.
set -euo pipefail

install_modelhub() (
  set -euo pipefail
  fail() { printf 'akool-mh: %s\n' "$*" >&2; exit 1; }
  base_url="${AKOOL_MH_DOWNLOAD_BASE_URL:-https://github.com/AKOOL-Official/model-hub-cli/releases}"
  layout="${AKOOL_MH_DOWNLOAD_LAYOUT:-}"
  version="${AKOOL_MH_VERSION:-}"
  install_dir="${AKOOL_MH_INSTALL_DIR:-$HOME/.local/bin}"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --version|--install-dir|--base-url|--layout)
        [ "$#" -ge 2 ] || fail "Missing value for $1"
        case "$1" in
          --version) version="$2" ;;
          --install-dir) install_dir="$2" ;;
          --base-url) base_url="$2" ;;
          --layout) layout="$2" ;;
        esac
        shift 2 ;;
      --help|-h)
        printf '%s\n' 'Usage: install.sh [--version VERSION] [--install-dir DIR] [--base-url HTTPS_URL] [--layout github|static]'
        exit 0 ;;
      *) fail "Unknown option: $1" ;;
    esac
  done
  command -v curl >/dev/null || fail 'curl is required'
  command -v shasum >/dev/null || command -v sha256sum >/dev/null || fail 'SHA256 utility is required'
  base_url="${base_url%/}"
  if [ -z "$layout" ]; then
    case "$base_url" in
      https://github.com/*/releases) layout=github ;;
      *) layout=static ;;
    esac
  fi
  case "$layout" in github|static) ;; *) fail 'Layout must be github or static' ;; esac
  protocol='=https'
  if [[ "$base_url" =~ ^http://(127\.0\.0\.1|localhost)(:[0-9]+)?(/[a-zA-Z0-9._~/-]*)?$ ]]; then
    protocol='=http' # Local release smoke tests only.
  elif ! [[ "$base_url" =~ ^https://[a-zA-Z0-9.-]+(:[0-9]+)?(/[a-zA-Z0-9._~/-]*)?$ ]]; then
    fail 'Download base must be HTTPS without credentials, query or fragment'
  fi
  case "$(uname -s)" in
    Darwin) os=darwin ;;
    Linux) os=linux ;;
    *) fail 'Supported systems: macOS and Linux' ;;
  esac
  case "$(uname -m)" in
    arm64|aarch64) arch=arm64 ;;
    x86_64|amd64) arch=amd64 ;;
    *) fail 'Supported architectures: arm64 and amd64' ;;
  esac
  [ -n "$install_dir" ] || fail 'Install directory must not be empty'
  mkdir -p "$install_dir"
  install_dir="$(cd "$install_dir" && pwd -P)"
  target="$install_dir/akool-mh"
  [ ! -L "$target" ] || fail 'Refusing to replace a symlink; install into a regular user directory'
  [ ! -d "$target" ] || fail 'Install target is a directory'
  staging="$(mktemp -d "$install_dir/.akool-mh-install.XXXXXX")"
  trap 'rm -rf "$staging"' EXIT
  fetch() {
    curl --fail --silent --show-error --location --proto "$protocol" --proto-redir "$protocol" \
      --connect-timeout 15 --max-time 300 --retry 2 --output "$2" "$1"
  }
  if [ -z "$version" ]; then
    if [ "$layout" = github ]; then
      latest_url="$base_url/latest/download/version.txt"
    else
      latest_url="$base_url/latest.txt"
    fi
    fetch "$latest_url" "$staging/latest.txt" || fail 'No downloadable release found; check the repository Releases page'
    [ "$(wc -c < "$staging/latest.txt")" -le 128 ] || fail 'Invalid release version file'
    version="$(cat "$staging/latest.txt")"
  fi
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+([.-][a-zA-Z0-9]+)*)?$ ]] || fail 'Invalid release version'
  asset="akool-mh-$os-$arch"
  if [ "$layout" = github ]; then
    release="$base_url/download/v$version"
  else
    release="$base_url/releases/$version"
  fi
  fetch "$release/SHA256SUMS" "$staging/SHA256SUMS"
  expected="$(awk -v asset="$asset" '$2 == asset { print $1 }' "$staging/SHA256SUMS")"
  [[ "$expected" =~ ^[a-fA-F0-9]{64}$ ]] || fail 'Missing or ambiguous checksum for this platform'
  fetch "$release/$asset" "$staging/akool-mh"
  if command -v sha256sum >/dev/null; then
    actual="$(sha256sum "$staging/akool-mh" | awk '{print $1}')"
  else
    actual="$(shasum -a 256 "$staging/akool-mh" | awk '{print $1}')"
  fi
  [ "$(printf '%s' "$expected" | tr 'A-F' 'a-f')" = "$actual" ] || fail 'Checksum mismatch; existing installation was preserved'
  chmod 755 "$staging/akool-mh"
  reported="$("$staging/akool-mh" --version)" || fail 'Downloaded binary cannot run on this system'
  [ "$reported" = "AKOOL Model Hub CLI $version" ] || fail 'Downloaded binary has an unexpected version'
  # Same filesystem: failed downloads/verification never overwrite a working installation.
  mv -f "$staging/akool-mh" "$target"
  printf 'Installed akool-mh %s at %s\n' "$version" "$target"
  case ":$PATH:" in
    *":$install_dir:"*) ;;
    *) printf 'Add this directory to PATH in your shell configuration:\n  export PATH=%q:"$PATH"\n' "$install_dir" >&2 ;;
  esac
)

install_modelhub "$@"
