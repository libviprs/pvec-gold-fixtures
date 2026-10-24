#!/usr/bin/env bash
# Rebuild corpus/r0-open from scratch: write the DWGs with acadrust, have ACadSharp and acadrust read
# them, assemble and check the corpus. Everything that executes does so in a container on MARS (native
# x86_64); this machine only runs ssh, docker through tools/nas.sh, and the pure-python assembly.
#   tools/r0-open/run.sh [AC1032]
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$here/../..
ver=${1:-AC1032}
"$here/mars.sh" push >/dev/null
"$here/mars.sh" run rust:1.99.1-bookworm "sh /work/tools/r0-open/rust/run-write.sh $ver"
"$here/mars.sh" run mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh /work/tools/r0-open/acadsharp-run.sh $ver"
"$here/mars.sh" pull .out-r0open "$root/.out-r0open"
"$here/mars.sh" done
(cd "$root" && python3 -m runner.r0_open assemble ".out-r0open/$ver/run1" corpus/r0-open --writer-info tools/r0-open/writer-info.json \
  && python3 -m runner.r0_open check corpus/r0-open)
