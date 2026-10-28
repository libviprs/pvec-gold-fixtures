#!/usr/bin/env bash
# Regenerate the corpus records from the parameter files, in the python container on MARS, and copy
# the generated directories back. With --check it only compares.
#   tools/corpus/author.sh [--check]
set -euo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
host=${NAS:-devshell@192.168.0.100}
name=gold-py-$(basename "$here")
"$here/tools/py.sh" python3 tools/authoring/author_corpus.py "$@"
if [ "${1:-}" != "--check" ]; then
  for d in edge mixed degenerate negative; do
    mkdir -p "$here/fixtures/$d"
    ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$name/fixtures/$d ." | tar -xf - -C "$here/fixtures/$d"
  done
fi
