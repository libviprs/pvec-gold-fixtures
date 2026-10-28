# hatch-gradient-001

hatch-gradient-001: IGNORED.

I authored the expectation before writing the DWG: `IGNORED`. A gradient fill is presentation with a colour ramp on top of a hatch. v1 drops it by policy and never renders a ramp. The drawing holds one HATCH entity with a gradient and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
