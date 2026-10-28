# Phase 1: converter qualification and the exit gate

Status: **run on the open route** (ADR 0009, `oracle_scope: OPEN_CONVERTERS`), with one oracle: the
`acadsharp-dwg2step` converter (lineage ACadSharp, issue 48) on the 30 `r0-open` DWGs, evaluated by `step_eval`,
native x86_64 (`linux/amd64`, MARS). The exit gate is green for that scope. Nothing here says a second converter
agrees with anything. What is still open is in
[open-route-status.md](open-route-status.md). There is no second open converter in the report yet, so no cell can be
`DUAL_ORACLE_EQUIVALENT`, and the report says "single oracle" on every capability.

## What the qualification does

`runner/qualify_probes.py` takes, for every known-truth probe (`fixtures/known-truth/`) and each
converter, the normalised evaluator record (`primary.verification.json` for the primary converter,
`secondary.verification.json` for the secondary) and its converter status, and gives every expected entity one
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

Open route, one oracle (what produced the numbers below): `tools/qualify/open_route.sh mars`, which runs
`python3 -m runner.qualify_probes --primary acadsharp-dwg2step DIR --lineage acadsharp-dwg2step=ACadSharp --excluded corpus/r0-open/quarantine.json`
in a throw-away container. With the second open converter, add `--secondary ID DIR` and its lineage:
`--primary acadsharp-dwg2step DIR --secondary libredwg-dwg2step DIR --lineage acadsharp-dwg2step=ACadSharp --lineage libredwg-dwg2step=LibreDWG`.

## Probe-by-converter matrix

Converter: `acadsharp-dwg2step`, policy PVec numeric policy v1, `reports/phase1/probe-qualification.json`
(`tools/qualify/open_route.sh mars` reproduces it). The second converter column does not exist yet. The converter ran on
all 30 `r0-open` DWGs (29 converted, `near-singular-001` refused). The report has 32 probes: 28 exact, one refusal as authored,
and three never run because the open writer cannot carry them (`corpus/r0-open/quarantine.json`). `layer-state-001` records
layer state, which has no STEP form, so it stays out of the report. An entity id is shown when a probe has more than one.
Deviations are in metres, measured against the authored curve both ways.

