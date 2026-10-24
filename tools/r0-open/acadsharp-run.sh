#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work and the run1 outputs of run-write.sh
# under /work/.out-r0open/<version>. Clones upstream ACadSharp at the pinned commit, builds the dumper, and
# has ACadSharp's DwgReader dump every DWG the acadrust writer produced.
set -eu
VER=${1:-AC1032}
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
cp -r /work/tools/r0-open/acadsharp-dump /tmp/dump
cd /tmp/dump
dotnet build -c Release -o /tmp/dumpbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
OUT=/work/.out-r0open/$VER/run1
for d in "$OUT"/*/; do
  id=$(basename "$d")
  dotnet /tmp/dumpbin/AcSharpDump.dll "$OUT/$id/source.dwg" "$OUT/$id/acadsharp.read.json" "ACadSharp@3.7.1+d7dc111" || echo "READFAIL $id"
done
