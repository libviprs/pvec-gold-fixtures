# Acceptance and quarantine

A fixture is either accepted for a stated reason or quarantined for a stated reason. The reasons are the five
of [ADR 0006](adr/0006-quarantine-policy.md): `UNRESOLVED_DISAGREEMENT`, `UNSUPPORTED_ENTITY`, `APPROXIMATION`,
`MALFORMED_FIXTURE` and `LICENCE_OR_PROVENANCE`. "Unknown" is not a reason. If a reason cannot be named, the
fixture is not admitted at all.

## The path of a fixture

1. Authored parameters and the `expected.math.json` record ([fixtures/authoring.md](fixtures/authoring.md)).
2. A DWG written from those parameters.
3. The read check. For `r0-open`, two open readers decode the DWG and `runner/r0_open.py` compares them to the
   authored truth, EXACT where the DWG stores the number verbatim and under the numeric policy where it stores
   a derived value. Verdict `AGREE`, or the fixture is quarantined.
4. Conversion and evaluation (where a converter ran): dwg2step to STEP, `step_eval` to a verification record,
   `runner/normalize.py` to a signature. `runner/qualify_probes.py` gives each expected entity a class
   (`STRUCTURAL_EXACT`, `GEOMETRIC_EXACT_REPARAMETERIZED`, `BOUNDED_APPROXIMATION`, `MISSING`, `UNSUPPORTED`) and
   the exit gate (`runner/phase1_gate.py`) says whether the qualification holds.
5. Acceptance is recorded in the revision's `manifest.json`; a quarantine is recorded in `quarantine.json` with
   its reason and its evidence.

## Excluded, not quarantined

A probe the writer cannot store exactly gets no DWG and is listed under `excluded` in `manifest.json`, with its
reason and evidence (`r0-open` lists `shear-001`, `general-affine-001` and `singular-001`; the first two are now profile-only records, with `shear-chain-001` and `general-affine-chain-001` in `r1-open` carrying their maps through a DWG). It is a gap that is
written down, not a fixture that hides.

## Who clears a quarantine

Only the repository owner, through a pull request that states the evidence, and the previous reason stays in
the fixture's history. The final audit ([../reports/final-audit.md](../reports/final-audit.md)) walks every
register once before a freeze.
