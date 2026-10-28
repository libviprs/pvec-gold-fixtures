# Phase 1: converter qualification and the exit gate

Status: **run on the open route** (ADR 0009, `oracle_scope: OPEN_CONVERTERS`), with two oracles of different lineages:
`acadsharp-dwg2step` (ACadSharp, issue 48) and `libredwg-dwg2step` (LibreDWG, issue 65) on the 30 `r0-open` DWGs, evaluated by
`step_eval`, native x86_64 (`linux/amd64`, MARS). The exit gate is green for that scope. Nothing here says CAD Exchanger or ODA
agree with anything: the licensed converters were never run, and what they still owe is in
[vendor-deferred.md](vendor-deferred.md). The two converters agree on every cell. The first two-column run did not: `closed-periodic-001` was
`BOUNDED_APPROXIMATION` (0.092) for LibreDWG, because its converter wrapped periodic splines on a rotated basis. That was a bug in the
converter, not something to resolve with an explanation, so it is fixed there (pvec-oracle-libredwg#3) and the report is from the
run after the fix, with no `--resolved` file.

## What the qualification does

`runner/qualify_probes.py` takes, for every known-truth probe (`fixtures/known-truth/`) and each
converter, the normalised evaluator record (`primary.verification.json` for CAD Exchanger,
`secondary.verification.json` for ODA) and its converter status, and gives every expected entity one
class. It reads the evaluator records, never STEP text, evaluates curves with its own pure-Python
evaluator (`runner/curves.py`, nothing shared with the OCCT-based `step_eval`), and takes every threshold
from the adopted policy (PVec numeric policy v1, NP-04 and NP-05), whose version id is in the report.

| Class | Meaning |
|---|---|
| `STRUCTURAL_EXACT` | class, degree, control points, knots with multiplicities, weights, domain, closure (and, for an instance, the local geometry and the composed matrix) match the expected record bit for bit |
| `GEOMETRIC_EXACT_REPARAMETERIZED` | the structure differs but the curves are the same point set within the policy, both ways (a reparameterised spline, an arc written as a rational quadratic, a flattened instance). The direction is recorded as `SAME`, `REVERSED` or `UNDETERMINED` |
| `BOUNDED_APPROXIMATION` | the curves differ by more than the policy allows. The cell carries the measured bound and the unit parameter where the maximum was found, and says whether the refinement stabilised by the policy's own criterion |
| `MISSING` | the converter produced no output for the probe, or no curve in it |
| `UNSUPPORTED` | the converter reported an error, or emitted only curves this evaluator can't place |

A probe whose expected outcome is a rejection (the singular, near-singular, shear and general-affine
transforms) is judged on expectation: emitting no geometry meets it, and emitting a curve is marked
`UNEXPECTED_GEOMETRY` and fails it.

`layer-state-001` records layer state, which has no STEP form, so it is a DWG reader-mapping probe for the open-writer
corpus (ADR 0008) and is not put through the converters.

## Capability verdicts

For each PVec v1 capability (the sections of `docs/ISO_PROFILE.md` in `libviprs/pvec`) and the
probes that cover it, the report gives the worst class per converter, and a verdict:

- certified (geometric) when at least one converter gives an exact representation on every probe of
  the capability, no rejection probe was violated, and no converter discrepancy is left unresolved. A
  discrepancy is one converter exact and the other not on the same probe, and it is resolved only by
  naming the probe in a `--resolved` file with the explanation in the ADR record.
- certified (structural) when the best class is `STRUCTURAL_EXACT`.
- blocked otherwise. A capability where both converters land in `BOUNDED_APPROXIMATION` is reported as
  not certified even though they agree, in those words.

Blocked capabilities are the explicit phase 2 blockers, and they are reported to EPIC P because they
bound what v1 can claim. The open-route list is below.

## The exit gate

`python3 -m runner.phase1_gate` checks three named things and is green only if all three are:

1. `probe-classification`: every probe is classified for both converters in
   `reports/phase1/probe-qualification.json`, every cell cites its evidence, every bounded
   approximation carries its bound and parameter, and the policy version matches.
2. `evaluator-selftest`: the hand-known primitives are reproduced and the mutations are caught.
3. `expected-math-roundtrip`: every `expected.math.json` validates and the worked example round-trips
   through the evaluator's output field for field.

Checks 2 and 3 need the `step_eval` binary, so they run in the step-validator image. Phase 2 issues cite this
gate. Its open-route run is in `reports/phase1/exit-gate.txt`: all three checks green.

## What is verified without the converters

`tests/test_qualify.py` runs the classification on stand-in outputs derived from the expected records,
and checks that identical records are `STRUCTURAL_EXACT`, a reparameterisation and an arc written as a
rational quadratic are `GEOMETRIC_EXACT_REPARAMETERIZED`, a weight renormalised to 1 and a 32-gon for a
circle are `BOUNDED_APPROXIMATION` with a measured bound (the polygon's matches its sagitta), a reversed
line is flagged `REVERSED`, and the rejection probes are judged by expectation. Every one of the 29
probes also goes through the machinery against its own expected record. None of that says anything
about what either converter actually does.

## Running it

Open route, two oracles (what produced the numbers below): `LIBREDWG_IMAGE=<digest ref or local image id> tools/qualify/open_route.sh mars`,
which converts every DWG with both images and runs
`python3 -m runner.qualify_probes --primary acadsharp-dwg2step DIR --secondary libredwg-dwg2step DIR --lineage acadsharp-dwg2step=ACadSharp --lineage libredwg-dwg2step=LibreDWG --excluded corpus/r0-open/quarantine.json [--resolved reports/phase1/resolved.json]`
in a throw-away container. A cross-converter discrepancy blocks its capability until the probe is named in a resolved file as
`{"probe": ID, "explanation": TEXT}`; a bare id is refused. The LibreDWG image is built from `libviprs/pvec-oracle-libredwg`, never
from this tree, so no GPL source is a build context here (`docker-compose.yml` declares it as an image reference only).

## Probe-by-converter matrix

Converters: `acadsharp-dwg2step` (lineage ACadSharp) and `libredwg-dwg2step` (lineage LibreDWG, the `pvec-oracle-libredwg`
image, GPL-3.0-or-later, used by local image id and never built here), policy PVec numeric policy v1,
`reports/phase1/probe-qualification.json` (`LIBREDWG_IMAGE=<id> tools/qualify/open_route.sh mars` reproduces it). Both ran on all
30 `r0-open` DWGs (29 converted, `near-singular-001` refused by both). The report has 32 probes: 28 exact for both converters,
one refusal as authored, and three never run because the open writer cannot carry them (`corpus/r0-open/quarantine.json`).
`layer-state-001` records layer state, which has no STEP form, so it stays out of the report. Deviations are in metres, the
worst case against the authored curve both ways; the full evidence per cell is in the report.

| Probe | acadsharp-dwg2step | libredwg-dwg2step | Agree |
|---|---|---|---|
| arc-seam-001 | GEOMETRIC_EXACT_REPARAM. (3.0e-15) | GEOMETRIC_EXACT_REPARAM. (3.0e-15) | same |
| bezier-d3-001 | GEOMETRIC_EXACT_REPARAM. (9.2e-16) | GEOMETRIC_EXACT_REPARAM. (9.2e-16) | same |
| bspline-d3-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| bspline-d5-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| bulge-arc-001 | GEOMETRIC_EXACT_REPARAM. (2.2e-15) | GEOMETRIC_EXACT_REPARAM. (1.8e-15) | same |
| bulge-arc-001 / equivalent-arc | GEOMETRIC_EXACT_REPARAM. (3.2e-15) | GEOMETRIC_EXACT_REPARAM. (2.4e-15) | same |
| bulge-arc-neg-001 | GEOMETRIC_EXACT_REPARAM. (4.4e-15 REVERSED) | GEOMETRIC_EXACT_REPARAM. (2.8e-15) | same |
| bulge-arc-neg-001 / equivalent-arc | GEOMETRIC_EXACT_REPARAM. (3.8e-15) | GEOMETRIC_EXACT_REPARAM. (2.6e-15 REVERSED) | same |
| circle-001 | GEOMETRIC_EXACT_REPARAM. (2.7e-15) | GEOMETRIC_EXACT_REPARAM. (2.7e-15) | same |
| closed-by-endpoint-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| closed-periodic-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| ellipse-001 | GEOMETRIC_EXACT_REPARAM. (3.2e-15) | GEOMETRIC_EXACT_REPARAM. (3.2e-15) | same |
| elliptical-arc-001 | GEOMETRIC_EXACT_REPARAM. (1.6e-15) | GEOMETRIC_EXACT_REPARAM. (1.6e-15) | same |
| general-affine-001 | MISSING (not run, no source.dwg) | MISSING (not run, no source.dwg) | same |
| large-coords-001 | GEOMETRIC_EXACT_REPARAM. (1.9e-09) | GEOMETRIC_EXACT_REPARAM. (1.9e-09) | same |
| line-001 | GEOMETRIC_EXACT_REPARAM. (5.0e-16) | GEOMETRIC_EXACT_REPARAM. (5.0e-16) | same |
| lwpolyline-closed-001 | GEOMETRIC_EXACT_REPARAM. (1.8e-15) | GEOMETRIC_EXACT_REPARAM. (1.8e-15) | same |
| near-singular-001 | UNSUPPORTED (expectation met) (refused, exit 15) | UNSUPPORTED (expectation met) (refused, exit 15) | same |
| nested-blocks-001 | GEOMETRIC_EXACT_REPARAM. (1.8e-15) | GEOMETRIC_EXACT_REPARAM. (1.8e-15) | same |
| nonuniform-scale-circle-001 | GEOMETRIC_EXACT_REPARAM. (5.3e-15) | GEOMETRIC_EXACT_REPARAM. (5.3e-15) | same |
| nonuniform-scale-rotated-001 | GEOMETRIC_EXACT_REPARAM. (5.5e-15) | GEOMETRIC_EXACT_REPARAM. (5.3e-15) | same |
| nonunit-weight-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| nurbs-d2-offconic-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| nurbs-d3-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| polyline-001 | GEOMETRIC_EXACT_REPARAM. (1.3e-15) | GEOMETRIC_EXACT_REPARAM. (1.3e-15) | same |
| polyline2d-001 | GEOMETRIC_EXACT_REPARAM. (2.3e-15) | GEOMETRIC_EXACT_REPARAM. (2.3e-15) | same |
| reflection-001 | GEOMETRIC_EXACT_REPARAM. (8.0e-16) | GEOMETRIC_EXACT_REPARAM. (8.0e-16) | same |
| repeated-knot-c0-001 | STRUCTURAL_EXACT (bit for bit) | STRUCTURAL_EXACT (bit for bit) | same |
| rotation-irrational-001 | GEOMETRIC_EXACT_REPARAM. (8.9e-16) | GEOMETRIC_EXACT_REPARAM. (9.0e-16) | same |
| shear-001 | MISSING (not run, no source.dwg) | MISSING (not run, no source.dwg) | same |
| singular-001 | MISSING (not run, no source.dwg) | MISSING (not run, no source.dwg) | same |
| tiny-radius-001 | GEOMETRIC_EXACT_REPARAM. (1.1e-16) | GEOMETRIC_EXACT_REPARAM. (1.1e-16) | same |
| translation-001 | GEOMETRIC_EXACT_REPARAM. (1.1e-16) | GEOMETRIC_EXACT_REPARAM. (1.1e-16) | same |
| uniform-scale-001 | GEOMETRIC_EXACT_REPARAM. (4.0e-15) | GEOMETRIC_EXACT_REPARAM. (4.0e-15) | same |

Reading it. Nothing is `BOUNDED_APPROXIMATION`. The splines and NURBS come back bit for bit. Everything else is
`GEOMETRIC_EXACT_REPARAMETERIZED` with a worst deviation of 1.9e-9, which is one ulp-scale error at the 1e7 offset of
`large-coords-001` (the feature size is 1e-4), and 5.5e-15 or less everywhere else. A segment polyline comes back as one line
per segment, a Bezier as a B-spline, a bulge as arcs, and a non-uniform scale of a circle as the ellipse with named axes (never a
circle). `bulge-arc-neg-001` is the one probe with direction `REVERSED`: the converter writes a negative bulge counter-clockwise
from the second vertex, which is the authored equivalent arc.

A first run of this matrix showed `lwpolyline-closed-001` as `BOUNDED_APPROXIMATION` at 0.0188. The converter was right. My
nearest-point search tied the first and last samples of a closed curve and refined around the wrong end; I fixed that in
`runner/qualify_probes.py` and the test is `test_closed_polyline_written_as_separate_lines_is_exact_at_the_seam`.

## Per-capability verdicts

| Capability | Probes | Best class | Verdict |
|---|---|---|---|
| line | line-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| polyline | polyline-001, large-coords-001, lwpolyline-closed-001, polyline2d-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| circle | circle-001, tiny-radius-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| ellipse | ellipse-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| trimmed_curve | arc-seam-001, elliptical-arc-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| composite_curve | bulge-arc-001, bulge-arc-neg-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| bezier | bezier-d3-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), both oracles |
| bspline | bspline-d3-001, bspline-d5-001, repeated-knot-c0-001, closed-by-endpoint-001, closed-periodic-001 | STRUCTURAL_EXACT | certified (structural), both oracles |
| nurbs | nurbs-d3-001, nurbs-d2-offconic-001, nonunit-weight-001 | STRUCTURAL_EXACT | certified (structural), both oracles |
| affine_transform | the 11 transform and block probes | GEOMETRIC_EXACT_REPARAMETERIZED | **blocked**: shear-001, general-affine-001 and singular-001 were not run |

The transform probes that did run (translation, irrational rotation, uniform and non-uniform scale, reflection, three-level
nested blocks) are exact, and `near-singular-001` is refused with exit 15 and `NEAR_SINGULAR_TRANSFORM`, so the converter emits
no geometry for it, which is the authored expectation. The capability stays blocked for the three probes nobody could write, and
that is the one explicit phase 2 blocker on the open route. Every other capability with a PVec v1 exact representation is
certified for both oracles.

## What the probes discriminate

The comparison input is mutated in `tests/test_probes.py`: renormalising weights to 1, collapsing a knot and reparameterising
each change the structural class of at least three named probes, reversing a curve turns the reflection comparison red, and
`tests/test_qualify.py` shows a weight renormalisation and a 32-gon for a circle land in `BOUNDED_APPROXIMATION` with their bound. Those mutate
records, not STEP output from a vendor converter; the vendor version of the criterion is in [vendor-deferred.md](vendor-deferred.md).

## Exit statement

No mass generation until the converters, the evaluator and the known-truth method pass the pathological probe suite. On the open
route they do, for two oracles: `acadsharp-dwg2step` and `libredwg-dwg2step` each reproduce 28 of the 32 probes exactly, refuse the near-singular one as authored, and the other three were never run,
the evaluator self-test and the `expected.math.json` round trip are green, and the gate is green. That releases open-route
generation (`OPEN_CONVERTERS`) with the `affine_transform` caveat above. It does not release a `VENDOR_CONVERTERS` claim, and it does not make
anything `DUAL_ORACLE_EQUIVALENT`.
