# mtext-001

mtext-001: IGNORED.

I authored the expectation before writing the DWG: `IGNORED`. Multiline text is not geometry v1 carries, and no glyph outline is promised. It is dropped by policy. The drawing holds one MTEXT entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
