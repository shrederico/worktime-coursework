#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PATH="$HOME/.docker/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
test -f .lab/runner/.runner || { printf 'Runner ещё не зарегистрирован.\n'; exit 1; }
cd .lab/runner
exec ./run.sh
