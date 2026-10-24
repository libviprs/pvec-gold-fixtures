#!/bin/sh
# Runs inside the rust container, with the repo tree at /work. Builds r0open, writes the probe DWGs
# twice (to check the writer is deterministic), and has acadrust's own reader dump each one.
set -eu
cd /work/tools/r0-open/rust
export CARGO_TARGET_DIR=/tmp/target CARGO_HOME=/tmp/cargo
cargo build --release -q
B=/tmp/target/release/r0open
VER=${1:-AC1032}
OUT=/work/.out-r0open/$VER
rm -rf "$OUT"
mkdir -p "$OUT/run1" "$OUT/run2"
$B write --kt /work/fixtures/known-truth --params /work/tools/authoring/params --out "$OUT/run1" --version "$VER" >/dev/null
$B write --kt /work/fixtures/known-truth --params /work/tools/authoring/params --out "$OUT/run2" --version "$VER" >/dev/null
for d in "$OUT"/run1/*/; do
  id=$(basename "$d")
  if cmp -s "$OUT/run1/$id/source.dwg" "$OUT/run2/$id/source.dwg"; then echo "deterministic $id"; else echo "DIFFERS $id"; fi
  $B read --dwg "$OUT/run1/$id/source.dwg" --out "$OUT/run1/$id/acadrust.read.json" || echo "READFAIL $id"
done
