#!/usr/bin/env bash
# Scan an image's history and every layer, and any log files, for licence material.
#
#   tools/check_no_licence.sh IMAGE [LOGFILE...]       IMAGE lives on the x86_64 build host (MARS)
#
# The image is streamed with `docker save` straight into a throw-away container that runs
# tools/scan_layers.sh, so nothing is unpacked on the host. It prints which place and which pattern
# matched and how many lines, never the matched text, so the check can't leak what it finds.
# Patterns: private key blocks, and name-then-value assignments such as licence_key=..., activation
# code: ..., serial_token=... with a 16+ character value. CANARY_PATTERN in the environment adds
# one more, which is how the check is shown to fire. Exit 1 on any match.
set -u
img=${1:?image}; shift
here=$(cd "$(dirname "$0")/.." && pwd)
nas=$here/../tools/nas.sh; [ -x "$nas" ] || nas=${NAS_SH:-/Users/rom/workspace/libviprs/tools/nas.sh}
host=${NAS:-devshell@192.168.0.100}
ssh=(ssh -o BatchMode=yes -o LogLevel=ERROR "$host")
name=gold-lic-$(basename "$here")
trap '"$nas" clean "$name" >/dev/null' EXIT
"$nas" push "$here" "$name" >/dev/null
dir=/work/nas-work/$name
"${ssh[@]}" "docker history --no-trunc --format '{{.CreatedBy}}' $img > $dir/.history.txt"
for f in "$@"; do cat "$f" | "${ssh[@]}" "cat > $dir/.log-$(basename "$f")"; done
logs=""; for f in "$@"; do logs="$logs /work/.log-$(basename "$f")"; done
"${ssh[@]}" "docker save $img | docker run --rm -i --platform linux/amd64 -v $dir:/work -e CANARY_PATTERN='${CANARY_PATTERN:-}' python:3.12-slim bash /work/tools/scan_layers.sh /work/.history.txt$logs"
