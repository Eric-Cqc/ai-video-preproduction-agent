#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/.." && pwd -P)"
version_file="$repo_root/.node-version"

if [[ ! -r "$version_file" ]]; then
  printf 'Node.js version file is missing or unreadable: %s\n' "$version_file" >&2
  exit 1
fi

expected_version="$(tr -d '[:space:]' < "$version_file")"
if [[ -z "$expected_version" ]]; then
  printf 'Node.js version file is empty: %s\n' "$version_file" >&2
  exit 1
fi

normalize_version() {
  printf '%s' "${1#v}"
}

node_matches_expected_version() {
  if ! command -v node >/dev/null 2>&1; then
    return 1
  fi

  local actual_version
  actual_version="$(node --version)"
  [[ "$(normalize_version "$actual_version")" == "$(normalize_version "$expected_version")" ]]
}

if ! node_matches_expected_version; then
  if ! command -v fnm >/dev/null 2>&1; then
    if command -v node >/dev/null 2>&1; then
      printf 'Expected Node.js %s, found %s; fnm is unavailable to select the required version.\n' \
        "$expected_version" "$(node --version)" >&2
    else
      printf 'Expected Node.js %s, but node and fnm are unavailable.\n' "$expected_version" >&2
    fi
    exit 1
  fi

  eval "$(fnm env --shell bash)"
  fnm use --silent-if-unchanged "$expected_version"

  if ! node_matches_expected_version; then
    if command -v node >/dev/null 2>&1; then
      printf 'Expected Node.js %s after fnm use, found %s.\n' "$expected_version" "$(node --version)" >&2
    else
      printf 'Expected Node.js %s after fnm use, but node is unavailable.\n' "$expected_version" >&2
    fi
    exit 1
  fi
fi

exec "$@"
