#!/bin/sh
# Stop the build, loudly, unless the licensee-supplied vendor artifact is present and is the one
# that was pinned. Nothing is downloaded and nothing else is ever substituted.
set -eu
ctx=${1:?context mount}
name=${CADEX_ARTIFACT:-}
want=${CADEX_SHA256:-}
ver=${CADEX_VERSION:-}
[ -n "$name" ] && [ -n "$want" ] && [ -n "$ver" ] || {
  echo "cadex-converter: set --build-arg CADEX_ARTIFACT, CADEX_SHA256 and CADEX_VERSION (the pinned vendor build)." >&2; exit 1; }
f="$ctx/vendor/cadex/$name"
[ -f "$f" ] || {
  echo "cadex-converter: vendor artifact vendor/cadex/$name is missing. The licensee supplies it; this build never fetches or substitutes one." >&2; exit 1; }
got=$(sha256sum "$f" | cut -d' ' -f1)
[ "$got" = "$want" ] || {
  echo "cadex-converter: vendor/cadex/$name has SHA-256 $got, but the pinned build is $want. Refusing to use a different artifact." >&2; exit 1; }
echo "cadex-converter: artifact $name matches pinned SHA-256 (build $ver)"
