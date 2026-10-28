# proxy-001

proxy-001: MISSING.

I authored the expectation before writing the DWG: `MISSING`. A proxy or custom entity is opaque application data with no decodable geometry, and a reader that cannot instantiate it returns nothing for it. The converter is expected to emit nothing, which is different from recognising and refusing it. The drawing holds one ACAD_PROXY_ENTITY entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
