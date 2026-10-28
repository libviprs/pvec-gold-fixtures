# rotation-irrational-001

A line rotated about z by exactly 1 radian. Sine and cosine of 1 are irrational, so the matrix entries are rounded f64 and a rounded matrix is visible against the exact world result.

I authored this probe from `tools/authoring/params/transforms/rotation-irrational-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
