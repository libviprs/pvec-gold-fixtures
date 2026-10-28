# corpus changelog

## r2-open (candidate)

The first `STEP_ORACLE` revision (#78). It holds the 59 fixtures of `r1-open` (which lists `r0-open`'s) with the result of running both open converters, `acadsharp-dwg2step` and `libredwg-dwg2step`, over each, in a clean docker daemon (`tools/clean_host_r2.sh`). `oracle_scope` is `OPEN_CONVERTERS`. Nothing earlier is edited: `r0-open` and `r1-open` stay as they were, and `r2-open` points at their DWGs.

A fixture moves only when the run backs it. A probe with a known truth moves to `STEP_ORACLE` when both converters' output is exact or the same geometry. A fixture that is refused by design keeps `QUARANTINED` and moves its scope to `STEP_ORACLE` when both converters refused it. A real-world drawing becomes `DUAL_ORACLE_EQUIVALENT` when both converted it and the signatures agree. Everything else keeps its class and scope and the table says why. The real-world fixtures were recorded again with the inch and foot scaling in both converters (#67, #68).

<!-- r2-open-moves -->
Run counts: 59 fixtures, 51 changed class or scope, 8 kept with a reason, 0 unchanged.

| fixture | from | to |
|---|---|---|
| `arc-seam-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `arc-tiny-sweep-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `bezier-d3-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `blocks-dynamic-linear-001` | REAL_WORLD_DIFFERENTIAL / READER_CENSUS_ONLY | DUAL_ORACLE_EQUIVALENT / STEP_ORACLE |
| `bspline-d3-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `bspline-d5-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `bspline-nonunit-domain-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `bulge-arc-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `bulge-arc-neg-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `circle-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `closed-by-endpoint-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `closed-periodic-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `dimension-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `ellipse-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `elliptical-arc-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `empty-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `general-affine-chain-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `hatch-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `hatch-gradient-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `huge-extent-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `image-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `large-coords-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `line-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `lwpolyline-closed-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `mesh-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `mtext-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `near-singular-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nested-blocks-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nonuniform-scale-circle-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nonuniform-scale-rotated-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nonunit-weight-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nurbs-d2-offconic-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `nurbs-d3-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `ole-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `polyline-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `polyline2d-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `proxy-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `reflection-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `region-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `repeated-knot-c0-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `rotation-irrational-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `shear-chain-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `singular-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `solid3d-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `table-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `text-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `tiny-radius-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `translation-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `uniform-scale-001` | KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY | KNOWN_TRUTH_EXACT / STEP_ORACLE |
| `wipeout-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |
| `xref-001` | QUARANTINED / CLASSIFICATION_EXPECTED | QUARANTINED / STEP_ORACLE |

Kept as they were, with the reason the run gave:

- `arch-aecobjects-001` (REAL_WORLD_DIFFERENTIAL / READER_CENSUS_ONLY): UNSUPPORTED_ENTITY (primary: CONVERSION_FAILED; secondary: CONVERSION_FAILED)
- `coincident-control-points-001` (QUARANTINED / REJECTION_EXPECTED): primary converter drew geometry for a fixture that should be refused
- `general-sample-ac1032-001` (REAL_WORLD_DIFFERENTIAL / READER_CENSUS_ONLY): UNRESOLVED_DISAGREEMENT
- `layer-state-001` (KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY): APPROXIMATION
- `mixed-entity-001` (KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY): APPROXIMATION
- `tiny-extent-001` (KNOWN_TRUTH_EXACT / READER_MAPPING_ONLY): UNSUPPORTED_ENTITY
- `zero-length-segment-001` (QUARANTINED / REJECTION_EXPECTED): primary converter drew geometry for a fixture that should be refused
- `zero-radius-001` (QUARANTINED / REJECTION_EXPECTED): primary and secondary converter drew geometry for a fixture that should be refused
<!-- /r2-open-moves -->

## r1-open (candidate)

Adds fixtures on top of `r0-open` (included by hash) without touching it (issues #11 and #18).

- `edge`: four valid extreme and boundary cases (a spline on the domain [2, 5], a 5e-9 segment, a circle of radius
  2.5e6 centred beyond 1e6, an arc with a 1e-6 sweep). `mixed`: one drawing with seven curve classes, a three-level
  nested block chain and a uniform scale. Both are `KNOWN_TRUTH_EXACT` for reader mapping only.
- `edge` also holds `shear-chain-001` and `general-affine-chain-001` (#69): the shear x += 0.5y and the general affine map
  of the two rejection records, carried as three and four nested INSERTs (rotate, scale, rotate, with a translation first
  for the second) from the singular value decomposition of the 2x2 part. A DWG stores no shear in one INSERT, so
  `shear-001` and `general-affine-001` stay as profile-only records with no DWG and the chains are what exercise
  `affine_transform`. The angles and scales are derived values, read back under policy and not exact. Both chains agree
  across the two readers and `acadsharp-dwg2step` lands them in `GEOMETRIC_EXACT_REPARAMETERIZED`. `r0-open` is untouched.
- `edge` also holds `singular-001` (#70), the first drawing with an INSERT scale of exactly 0.0 (r0-open still lists it as
  excluded). acadrust's checked setters rewrite the zero to 1e-12, so it is written with `Insert::set_scale_unchecked` from
  libviprs/acadrust#52 (`tools/corpus/singular`). Three readers return the zero bit for bit and agree: acadrust at that commit,
  ACadSharp with the converter's zero-scale patch, and LibreDWG's `dwgdump`. `acadsharp-dwg2step` refuses it as
  `SINGULAR_TRANSFORM` and `libredwg-dwg2step` refuses it too, both with exit 15 and no STEP. `quarantine.json` no longer lists
  it as excluded, and lists `shear-001` and `general-affine-001` as `PROFILE_ONLY` (see the chain probes above).
- `degenerate`: a zero-length line, a zero-radius circle and a spline with coincident control points. They are
  `QUARANTINED` by design with an expected refusal. ACadSharp clamps a zero radius up to 1e-12, so the refusal rule
  uses NP-06 and not exact zero.
- `negative`: fifteen fixtures, one per entity class outside v1 (hatch, gradient hatch, dimension, text, MTEXT, 3D solid,
  mesh, region, proxy, OLE, wipeout, table, image, external reference) plus an empty drawing. `QUARANTINED` with reason
  `UNSUPPORTED_ENTITY`, each with an expected `UNSUPPORTED`, `IGNORED` or `MISSING`.
- `real-world`: three public drawings from ACadSharp's samples (MIT), `REAL_WORLD_DIFFERENTIAL`. The open converter
  refuses all three, for reasons recorded per fixture.
- Open converter: `acadsharp-dwg2step` ran over every fixture. It wrote no STEP for any negative fixture, and its STEP held
  evaluable geometry for two degenerate fixtures, which is listed as a failure. `oracle_scope` stays `NONE` (one converter).
- `fixtures/negative/mesh-001/source.dwg` is regenerated byte for byte (#73). acadrust's `Mesh::compute_edges` walks a
  `HashSet`, so the edge order, and the file, used to change from run to run; `corpus-writer` now sorts the edges. The
  file's hash, its census and its converter status changed once with that, and 23 of 23 DWGs of the write run are
  identical across two runs.

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
- The next revision is `r2-open` (ADR 0010) and will say here why each fixture's class moved.
