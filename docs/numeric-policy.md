# Numeric policy

I don't define any tolerance in this repository. The numeric policy for `pvec`, `libviprs`,
`maplibre-pvec` and this repo is defined exactly once, by `P1.2` in `libviprs/pvec#1`
(`libviprs/pvec#27`), and this repo adopts a version of it. If a fixture is accepted, it's because
it met the same bar the library has to meet, not because the corpus was more forgiving.

## What is adopted

- The policy file lives at `policy/pvec-numeric-policy.<version>.json`, copied verbatim from `pvec`.
  It is the only place a numeric threshold may exist here.
- The version id in that file is the adopted version. It goes into every `comparison.json`, every
  `*.verification.json` and the corpus manifest, so a result always says which policy produced it.
- Adopting a new `P1.2` revision is a version bump in `policy/`, plus a report of how many accept and
  quarantine outcomes changed.

Status: `P1.2` hasn't landed in `pvec` yet, so there's no vendored file, and `runner/numeric.py`
refuses to run without one. The helpers are tested against a made-up file in
`policy/testdata/synthetic-not-p1.2.json`, which is never loaded by default and isn't the policy.
`runner/numeric.py` documents the field names it assumes (`tolerance.absolute`, `tolerance.relative`,
`tolerance.ulp`, `scale_term`, `adaptive.*`); when the real file lands the mapping is the one thing
that may need to change.

## What this repo may decide, and what it may not

I'm allowed to decide which comparisons run: which curves to sample, where, in which parameter
space, and what the evidence classes say about the outcome. I'm not allowed to decide any number
that makes two values count as equal.

`runner/numeric.py` covers the comparisons:

- units normalisation to the canonical unit, exact in rational arithmetic and rounded once
- tolerance selection from the policy's absolute, relative and ULP terms (the scale term is named
  by the policy)
- parameter-domain alignment, mapping both curves onto the unit interval before sampling
- derivative exclusion at C0 knots and curve joins, enumerated per fixture (an entity id plus the
  parameter plus a reason). A fixture with a C0 join must list the parameter or the helper fails.
- adaptive geometry checks that refine the sampling until the deviation estimate is stable by the
  policy's own criterion, and fail loudly if it never is

## The repository check

`python3 -m runner.check_tolerance_literals` fails when a small float literal, or a numeric
constant bound to a name like `eps`, `tol` or `tolerance`, shows up anywhere outside `policy/`.
`tests/test_numeric.py` runs it over the whole repo and also exercises the mutation once: a bare
constant in a scratch tree turns it red.

The conformance classes (structural exactness, geometric exactness, display fidelity) are EPIC P's.
They are cited here and never redefined.
