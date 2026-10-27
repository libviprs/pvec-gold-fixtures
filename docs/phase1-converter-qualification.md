# Phase 1: converter qualification and the exit gate

Status: **not run. Both converters are missing**, so no probe has a class yet and the exit gate is
red. What's here is the machinery, tested on stand-in records, and the exact list of what's left.

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
bound what v1 can claim. Today that list is empty only because nothing has been run.

## The exit gate

`python3 -m runner.phase1_gate` checks three named things and is green only if all three are:

1. `probe-classification`: every probe is classified for both converters in
   `reports/phase1/probe-qualification.json`, every cell cites its evidence, every bounded
   approximation carries its bound and parameter, and the policy version matches.
2. `evaluator-selftest`: the hand-known primitives are reproduced and the mutations are caught.
3. `expected-math-roundtrip`: every `expected.math.json` validates and the worked example round-trips
   through the evaluator's output field for field.

Checks 2 and 3 need the `step_eval` binary, so they run in the step-validator image. On native x86_64
(MARS) those two are green and check 1 is red, because there is no report. Phase 2 issues cite this
gate.

## What is verified without the converters

`tests/test_qualify.py` runs the classification on stand-in outputs derived from the expected records,
and checks that identical records are `STRUCTURAL_EXACT`, a reparameterisation and an arc written as a
rational quadratic are `GEOMETRIC_EXACT_REPARAMETERIZED`, a weight renormalised to 1 and a 32-gon for a
circle are `BOUNDED_APPROXIMATION` with a measured bound (the polygon's matches its sagitta), a reversed
line is flagged `REVERSED`, and the rejection probes are judged by expectation. Every one of the 29
probes also goes through the machinery against its own expected record. None of that says anything
about what either converter actually does.

## What is left

1. The CAD Exchanger and ODA images (`docs/converters/*-qualification.md` list the exact blockers).
2. `source.dwg` for each probe, written by the ODA Drawings SDK writer.
3. Running both converters on every probe on native x86_64, evaluating both outputs with `step_eval`,
   and `python3 -m runner.qualify_probes --primary cadex DIR --secondary oda DIR --lineage cadex=NAME --lineage oda=NAME`.
4. The probe-by-converter matrix and the per-capability verdict table, written into this file from the
   report, with every cell's deciding evidence.
5. A statement of which PVec v1 capabilities have no exact representation (phase 2 blockers).
6. The exit statement: no mass generation until both converters, the evaluator and the known-truth
   method pass the pathological probe suite.
