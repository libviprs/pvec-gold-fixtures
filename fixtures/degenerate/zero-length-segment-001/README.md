# zero-length-segment-001

A LINE whose start and end are the same point (2.5, 1.5, 0). It has no direction, so there is no curve to carry.

I authored this from `tools/authoring/corpus-params/degenerate/zero-length-segment-001.json`. It is the degenerate case: the expected outcome is the refusal `DEGENERATE_ZERO_LENGTH_SEGMENT`, with no geometry emitted. It has no `expected.math.json` because the record validator rejects a zero-length line, a zero radius and a spline with no extent, which is the point. The DWG carries the entity as authored.
