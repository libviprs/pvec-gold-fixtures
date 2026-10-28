#!/bin/sh
# Runs inside the rust container, with the repo tree at /work and the run1 output of build-run.sh under
# /work/.out-wf-acadsharp/<version>. Builds the r0-open tool (acadrust at its pin) and has acadrust's DwgReader dump
# every DWG that ACadSharp's DwgWriter produced.
set -eu
VER=${1:-AC1032}
cd /work/tools/r0-open/rust
export CARGO_TARGET_DIR=/tmp/target CARGO_HOME=/tmp/cargo
cargo build --release -q
B=/tmp/target/release/r0open
OUT=/work/.out-wf-acadsharp/$VER/run1
for d in "$OUT"/*/; do
  id=$(basename "$d")
  $B read --dwg "$d/source.dwg" --out "$d/acadrust.read.json" || echo "READFAIL $id"
done
