#!/usr/bin/env zsh
set -euo pipefail

eval "$(fnm env --shell zsh)"
fnm use --silent-if-unchanged

exec "$@"
