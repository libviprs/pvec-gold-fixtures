# The independent STEP evaluator

`step_eval` reads a STEP file with Open CASCADE (OCCT) and writes a `*.verification.json`
describing every curve it finds. Both converter outputs (`primary.step`, `secondary.step`) go
through this one program, so neither converter is its own witness, and the program itself is
checked against STEP files I wrote by hand.

It lives in `validator/src/step_eval.cpp`, builds in the `step-validator` image
(`docker/step-validator/Dockerfile`), and has no converter SDK, licence or credential in it.

## What it reports

Per curve: the semantic class (`line`, `circle`, `circular_arc`, `ellipse`, `elliptical_arc`,
`bezier`, `bspline`, `nurbs`, or `unsupported` with the OCCT type name), the geometry using the same
field names as `expected.math.json` (centre, axes, radius, degree, control points, knots with
multiplicities, weights, `weights_all_unit`), the parameter domain, closure, the composed transform
(row-major 4x4, same convention as the expected record), and samples: a point, unit tangent and
curvature at 17 uniform parameters plus every distinct interior knot. At an interior knot where the
curve is only C0 (multiplicity at least the degree) the tangent is not evaluated, and at C1 (one
less) the curvature is not; the sample says why, and the entity lists the C0 parameters under
`derivative_exclusions`.

Scalars are `{decimal, f64_hex}` exactly as in `docs/fixtures/expected-math.md`. The decimal is the
shortest text that round-trips, so `1.0` appears as `1` here and as `1.0` in the Python-written
records. The bits are what's compared, never the spelling.

The output also carries the OCCT version, the evaluator version and the numeric policy version id it
was told to stamp (`--policy-version`). The schema is `validator/schema/verification.schema.json`,
which points at the definitions in `schema/expected.math.schema.json` rather than copying them.

## No tolerance in it

The evaluator never decides two numbers are equal. The only comparisons are exact ones on stored
values (a weight equal to 1.0, a trimmed span equal to 2*pi in f64, a first and last pole identical).
The sample count (16 intervals) is a count, not a threshold. Verdicts come from the vendored
numeric policy, in the harness and later in the comparison stages.

## Why it's independent (input to ADR 0004)

OCCT is a separately developed, open source geometry kernel. The claim is that its STEP reader
shares no code with either converter path: CAD Exchanger's reader and writer are the vendor's, and
ODA's STEP SDK is ODA's. What I haven't done is verify that against each vendor's own component
list, and the claim shouldn't be frozen in ADR 0004 until someone has (CAD Exchanger's history
includes Open CASCADE people, and I haven't checked whether any current build links OCCT). If either
converter does link OCCT, the evaluator stops being independent of it for that path, and the
alternative is a second, non-OCCT reader for that path only.

## Self-test

`fixtures/validator-selftest/` has hand-written STEP files for a line, circle, ellipse, a trimmed
circular arc, a B-spline and a rational B-spline, with `*.expected.json` holding values I worked out
by hand (the derivation is in each file, and `tools/authoring/selftest_expected.py` only turns the
exact rationals into f64). Nothing in them comes from `step_eval`.

`validator/selftest.py` runs the evaluator on each file. Stored values (control points, knots,
weights) must come back bit for bit. Derived values (line ends, directions, sample points, tangents,
curvature) are compared with the vendored policy at the fixture's scale. With `--mutation-check` it
also edits the STEP text (an interior knot, one weight, all weights to 1), and the run fails if the
self-test stays green on any of them. The rational case separates real weights from the
renormalised form: at u = 0.5 the rational curve passes through (2.6, 2.4), and with all weights 1 it
would pass through (2, 2.25).

The `final` stage of the Dockerfile runs this, with `--mutation-check`, against
`policy/pvec-numeric-policy.*.json`, so the image build fails if a primitive isn't reproduced, if a
mutation is not caught, or if no policy has been vendored (the `COPY` has nothing to copy). Each
comparison uses the policy's NP-04 scale term: the entity's feature size for geometry and sample
points, 1 for unit tangents, a curvature's own magnitude, and the domain width for parameters and
angles. Stored values are compared bit for bit regardless.

## Cross-platform

The Debian package pins OCCT to 7.6.3+dfsg1-7 on arm64 and x86_64, `-ffp-contract=off` stops fused
multiply-add from differing between the two, and `validator/compare_platforms.py` diffs two output
directories on every `f64_hex`. Native x64 results are from MARS; arm64 results come from a local
arm64 container.

## Open points for O1.8

- As far as I know OCCT reads closed STEP B-splines as non-periodic (I haven't exercised it), so `closed_by_knots`/`periodic` (the knot-defined
  kind) can't survive a STEP round trip as such. A converter has to write a clamped spline with
  repeated end poles, and the evaluator reports it as `closed_by_endpoint`. That matters for the
  closed-periodic probe and is for O1.8 to classify.
- I expect a STEP polyline to arrive as separate line edges (not exercised yet).
- `gp_Trsf` carries translation, rotation, uniform scale and mirror, not a general affine map. How a
  non-uniform scale on an instance is represented in converter output hasn't been exercised yet
  (no converter output exists in this repository), so I haven't claimed anything about it.

## Cross-platform result (measured)

I ran the same six self-test files through the image on native x86_64 (MARS) and on arm64 (a local
arm64 container) and diffed every `f64_hex` with `validator/compare_platforms.py`. Of 1219 values,
1208 are identical, including every stored value (control points, knots, weights, centres, radii,
axes) and every sample point. The 11 that diverge are all in `rational-bspline`: tangent
components at samples 5, 8, 9 and 15, and curvature at samples 5, 9, 11, 12, 13 and 15. They are
last-digit differences, from 1 ulp up to about 9 ulp in the largest curvature value. These are
derived derivative values from OCCT's rational evaluation; my guess is that the distribution's OCCT
library is compiled with a different floating-point contraction on arm64, but I haven't checked
that. They fall well inside what the policy comparison is for, and nothing downstream may compare
derived samples bit for bit across platforms.
