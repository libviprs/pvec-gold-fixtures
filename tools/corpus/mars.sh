#!/usr/bin/env bash
# Run a command for the corpus tooling on MARS (native x86_64) in a throw-away container.
#   tools/corpus/mars.sh push                      copy the tree to the scratch dir
#   tools/corpus/mars.sh run <image> <cmd...>      run in <image> with the tree at /work
#   tools/corpus/mars.sh pull <remote-rel> <local> copy a directory back out of the scratch dir
#   tools/corpus/mars.sh done                      remove the scratch tree
# Everything executes in a container; the host only sees ssh, docker and the scratch directory.
set -euo pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
nas=$here/../tools/nas.sh
[ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
host=${NAS:-devshell@192.168.0.100}
name=gold-corpus
ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR "$host")
cmd=${1:-}; shift || true
case $cmd in
  push) "$nas" push "$here" "$name" ;;
  run) img=$1; shift; "$nas" run "$name" "$img" "$*" ;;
  pull) tar_dir=$1; dest=$2; mkdir -p "$dest"
        "${ssh[@]}" "tar -cf - -C /work/nas-work/$name/$tar_dir ." | tar -xf - -C "$dest" ;;
  done) "$nas" clean "$name" ;;
  *) sed -n '2,8p' "$0" >&2; exit 2 ;;
esac
