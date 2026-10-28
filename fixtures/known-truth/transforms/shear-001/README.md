# shear-001

A line under the shear x += 0.5y. A DWG INSERT carries scale, rotation and translation but no shear, so I expect the path to classify this as unrepresentable and quarantine it, not to emit a silently different curve.

I authored this probe from `tools/authoring/params/transforms/shear-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
