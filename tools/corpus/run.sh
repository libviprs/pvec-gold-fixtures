#!/usr/bin/env bash
# Write the corpus DWGs and read them back. Everything that executes does so in a container on MARS
# (native x86_64); this machine only runs ssh, docker through tools/nas.sh, and the pure-python assembly.
#   tools/corpus/run.sh [AC1032]        writes into .out-corpus/ (ignored by git)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$here/../..
ver=${1:-AC1032}
"$here/mars.sh" push >/dev/null
"$here/mars.sh" run rust:1.99.1-bookworm "sh /work/tools/corpus/write-run.sh $ver"
"$here/mars.sh" run mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh /work/tools/corpus/census-run.sh $ver"
"$here/mars.sh" pull .out-corpus "$root/.out-corpus"
"$here/mars.sh" done
