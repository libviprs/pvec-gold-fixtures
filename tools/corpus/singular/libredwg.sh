#!/bin/sh
# Runs inside the pvec-oracle-libredwg image (used by id or digest, never built from this repository), with the repo tree
# at /work and acadrust.sh's output under /work/.out-singular. Has dwgdump read the DWG and runs the LibreDWG converter
# over it, so its refusal is on record.
set -eu
OUT=/work/.out-singular/run1
dwgdump --in "$OUT/source.dwg" --out "$OUT/libredwg.read.json"
set +e
dwg2step --in "$OUT/source.dwg" --out "$OUT/libredwg-dwg2step.step" --status "$OUT/libredwg-dwg2step.status.json"
echo "libredwg-dwg2step exit $?"
