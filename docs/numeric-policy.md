# Numeric policy

I don't define any tolerance in this repository. The numeric policy for `pvec`, `libviprs`,
`maplibre-pvec` and this repo is defined exactly once, by `P1.2` in `libviprs/pvec#1`
(`libviprs/pvec#27`, merged as `docs/NUMERIC_POLICY.md` in `libviprs/pvec`), and this repo adopts a
version of it. If a fixture is accepted, it's because it met the same bar the library has to meet,
not because the corpus was more forgiving. The citation form is `PVec numeric policy v1, NP-nn`.

## What is adopted

- `policy/pvec-numeric-policy.v1.json` holds the constants (`ABS`, `REL`, `ULP`, `WEIGHT_FLOOR`,
  `AXIS_RATIO_MAX`, `MAX_ABS_COORD`), the version id `PVec numeric policy v1`, and where they came
  from (pvec commit, the document's SHA-256). It is the only place a numeric threshold may exist
  here, and `runner/check_tolerance_literals.py` fails on any other.
- pvec publishes the constants as a table in the document and as Rust consts, not as a data file, so
  the JSON is a transcription of that table and not a byte copy of anything. `runner.check_vendored_policy`
  parses the table from a copy of the document and fails if a number or the hash differs
  (`python3 -m runner.check_vendored_policy NUMERIC_POLICY.md`). It would be tidier if pvec
  published the file itself, and that's a request for pvec, not something I should do from here.
- The version id goes into every `comparison.json`, every `*.verification.json` and the corpus
  manifest. `numeric.policy_stamp()` builds the field, `runner/step_eval.py` stamps it onto
  evaluator output, and `python3 -m runner.check_policy_stamp FILE...` fails on any artifact whose
  version differs. `comparison.json` and the manifest are written by phase 2 and use the same helper.
- Adopting a new revision is a version bump in `policy/`, plus a report of the accept and quarantine
  outcomes that changed, with counts: `python3 -m runner.policy_bump OLD.json NEW.json` prints them
  from two lists of `{fixture, outcome}`.

## What this repo may decide, and what it may not

I'm allowed to decide which comparisons run: which curves to sample, where, in which parameter
space, and what the evidence classes say about the outcome. I'm not allowed to decide any number that
makes two values count as equal.

`runner/numeric.py` implements the policy's own rules and nothing beyond them:

- NP-04 `tol(scale, mag) = max(ABS, REL * |scale|, ULP * ulp(mag))` and NP-05 `near`
- NP-06 degenerate length, NP-13 unit parameter map, NP-16 which derivatives exist at a knot
- units normalisation to the canonical unit, exact in rational arithmetic and rounded once
- derivative exclusions at C0 knots (full multiplicity, NP-14), enumerated per fixture. A fixture
  with a C0 join must list the parameter, and the expected-record validator derives the required
  list from the knots and vertices.
- an adaptive deviation check that doubles the sampling until the estimate moves by no more than
  the policy's own `near` at the feature scale. That stability criterion is the policy's tolerance
  reused, not a new number; the refinement cap is an iteration count.

The scale term in NP-04 is "the size of the feature being compared". `numeric.feature_scale()` is
my reading of that for each curve class (a segment's length, an arc's radius, an ellipse's
semi-major axis, a polyline's longest segment, and the control-point bounding-box diagonal for
Beziers and splines). The spline choice is mine and not the policy's, so it's worth a look when P2.6
compares real curves.

## Things in the policy that touch the probes

- NP-18 says PVec is exactly 2D, while the probes are 3D with `z = 0` (and `translation-001` and
  `uniform-scale-001` move or scale along z). A 2D comparison can't see z. I left the probes as they
  are, since DWG and STEP are 3D, and the 2D projection is for the comparison stage to state.
- NP-19 refuses an affine map whose `|ad - bc| <= REL * big^2`. The near-singular probe has
  determinant about 1e-12 with `big = 1`, which the policy refuses as singular, so its expected
  `NEAR_SINGULAR` quarantine is consistent with it.
- NP-01 refuses subnormals and NP-02 refuses `|x| > 2^40`; the large-coordinate probe sits at 1e7.

## The repository check

`python3 -m runner.check_tolerance_literals` fails when a small float literal, or a numeric constant
bound to a name like `eps`, `tol` or `tolerance`, shows up anywhere outside `policy/`.
`tests/test_numeric.py` runs it over the whole repo and exercises the mutation once: a bare constant
in a scratch tree turns it red.

The conformance classes (structural exactness, geometric exactness, display fidelity) are EPIC P's.
They are cited here and never redefined.
