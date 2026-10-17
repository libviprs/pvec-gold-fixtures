# uniform-scale-001

A circle scaled uniformly by 2.5, so the expected result is a circle with the centre and radius scaled.

I authored this probe from `tools/authoring/params/transforms/uniform-scale-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
