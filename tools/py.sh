#!/usr/bin/env bash
# Run a python command for this repo on MARS, in a throw-away container.
#   tools/py.sh <cmd...>     e.g. tools/py.sh python3 -m unittest discover -s tests -t .
# Pushes the working tree, runs it, then removes the scratch tree. Nothing executes on this machine.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
nas=$here/../tools/nas.sh
[ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
name=gold-$(basename "$here")-$$
trap '"$nas" clean "$name" >/dev/null' EXIT
"$nas" push "$here" "$name" >/dev/null
"$nas" run "$name" python:3.12-slim "pip install -q --disable-pip-version-check --root-user-action=ignore -r requirements.txt 2>&1 | tail -1; $*"
