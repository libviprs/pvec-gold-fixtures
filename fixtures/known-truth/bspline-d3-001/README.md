# bspline-d3-001

A clamped non-rational cubic B-spline with three distinct interior knots (0.35, 0.5, 0.8) of multiplicity 1.

I authored this probe from `tools/authoring/params/bspline-d3-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
