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
  significant digits and `precision` is 12. `f64_hex` of such a scalar is the bits of the
  rounded decimal, not what the evaluator computed, so a consumer that wants the evaluator's
  own bits cannot get them from a signature; only stored values are bit-for-bit.

Rounding is what absorbs the last-digit differences OCCT's rational evaluation shows between
arm64 and x86_64 (see `docs/validator/step-evaluator.md`), but it does not remove them in every
case, and I would rather say where it fails than let the byte equality look stronger than it is:

- A value near a rounding boundary can split. `1.234567890125` rounds to `1.23456789012e+0`,
  and the next f64 up rounds to `1.23456789013e+0`. If two architectures differ by one ulp on a
  value that sits that close to a boundary, the signatures differ. Because entities are sorted
  by a hash that includes their samples, one such value can also change the entity order.
- Noise around zero is not absorbed. Twelve significant digits are relative, so `0` and `1e-17`
  stay different. A true zero on one architecture and rounding noise on the other (tangent
  components of an axis-aligned curve are the likely place) would split. I haven't seen this
  across architectures, but I haven't ruled it out.
- Byte equality across architectures is measured on six files only: the self-test files in
  `fixtures/validator-selftest/`, where all six signatures were identical on native x86_64 and
  native arm64. It is not a guarantee for other inputs.

So a consumer compares derived scalars under the numeric policy tolerance, never by bytes across
architectures. Byte equality is a same-architecture property (regenerating gives the same file)
plus those six measured cases. Stored values are exact and can be compared bit for bit.

There is no tolerance anywhere. The signature rounds to a fixed number of digits, which is a
format, not a comparison; whether two signatures are equivalent under the numeric policy is for
the comparison stage.

## Arc length and bounds are not carried

The tracker text for O2.4 lists arc length and bounds among the evaluated signatures. The
`step_eval` record has neither, and the normaliser only reads that record, so signature v1
carries samples and no arc length or bounds. This costs the consumers nothing:
`plan_from_signature` needs the class, structure, geometry, domain, closure, composed transform
and samples, and anything else a consumer wants (a bound, a length) it derives from the geometry
and the samples. If an arc length or bounds ever have to be in the signature, the way to add
them is a change to the evaluator, so that OCCT computes them and they appear in the
verification record, followed by a schema version bump here. The normaliser does not compute
geometry of its own.

## Checks

`tests/test_normalize.py` covers the acceptance criteria of issue 49:

- renumbering every `#nnn` and shuffling the DATA section of each self-test file leaves the
  signature byte-identical (this one needs `step_eval`, so it runs in the step-validator image).
  Every self-test STEP file holds a single curve, so this test does not exercise entity ordering;
  that is covered at record level, with two entities combined by hand and flipped (a two-curve STEP
  file would close the gap and is not there yet);
- a zero or negative `scale_to_canonical` is refused with a message, not a traceback;
- one moved knot, weight or control point changes the signature, and the differing field is named;
- no field carries an entity id, a file offset or a converter name;
- every scalar declares `precision` equal to its digits;
- the arm64 and x86_64 signatures of the self-test files are identical, or the test names the
  field that differs. The raw `step_eval` records from both architectures are committed in
  `fixtures/validator-selftest/verification/{x64,arm64}/`, so this runs anywhere.
