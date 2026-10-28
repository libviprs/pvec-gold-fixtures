#!/usr/bin/env bash
# Run the dwg2step-acadsharp container tests on a native docker host, everything in throw-away containers.
#
#   tools/converters/acadsharp/test.sh mars|mercury [unittest args...]    default: the whole test module
#   tools/converters/acadsharp/test.sh mars|mercury --done                remove the volume and every image this made
#
# mars is native x86_64, mercury native arm64. The tree goes into a named docker volume (no host path
# is mounted, so nothing is left on the host to clean up), a driver container with the host's docker
# socket builds the converter image and the step-validator image, runs the tests, and the volume is
# dropped at the end unless KEEP=1. Only ssh and docker run on the host. Nothing here reads a credential.
set -euo pipefail
here=$(cd "$(dirname "$0")/../../.." && pwd)
host=${1:?mars|mercury}; shift || true
case $host in
  mars)    ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR devshell@192.168.0.100); dk=docker; arch=amd64
           cfg=DOCKER_CONFIG=/work/nas-work/.docker-config-gold-acs ;;
  mercury) ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR mercury); dk=/opt/homebrew/bin/docker; arch=arm64; cfg="" ;;
  *) echo "host?" >&2; exit 2 ;;
esac
plat=linux/$arch
vol=gold-acs-48-$arch
drv=gold-acs-driver:$arch
r() { "${ssh[@]}" "$cfg $*"; }
if [ "${1:-}" = "--done" ]; then
  r "$dk volume rm $vol >/dev/null 2>&1; $dk rmi $drv gold-dwg2step-acadsharp:test-$arch gold-stepval:$arch >/dev/null 2>&1; true"
  exit 0
fi
r "$dk volume create $vol >/dev/null"
if ! r "$dk image inspect $drv >/dev/null 2>&1"; then
  tar -cf - -C "$here/tools/converters/acadsharp" driver.Dockerfile -C "$here" requirements.txt \
    | r "$dk build -q --platform $plat -f driver.Dockerfile -t $drv - >/dev/null"
fi
# push the tree into the volume from inside a container
tar --exclude='.git' --exclude='__pycache__' --exclude='.out-*' -cf - -C "$here" . \
  | r "$dk run --rm -i --platform $plat -v $vol:/work alpine:3.20 sh -c 'tar -xf - -C /work'" 
args=${*:-tests.test_acadsharp_converter}
set +e
r "$dk run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v $vol:/work -w /work \
   -e GOLD_VOLUME=$vol -e GOLD_VOLUME_AT=/work -e GOLD_DOCKER_TESTS=1 -e DOCKER_PLATFORM=$plat ${DWG2STEP_IMAGE:+-e DWG2STEP_IMAGE=$DWG2STEP_IMAGE} \
   $drv sh -c 'docker image inspect gold-stepval:$arch >/dev/null 2>&1 || docker build -q --platform $plat -f docker/step-validator/Dockerfile -t gold-stepval:$arch . >/dev/null; python3 -m unittest $args -v'"
rc=$?
[ "${KEEP:-0}" = "1" ] || r "$dk volume rm $vol >/dev/null 2>&1; true"
exit $rc
