# Final corpus audit: r0-open

I walked the four registers once by hand before the freeze. The scope is the open route (`oracle_scope: NONE` on the
corpus, one open converter behind the STEP files), because nothing else exists here; what needs a licence is in
[docs/vendor-deferred.md](../docs/vendor-deferred.md).

**Audited:** corpus revision `r0-open`, bundle SHA-256 `b0e3377be9581fac4c0e172982bdeb3319f93c95383428823097ef82918c3eeb`,
manifest SHA-256 `aaa7fcac8eeecd5e0e60dd7084ca40601df9194967107cd0330ab3f515b98ace`; release candidate
`corpus/release/r0-open-1` (not tagged). Images: base digests are in the release manifest. The built image ids differ on
every build (see [docs/reproducibility.md](../docs/reproducibility.md)), so the ids of the audited runs are in
`reports/reproducibility.json` (`dwg2step-acadsharp` `sha256:43587c3a...`, `step-validator` `sha256:474a4af8...`, native x64).

## 1. Quarantine register

Quarantined fixtures: **0**. `corpus/r0-open/quarantine.json` has an empty `quarantined` list, so no entry has an unknown
or empty reason. It also lists three probes excluded with no DWG, each with a named reason and its evidence:

| probe | reason | decision |
|---|---|---|
| `general-affine-001` | `UNSUPPORTED_ENTITY` (no single INSERT form carries a general matrix) | retain the exclusion |
| `shear-001` | `UNSUPPORTED_ENTITY` (the same) | retain the exclusion |
| `singular-001` | `UNSUPPORTED_ENTITY` (the writer rewrites a zero scale to 1e-12) | retain the exclusion |

These three decisions are mine as the auditor and the repository owner (spdrman) clears or confirms them by merging this
audit; nothing was resolved or removed. One accepted fixture needs saying plainly: `near-singular-001` is accepted for
reader mapping, its authored outcome is a rejection (`NEAR_SINGULAR_TRANSFORM`), and the converter refuses it with
exit 15 in every clean-host run. Its release entry is under `refused`, with no STEP and no signature.

## 2. Approximation register

Entries: **0 claimed**. Reader-mapping comparisons are EXACT for 968 fields and POLICY (PVec numeric policy v1) for 68
derived fields (an arc's end angle, an ellipse's major axis, an INSERT's rotation), all `ok`. A policy comparison records
pass or fail, not the measured deviation, so there is no per-field bound to quote. On the STEP side no geometric
comparison against a second converter exists (O2.5 and O2.6 are not built), so no `BOUNDED_APPROXIMATION` was
measured, and I am not claiming there is none: **the STEP-side bound is unmeasured**. No approximation is in the release,
so none blocks the freeze, and the measurement is a gap for the vendor or second-open-converter route.

## 3. Negative-suite and unsupported-type register

The negative and unsupported suite (issue 18, O2.8) is not built. What this corpus observes: the three exclusions above,
`near-singular-001`, and the converter's own refusals documented in `docs/converters/acadsharp-dwg2step.md` (MINSERT
arrays, nesting deeper than 64, a spline with fit points only, inches and feet). Entity types the converter skips (text,
hatches, dimensions) do not occur in any r0-open probe. Adding those to O2.8's suite is not done here.

## 4. Provenance register

All 30 fixtures are `SYNTHETIC_AUTHORED` and `PUBLIC_REDISTRIBUTABLE`, re-confirmed against
`corpus/r0-open/manifest.json`. There are no real-world fixtures (`corpus/provenance.json` does not exist; issue 11 is
open), so none was removed for a missing licence. `tools/vendor_guard.sh --tree` is clean: no vendor bytes, licence file
or key-shaped string.

## Converter discrepancies

One converter ran, so no cross-converter discrepancy was classified and none produced a quarantine. The only discrepancy
is architectural: on native arm64, 10 of 29 signatures differ from the frozen native x86_64 ones in the last digits
(`bspline-d3-001`, `ellipse-001`, `elliptical-arc-001`, `large-coords-001`, `lwpolyline-closed-001`, `nonunit-weight-001`,
`polyline-001`, `polyline2d-001`, `rotation-irrational-001`, `translation-001`), with byte-identical STEP and the same
normaliser. The frozen set is x64 only, and the reproducibility hashes are x64 only.

## Capability certification

Evidence for each PVec v1 capability (the list `runner/qualify_probes.py` carries from `libviprs/pvec` `docs/ISO_PROFILE.md`).
No capability rests on converter agreement, because no fixture is `DUAL_ORACLE_EQUIVALENT`. None is certified exact on
the STEP route.

| capability | fixtures | class | what it supports |
|---|---|---|---|
| line | 1 | `KNOWN_TRUTH_EXACT`, reader mapping only | the DWG carries the authored numbers |
| polyline | 4 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| circle | 2 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| ellipse | 1 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| trimmed_curve | 2 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| composite_curve | 2 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| bezier | 1 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| bspline | 5 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| nurbs | 3 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |
| affine_transform | 8 | `KNOWN_TRUTH_EXACT`, reader mapping only | the same |

The STEP files and signatures are regression artifacts of one open converter. They say what `dwg2step-acadsharp`
wrote, not that a STEP route is exact, and nothing here says CAD Exchanger or ODA agree.

## Per fixture

| fixture | capabilities | class | scope | provenance | licence | cross-read |
|---|---|---|---|---|---|---|
| arc-seam-001 | trimmed_curve | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| bezier-d3-001 | bezier | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| bspline-d3-001 | bspline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| bspline-d5-001 | bspline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| bulge-arc-001 | composite_curve | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| bulge-arc-neg-001 | composite_curve | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| circle-001 | circle | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| closed-by-endpoint-001 | bspline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| closed-periodic-001 | bspline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| ellipse-001 | ellipse | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| elliptical-arc-001 | trimmed_curve | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| large-coords-001 | polyline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| layer-state-001 |  | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| line-001 | line | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| lwpolyline-closed-001 | polyline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| near-singular-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nested-blocks-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nonuniform-scale-circle-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nonuniform-scale-rotated-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nonunit-weight-001 | nurbs | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nurbs-d2-offconic-001 | nurbs | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| nurbs-d3-001 | nurbs | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| polyline-001 | polyline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| polyline2d-001 | polyline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| reflection-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| repeated-knot-c0-001 | bspline | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| rotation-irrational-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| tiny-radius-001 | circle | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| translation-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |
| uniform-scale-001 | affine_transform | KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | SYNTHETIC_AUTHORED | PUBLIC_REDISTRIBUTABLE | AGREE |

## Conclusion

The audit admits a freeze of `r0-open-1` as an open-scope candidate: no unknown quarantine reason, no unbounded
approximation claim, a verdict on every fixture, and a clean second clean-host run. It does not admit any claim beyond
reader mapping, and the three gaps (STEP-side bounds, the O2.8 suite, vendor rows) are carried to
`docs/vendor-deferred.md`.
