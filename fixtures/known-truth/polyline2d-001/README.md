# polyline2d-001

The same idea as polyline-001 but written as an old-style 2D POLYLINE entity (a header, VERTEX records and a SEQEND), not a lightweight polyline. Five vertices that are neither sorted nor symmetric, all bulges zero.

I authored this probe from `tools/authoring/params/polyline2d-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
