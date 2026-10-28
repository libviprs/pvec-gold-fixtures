# Validation and comparison cost

Issue 20 (O3.2). Measured by `bench/validation/run.py` inside the step-validator image (`--target test`: `step_eval`, python, jsonschema), 7 repeats per fixture, over the 29 accepted `r0-open` fixtures. Raw record: `reports/bench/validation.json`.

- **native x86_64**: host `mars`. **native arm64**: host `mercury`. Both native, no emulation. Every number below is labelled with its architecture.
- Versions measured: evaluator 1, OCCT 7.6.3, numeric policy PVec numeric policy v1 (identical on both).

## Stages

| stage | what it times |
|---|---|
| load | `step_eval` on the retained STEP: OCCT reads the file and the evaluator samples every curve. One binary, so reading and evaluating are not separable from outside |
| normalise | `runner.normalize` plus the schema and scalar checks on the signature |
| structural | `runner.structural.structural_diff` of the derived signature against the frozen one, entity by entity |
| report | building and serialising the comparison report |
| adaptive_geometric | **not measured**: no adaptive geometric comparison stage exists in this repository (O2.5 and O2.6 are not built), so there is no converged sample count to report. Listed in `docs/vendor-deferred.md` as waiting on that work, not on a licence |

## Per fixture (median ms)

| fixture | x64 load | x64 normalise | x64 structural | x64 report | arm64 load | arm64 normalise | arm64 structural | arm64 report |
|---|---|---|---|---|---|---|---|---|
| arc-seam-001 | 18.19 | 7.53 | 0.07 | 0.13 | 13.36 | 6.12 | 0.05 | 0.07 |
| bezier-d3-001 | 15.43 | 6.61 | 0.06 | 0.11 | 13.44 | 6.25 | 0.06 | 0.07 |
| bspline-d3-001 | 13.31 | 7.39 | 0.08 | 0.09 | 13.40 | 7.19 | 0.09 | 0.07 |
| bspline-d5-001 | 16.24 | 12.00 | 0.10 | 0.10 | 13.47 | 7.68 | 0.10 | 0.07 |
| bulge-arc-001 | 20.34 | 8.01 | 0.05 | 0.11 | 13.34 | 6.17 | 0.05 | 0.07 |
| bulge-arc-neg-001 | 14.67 | 6.34 | 0.04 | 0.09 | 13.36 | 6.17 | 0.05 | 0.07 |
| circle-001 | 14.69 | 8.88 | 0.05 | 0.12 | 13.38 | 6.11 | 0.05 | 0.07 |
| closed-by-endpoint-001 | 14.97 | 7.19 | 0.08 | 0.09 | 13.47 | 6.62 | 0.09 | 0.07 |
| closed-periodic-001 | 16.20 | 10.22 | 0.08 | 0.10 | 13.39 | 7.76 | 0.09 | 0.07 |
| ellipse-001 | 14.23 | 6.40 | 0.04 | 0.12 | 13.39 | 6.16 | 0.05 | 0.08 |
| elliptical-arc-001 | 17.22 | 7.70 | 0.05 | 0.10 | 13.40 | 6.24 | 0.05 | 0.08 |
| large-coords-001 | 17.03 | 17.87 | 0.07 | 0.11 | 13.73 | 17.00 | 0.08 | 0.08 |
| layer-state-001 | 13.78 | 18.15 | 0.07 | 0.09 | 13.43 | 16.96 | 0.08 | 0.07 |
| line-001 | 17.08 | 6.66 | 0.04 | 0.12 | 13.30 | 6.01 | 0.03 | 0.07 |
| lwpolyline-closed-001 | 15.34 | 23.75 | 0.09 | 0.10 | 13.62 | 22.45 | 0.10 | 0.09 |
| nested-blocks-001 | 16.88 | 7.74 | 0.04 | 0.12 | 13.41 | 5.95 | 0.03 | 0.07 |
| nonuniform-scale-circle-001 | 16.51 | 6.60 | 0.05 | 0.12 | 13.34 | 6.13 | 0.05 | 0.07 |
| nonuniform-scale-rotated-001 | 14.97 | 6.44 | 0.04 | 0.09 | 13.44 | 6.16 | 0.05 | 0.07 |
| nonunit-weight-001 | 14.29 | 7.45 | 0.08 | 0.09 | 13.46 | 7.11 | 0.09 | 0.07 |
| nurbs-d2-offconic-001 | 13.78 | 7.52 | 0.08 | 0.12 | 13.42 | 7.10 | 0.09 | 0.07 |
| nurbs-d3-001 | 15.37 | 7.55 | 0.08 | 0.09 | 13.42 | 7.20 | 0.10 | 0.07 |
| polyline-001 | 15.25 | 23.95 | 0.09 | 0.10 | 13.61 | 22.42 | 0.10 | 0.08 |
| polyline2d-001 | 14.63 | 23.91 | 0.09 | 0.10 | 13.52 | 22.37 | 0.10 | 0.08 |
| reflection-001 | 17.10 | 7.30 | 0.05 | 0.09 | 13.51 | 6.23 | 0.05 | 0.07 |
| repeated-knot-c0-001 | 12.42 | 6.73 | 0.08 | 0.09 | 13.37 | 6.51 | 0.08 | 0.07 |
| rotation-irrational-001 | 16.54 | 8.79 | 0.03 | 0.10 | 13.40 | 6.03 | 0.03 | 0.08 |
| tiny-radius-001 | 14.49 | 6.34 | 0.04 | 0.09 | 13.32 | 6.19 | 0.04 | 0.07 |
| translation-001 | 16.80 | 11.59 | 0.04 | 0.12 | 13.26 | 6.01 | 0.03 | 0.08 |
| uniform-scale-001 | 14.19 | 8.59 | 0.04 | 0.11 | 13.39 | 6.13 | 0.04 | 0.07 |

