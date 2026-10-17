#!/bin/sh
# Stop the build, loudly, unless both ODA SDK artifacts are present and are the pinned ones.
# Never downloads, never falls back to another version.
set -eu
ctx=${1:?context mount}
for pair in "ODA_DRAWINGS_ARTIFACT ODA_DRAWINGS_SHA256 drawings" "ODA_STEP_ARTIFACT ODA_STEP_SHA256 step"; do
  set -- $pair
  eval name=\${$1:-} want=\${$2:-}
  [ -n "$name" ] && [ -n "$want" ] || { echo "oda-converter: set --build-arg $1 and $2 (the pinned SDK build)." >&2; exit 1; }
  f="$ctx/vendor/oda/$name"
  [ -f "$f" ] || { echo "oda-converter: SDK artifact vendor/oda/$name is missing. ODA members download it; this build never fetches or substitutes one." >&2; exit 1; }
  got=$(sha256sum "$f" | cut -d' ' -f1)
  [ "$got" = "$want" ] || { echo "oda-converter: vendor/oda/$name has SHA-256 $got, but the pinned build is $want. Refusing to use a different SDK." >&2; exit 1; }
  echo "oda-converter: $3 SDK artifact $name matches its pinned SHA-256"
done
