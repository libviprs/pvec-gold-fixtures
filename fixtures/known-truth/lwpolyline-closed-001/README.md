# lwpolyline-closed-001

A closed lightweight polyline of four vertices that are neither a rectangle nor symmetric, all bulges zero. The closing segment from the last vertex back to the first is implicit, so closed-by-flag is the only thing that makes it closed, and the vertex count stays four.

I authored this probe from `tools/authoring/params/lwpolyline-closed-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, so this directory has the record without the drawing.
