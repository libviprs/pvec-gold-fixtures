# ADR 0001: evidence classes

Status: frozen at the phase 1 exit gate (`docs/phase1-converter-qualification.md`, open route, 2026-10-28).
Panel finding answered: 1 (dual-converter agreement is not absolute truth) and 2 (add independently
specified source mathematics).

## Context

Four repositories read this corpus (`pvec`, `libviprs`, `maplibre-pvec` and this one), and they need
one vocabulary for how much a fixture proves. Without it, "the two converters agree" and "the
mathematics is known" get used as if they meant the same thing, and the first is much weaker than the
second.

## Decision

Every fixture carries exactly one evidence class. This is the only place the classes are defined;
every other document refers to them by name.

- `KNOWN_TRUTH_EXACT`: a synthetic fixture whose expected mathematics was specified independently of
  any converter (ADR 0002) and whose converted output agrees with it. It is the only class that proves
  that a source representation survived exactly.
- `DUAL_ORACLE_EQUIVALENT`: both converters, read by the independent evaluator (ADR 0004), agree
  geometrically, and the original source parameters are not independently known. It has
  interoperability and regression value. It is not proof.
- `REAL_WORLD_DIFFERENTIAL`: a real, production-style DWG kept for regression and for detecting
  differences between providers. It carries provenance and a licence classification, and it may live
  in a private fixture pack.
- `QUARANTINED`: an unresolved material disagreement, an unsupported entity, an approximation, a
  malformed fixture, or a licensing or provenance problem (ADR 0006).

Exactness is a statement about structure and about geometry, and the two are kept separate. The
conformance classes themselves (structural exactness, geometric exactness, display fidelity) belong
to EPIC P in `libviprs/pvec#1` and are cited here, never redefined. A display-fidelity result is never
described as mathematically exact, in any document of this repository.

## Consequences

A claim of exactness can be traced to a `KNOWN_TRUTH_EXACT` fixture and nothing weaker. Converter
agreement alone can never promote a fixture to that class. Adding a class is an ADR.
