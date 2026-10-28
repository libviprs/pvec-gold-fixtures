# solid3d-001

solid3d-001: UNSUPPORTED.

I authored the expectation before writing the DWG: `UNSUPPORTED`. An ACIS solid is three-dimensional boundary-representation data, outside the 2D profile. It is recognised and refused. The drawing holds one 3DSOLID entity and nothing else, so any geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`.
