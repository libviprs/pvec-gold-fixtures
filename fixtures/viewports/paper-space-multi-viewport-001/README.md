# paper-space-multi-viewport-001

One paper-space layout with twenty rectangular viewports in a grid, each looking at a different part of the same model-space line. The count and each viewport's rectangle and view have to survive.

I authored this probe from `tools/authoring/params-r3/paper-space-multi-viewport-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
