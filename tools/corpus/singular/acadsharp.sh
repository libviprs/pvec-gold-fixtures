#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work and libredwg.sh's output under /work/.out-singular.
# Clones ACadSharp at the pinned commit, applies the converter's patch (the zero-scale guard is gone), builds the r0-open
# dump tool against it and reads the DWG.
set -eu
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
git -C /tmp/acs apply /work/tools/converters/acadsharp/patches/0001-insert-keep-zero-scale.patch
cp -r /work/tools/r0-open/acadsharp-dump /tmp/dump
cd /tmp/dump
dotnet build -c Release -o /tmp/dumpbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
dotnet /tmp/dumpbin/AcSharpDump.dll /work/.out-singular/run1/source.dwg /work/.out-singular/run1/acadsharp.read.json "ACadSharp@3.7.1+d7dc111+insert-keep-zero-scale"
