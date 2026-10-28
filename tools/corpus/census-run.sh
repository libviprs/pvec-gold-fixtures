#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work. Clones upstream ACadSharp at the pinned
# commit, builds tools/corpus/census, and reads every source.dwg under /work/.out-corpus/<ver>/run1 and
# every real-world DWG under /work/.out-corpus/real-world, writing census.acadsharp.json beside each.
set -eu
VER=${1:-AC1032}
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
cp -r /work/tools/corpus/census /tmp/census
cd /tmp/census
dotnet build -c Release -o /tmp/censusbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
cp -r /work/tools/r0-open/acadsharp-dump /tmp/dump
(cd /tmp/dump && dotnet build -c Release -o /tmp/dumpbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build2.log 2>&1) || { tail -30 /tmp/build2.log; exit 1; }
for g in edge mixed degenerate; do
  for d in /work/.out-corpus/$VER/run1/$g/*/; do
    dotnet /tmp/dumpbin/AcSharpDump.dll "$d/source.dwg" "$d/read.acadsharp.json" "ACadSharp@3.7.1+d7dc111" || echo "READFAIL $d"
  done
done
for root in /work/.out-corpus/$VER/run1 /work/.out-corpus/real-world; do
  [ -d "$root" ] || continue
  for f in $(find "$root" -name source.dwg | sort); do
    d=$(dirname "$f")
    dotnet /tmp/censusbin/Census.dll "$f" "$d/census.acadsharp.json" "ACadSharp@3.7.1+d7dc111" || echo "READFAIL $f"
  done
done
