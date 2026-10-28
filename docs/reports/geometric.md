# Geometric report

A reparameterised or differently represented curve can still be the same geometry. The geometric report
measures that instead of assuming it. It never says anything about structural exactness, and neither
word is ever used for display fidelity, which is a separate conformance class.

```
python3 -m runner.compare_geometric expected.math.json primary.signature.json geometric.primary.json
```

Schema: `schema/geometric-report.schema.json` (`pvec-gold/geometric-report/1`). Reads a signature and
`expected.math.json`; refused without the latter.

## Quantities

Per matched entity: both endpoints (a reversed curve is recognised and reported as `REVERSED`), the
maximum deviation between the two curves in both directions, arc length, and unit tangent and curvature at
the signature's samples. For the fixture: the bounding box of the union. If the entity counts differ, the
two sets are compared as sets as well (`union_curve_deviation`), which is how a flattened block can come
out geometrically equal.

Every quantity is a record with `deviation` (a number), `unit`, `at_unit_parameter` (where it occurred, in
[0, 1] on the curve that was sampled), `tolerance` (the policy's NP-04 triple at the feature scale, and
nothing else) and `admitted`. A verdict without those four is not written.

The deviation is found by adaptive sampling: the policy's `adaptive_max_deviation` doubles the sampling
until the estimate stops moving by more than the policy's own tolerance. The record carries the
refinement level, the sample count at that level, and `converged`. A last golden-section refinement runs
around the best sample.

Two measurements have an error of their own, and I record it instead of hiding it: arc length is a
polygon length extrapolated from n and 2n segments, and curvature on a spline is a finite difference. Both
write `estimator_error`, and a value is admitted within `tolerance` plus that error. Circles, arcs and
lines use the closed form for curvature, so their error is 0.

## Derivative exclusions

Derivatives are not compared at a C0 knot (multiplicity at least the degree, NP-14), at a polyline vertex,
or inside the finite-difference stencil of a knot that is not smooth enough for the order asked (C1 for
tangents, C2 for curvature) or of a domain end. Each is listed by name: `derivative_exclusions` per
entity (from the expected geometry, so a fixture with a full-multiplicity interior knot always lists it),
and `samples_excluded` for the signature's own samples with the reason. Curvature is only compared where
the curve is C2. Tangents and curvature are of the curve in its own frame, the transform being a separate
fact.

## Class

`GEOMETRIC_EXACT_REPARAMETERIZED` when everything is admitted. `BOUNDED_APPROXIMATION` with `bound` (the
largest measured deviation, in metres) otherwise. `UNSUPPORTED` and `MISSING` when the signature carries a
curve this evaluator cannot place, or nothing at all. The report records the policy version, the signature
schema version, and the architecture of the stage.
