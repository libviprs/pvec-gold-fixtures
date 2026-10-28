# generator-input.json

The pvec-testkit generator has a record input (an `expected.math.json` in, a `Plan` out). Real-world
fixtures have no authored truth, only STEP, so the generator needs a second input: a signature in, the same
`Plan` out, which keeps the writer path, the provenance fields and the refusal rules shared. This file is
what I hand over for that. `runner/generator_input.py` writes it and `schema/generator-input.schema.json`
(`pvec-gold/generator-input/1`) is its shape.

```
python3 -m runner.generator_input --manifest corpus/<rev>/manifest.json --fixtures corpus/<rev>/fixtures --out DIR
```

Per fixture it writes `<fixture>.generator-input.json`, plus `index.json` with the SHA-256 of every file.
The bytes depend on content only (the normaliser's serialisation), so a second run is byte-identical.

## What is in it

- `provenance`: `fixture_id`, `corpus_revision`, `oracle_revision` and `derivation: STEP_SIGNATURE`. The
  fourth provenance field, the generator version, is the generator's own and is stamped on the pvec side.
  `oracle_revision` is the SHA-256 of the oracle scope and the converters (id, version, lineage, image
  digest), so another converter image is another revision.
- `oracle`: the scope, the two converters, `evidence_scope: STEP_ORACLE`, `evidence_class:
  DUAL_ORACLE_EQUIVALENT`, `is_source_truth: false` and the converter classification.
- `signature`: the primary converter's signature, unchanged, with its digest and the secondary's digest.

## What is refused

A fixture is not handed over when the oracle scope is `NONE`, when the manifest fails the ADR 0009 scope
rules (two converters of one lineage, a vendor named under `OPEN_CONVERTERS`, and so on), when its converter
section is a `MATERIAL_DIFFERENCE` or QUARANTINED, when the section was not computed from these signatures,
or when a signature carries another numeric policy version.

## What is not an input

A DWG reader's output (`read.*.json`) is never an input. It would put a CAD reader into the generator's
dependency tree and measure the ingestion path, which is what the generator exists to avoid. The schema
fixes `derivation` to `STEP_SIGNATURE` for the same reason.
