#!/bin/sh
# Runs inside the dotnet sdk container, with the repo tree at /work. Has ACadSharp (pinned) write one small drawing (a
# single line, header stamps pinned) as R2000 and as R2004. dwgread turns each into the JSON skeleton author.py
# starts from: the tables, dictionaries, layouts and header of an empty drawing of that version. No entity of it
# survives into a fixture; every entity is authored from the parameter files.
set -eu
PIN=d7dc111023477d8a9fffc2153139459c95b4f345
export HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
mkdir -p /tmp/home /tmp/dn
git clone -q https://github.com/DomCR/ACadSharp /tmp/acs
git -C /tmp/acs checkout -q "$PIN"
test "$(git -C /tmp/acs rev-parse HEAD)" = "$PIN"
git -C /tmp/acs submodule update -q --init --recursive
cp -r /work/tools/corpus/writer-acadsharp /tmp/wr
(cd /tmp/wr && dotnet build -c Release -o /tmp/wrbin -p:AcsSrc=/tmp/acs/src -p:GenerateDocumentationFile=false >/tmp/build-wr.log 2>&1) || { grep -E " error " /tmp/build-wr.log | sort -u | head -30; exit 1; }
for V in AC1015 AC1018; do
  dotnet /tmp/wrbin/WriterAcadSharp.dll write --kt /work/fixtures/known-truth --params /work/tools/authoring/params --version $V \
    --out /work/.out-wf-libredwg/skeleton/$V --fixed-header --only line-001 >/dev/null
done
