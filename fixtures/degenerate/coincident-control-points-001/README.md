# coincident-control-points-001

A clamped cubic SPLINE whose four control points are all (1, 1, 0). Its image is a single point however it is parameterised.

I authored this from `tools/authoring/corpus-params/degenerate/coincident-control-points-001.json`. It is the degenerate case: the expected outcome is the refusal `DEGENERATE_COINCIDENT_CONTROL_POINTS`, with no geometry emitted. It has no `expected.math.json` because the record validator rejects a zero-length line, a zero radius and a spline with no extent, which is the point. The DWG carries the entity as authored.
