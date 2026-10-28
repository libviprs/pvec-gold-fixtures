# Evidence classes: how to read a fixture

The four classes are defined once, in [ADR 0001](adr/0001-evidence-classes.md), and this page does not redefine
them. It says how to read them, and what two extra fields (ADR 0008 and ADR 0009) add.

- **`KNOWN_TRUTH_EXACT`** reads as: the expected mathematics was authored before any DWG or converter existed,
  and the thing under test agrees with it. It is the only class that supports an "exact" claim.
- **`DUAL_ORACLE_EQUIVALENT`** reads as: two converters, read by the one independent evaluator, agree. That is
  interoperability and regression value. Converter agreement is never source truth, and no document here
  calls a fixture exact because two tools agreed.
- **`REAL_WORLD_DIFFERENTIAL`** reads as: a real drawing kept to spot differences between providers. It
  carries a licence verdict.
- **`QUARANTINED`** reads as: not to be relied on, with a named reason that is never "unknown"
  ([acceptance-and-quarantine.md](acceptance-and-quarantine.md)).

## Two fields that bound a class

- `evidence_scope`: `READER_MAPPING_ONLY` means the DWG bytes carry the authored numbers when decoded by open
  readers, and no STEP file was involved. `STEP_ORACLE` means a converter's STEP output, read by the
  evaluator, was part of the evidence.
- `oracle_scope`: `NONE` or `OPEN_CONVERTERS` (ADR 0010), so a consumer filters on it instead of reading a
  class as more than it says.

The revision in the repository today is `r0-open`: every fixture is `KNOWN_TRUTH_EXACT`, with
`evidence_scope: READER_MAPPING_ONLY` and `oracle_scope: NONE`. The STEP outputs of the open converter in the
release candidate are regression artifacts of one converter. No fixture is `DUAL_ORACLE_EQUIVALENT`, because a
second independent converter has not run on them (the LibreDWG route lives in `libviprs/pvec-oracle-libredwg`),
and none has an oracle scope other than `NONE`.

## What the classes do not say

- Exactness has two parts, structure and geometry, and the conformance classes for them (structural
  exactness, geometric exactness, display fidelity) belong to EPIC P in `libviprs/pvec#1`. I cite them and
  never redefine them.
- A display-fidelity result is never called
  exact, in any sense, anywhere in this repository.
- Where the evaluator compares evaluated values, the thresholds come from the adopted numeric policy
  ([numeric-policy.md](numeric-policy.md)), not from this repository.
