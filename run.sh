#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Cree el entorno: python3 -m venv .venv' >&2
  exit 1
fi
exec .venv/bin/python -m app.main "$@"
