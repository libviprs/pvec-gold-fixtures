# hatch-001

hatch-001: IGNORED.

I authored the expectation before writing the DWG: `IGNORED`. A pattern fill is presentation. It has no stroke of its own and the boundary it fills is not asserted as a curve, so v1 drops it by policy. The drawing holds one HATCH entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
