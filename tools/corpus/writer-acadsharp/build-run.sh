#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work. Clones upstream ACadSharp at the pinned
# commit, builds the writer and the r0-open reader dump, then writes the r0-open probes through DwgWriter: twice with
# the stamped header fields pinned (run1, run2: run1 is the corpus), twice as ACadSharp writes them (raw1, raw2),
# and once per stamped field left raw on one fixture (leave-<field>), so the determinism note can name the fields.
# ACadSharp's own reader dumps every DWG of run1.
set -eu
VER=${1:-AC1032}
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
cp -r /work/tools/corpus/writer-acadsharp /tmp/wr
cp -r /work/tools/r0-open/acadsharp-dump /tmp/dump
(cd /tmp/wr && dotnet build -c Release -o /tmp/wrbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build-wr.log 2>&1) || { grep -E " error " /tmp/build-wr.log | sort -u | head -30; exit 1; }
(cd /tmp/dump && dotnet build -c Release -o /tmp/dumpbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build-dump.log 2>&1) || { grep -E " error " /tmp/build-dump.log | sort -u | head -30; exit 1; }
OUT=/work/.out-wf-acadsharp/$VER
rm -rf "$OUT"
mkdir -p "$OUT"
W="dotnet /tmp/wrbin/WriterAcadSharp.dll write --kt /work/fixtures/known-truth --params /work/tools/authoring/params --version $VER"
$W --out "$OUT/run1" --fixed-header >/dev/null
$W --out "$OUT/run2" --fixed-header >/dev/null
$W --out "$OUT/raw1" >/dev/null
$W --out "$OUT/raw2" >/dev/null
for f in CreateDateTime UpdateDateTime UniversalCreateDateTime UniversalUpdateDateTime FingerPrintGuid VersionGuid SummaryInfo.CreatedDate SummaryInfo.ModifiedDate; do
  $W --out "$OUT/leave-$f" --fixed-header --leave-raw $f --only arc-seam-001 >/dev/null
done
for d in "$OUT"/run1/*/; do
  id=$(basename "$d")
  [ -f "$d/source.dwg" ] || continue
  dotnet /tmp/dumpbin/AcSharpDump.dll "$d/source.dwg" "$d/acadsharp.read.json" "ACadSharp@3.7.1+d7dc111" || echo "READFAIL $id"
done
for c in run1 raw1; do
  if [ $c = run1 ]; then g=run2; else g=raw2; fi
  for d in "$OUT"/$c/*/; do
    id=$(basename "$d")
    [ -f "$d/source.dwg" ] || continue
    if cmp -s "$d/source.dwg" "$OUT/$g/$id/source.dwg"; then echo "identical $g $id"; else echo "DIFFERS $g $id"; fi
  done
done
