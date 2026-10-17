# nonuniform-scale-circle-001

A circle of radius 2 scaled by (3, 1, 1). The exact result is an ellipse with semi-major axis 6 along x and semi-minor axis 2. A converter that returns a circle is wrong, not merely different.

I authored this probe from `tools/authoring/params/transforms/nonuniform-scale-circle-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
