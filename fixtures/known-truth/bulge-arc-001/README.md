# bulge-arc-001

Two polyline vertices joined by a bulge of 2/5. The included angle is 4*atan(0.4), about 87.2 degrees, close to a quarter circle (bulge tan(pi/8), about 0.4142) but not one, and nowhere near a half circle (bulge 1), so a converter that snaps to either shows.

I authored this probe from `tools/authoring/params/bulge-arc-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
