#!/bin/sh
# Runs inside the rust container, with the repo tree at /work. Builds the r0-open tool (acadrust at its pin) and has
# acadrust's DwgReader dump every DWG that dwgwrite produced for the version.
set -eu
V=${1:?version}
cd /work/tools/r0-open/rust
export CARGO_TARGET_DIR=/tmp/target CARGO_HOME=/tmp/cargo
cargo build --release -q
for d in /work/.out-wf-libredwg/$V/run1/*/; do
  [ -f "$d/source.dwg" ] || continue
  /tmp/target/release/r0open read --dwg "$d/source.dwg" --out "$d/acadrust.read.json" || echo "READFAIL $(basename "$d")"
done
