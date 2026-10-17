# ADR 0003: the role of the dual oracle

Status: proposed, frozen by the phase 1 exit gate. Panel finding answered: 1, with 3 and 4.

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
