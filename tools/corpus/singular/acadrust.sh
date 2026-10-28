#!/bin/sh
# Runs inside the rust container, with the repo tree at /work. Builds singular-tool against the pinned acadrust commit,
# writes singular-001's DWG twice from its parameter file (to show it is deterministic) and has acadrust's DwgReader dump it.
set -eu
cd /work/tools/corpus/singular/tool
export CARGO_TARGET_DIR=/tmp/target CARGO_HOME=/tmp/cargo
cargo build --release -q
B=/tmp/target/release/singular-tool
OUT=/work/.out-singular
rm -rf "$OUT"; mkdir -p "$OUT/run1" "$OUT/run2" /tmp/params
cp /work/tools/authoring/params/transforms/singular-001.json /tmp/params/
$B write --kt /work/fixtures/known-truth --params /tmp/params --out /tmp/w1 >/dev/null
$B write --kt /work/fixtures/known-truth --params /tmp/params --out /tmp/w2 >/dev/null
cp /tmp/w1/singular-001/source.dwg "$OUT/run1/source.dwg"; cp /tmp/w1/write-report.json "$OUT/run1/write-report.json"
cp /tmp/w2/singular-001/source.dwg "$OUT/run2/source.dwg"
cmp "$OUT/run1/source.dwg" "$OUT/run2/source.dwg" && echo "deterministic: the two writes are byte-identical"
$B read --dwg "$OUT/run1/source.dwg" --out "$OUT/run1/acadrust.read.json"
cp Cargo.lock "$OUT/Cargo.lock"
