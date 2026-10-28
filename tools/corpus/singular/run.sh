#!/usr/bin/env bash
# Write singular-001's DWG with acadrust, have three readers read it, record both converters' refusal, and assemble fixtures/edge/singular-001.
# Everything that executes does so in a container on MARS (native x86_64); this machine runs ssh, docker through
# tools/nas.sh, tar and the pure-python assembly.
#   LIBREDWG_IMAGE=<pvec-oracle-libredwg image id or digest> tools/corpus/singular/run.sh
# The LibreDWG image is GPL and is never a build context here. The acadsharp converter's own result comes from
# tools/corpus/open_route.sh, which builds the patched converter image.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$here/../../..
nas=${NAS_SH:-$root/../tools/nas.sh}
name=${NAS_NAME:-gold-singular}
host=${NAS:-devshell@192.168.0.100}
: "${LIBREDWG_IMAGE:?set LIBREDWG_IMAGE to the pvec-oracle-libredwg image id or digest}"
"$nas" push "$root" "$name" >/dev/null
"$nas" run "$name" rust:1.99.1-bookworm "sh /work/tools/corpus/singular/acadrust.sh"
"$nas" run "$name" "$LIBREDWG_IMAGE" "sh /work/tools/corpus/singular/libredwg.sh"
"$nas" run "$name" mcr.microsoft.com/dotnet/sdk:10.0.401-noble "sh /work/tools/corpus/singular/acadsharp.sh"
rm -rf "$root/.out-singular"; mkdir -p "$root/.out-singular"
ssh -o BatchMode=yes -o LogLevel=ERROR "$host" "tar -cf - -C /work/nas-work/$name/.out-singular ." | tar -xf - -C "$root/.out-singular"
cp "$root/.out-singular/Cargo.lock" "$here/tool/Cargo.lock"
"$nas" clean "$name"
echo "now: LIBREDWG_IMAGE=... python3 -m runner.singular_probe assemble .out-singular   (in the python container, tools/py.sh)"
