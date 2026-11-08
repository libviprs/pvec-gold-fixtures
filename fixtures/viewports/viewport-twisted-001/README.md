# viewport-twisted-001

One plan viewport twisted by 30 degrees about its view direction, looking at one model-space line. The twist, the view and the rectangle have to survive; the sign of the twist is what a reader has to get right.

I authored this probe from `tools/authoring/params-r3/viewport-twisted-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
