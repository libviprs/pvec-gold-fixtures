# empty-001

empty-001: MISSING.

I authored the expectation before writing the DWG: `MISSING`. The drawing holds no entity at all, so the converter is expected to emit nothing. The drawing holds an empty drawing and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
