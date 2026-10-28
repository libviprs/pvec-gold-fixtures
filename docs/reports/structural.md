# Structural report

A structural report answers one question: did the converter hand back the same representation the
authored mathematics has? Same class, degree, control points, knots and their multiplicities, weights,
parameter domain, closure and transform, bit for bit. A curve that traces the right path with other
parameters is not structurally exact, and the report says so. Whether the path is right is the
geometric report's question ([geometric.md](geometric.md)), and I keep the two apart on purpose: panel
finding 4.

```
python3 -m runner.compare_structural expected.math.json primary.signature.json structural.primary.json
```

Schema: `schema/structural-report.schema.json` (`pvec-gold/structural-report/1`). It reads a signature
(`pvec-gold/signature/1`) and `expected.math.json`, never STEP text. The expected entity is written the
way a signature writes one (metres, stored scalars, a transform) with the normaliser's own helpers, so
both sides take the same path.

## What it says

Per entity and per field the verdict is one of:

- `MATCH`: the two values are equal. Integers (degree, multiplicity, counts) compare as integers, reals
  compare on their `f64_hex`.
- `DIFFERENT`: they are not. The row carries the field path, the expected value and the produced value,
  and for reals both the canonical decimal and the `f64_hex`.
- `REPARAMETERIZED`: the field differs, but a geometric report found the entity's geometry equal under
  the numeric policy. It is only ever set from a geometric report passed in with `--geometric`, and only
  for fields under `geometry.` and `parameter_domain.`. A class or closure change stays `DIFFERENT`.

The overall `class` is `STRUCTURAL_EXACT` only when every field of every entity is `MATCH` and nothing
unexpected was produced; otherwise it is `STRUCTURAL_DIFFERS`. `REPARAMETERIZED` rows do not soften that.
Renormalising a rational curve's weights keeps the geometry and changes the weights, so it reports
`STRUCTURAL_DIFFERS` with `REPARAMETERIZED` weights, never exact.

## What it does not say

There is no tolerance here and none is defined here. The report records the numeric policy version and
the signature schema version it ran under, because the geometric report next to it uses the policy, and
`stage` records the architecture it ran on (`compare_structural` reads signatures only, so it needs no
proprietary converter and runs anywhere; the STEP behind the signatures came from the converter images
named in the converter section of `comparison.json`).

A report is refused (`ReportRefused`, exit code 2) when the fixture has no `expected.math.json`. I won't
compare the two converters against each other under this name; that is `compare_converters`.

An expected rejection (a probe whose truth is "no curve") is honoured when the signature has no entities.

## Where the blocks live

The issue asked for a structural block inside `primary.verification.json`. That file is the evaluator's
record and has its own schema, so I left it alone and write `primary.structural.json` and
`secondary.structural.json` beside it. The converter section of `comparison.json` points at the same
classes.
