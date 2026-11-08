# viewport-non-plan-001

One viewport whose view direction is (-1, -1, 1), an isometric view and not a plan view, looking at one model-space line. The direction has to survive.

I authored this probe from `tools/authoring/params-r3/viewport-non-plan-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
