# nurbs-d2-offconic-001

A clamped quadratic NURBS with five control points and weights (1, 0.6, 1.7, 0.9, 1) that do not describe a conic.

I authored this probe from `tools/authoring/params/nurbs-d2-offconic-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
