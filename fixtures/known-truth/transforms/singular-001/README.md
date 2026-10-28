# singular-001

A line under scale (1, 0, 1), determinant exactly 0. The expected outcome is rejection, and a pipeline that emits geometry for it fails.

I authored this probe from `tools/authoring/params/transforms/singular-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
