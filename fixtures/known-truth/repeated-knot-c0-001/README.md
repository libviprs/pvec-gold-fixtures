# repeated-knot-c0-001

A clamped cubic B-spline with the interior knot 0.5 at full multiplicity 3, which makes a C0 join. Derivatives at 0.5 are excluded from comparison and listed in derivative_exclusions.

I authored this probe from `tools/authoring/params/repeated-knot-c0-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
