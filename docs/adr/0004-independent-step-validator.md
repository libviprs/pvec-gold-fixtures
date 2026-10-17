# ADR 0004: one independent STEP validator, itself validated

Status: proposed, and **not yet freezable**: the independence claim below still needs checking
against the two vendors' own component lists. Panel finding answered: 5.

## Context

Both converter outputs have to be read by one implementation, and that implementation must not share
its reading of STEP with either converter. If it did, a shared misreading would pass silently. And an
evaluator nobody validated would define the truth of the whole corpus.

## Decision

`step_eval` (`validator/src/step_eval.cpp`) reads both outputs. It is built on Open CASCADE, pinned by
Debian package version and base-image digest, and has no converter SDK in it.

- Its claim to independence is that Open CASCADE's STEP reader shares no code with CAD Exchanger's
  reader and writer or with ODA's STEP SDK. That has to be confirmed from each vendor's component
  list before this ADR is frozen. If a converter turns out to link Open CASCADE, the evaluator is not
  independent of that path, and the remedy is a second, non-OCCT reader for that path alone.
- It is validated against hand-written STEP files for a line, circle, ellipse, trimmed arc, B-spline
  and rational B-spline, with expected values worked out by hand. The image build runs this
  self-test and stops if any primitive is not reproduced or if a mutation (a moved knot, a moved
  weight, weights renormalised to 1) is not caught.
- It defines no tolerance. It states what it read, and verdicts come from ADR 0005.

## Consequences

The validator is part of the trust base, so changing it re-runs the self-test, and its arm64 and x64
differences are named rather than hidden (`docs/validator/step-evaluator.md`).
