# nurbs-d3-001

A clamped cubic rational B-spline whose weights (1, 0.7, 1.8, 0.45, 1.3, 1) do not describe a conic, so renormalising them to 1 changes the curve and shows.

I authored this probe from `tools/authoring/params/nurbs-d3-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