| Probe | Entity | Class | Deciding evidence |
|---|---|---|---|
| arc-seam-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (geometry.x_axis[2]); max deviation 3.02e-15 at unit parameter 0.0555, direction SAME |
| bezier-d3-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 6 structural field(s) differ (class, geometry.knots#len...); max deviation 9.16e-16 at unit parameter 0.4305, direction SAME |
| nested-blocks-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 6 structural field(s) differ (geometry.end[0], geometry.end[1]...); max deviation 1.83e-15 at unit parameter 0.6805, direction SAME |
| bspline-d3-001 |  | STRUCTURAL_EXACT | 47 fields equal bit for bit |
| bspline-d5-001 |  | STRUCTURAL_EXACT | 55 fields equal bit for bit |
| bulge-arc-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 30 structural field(s) differ (class, geometry.bulges#len...); max deviation 2.22e-15 at unit parameter 0.6180, direction SAME |
| bulge-arc-001 | bulge-arc-001-equivalent-arc | GEOMETRIC_EXACT_REPARAMETERIZED | 4 structural field(s) differ (geometry.center[0], geometry.center[1]...); max deviation 3.23e-15 at unit parameter 0.6180, direction SAME |
| bulge-arc-neg-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 30 structural field(s) differ (class, geometry.bulges#len...); max deviation 4.37e-15 at unit parameter 0.0555, direction REVERSED |
| bulge-arc-neg-001 | bulge-arc-neg-001-equivalent-arc | GEOMETRIC_EXACT_REPARAMETERIZED | 2 structural field(s) differ (geometry.radius, geometry.x_axis[2]); max deviation 3.82e-15 at unit parameter 0.7430, direction SAME |
| circle-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (geometry.x_axis[2]); max deviation 2.66e-15 at unit parameter 0.9930, direction SAME |
| closed-by-endpoint-001 |  | STRUCTURAL_EXACT | 47 fields equal bit for bit |
| closed-periodic-001 |  | STRUCTURAL_EXACT | 47 fields equal bit for bit |
| ellipse-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (geometry.major_axis[2]); max deviation 3.20e-15 at unit parameter 0.8680, direction SAME |
| elliptical-arc-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (geometry.major_axis[2]); max deviation 1.60e-15 at unit parameter 0.8680, direction SAME |
| large-coords-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (different number of curves: 3); max deviation 1.86e-09 at unit parameter 0.6805, direction n/a |
| line-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (parameter_domain.end); max deviation 4.97e-16 at unit parameter 0.4930, direction SAME |
| lwpolyline-closed-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (different number of curves: 4); max deviation 1.78e-15 at unit parameter 0.7429, direction n/a |
| nonunit-weight-001 |  | STRUCTURAL_EXACT | 44 fields equal bit for bit |
| nurbs-d2-offconic-001 |  | STRUCTURAL_EXACT | 44 fields equal bit for bit |
| nurbs-d3-001 |  | STRUCTURAL_EXACT | 49 fields equal bit for bit |
| polyline-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (different number of curves: 4); max deviation 1.29e-15 at unit parameter 0.0182, direction n/a |
| polyline2d-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (different number of curves: 4); max deviation 2.32e-15 at unit parameter 0.9622, direction n/a |
| repeated-knot-c0-001 |  | STRUCTURAL_EXACT | 43 fields equal bit for bit |
| tiny-radius-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 1 structural field(s) differ (geometry.x_axis[2]); max deviation 1.11e-16 at unit parameter 0.1180, direction SAME |
| general-affine-001 |  | MISSING | not run: no source.dwg (UNSUPPORTED_ENTITY) |
| near-singular-001 |  | UNSUPPORTED (expectation met) | refused, exit 15 NEAR_SINGULAR_TRANSFORM (NP-19); no geometry emitted, as expected |
| nonuniform-scale-circle-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 14 structural field(s) differ (class, geometry.center[0]...); max deviation 5.33e-15 at unit parameter 0.7430, direction SAME |
| nonuniform-scale-rotated-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 15 structural field(s) differ (class, geometry.center[0]...); max deviation 5.52e-15 at unit parameter 0.7430, direction SAME |
| reflection-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 4 structural field(s) differ (geometry.center[0], geometry.normal[2]...); max deviation 8.01e-16 at unit parameter 0.6805, direction SAME |
| rotation-irrational-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 6 structural field(s) differ (geometry.end[0], geometry.end[1]...); max deviation 8.90e-16 at unit parameter 0.9305, direction SAME |
| shear-001 |  | MISSING | not run: no source.dwg (UNSUPPORTED_ENTITY) |
| singular-001 |  | MISSING | not run: no source.dwg (UNSUPPORTED_ENTITY) |
| translation-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 8 structural field(s) differ (geometry.end[0], geometry.end[1]...); max deviation 1.11e-16 at unit parameter 0.0239, direction SAME |
| uniform-scale-001 |  | GEOMETRIC_EXACT_REPARAMETERIZED | 5 structural field(s) differ (geometry.center[0], geometry.center[1]...); max deviation 3.97e-15 at unit parameter 0.7430, direction SAME |

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
| line | line-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| polyline | polyline-001, large-coords-001, lwpolyline-closed-001, polyline2d-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| circle | circle-001, tiny-radius-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| ellipse | ellipse-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| trimmed_curve | arc-seam-001, elliptical-arc-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| composite_curve | bulge-arc-001, bulge-arc-neg-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| bezier | bezier-d3-001 | GEOMETRIC_EXACT_REPARAMETERIZED | certified (geometric), single oracle |
| bspline | bspline-d3-001, bspline-d5-001, repeated-knot-c0-001, closed-by-endpoint-001, closed-periodic-001 | STRUCTURAL_EXACT | certified (structural), single oracle |
| nurbs | nurbs-d3-001, nurbs-d2-offconic-001, nonunit-weight-001 | STRUCTURAL_EXACT | certified (structural), single oracle |
| affine_transform | the 11 transform and block probes | GEOMETRIC_EXACT_REPARAMETERIZED | **blocked**: shear-001, general-affine-001 and singular-001 were not run |

The transform probes that did run (translation, irrational rotation, uniform and non-uniform scale, reflection, three-level
nested blocks) are exact, and `near-singular-001` is refused with exit 15 and `NEAR_SINGULAR_TRANSFORM`, so the converter emits
no geometry for it, which is the authored expectation. The capability stays blocked for the three probes nobody could write, and
that is the one explicit phase 2 blocker on the open route. Every other capability with a PVec v1 exact representation is
certified for this oracle only.

## What the probes discriminate

The comparison input is mutated in `tests/test_probes.py`: renormalising weights to 1, collapsing a knot and reparameterising
each change the structural class of at least three named probes, reversing a curve turns the reflection comparison red, and
`tests/test_qualify.py` shows a weight renormalisation and a 32-gon for a circle land in `BOUNDED_APPROXIMATION` with their bound. Those mutate
records, not STEP output from a converter; the run on real converter output is in [open-route-status.md](open-route-status.md).

## Exit statement

No mass generation until the converters, the evaluator and the known-truth method pass the pathological probe suite. On the open
route they do, for one oracle: `acadsharp-dwg2step` reproduces 28 of the 32 probes exactly, refuses the near-singular one as authored, and the other three were never run,
the evaluator self-test and the `expected.math.json` round trip are green, and the gate is green. That releases open-route
generation (`OPEN_CONVERTERS`) with the `affine_transform` caveat above. It does not make
anything `DUAL_ORACLE_EQUIVALENT`.
