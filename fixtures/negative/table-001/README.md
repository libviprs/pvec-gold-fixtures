# table-001

table-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. A table is a grid of generated lines and text with a style. v1 has no table entity and does not explode one. The drawing holds one ACAD_TABLE entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
