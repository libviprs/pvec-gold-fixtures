#!/usr/bin/env bash
# Author the r0-open probes as LibreDWG JSON, write them with dwgwrite as R2000 and R2004, have three readers read them
# back, and assemble corpus/writers/libredwg-r2000 and libredwg-r2004. Everything that executes does so in a container
# on MARS (native x86_64); this machine runs ssh, docker through tools/nas.sh, tar, and nothing else.
#   LIBREDWG_IMAGE=<pvec-oracle-libredwg image id or digest> tools/corpus/writer-libredwg/run.sh
# The image is GPL; it is used by id or digest and is never a build context of this repository.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$here/../../..
nas=${NAS_SH:-$root/../tools/nas.sh}
name=${NAS_NAME:-gold-wf-libredwg}
: "${LIBREDWG_IMAGE:?set LIBREDWG_IMAGE to the pvec-oracle-libredwg image id or digest}"
host=${NAS:-devshell@192.168.0.100}
t=/work/tools/corpus/writer-libredwg
"$nas" push "$root" "$name" >/dev/null
"$nas" run "$name" mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh $t/skeleton-run.sh"
for v in AC1015 AC1018; do
  "$nas" run "$name" "$LIBREDWG_IMAGE" "sh $t/write-run.sh $v"
  "$nas" run "$name" rust:1.99.1-bookworm "sh $t/read-acadrust.sh $v"
  "$nas" run "$name" mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh $t/read-acadsharp.sh $v"
done
rm -rf "$root/.out-wf-libredwg"; mkdir -p "$root/.out-wf-libredwg"
ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$name/.out-wf-libredwg ." | tar -xf - -C "$root/.out-wf-libredwg"
"$nas" clean "$name"
# The assembly reads JSON and hashes files, so it runs in the python container too, and the results come back by tar.
py=gold-py-$(basename "$(cd "$root" && pwd)")
for v in AC1015:libredwg-r2000 AC1018:libredwg-r2004; do
  "$root/tools/py.sh" python3 -m runner.writer_family assemble ".out-wf-libredwg/${v%%:*}" "corpus/writers/${v##*:}" --info tools/corpus/writer-libredwg/writer-info.json
  rm -rf "$root/corpus/writers/${v##*:}"; mkdir -p "$root/corpus/writers/${v##*:}"
  ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$py/corpus/writers/${v##*:} ." | tar -xf - -C "$root/corpus/writers/${v##*:}"
done
