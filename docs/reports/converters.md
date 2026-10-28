# Converter comparison and the differences report

`runner/compare_converters.py` classifies the primary converter's signature against the secondary's and
writes the converter section of `comparison.json` (`schema/converter-section.schema.json`).

## Who the two oracles are

ADR 0009 changed what "dual" means here, because CAD Exchanger and ODA have no licence on this side.

- Primary: the open ACadSharp-lineage converter, `dwg2step-acadsharp` (`tools/converters/acadsharp`,
  `docs/converters/acadsharp-dwg2step.md`).
- Secondary, where one exists: the open LibreDWG-lineage converter, `libviprs/pvec-oracle-libredwg`
  (GPL-3.0, kept in its own repository). Its image is in a draft PR as I write this, so it has not produced
  a signature yet. Until it has, a fixture has a primary signature only and no converter section: I don't
  fake a secondary.
- The licensed pair (`cadex` and `oda`) is the vendor route, `oracle_scope: VENDOR_CONVERTERS`. The code
  doesn't look at ids, only at lineages (which must differ) and at the oracle scope (which must not be
  `NONE`), so the same module classifies that pair once the images exist. See `docs/vendor-deferred.md`.

The converter section names both converters with version, lineage and image digest, the numeric policy
version, and the SHA-256 of each signature it was computed from.

## Classes

- `MATCH`: the signatures agree structurally (or both are structurally exact against the truth).
- `EXACT_REPARAMETERIZATION`: same curve classes, different representation fields, geometry equal under
  the policy.
- `EQUIVALENT_GEOMETRY`: geometry equal under the policy, but the curve classes differ (a circle against a
  rational spline, a line against a polyline).
- `MATERIAL_DIFFERENCE`: anything else. It carries the deciding field or quantity and the measured
  deviation, and it is quarantined.

## Precedence

Where `expected.math.json` exists, the verdict against it governs. Each converter is classified against
the truth first, and a converter outside the exact classes makes the fixture a `MATERIAL_DIFFERENCE`,
including when the two converters agree with each other: the section then says both converters agree and
both contradict the authored mathematics. Only when both are exact against the truth is the pair compared
with each other. With no truth (the real-world case) the signatures are compared as they stand.

Agreement is `DUAL_ORACLE_EQUIVALENT` evidence with `evidence_scope: STEP_ORACLE`, `is_source_truth: false`
and the oracle scope, and the statement says "not source truth". It is never a statement about what the
original DWG meant.

## Quarantine

A `MATERIAL_DIFFERENCE` sets `quarantine: {state: QUARANTINED, reason, detail}` and
`quarantine_add` appends it to a `quarantined` list once. The reason is one of ADR 0006's named ones:
`UNRESOLVED_DISAGREEMENT` for a disagreement, `APPROXIMATION` when both agree on a bounded approximation of
the truth, `UNSUPPORTED_ENTITY` when they agree on nothing usable. It is never "unknown".

## The differences report

`render_differences` groups the sections by class and then by the construct that decided them (for
example `geometry.weights`, `class`, `bounds`), so a systematic behaviour such as weight renormalisation
shows as a row pattern instead of scattered fixtures. It names the converters and the policy version.
