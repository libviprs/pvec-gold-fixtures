# corpus changelog

## r0-open (candidate)

First revision. It exists because Epic O has no qualified vendor writer or STEP SDK, so I built it from DWGs
written by acadrust and cross-read by ACadSharp (ADR 0008).

- 26 probe DWGs, all accepted as `KNOWN_TRUTH_EXACT` for reader mapping only, none disagreed between the two
  readers.
- 3 probes excluded with a named reason: `shear-001` and `general-affine-001` (no DWG INSERT form), and
  `singular-001` (the writer rewrites a zero scale).
- Oracles: none. STEP oracle: none. No file is attributed to CAD Exchanger or ODA, and no fixture is
  `DUAL_ORACLE_EQUIVALENT`.
- The next revision is vendor-qualified (#42) and will say here why each fixture's class moved.
