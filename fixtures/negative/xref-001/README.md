# xref-001

xref-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. An external reference points at geometry in another file that the pipeline does not resolve. It is recognised and refused. The drawing holds one XREF entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
