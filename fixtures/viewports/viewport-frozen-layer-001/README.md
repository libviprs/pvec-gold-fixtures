# viewport-frozen-layer-001

Two viewports on one layout looking at the same model space, which has a line on WALLS and one on DOORS. DOORS is frozen in the first viewport only, so it shows in the second and not in the first.

I authored this probe from `tools/authoring/params-r3/viewport-frozen-layer-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
