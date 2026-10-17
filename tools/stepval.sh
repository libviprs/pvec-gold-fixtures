#!/usr/bin/env bash
# Build and run the step-validator image.
#   tools/stepval.sh build amd64|arm64      build gold-stepval:<arch>  (amd64 on MARS, arm64 on this Mac's docker)
#   tools/stepval.sh run amd64|arm64 <cmd>  run <cmd> in it with the repo tree at /work
#   tools/stepval.sh done                   remove the scratch tree and both images
# x86_64 work happens on MARS (native), arm64 in a local arm64 container. Nothing else runs here.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
nas=$here/../tools/nas.sh
[ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
host=${NAS:-devshell@192.168.0.100}
name=gold-stepval-$(basename "$here")
ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR "$host")
cmd=${1:-}; arch=${2:-}
case $cmd in
  build)
    case $arch in
      amd64) "$nas" push "$here" "$name" >/dev/null
             "${ssh[@]}" "cd /work/nas-work/$name && docker build --platform linux/amd64 -f docker/step-validator/Dockerfile -t gold-stepval:amd64 ${BUILD_ARGS:-} ." ;;
      arm64) docker build --platform linux/arm64 -f "$here/docker/step-validator/Dockerfile" -t gold-stepval:arm64 ${BUILD_ARGS:-} "$here" ;;
      *) echo "arch?" >&2; exit 2 ;;
    esac ;;
  run)
    shift 2
    case $arch in
      amd64) "$nas" push "$here" "$name" >/dev/null
             "$nas" run "$name" gold-stepval:amd64 "$*" ;;
      arm64) docker run --rm --platform linux/arm64 -v "$here":/work -w /work gold-stepval:arm64 sh -c "$*" ;;
      *) echo "arch?" >&2; exit 2 ;;
    esac ;;
  done)
    "$nas" clean "$name"
    "${ssh[@]}" "docker rmi gold-stepval:amd64 >/dev/null 2>&1 || true"
    docker rmi gold-stepval:arm64 >/dev/null 2>&1 || true ;;
  *) sed -n '2,7p' "$0" >&2; exit 2 ;;
esac
