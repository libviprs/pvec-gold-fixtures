#!/bin/sh
# Runs inside the LibreDWG converter image (used by id or digest, never built from this repository), with the repo
# tree at /work. Has its dwgdump write the read record of every DWG that ACadSharp's DwgWriter produced.
set -eu
VER=${1:-AC1032}
OUT=/work/.out-wf-acadsharp/$VER/run1
for d in "$OUT"/*/; do
  id=$(basename "$d")
  dwgdump --in "$d/source.dwg" --out "$d/libredwg.read.json" || echo "READFAIL $id"
done
