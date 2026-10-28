# ADR 0004: one independent STEP validator, itself validated

Status: frozen for the open route at the phase 1 exit gate (2026-10-28). ADR 0010 removes the licensed paths, so there is nothing left to check on that side. Panel finding answered: 5.

## Context

Both converter outputs have to be read by one implementation, and that implementation must not share
its reading of STEP with either converter. If it did, a shared misreading would pass silently. And an
evaluator nobody validated would define the truth of the whole corpus.

## Decision

`step_eval` (`validator/src/step_eval.cpp`) reads both outputs. It is built on Open CASCADE, pinned by
Debian package version and base-image digest, and has no converter SDK in it.

- Its claim to independence is that Open CASCADE's STEP reader shares no code with either converter.
  Each converter entry in a manifest states `links_occt`, and anything but `false` is refused. If a
  converter ever linked Open CASCADE, the evaluator would not be independent of that path, and the
  remedy would be a second, non-OCCT reader for that path alone.
- It is validated against hand-written STEP files for a line, circle, ellipse, trimmed arc, B-spline
  and rational B-spline, with expected values worked out by hand. The image build runs this
  self-test and stops if any primitive is not reproduced or if a mutation (a moved knot, a moved
  weight, weights renormalised to 1) is not caught.
- It defines no tolerance. It states what it read, and verdicts come from ADR 0005.

## Consequences

The validator is part of the trust base, so changing it re-runs the self-test, and its arm64 and x64
differences are named rather than hidden (`docs/validator/step-evaluator.md`).

## Amendment (ADR 0009)

For the open route the independence claim is settled: neither open converter links Open CASCADE (the
ACadSharp one is C# code; LibreDWG is C, and the converter is Python over dwgread JSON), so the evaluator shares
no STEP code with either. Each converter entry in a manifest states `links_occt`, and an `OPEN_CONVERTERS`
revision with anything but `false` there is refused. That lets this ADR be frozen.

## Amendment (ADR 0010)

Only open converters are allowed, so the `links_occt` rule above is the whole independence check.
