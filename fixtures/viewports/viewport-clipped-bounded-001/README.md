# viewport-clipped-bounded-001

The same line and viewport, but the clip is recorded as bounded only: a reader that reports just the bounding box of the clip is right, and one that reports the polygon is also right. Nothing may report a clip outside the bounds.

I authored this probe from `tools/authoring/params-r3/viewport-clipped-bounded-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
