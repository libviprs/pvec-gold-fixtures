# elliptical-arc-001

The same near-circular, rotated ellipse as ellipse-001, cut to an arc from 0.3 rad (eccentric anomaly) with a sweep of 2.2 rad.

I authored this probe from `tools/authoring/params/elliptical-arc-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
