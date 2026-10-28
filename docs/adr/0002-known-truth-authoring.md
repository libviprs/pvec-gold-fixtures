# ADR 0002: known-truth authoring

Status: frozen at the phase 1 exit gate (open route, 2026-10-28). Panel findings answered: 2 and 6.

## Context

If the expected mathematics of a fixture were read back from a converter's output, the converter
would be marking its own homework. A rounded JSON number would have the same effect: it would quietly
become the oracle.

## Decision

The expected mathematics of a known-truth fixture comes from authored parameters and from nothing
else. The authoring script (`tools/authoring/author_probes.py` and its parameter files under
`tools/authoring/params/`) is the only producer of `expected.math.json`. The record format is
`schema/expected.math.schema.json`, checked by `runner/expected_math.py`.

- Every number is a decimal plus the intended `f64` as hex, and the validator rejects a decimal that
  doesn't round to exactly those bits.
- Units, parameter domains, trims, weights, knots with multiplicities and transforms are preserved
  explicitly in the record.
- A fixture's provenance names its parameter file and the file's hash, and every fixture's README says
  that no expected value was taken from `primary.step` or `secondary.step`.
- The DWG is written from the same parameters by the ODA Drawings SDK writer.

## Consequences

The expected side of a probe can be regenerated and reviewed without any proprietary software. The
DWG side cannot, which is why `source.dwg` is a separate step in the pipeline.
