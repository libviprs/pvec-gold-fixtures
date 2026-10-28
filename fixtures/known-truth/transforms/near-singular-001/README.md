# near-singular-001

A line under scale (1, 1e-12, 1), determinant about 1e-12. The expected outcome is a near-singular classification and quarantine, not a curve.

I authored this probe from `tools/authoring/params/transforms/near-singular-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