## Ten most expensive fixtures (native x86_64)

| fixture | total ms | structural reason |
|---|---|---|
| polyline-001 | 39.39 | 4 entities and 68 evaluated samples |
| lwpolyline-closed-001 | 39.27 | 4 entities and 68 evaluated samples |
| polyline2d-001 | 38.73 | 4 entities and 68 evaluated samples |
| large-coords-001 | 35.08 | 3 entities and 51 evaluated samples, coordinates up to 1e+07 m |
| layer-state-001 | 32.08 | 3 entities and 51 evaluated samples |
| translation-001 | 28.56 | 1 entities and 17 evaluated samples, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| bulge-arc-001 | 28.52 | 1 entities and 17 evaluated samples, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| bspline-d5-001 | 28.44 | 1 entities and 20 evaluated samples, up to 9 control points, knot multiplicity up to 6, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| closed-periodic-001 | 26.60 | 1 entities and 21 evaluated samples, up to 6 control points, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| arc-seam-001 | 25.92 | 1 entities and 17 evaluated samples, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |

## Ten most expensive fixtures (native arm64)

| fixture | total ms | structural reason |
|---|---|---|
| lwpolyline-closed-001 | 36.26 | 4 entities and 68 evaluated samples |
| polyline-001 | 36.22 | 4 entities and 68 evaluated samples |
| polyline2d-001 | 36.08 | 4 entities and 68 evaluated samples |
| large-coords-001 | 30.89 | 3 entities and 51 evaluated samples, coordinates up to 1e+07 m |
| layer-state-001 | 30.54 | 3 entities and 51 evaluated samples |
| bspline-d5-001 | 21.33 | 1 entities and 20 evaluated samples, up to 9 control points, knot multiplicity up to 6, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| closed-periodic-001 | 21.31 | 1 entities and 21 evaluated samples, up to 6 control points, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| nurbs-d3-001 | 20.79 | 1 entities and 19 evaluated samples, up to 6 control points, knot multiplicity up to 4, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| bspline-d3-001 | 20.75 | 1 entities and 19 evaluated samples, up to 7 control points, knot multiplicity up to 4, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |
| nonunit-weight-001 | 20.73 | 1 entities and 19 evaluated samples, up to 5 control points, knot multiplicity up to 3, no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost) |

