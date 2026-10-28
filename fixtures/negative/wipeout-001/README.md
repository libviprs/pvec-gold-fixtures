# wipeout-001

wipeout-001: IGNORED.

I authored the expectation before writing the DWG: `IGNORED`. A wipeout is a masking boundary, a display effect that draws nothing of its own. v1 drops it by policy. The drawing holds one WIPEOUT entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
