# ADR 0003: the role of the dual oracle

Status: frozen at the phase 1 exit gate (open route, 2026-10-28). The open route has one converter so far, so nothing is
`DUAL_ORACLE_EQUIVALENT` yet; the second oracle is tracked in `docs/vendor-deferred.md`. Panel finding answered: 1, with 3 and 4.

## Context

CAD Exchanger and the ODA SDKs are two independent paths from DWG to STEP AP242. Two independent
paths are useful, but both can normalise or approximate the same construct in the same way, so their
agreement is evidence of something weaker than the original intent.

## Decision

The two converters exist to detect disagreement. If they disagree materially, the fixture is
quarantined (ADR 0006) until the disagreement is explained. If they agree, the fixture is
`DUAL_ORACLE_EQUIVALENT` (ADR 0001) and is never source truth.

- Comparison reads the normalised evaluator records, never STEP text, and never judges by textual
  equality.
- Structural exactness and geometric equivalence are reported separately.
- For a probe, a capability where both converters land in `BOUNDED_APPROXIMATION` is reported as not
  certified even though they agree.
- A capability is certified only when at least one converter produces an exact representation and no
  converter discrepancy is left unresolved (`runner/qualify_probes.py`).

## Consequences

Agreement can raise confidence in a real-world drawing, but it can never be used to certify a PVec
capability. Only the known-truth probes can.

## Amendment (ADR 0009)

The two converters are whichever the corpus revision names in its manifest, not always CAD Exchanger
and ODA. The decision above already reads generically, so nothing in it changes. What a pair of
converters can claim is recorded in `oracle_scope` (ADR 0009), and two converters of one lineage don't
count as a dual oracle.
