# bulge-arc-neg-001

Two polyline vertices joined by a bulge of -3/10. A negative bulge is a clockwise arc, so the sweep is negative (4*atan(-0.3), about -66.8 degrees) and the centre lies on the right of the chord. The sign is what a mapper has to get right, and the derived arc is in the record so centre, radius, start angle and sweep sign are all checkable.

I authored this probe from `tools/authoring/params/bulge-arc-neg-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
