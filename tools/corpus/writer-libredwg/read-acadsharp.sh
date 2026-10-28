#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work. Builds ACadSharp (pinned) and its r0-open reader
# dump, and has DwgReader read every DWG that dwgwrite produced for the version.
set -eu
V=${1:?version}
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
cp -r /work/tools/r0-open/acadsharp-dump /tmp/dump
(cd /tmp/dump && dotnet build -c Release -o /tmp/dumpbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build-dump.log 2>&1) || { grep -E " error " /tmp/build-dump.log | sort -u | head -30; exit 1; }
for d in /work/.out-wf-libredwg/$V/run1/*/; do
  [ -f "$d/source.dwg" ] || continue
  dotnet /tmp/dumpbin/AcSharpDump.dll "$d/source.dwg" "$d/acadsharp.read.json" "ACadSharp@3.7.1+d7dc111" || echo "READFAIL $(basename "$d")"
done