Every fixture pays a floor of about 13 ms to start `step_eval` and about 6 ms of fixed normalise cost. Above that, the cost follows the number of entities and evaluated samples (17 uniform parameters plus every distinct interior knot, per entity), and it lands in normalise: the polylines, with one entity per segment, are the five most expensive on both architectures. Control-point count, knot multiplicity and coordinate magnitude do not show at these sizes (`large-coords-001` is expensive because it has three entities). Below the top five the fixtures sit within noise of the floor, which is why those rows say there is no structural reason. Costs on `mars`, a shared host, vary by a few ms run to run.

## Signature path against STEP path

Over all 29 accepted fixtures, medians summed: STEP path (load + normalise + structural + report) **752.0 ms** native x86_64 and 649.9 ms native arm64; signature path (manifest and hash check, JSON parse, structural compare, no OCCT) **7.36 ms** native x86_64 and 9.59 ms native arm64. That is **102x** on x86_64 (68x on arm64). The signature path here includes the hash check; its structural comparison is of the signature against itself, which is what a consumer asserting a frozen value does.

The STEP path also needs OCCT and an image; the signature path needs python and the standard library.

## Across architectures

The STEP files are byte identical on both (the converter runs with `SOURCE_DATE_EPOCH` fixed). The signatures are not: 19 of 29 are identical, and the rest diverge only in the fields listed. All of them are last-digit differences in values OCCT evaluates (line ends through a transform, an ellipse's major axis, sample points on rational curves, anything near 1e7 m); stored control points, knots and weights agree everywhere. The structural verdict of the arm64 re-derivation against the frozen x86_64 signature is `STRUCTURAL_DIFFERS` for exactly these fixtures and `STRUCTURAL_EXACT` for the rest.
I did not change the normaliser to hide them (that is O2.4 and out of scope here); the consequence is that the frozen signatures are the native x86_64 ones and `verify_signatures` is run there.

| fixture | differing fields | first fields (entity.field) |
|---|---|---|
| bspline-d3-001 | 1 | entities[0].samples[18].point[1] |
| ellipse-001 | 2 | entities[0].geometry.major_axis[0]; entities[0].geometry.major_axis[1] |
| elliptical-arc-001 | 2 | entities[0].geometry.major_axis[0]; entities[0].geometry.major_axis[1] |
| large-coords-001 | 226 | entities[0].geometry.end[0]; entities[0].geometry.end[1]; entities[0].geometry.start[0] ... |
| lwpolyline-closed-001 | 182 | entities[1].geometry.end[0]; entities[1].geometry.end[1]; entities[1].samples[16].point[0] ... |
| nonunit-weight-001 | 1 | entities[0].samples[18].point[1] |
| polyline-001 | 179 | entities[0].geometry.end[0]; entities[1].geometry.end[0]; entities[1].geometry.end[1] ... |
| polyline2d-001 | 179 | entities[0].geometry.end[0]; entities[0].geometry.end[1]; entities[0].geometry.start[0] ... |
| rotation-irrational-001 | 1 | entities[0].geometry.end[0] |
| translation-001 | 1 | entities[0].geometry.end[1] |

## Drift check, exercised

`python3 -m runner.verify_signatures signatures` on native x86_64: 29 of 29 signatures re-derived identically. With one `f64_hex` of `line-001` changed (manifest rewritten to match, so only the re-derivation can notice) it exits 1 and prints `DRIFT line-001: entities[0].geometry.start[0]`. On native arm64 against the x86_64 set it reports the divergences above (19 of 29 identical).
