#!/usr/bin/env bash
# Run a command for this repo on MARS (native x86_64), in a throw-away python container.
#   tools/py.sh <cmd...>    e.g. tools/py.sh python3 -m unittest discover -s tests -t .
#   tools/py.sh --done      remove the scratch tree and the cached dependency image
# The tree is pushed to /work/nas-work/<name> and kept between runs; the dependency image is
# built once from requirements.txt. Nothing executes on this machine.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
nas=$here/../tools/nas.sh
[ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
host=${NAS:-devshell@192.168.0.100}
name=gold-py-$(basename "$here")
img=gold-py:$(shasum "$here/requirements.txt" | cut -c1-12)
ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR "$host")
if [ "${1:-}" = "--done" ]; then
  "$nas" clean "$name"
  "${ssh[@]}" "docker rmi $img >/dev/null 2>&1 || true"
  exit 0
fi
if ! "${ssh[@]}" "docker image inspect $img >/dev/null 2>&1"; then
  tar -cf - -C "$here/docker/py" Dockerfile -C "$here" requirements.txt \
    | "${ssh[@]}" "DOCKER_CONFIG=${DOCKER_CONFIG_REMOTE:-/tmp/dcgold} docker build -q --platform linux/amd64 -t $img -" >/dev/null
fi
"$nas" push "$here" "$name" >/dev/null
"$nas" run "$name" "$img" "$*"
