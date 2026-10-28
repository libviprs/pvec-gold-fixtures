#!/usr/bin/env bash
# Qualify the open converter against the probe corpus on a native docker host, everything in throw-away
# containers. Same shape as tools/converters/acadsharp/test.sh: the tree goes into a named volume, a
# driver container with the host's socket builds the converter and evaluator images and runs
# tools/qualify/open_route.py, and the report and the per-probe records are copied back here.
#
#   LIBREDWG_IMAGE=<digest ref or local image id> tools/qualify/open_route.sh mars|mercury
#   tools/qualify/open_route.sh mars|mercury --done      remove the images this made
set -euo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
host=${1:?mars|mercury}; shift || true
case $host in
  mars)    ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR devshell@192.168.0.100); dk=docker; arch=amd64
           cfg=DOCKER_CONFIG=/work/nas-work/.docker-config-gold-acs ;;
  mercury) ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR mercury); dk=/opt/homebrew/bin/docker; arch=arm64; cfg="" ;;
  *) echo "host?" >&2; exit 2 ;;
esac
plat=linux/$arch
vol=gold-qual-$arch
drv=gold-acs-driver:$arch
r() { "${ssh[@]}" "$cfg $*"; }
if [ "${1:-}" = "--done" ]; then
  r "$dk volume rm $vol >/dev/null 2>&1; $dk rmi $drv gold-dwg2step-acadsharp:qualify-$arch gold-stepval:$arch gold-stepval-test:$arch >/dev/null 2>&1; true"
  exit 0
fi
r "$dk volume rm $vol >/dev/null 2>&1; $dk volume create $vol >/dev/null"
if ! r "$dk image inspect $drv >/dev/null 2>&1"; then
  tar -cf - -C "$here/tools/converters/acadsharp" driver.Dockerfile -C "$here" requirements.txt \
    | r "$dk build -q --platform $plat -f driver.Dockerfile -t $drv - >/dev/null"
fi
tar --exclude='.git' --exclude='__pycache__' --exclude='.out-*' -cf - -C "$here" . \
  | r "$dk run --rm -i --platform $plat -v $vol:/work alpine:3.20 sh -c 'tar -xf - -C /work'"
set +e
r "$dk run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v $vol:/work -w /work -e GOLD_VOLUME=$vol -e LIBREDWG_IMAGE=${LIBREDWG_IMAGE:?set LIBREDWG_IMAGE to the digest or local id} \
   $drv sh -c 'mkdir -p reports/phase1 && PYTHONPATH=/work python3 tools/qualify/open_route.py'"
rc=$?
mkdir -p "$here/.out-qualify" "$here/reports/phase1"
r "$dk run --rm --platform $plat -v $vol:/work alpine:3.20 tar -cf - -C /work reports .out-qualify" | tar -xf - -C "$here"
r "$dk volume rm $vol >/dev/null 2>&1; true"
exit $rc
