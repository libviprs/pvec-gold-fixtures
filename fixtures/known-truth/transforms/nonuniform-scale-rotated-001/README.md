# nonuniform-scale-rotated-001

The same circle under a rotation (cos 0.6, sin 0.8) applied after the scale (3, 1, 1), so the ellipse carries a rotation: its major axis points along (0.6, 0.8).

I authored this probe from `tools/authoring/params/transforms/nonuniform-scale-rotated-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
