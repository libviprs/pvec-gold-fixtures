#!/bin/sh
# Runs inside the LibreDWG converter image (used by id or digest, never built from this repository), with the repo tree
# at /work. author.py writes the probes as LibreDWG JSON and dwgwrite turns each into a DWG, twice (run1, run2) for
# the determinism count; dwgdump, the image's own reader, reads the DWGs of run1.
set -eu
V=${1:?version AC1015 or AC1018}
case $V in AC1015) AS=r2000 ;; AC1018) AS=r2004 ;; *) echo "dwgwrite writes r2000 and r2004 here" >&2; exit 2 ;; esac
B=/work/.out-wf-libredwg
dwgread-exact -O JSON -o "$B/skeleton/$V/skeleton.json" "$B/skeleton/$V/line-001/source.dwg" >/dev/null 2>&1
for r in run1 run2; do
  python3 -I /work/tools/corpus/writer-libredwg/author.py --skeleton "$B/skeleton/$V/skeleton.json" --kt /work/fixtures/known-truth \
    --params /work/tools/authoring/params --out "$B/$V/$r" --dwgwrite dwgwrite-exact --as $AS --writer "LibreDWG@0.14+patch0001" --version $V
done
for d in "$B/$V/run1"/*/; do
  id=$(basename "$d")
  [ -f "$d/source.dwg" ] || continue
  dwgdump --in "$d/source.dwg" --out "$d/libredwg.read.json" || echo "READFAIL $id"
done
