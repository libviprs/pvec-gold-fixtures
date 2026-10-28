# ole-001

ole-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. An embedded OLE object is a foreign document, not geometry. It is recognised and refused. The drawing holds one OLE2FRAME entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
