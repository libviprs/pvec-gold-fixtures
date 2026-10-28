#!/usr/bin/env bash
# Assemble fixtures/**, corpus/capability-matrix.json and corpus/r1-open from a tools/corpus/run.sh run,
# in the python container on MARS, then copy fixtures/ and corpus/ back.
#   tools/corpus/assemble.sh [AC1032]
set -euo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
host=${NAS:-devshell@192.168.0.100}
name=gold-py-$(basename "$here")
ver=${1:-AC1032}
"$here/tools/py.sh" python3 -m runner.corpus assemble ".out-corpus/$ver/run1" .out-corpus/real-world
for d in fixtures corpus; do
  ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$name/$d ." | tar -xf - -C "$here/$d"
done
