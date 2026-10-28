# general-affine-chain-001

A line under a general affine map (mixed rotation, scale, shear and translation), carried as a four-level INSERT chain: a translation, then the rotation, non-uniform scale and rotation of the 2x2 part's singular value decomposition. A single INSERT cannot store the map, the chain reaches the same world-space line. The angles and scales are derived values (tools/authoring/chain_svd.py), compared under PVec numeric policy v1 and not exact.

I authored this edge case from `tools/authoring/corpus-params/edge/general-affine-chain-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
