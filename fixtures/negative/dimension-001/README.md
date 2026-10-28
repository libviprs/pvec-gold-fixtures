# dimension-001

dimension-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. A dimension is an annotation whose lines and arrowheads live in a generated anonymous block and a style. v1 has no annotation entity and does not explode one. The drawing holds one DIMENSION entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
