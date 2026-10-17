# general-affine-001

A line under a general affine map (mixed rotation, scale, shear and translation). As with the shear, a DWG INSERT cannot carry it, so the expected outcome is an unrepresentable classification and quarantine.

I authored this probe from `tools/authoring/params/transforms/general-affine-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
