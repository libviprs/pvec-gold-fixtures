# large-coords-001

Four vertices with features of 1e-4 m at an origin offset of 1e7 m, so the f64 spacing there (about 1.9e-9) is what resolves them.

I authored this probe from `tools/authoring/params/large-coords-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
