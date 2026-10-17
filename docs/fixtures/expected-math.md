# expected.math.json

This is the record a known-truth fixture carries to say what its DWG is supposed to mean. I wrote
it down independently of any converter, because a rounded JSON number that came out of a STEP
file would quietly turn into the oracle. Every value in one of these files comes from the
authoring parameters (see `provenance`), never from `primary.step` or `secondary.step`.

The schema is `schema/expected.math.schema.json`. A few relations can't be said in JSON Schema
(knot counts, exact determinants, decimal versus hex), so `runner/expected_math.py` checks those
right after the schema passes. The two together are the gate:

```
python3 -m runner.expected_math fixtures/known-truth/**/expected.math.json
```

Tolerances are not here. Comparing a record with evaluator output uses the numeric policy defined
once by `P1.2` in `libviprs/pvec#1`, and nothing in the schema or the validator has an epsilon.

## Canonical numbers

Every coordinate, knot, weight, angle, radius and scale is a scalar object:

```json
{ "decimal": "0.70710678118654757", "f64_hex": "0x3fe6a09e667f3bcd" }
```

`f64_hex` is the intended IEEE-754 binary64 (16 lowercase hex digits) and is the authoritative
half. `decimal` is a convenience for people, and the validator rejects any scalar whose decimal
doesn't parse, under correct round-to-nearest, to exactly those bits. A 15 digit truncation of
sqrt(1/2) (`0.707106781186548`) is rejected for that reason, and `tests/test_expected_math.py`
exercises it. Bare JSON numbers are only for integers that are exact by construction: degree,
multiplicity, counts. A bare float anywhere fails the load.

One thing worth knowing: the example in epic #1 and in issue O1.4 pairs
`0.70710678118654757` with `0x3fe6a09e667f3bcc`, but that decimal rounds to `...3bcd` (the nearest
f64 to sqrt(1/2)), so the quoted pair is off by one ulp. It is exactly the mistake this check is
for, and the pair above is the corrected one.

## Units

`units.name` is what the source drawing uses, and `units.scale_to_canonical` is the exact factor to
the canonical unit (metre) as a scalar. Coordinates in the record are in the source units, so a
reader scales explicitly rather than finding pre-scaled values.

## Entities

Each entity has an `id`, a semantic curve `class`, its `geometry`, `parameter_domain`, `closure`,
and a `structure` that says what the fixture asserts about representation (`CURVE_ONLY`,
`INSTANCE_PLUS_TRANSFORM` or `FLATTENED`).

| class | geometry fields |
|---|---|
| `line` | `start`, `end` |
| `polyline` | `vertices`, `bulges` (one per vertex, the last only used when closed) |
| `circle` | `center`, `normal`, `x_axis`, `radius` |
| `circular_arc` | circle fields plus `start_angle`, `sweep_angle` (radians, counter-clockwise about `normal`, so a seam crossing is a start near 2pi with a sweep running past it) |
| `ellipse` | `center`, `normal`, `major_axis`, `semi_major`, `semi_minor` |
| `elliptical_arc` | ellipse fields plus `start_angle`, `sweep_angle` (eccentric anomaly) |
| `bezier` | `degree`, `control_points` (degree + 1 of them) |
| `bspline` | `degree`, `control_points`, `knots` |
| `nurbs` | bspline fields plus `weights` and `weights_all_unit` |

Knots are `{value, multiplicity}` pairs, so a full-multiplicity interior knot is visible as such
and not as a run of repeated numbers. Weights are required if and only if the class is `nurbs`
(rational). A rational entity whose weights are all 1 has to say `weights_all_unit: true`, and the
validator checks the flag against the weights, so "rational but unit weights" can't be confused
with a plain B-spline by accident.

### Counting rules

- Non-periodic spline: `sum(multiplicities) == len(control_points) + degree + 1`. Interior
  multiplicities are at most `degree`, end multiplicities at most `degree + 1`, and
  `parameter_domain` lies inside the valid span (`knot[degree]` to `knot[n]` in the expanded
  vector).
- Periodic spline (`closure.periodic`): control points are the unique ones, and
  `sum(multiplicities) == len(control_points) + 1`, with equal first and last multiplicity and no
  multiplicity above `degree`.
- `closed_by_endpoint` (first control point equals the last) and `closed_by_knots` (the knot vector
  wraps) are separate on purpose. For a spline `closed_by_knots` and `periodic` agree.

## Transforms

```json
{
  "convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT",
  "matrix": [16 scalars, row-major 4x4],
  "determinant": scalar,
  "classification": "ROTATION"
}
```

The matrix acts on column vectors, `p' = M * [x y z 1]^T`, and is stored row by row, so the
translation is entries 3, 7 and 11. Nested transforms compose with the parent on the left:
`M_world = M_outer * M_inner`. A `transform_chain` lists the transforms `OUTERMOST_FIRST` plus the
`composed` matrix, and the validator recomputes the product in exact rational arithmetic from the
stated f64 values and requires the rounded result to match, so a wrong multiplication order fails.

`determinant` is the exact determinant of the stated matrix, computed rationally and rounded once
to f64. Classification has to agree: `SINGULAR` means the exact determinant is zero, `REFLECTION`
means it is negative. `NEAR_SINGULAR` is the author's claim and is only checked for being nonzero,
because what counts as near depends on the policy.

A singular or near-singular transform carries a `rejection` (`classification` plus a `REJECT` or
`QUARANTINE` `disposition`) and no `world` curve. Everything else with a transform carries
`world`, the expected curve after the transform. A circle under a non-uniform scale has to be
expected as an `ellipse`. A reflection has to record `orientation`, so a silent parameter reversal
has something to fail against.

## Provenance

`provenance.derivation` is always `AUTHORING_PARAMETERS`. It names the authoring script, the
parameter file and the file's hash, and can embed the parameters themselves. If a field can't be
traced back to those parameters, it doesn't belong in the record.

## Assertions

`assertions` lists what the fixture claims, split into `STRUCTURAL` (class, knots, weights,
transform, parameter order preserved) and `GEOMETRIC` (the world-space result, equivalent shape
under reparameterisation). The evidence classes themselves are defined once, in the ADR that O1.9
adds, and are only named here.

## Worked example

`docs/fixtures/examples/rational-bspline.expected.math.json` is a degree 2 rational B-spline with
four control points, knots 0 (x3), 0.5, 1 (x3) and weights 1, 0.5, 2, 1. The weights don't describe
a conic, so renormalising them to 1 changes the class and shows. `tools/authoring/worked_example.py`
writes it from the parameters at the top of that script, and the unit tests check that it validates.
The field names in `geometry` (`degree`, `control_points`, `knots` with multiplicities, `weights`)
and the scalar shape are the same ones the evaluator in O1.3 emits in `*.verification.json`, so the
two can be compared field for field.
