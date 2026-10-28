# shear-001

A line under the shear x += 0.5y. A DWG INSERT carries scale, rotation and translation but no shear, so I expect the path to classify this as unrepresentable and quarantine it, not to emit a silently different curve.

I authored this record from `tools/authoring/params/transforms/shear-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

This is a profile only probe and it has no `source.dwg`. A single INSERT carries a translation, one rotation, three scales and no shear, so no writer can store this matrix in one INSERT and there is no DWG for this record on purpose. It is a profile-only probe: it states what pvec must do with a single stored matrix of this kind (pvec ADR 0012 and 0017). The DWG path is covered by shear-chain-001, a three-INSERT chain that reaches the same world-space line.

The drawing for the same map is `shear-chain-001` under `fixtures/edge`. It keeps this record's matrix as its chain matrix, so the two stay comparable, and it is the probe that exercises `affine_transform` through a DWG.
