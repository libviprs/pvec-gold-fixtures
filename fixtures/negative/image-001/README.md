# image-001

image-001: IGNORED.

I authored the expectation before writing the DWG: `IGNORED`. A raster image is an external pixel reference, not vector geometry. v1 drops it by policy. The drawing holds one IMAGE entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
