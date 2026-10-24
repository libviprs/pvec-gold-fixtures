# corpus changelog

## r0-open (candidate)

First revision. It exists because Epic O has no qualified vendor writer or STEP SDK, so I built it from DWGs
written by acadrust and cross-read by ACadSharp (ADR 0008).

- Probe DWGs for every curve and transform probe of O1.5a/O1.6a that a DWG can carry, plus four added with the
  revision: `bulge-arc-neg-001` (negative bulge), `lwpolyline-closed-001`, `polyline2d-001` (old-style POLYLINE)
  and `layer-state-001` (off and frozen layers). All were accepted as `KNOWN_TRUTH_EXACT` for reader mapping only,
  and none disagreed between the two readers.
- Probes excluded with a named reason and no file: `shear-001` and `general-affine-001` (no single INSERT form; a
  three-level nested chain could carry them but was not attempted), and `singular-001` (the writer rewrites a
  zero scale).
- `near-singular-001` is accepted although its record says the pipeline must reject it (`NEAR_SINGULAR_TRANSFORM`,
  quarantine). What is checked is that the DWG carries the transform as authored. It has a
  `downstream_disposition` in the manifest, and a mapper must not emit a curve for it.
- Oracles: none. STEP oracle: none. No file is attributed to CAD Exchanger or ODA, and no fixture is
  `DUAL_ORACLE_EQUIVALENT`. The two readers share a DWG specification, so a shared misreading would not show.
- The next revision is vendor-qualified (#42) and will say here why each fixture's class moved.
