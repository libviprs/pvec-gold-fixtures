# layout-plot-settings-mm-001

A layout with plot settings in millimetres: ISO A3 (420 by 297), landscape rotation code 1, plot scale 1:50, margins 5, 6, 7 and 8 (left, bottom, right, top), plot origin (10, 12), lineweights not printed and the monochrome.ctb style table named. One viewport and a paper-space border line. Every plot setting has to survive.

I authored this probe from `tools/authoring/params-r3/layout-plot-settings-mm-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
