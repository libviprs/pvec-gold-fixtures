#!/usr/bin/env bash
# Write the r0-open probes with ACadSharp's DwgWriter, have three readers read them back, and assemble corpus/writers/acadsharp.
# Everything that executes does so in a container on MARS (native x86_64); this machine only runs ssh, docker through
# tools/nas.sh, tar, and the pure-python assembly (which reads JSON and runs no DWG library).
#   tools/corpus/writer-acadsharp/run.sh [AC1032]
# LIBREDWG_IMAGE is the pvec-oracle-libredwg image, by digest or local id. It is GPL and is never a build context here.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$here/../../..
ver=${1:-AC1032}
nas=${NAS_SH:-$root/../tools/nas.sh}
name=${NAS_NAME:-gold-wf-acadsharp}
: "${LIBREDWG_IMAGE:?set LIBREDWG_IMAGE to the pvec-oracle-libredwg image id or digest}"
host=${NAS:-devshell@192.168.0.100}
"$nas" push "$root" "$name" >/dev/null
"$nas" run "$name" mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh /work/tools/corpus/writer-acadsharp/build-run.sh $ver"
"$nas" run "$name" "$LIBREDWG_IMAGE" "sh /work/tools/corpus/writer-acadsharp/read-libredwg.sh $ver"
"$nas" run "$name" rust:1.99.1-bookworm "sh /work/tools/corpus/writer-acadsharp/read-acadrust.sh $ver"
rm -rf "$root/.out-wf-acadsharp"; mkdir -p "$root/.out-wf-acadsharp"
ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$name/.out-wf-acadsharp ." | tar -xf - -C "$root/.out-wf-acadsharp"
"$nas" clean "$name"
# The assembly reads JSON and hashes files, so it runs in the python container too, and the result comes back by tar.
"$root/tools/py.sh" python3 -m runner.writer_family assemble ".out-wf-acadsharp/$ver" corpus/writers/acadsharp --info tools/corpus/writer-acadsharp/writer-info.json
py=gold-py-$(basename "$(cd "$root" && pwd)")
rm -rf "$root/corpus/writers/acadsharp"; mkdir -p "$root/corpus/writers/acadsharp"
ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$py/corpus/writers/acadsharp ." | tar -xf - -C "$root/corpus/writers/acadsharp"
