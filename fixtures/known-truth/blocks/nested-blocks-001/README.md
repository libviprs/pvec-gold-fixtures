# nested-blocks-001

A line inside three nested block instances: an outer translation (4, 1, 0), a middle 90 degree rotation, and an inner scale (2, 1, 1). The three do not commute, so the multiplication order decides the world coordinates.

I authored this probe from `tools/authoring/params/blocks/nested-blocks-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.

`source.dwg` isn't here yet. It gets written from the same parameters by the ODA Drawings SDK writer in `oda-converter` (O1.2), which needs a licensed SDK I don't have, so this directory has the record without the drawing.

## Multiplication order

The stated chain is outermost first and composes with the parent on the left, so the world matrix is M0 * M1 * ... * Mn. The line's start and end land at (3.75, 2.0, 0.0) and (1.5, 8.5, 0.0).
Composing in the other order (Mn * ... * M0) puts them at (-2.5, 4.5, 0.0) and (-7.0, 7.75, 0.0), a different place, so a converter that flattens in the wrong order is caught.
