#!/usr/bin/env bash
# A clean-host run: a native docker host with none of this repository's images cached rebuilds them from
# pinned inputs and regenerates the corpus's derived artifacts with one command (runner/reproduce.py).
#
#   tools/clean_host.sh mars|mercury [--against MANIFEST] [--write-release DIR] [--keep]
#
# "Clean" is a fresh docker daemon, not a prune: a throw-away docker-in-docker daemon starts with an empty
# image store, so every base image is pulled again and every layer is built again, and nothing on the host
# (or another job's images) is touched. The tree is a fresh checkout of HEAD (git archive), copied into
# that daemon's filesystem. A driver container with the daemon's socket runs the one command. Results come
# back as a tar of reports/ and the release directory. The daemon and everything in it is removed at the end.
# mars is native x86_64, mercury native arm64. No credential is read, written or copied: the pinned inputs
# are public images and public source. Nothing runs on this machine but ssh and git.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
host=${1:?mars|mercury}; shift || true
case $host in
  mars)    ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR devshell@192.168.0.100); dk=docker; arch=amd64; label=native-x64 ;;
  mercury) ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR mercury); dk=/opt/homebrew/bin/docker; arch=arm64; label=native-arm64 ;;
  *) echo "host?" >&2; exit 2 ;;
esac
against=""; release=""; keep=0
while [ $# -gt 0 ]; do case $1 in
  --against) against=$2; shift 2 ;; --write-release) release=$2; shift 2 ;; --keep) keep=1; shift ;; *) echo "arg?" >&2; exit 2 ;; esac; done
plat=linux/$arch
d=gold-clean-$arch-$$
r() { "${ssh[@]}" "$@"; }
dd() { r "$dk exec -i $d $*"; }
cleanup() { [ "$keep" = 1 ] || r "$dk rm -f -v $d >/dev/null 2>&1; true"; }
trap cleanup EXIT
r "$dk run -d --rm --privileged --platform $plat --name $d -e DOCKER_TLS_CERTDIR= docker:27-dind >/dev/null"
for i in $(seq 1 60); do dd docker info >/dev/null 2>&1 && break; sleep 2; done
echo "daemon images before: $(dd docker images -q | wc -l | tr -d ' ')"
# fresh checkout of HEAD into the clean daemon, and the driver image built there from scratch
git -C "$here" archive --format=tar HEAD | r "$dk exec -i $d sh -c 'mkdir -p /tree && tar -xf - -C /tree'"
dd "docker build -q --platform $plat -f /tree/tools/converters/acadsharp/driver.Dockerfile -t gold-driver /tree" >/dev/null 2>&1 || {
  # driver.Dockerfile copies requirements.txt relative to its context; build with a tiny context
  dd "sh -c 'mkdir -p /ctx && cp /tree/requirements.txt /tree/tools/converters/acadsharp/driver.Dockerfile /ctx/ && docker build -q --platform $plat -f /ctx/driver.Dockerfile -t gold-driver /ctx'" >/dev/null; }
args="--label $label --platform $plat --out /tree/.out-repro/run"
[ -n "$against" ] && args="$args --against /tree/$against"
[ -n "$release" ] && args="$args --write-release /tree/$release"
set +e
dd "docker run --rm --platform $plat -v /var/run/docker.sock:/var/run/docker.sock -v /tree:/tree -w /tree -e GOLD_TREE=/tree gold-driver python3 -m runner.reproduce run $args"
rc=$?
set -e
res=${RESULTS:-$here/.out-clean-$arch}; mkdir -p "$res"
dd "tar -cf - -C /tree/.out-repro/run reproducibility.json" | tar -xf - -C "$res" || true
[ -n "$release" ] && { dd "tar -cf - -C /tree $release" | tar -xf - -C "$res" || true; }
echo "daemon images after: $(dd docker images --format '{{.Repository}}:{{.Tag}}' | tr '\n' ' ')"
exit $rc
