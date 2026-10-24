# layer-state-001

One drawing with three lines, each on its own layer: SHOWN_L (on, thawed), OFF_L (off, thawed) and FROZEN_L (on, frozen). Each line is different, so a mapper that drops or moves the wrong one is visible. This records what the DWG says about layer state. Whether an off or frozen layer is drawn is libviprs policy and not a PVec capability.

I authored this probe from `tools/authoring/params/layer-state-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.
