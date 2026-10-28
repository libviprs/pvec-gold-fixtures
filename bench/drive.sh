#!/usr/bin/env bash
# Drive the benchmarks and the regeneration on a native docker host, everything in throw-away containers.
#
#   bench/drive.sh mars|mercury up                 push the tree into a docker volume, build the images this needs
#   bench/drive.sh mars|mercury run <cmd...>       run <cmd> in the driver container (python, docker CLI, the host socket)
#   bench/drive.sh mars|mercury pull <rel> <dir>   copy <rel> (a path in the tree) out of the volume into <dir>
#   bench/drive.sh mars|mercury push <dir> <rel>   copy a local directory into the volume at <rel>
#   bench/drive.sh mars|mercury down               drop the volume and the images only this made
#
# mars is native x86_64, mercury is native arm64. The tree lives in a named volume (no host path is mounted,
# so nothing is left on the host), and the driver gets the host's docker socket, which is enough for a driver
# that only runs docker run/build/rm. The converter image comes from tools/converters/acadsharp/test.sh
# (gold-dwg2step-acadsharp:test-<arch>), built here when it is missing. Nothing here reads a credential.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
host=${1:?mars|mercury}; cmd=${2:?up|run|pull|down}; shift 2
case $host in
  mars)    ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR devshell@192.168.0.100); dk=docker; arch=amd64
           cfg=DOCKER_CONFIG=/work/nas-work/.docker-config-gold-acs ;;
  mercury) ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR mercury); dk=/opt/homebrew/bin/docker; arch=arm64; cfg="" ;;
  *) echo "host?" >&2; exit 2 ;;
esac
plat=linux/$arch
vol=gold-bench-20-$arch
drv=gold-acs-driver:$arch
r() { "${ssh[@]}" "$cfg $*"; }
case $cmd in
  up)
    r "$dk volume create $vol >/dev/null"
    if ! r "$dk image inspect $drv >/dev/null 2>&1"; then
      tar -cf - -C "$here/tools/converters/acadsharp" driver.Dockerfile -C "$here" requirements.txt \
        | r "$dk build -q --platform $plat -f driver.Dockerfile -t $drv - >/dev/null"
    fi
    tar --exclude='.git' --exclude='__pycache__' --exclude='.out-*' -cf - -C "$here" . \
      | r "$dk run --rm -i --platform $plat -v $vol:/work alpine:3.20 sh -c 'tar -xf - -C /work'"
    r "$dk run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v $vol:/work -w /work $drv sh -c '
       docker image inspect gold-dwg2step-acadsharp:test-$arch >/dev/null 2>&1 || docker build -q --platform $plat -f tools/converters/acadsharp/Dockerfile -t gold-dwg2step-acadsharp:test-$arch . >/dev/null
       docker image inspect gold-stepval:test-$arch >/dev/null 2>&1 || docker build -q --platform $plat --target test -f docker/step-validator/Dockerfile -t gold-stepval:test-$arch . >/dev/null
       docker image inspect gold-stepval:$arch >/dev/null 2>&1 || docker build -q --platform $plat -f docker/step-validator/Dockerfile -t gold-stepval:$arch . >/dev/null'"
    ;;
  run)
    r "$dk run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v $vol:/work -w /work \
       -e GOLD_VOLUME=$vol -e GOLD_VOLUME_AT=/work -e DOCKER_PLATFORM=$plat -e GOLD_HOST=$host \
       $drv sh -c $(printf '%q' "$*")"
    ;;
  pull)
    mkdir -p "$2"
    r "$dk run --rm --platform $plat -v $vol:/v alpine:3.20 tar -cf - -C /v/$1 ." | tar -xf - -C "$2"
    ;;
  push)
    tar -cf - -C "$1" . | r "$dk run --rm -i --platform $plat -v $vol:/v alpine:3.20 sh -c 'mkdir -p /v/$2 && tar -xf - -C /v/$2'"
    ;;
  down)
    r "$dk volume rm $vol >/dev/null 2>&1; $dk rmi gold-stepval:test-$arch >/dev/null 2>&1; true"
    ;;
esac
