#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if [ -d wheelhouse ]; then
  .venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements.txt
else
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m app
