# viewport-hide-plot-001

Three viewports onto the same model line: one hidden when plotting, one whose VIEWPORT entity sits on the no-plot layer VPNOPLOT, and one that plots. Only the third prints.

I authored this probe from `tools/authoring/params-r3/viewport-hide-plot-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
