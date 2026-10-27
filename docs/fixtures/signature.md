# signature.json

A signature is what a STEP file means, with everything that is only about how it was written
taken out. Two converters can write the same curve with different entity numbers, a different
DATA order and different ids, and a text comparison would call that a difference. The signature
doesn't, because it never sees any of it: `runner/normalize.py` reads the `step_eval`
verification record (the only STEP reader in the pipeline) and writes
`<fixture>/{primary,secondary}.signature.json`. Nothing downstream reads STEP text.

```
python3 -m runner.normalize primary.verification.json primary.signature.json
```

The schema is `schema/signature.schema.json`, `pvec-gold/signature/1`. As with the other
records, the relations JSON Schema can't say (decimal against `f64_hex`, `precision` against the
digits of the decimal) are checked by `runner/normalize.py` right after the schema passes.

## Shape

```json
{
  "schema_version": "pvec-gold/signature/1",
  "versions": { "evaluator": "1", "occt": "7.6.3", "schema": "pvec-gold/signature/1", "policy": "PVec numeric policy v1" },
  "units": { "canonical": "metre" },
  "entities": [ { "class": "bspline", "structure": "CURVE_ONLY", "geometry": {}, "parameter_domain": {},
                  "closure": {}, "transform": {}, "samples": [], "derivative_exclusions": [] } ]
}
```

Per entity: the semantic class (`line`, `polyline`, `circle`, `circular_arc`, `ellipse`,
`elliptical_arc`, `bezier`, `bspline`, `nurbs`, or `unsupported` with the OCCT type name), the
geometry with the same field names as `expected.math.json` (degree, control points, knots with
multiplicities, weights, centre, axes, radius), the parameter domain, closure, the composed
transform in the row-major, column-vector, parent-left convention, and the evaluated samples
(point, unit tangent, curvature at the evaluator's sample parameters, with the reason when a
derivative is not evaluated).

The versions block carries the evaluator version, the OCCT version, the numeric policy version
that was stamped into the record, and the signature schema version.

## What is dropped, on purpose

- Entity ids, STEP entity numbers, file offsets and comment text. No field and no string value
  holds one, and the schema refuses an `id`.
- Anything that names a converter. The record doesn't know which converter wrote the file, and
  the signature has nowhere to put it. Which converter made which file lives in the manifest.
- The order of the entities. They are sorted by class and then by the SHA-256 of each entity's
  canonical JSON, so the order depends on content only. Lists that mean something stay in order
  (control points, knots, weights, vertices, samples by parameter).
- The sign of a zero. `-0` is written as `0`.
- The unit name. Lengths are multiplied by the record's `scale_to_canonical` (one multiplication
  per value, and a scale of exactly 1 changes nothing) and the signature says `metre`. A line's
  parameter is a length, so its domain and sample parameters are scaled too. Directions, angles,
  weights, knots and the parameters of every other class are not lengths and are left alone.

## Scalars and precision

Every number is `{ "decimal", "f64_hex", "precision" }`. `f64_hex` is the authoritative binary64
and `decimal` has to round to exactly those bits. The decimal is always scientific (`2.75e+0`),
so `precision`, the number of significant digits in its mantissa, can be read off without
guessing about trailing zeros: `2.75e+0` has 3, `5e-1` has 1, `1.23456789012e-3` has 12. The
check is that `precision` equals that count, for every scalar.

There are two kinds of value, and they are told apart by how many digits they keep:

- Stored values (control points, knots, weights, centres, radii, axes, angles, matrices,
  domains) keep their f64 bits. The decimal is the shortest text that round-trips, so
  `precision` is at most 17.
- Evaluated values (sample parameters, points, tangents, curvatures) are rounded to 12
  significant digits and `f64_hex` is the bits of that rounded decimal, so `precision` is 12.
  OCCT's rational evaluation gives last-digit differences between arm64 and x86_64 (see
  `docs/validator/step-evaluator.md`); rounding is what lets two architectures, and two
  converters that mean the same curve, produce the same signature. A value that lands exactly
  on a rounding boundary could still split across architectures, and the cross-architecture
  check below is what would show it.

There is no tolerance anywhere. The signature rounds to a fixed number of digits, which is a
format, not a comparison; whether two signatures are equivalent under the numeric policy is for
the comparison stage.

## Checks

`tests/test_normalize.py` covers the acceptance criteria of issue 49:

- renumbering every `#nnn` and shuffling the DATA section of each self-test file leaves the
  signature byte-identical (this one needs `step_eval`, so it runs in the step-validator image);
- one moved knot, weight or control point changes the signature, and the differing field is named;
- no field carries an entity id, a file offset or a converter name;
- every scalar declares `precision` equal to its digits;
- the arm64 and x86_64 signatures of the self-test files are identical, or the test names the
  field that differs. The raw `step_eval` records from both architectures are committed in
  `fixtures/validator-selftest/verification/{x64,arm64}/`, so this runs anywhere.
