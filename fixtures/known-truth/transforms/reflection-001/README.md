# reflection-001

A counter-clockwise arc reflected across the y axis (x to -x), determinant -1. Start maps to start, so the parameter direction is kept while the sense about the source normal flips to clockwise. A silent reversal fails.

I authored this probe from `tools/authoring/params/transforms/reflection-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
