# no-plot-layer-001

A no-plot layer NOPLOT (the Defpoints idea) holding one line in model space and one in paper space, beside a line on layer 0 in each. One plain viewport shows model space. The plot flag of each layer has to survive.

I authored this probe from `tools/authoring/params-r3/no-plot-layer-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
