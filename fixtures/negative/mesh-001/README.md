# mesh-001

mesh-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. A subdivision mesh is faceted surface geometry, outside the 2D profile. It is recognised and refused. The drawing holds one MESH entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
