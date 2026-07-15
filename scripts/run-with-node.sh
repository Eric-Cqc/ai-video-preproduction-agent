#!/usr/bin/env zsh
set -euo pipefail

if command -v fnm >/dev/null 2>&1; then
  eval "$(fnm env --shell zsh)"
  fnm use --silent-if-unchanged
else
  expected_version="v$(<.node-version)"
  actual_version="$(node --version)"
  if [[ "$actual_version" != "$expected_version" ]]; then
    print -u2 "Expected Node.js $expected_version, found $actual_version"
    exit 1
  fi
fi

exec "$@"
