# shear-chain-001

A line under the shear x += 0.5y, carried as a three-level INSERT chain. A DWG stores no shear in any single INSERT, but the singular value decomposition of the 2x2 matrix is a rotation, a non-uniform scale and a rotation, so three nested INSERTs reach the same world-space line. The angles and scales are derived values (tools/authoring/chain_svd.py), compared under PVec numeric policy v1 and not exact.

I authored this edge case from `tools/authoring/corpus-params/edge/shear-chain-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
