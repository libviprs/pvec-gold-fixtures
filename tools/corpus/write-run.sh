#!/bin/sh
# Runs inside the rust container, with the repo tree at /work. Builds corpus-writer, writes every edge,
# mixed, degenerate and negative DWG twice (to check the writer is deterministic) and compares them.
set -eu
cd /work/tools/corpus/writer
export CARGO_TARGET_DIR=/tmp/target CARGO_HOME=/tmp/cargo
cargo build --release -q
B=/tmp/target/release/corpus-writer
VER=${1:-AC1032}
OUT=/work/.out-corpus/$VER
rm -rf "$OUT"
mkdir -p "$OUT/run1" "$OUT/run2"
$B all --root /work --out "$OUT/run1" --version "$VER" >/dev/null
$B all --root /work --out "$OUT/run2" --version "$VER" >/dev/null
n=0; same=0
for f in $(cd "$OUT/run1" && find . -name source.dwg | sort); do
  n=$((n+1))
  if cmp -s "$OUT/run1/$f" "$OUT/run2/$f"; then same=$((same+1)); echo "deterministic $f"; else echo "DIFFERS $f"; fi
done
echo "$same of $n identical"
for g in edge mixed degenerate; do
  for d in "$OUT"/run1/$g/*/; do
    $B read --dwg "$d/source.dwg" --out "$d/read.acadrust.json" || echo "READFAIL $d"
  done
done
