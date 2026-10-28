# zero-radius-001

A CIRCLE of radius 0 at (3, 2, 0). It is a point, and a circle of radius zero has no normal frame.

I authored this from `tools/authoring/corpus-params/degenerate/zero-radius-001.json`. It is the degenerate case: the expected outcome is the refusal `DEGENERATE_ZERO_RADIUS`, with no geometry emitted. It has no `expected.math.json` because the record validator rejects a zero-length line, a zero radius and a spline with no extent, which is the point. The DWG carries the entity as authored.
