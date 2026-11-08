# layout-plot-settings-inch-001

A layout with plot settings in inches: ANSI B (11 by 17 inches, stored as 279.4 by 431.8 millimetres), no rotation, plot scale 1:96, margins 0.25 mm all round and plot origin (0.5, 0.75) mm (a DWG keeps margins and origin in millimetres whatever the paper unit), lineweights printed and the acad.ctb style table named. One viewport and a paper-space border line. Every plot setting has to survive.

I authored this probe from `tools/authoring/params-r3/layout-plot-settings-inch-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
