#!/usr/bin/env bash
# A clean-host run of r2-open: a throw-away docker-in-docker daemon with an empty image store, the two open
# converters and the evaluator, one command (runner.r2_open run) over r0-open and r1-open.
#
#   LIBREDWG_LOCAL=<local image id or tag on the host> tools/clean_host_r2.sh mars|mercury [--keep]
#
# The tree is a fresh checkout of HEAD (git archive). The step-validator and the ACadSharp converter are built
# in the clean daemon from pinned inputs. The LibreDWG image is GPL and is built in libviprs/pvec-oracle-libredwg,
# never from a context here: it is moved into the clean daemon by `docker save | docker load` from a local image
# on the host, and used by id. Nothing is pushed anywhere and no credential is read or copied. Results (the
# generated revision, the release candidate, the run report) come back as a tar under $RESULTS (default .out-r2-<arch>).
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
host=${1:?mars|mercury}; shift || true
lr=${LIBREDWG_LOCAL:?LIBREDWG_LOCAL: a local image on the host}
case $host in
  mars)    ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR devshell@192.168.0.100); dk=docker; arch=amd64; label=native-x64 ;;
  mercury) ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR mercury); dk=/opt/homebrew/bin/docker; arch=arm64; label=native-arm64 ;;
  *) echo "host?" >&2; exit 2 ;;
esac
keep=0; [ "${1:-}" = "--keep" ] && keep=1
plat=linux/$arch
d=gold-r2-$arch-$$
r() { "${ssh[@]}" "$@"; }
dd() { r "$dk exec -i $d $*"; }
trap '[ "$keep" = 1 ] || r "$dk rm -f -v $d >/dev/null 2>&1; true"' EXIT
r "$dk run -d --rm --privileged --platform $plat --name $d -e DOCKER_TLS_CERTDIR= docker:27-dind >/dev/null"
for i in $(seq 1 60); do dd docker info >/dev/null 2>&1 && break; sleep 2; done
echo "daemon images before: $(dd docker images -q | wc -l | tr -d ' ')"
git -C "$here" archive --format=tar HEAD | r "$dk exec -i $d sh -c 'mkdir -p /tree && tar -xf - -C /tree'"
r "$dk save $lr | $dk exec -i $d docker load" >/dev/null
lrid=$(dd docker images -q | head -1)
dd "docker tag $lrid pvec-oracle-libredwg:local"
dd "docker build -q --platform $plat -f /tree/docker/step-validator/Dockerfile --target final -t pvec-gold/step-validator:local /tree" >/dev/null
dd "docker build -q --platform $plat -f /tree/tools/converters/acadsharp/Dockerfile -t pvec-gold/dwg2step-acadsharp:local /tree" >/dev/null
dd "docker build -q --platform $plat -f /tree/docker/fixture-runner/Dockerfile -t gold-fixture-runner /tree" >/dev/null
set +e
dd "docker run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v /tree:/tree -w /tree --entrypoint python3 \
  -e GOLD_TREE=/tree -e FIXTURE_DIR=/tree/.out-r2/stage/fixtures -e ACADSHARP_PLATFORM=$plat -e LIBREDWG_PLATFORM=$plat -e VALIDATOR_PLATFORM=$plat \
  gold-fixture-runner -m runner.r2_open run /tree/.out-r2 --label $label"
rc=$?
set -e
res=${RESULTS:-$here/.out-r2-$arch}; mkdir -p "$res"
dd "tar -cf - -C /tree/.out-r2 corpus release reproducibility.r2-open.json run-a" | tar -xf - -C "$res" || true
echo "daemon images after: $(dd docker images --format '{{.Repository}}:{{.Tag}}' | tr '\n' ' ')"
exit $rc
