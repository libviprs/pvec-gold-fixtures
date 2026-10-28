# What a downstream test may depend on

`pvec`, `libviprs` and `maplibre-pvec` read the frozen artifacts of this repository and nothing else. This is
the line between what they may rely on and what they may not. It is checked by `tests/test_signature_path_20.py`
and by `runner/verify_signatures.py`.

## Signature artifacts

Under `signatures/`:

```
signatures/manifest.json                 versions, and the SHA-256 of every signature and retained STEP
signatures/<fixture-id>/signature.json   pvec-gold/signature/1, written by runner.normalize
signatures/<fixture-id>/primary.step     the STEP file the signature was derived from (audit source)
```

Every accepted fixture ships both files. A fixture the converter refuses by design (`near-singular-001`,
`NEAR_SINGULAR_TRANSFORM`) ships neither, and the manifest does not list it.

## A downstream test may depend on

- The signature JSON: `schema/signature.schema.json`, version `pvec-gold/signature/1`. The field names, the
  `{decimal, f64_hex, precision}` scalar, the metre as the one length unit, and the sort order of entities
  (class, then a hash of the content).
- The manifest: `manifest_version`, `versions.schema`, `versions.evaluator`, `versions.occt`,
  `versions.policy`, and the hash of each signature. A consumer pins the schema and policy versions it was
  written against and calls `runner.signatures.load(dir, id, expect_schema=..., expect_policy=...)`, which
  refuses a manifest or a signature that is not what was pinned. That module is standard library only: no
  OCCT, no STEP parser, no converter, no jsonschema.
- Stored values (control points, knots, weights, centres, radii, parameter domains) as exact f64 bits. They are
  the same on every architecture, and `runner/verify_signatures.py` compares them bit for bit.
  Values OCCT derives are not file content: sample points, tangents and curvatures (rounded to 12 significant
  digits), a line's ends and an ellipse's major axis (`runner.normalize.DERIVED_GEOMETRY`). Compare those
  with the numeric policy, never bit for bit. They move in the last digits between native x86_64 and native
  arm64, and that is not a difference.
- The hashes. If a hash in the manifest does not match the file, the artifact is damaged and the test should
  fail, not skip.

## A downstream test may not depend on

- STEP text. The STEP file is retained for audit and for `runner/verify_signatures.py`; its entity numbers,
  its time stamp, its line order and its spelling of reals are the converter's. Nothing downstream parses it.
- Entity ids of any kind: STEP `#n` numbers, the evaluator's own labels.
- A converter being present, or its name. The signature does not say which converter made the STEP, and a
  test that needs to know has stopped being a downstream test.

## Drift

`python3 -m runner.verify_signatures signatures` re-derives every signature from its retained STEP and compares
them: stored values bit for bit, derived values under the numeric policy. It needs `step_eval`, so it runs in the
step-validator image, and it passes on native x86_64 and on native arm64 against the same frozen set. Any difference fails
the job and names the fields that differ; a byte difference with no differing field fails as such. It was
exercised once with a mutated signature (one `f64_hex` changed with the manifest rewritten to match), and it
named the field. See `docs/benchmarks/validation.md`.

## Release pinning

A frozen release is `corpus/release/<version>/` (today `r0-open-1`, a candidate that is not tagged). Pin the
version and the SHA-256 of its `manifest.json`, and verify before use:

```
cd corpus/release/<version> && sha256sum -c SHA256SUMS
```

That needs `sha256sum` and nothing else (`python3 -m runner.reproduce verify <dir>` does the same with python
only). The manifest pins eight things: corpus revision, source hashes, signature hashes, STEP hashes, image
references, converter versions, evaluator version and numeric policy version. Its signature hashes are the
`signatures/manifest.json` ones; its STEP hashes are of the text with the `FILE_NAME` time stamp replaced by
`<TIMESTAMP>`, which is how `step/*.step` is shipped.

No proprietary converter, evaluator, docker or vendor network access is needed to read a release. The evidence is
`KNOWN_TRUTH_EXACT` for reader mapping only with `oracle_scope: NONE` on the corpus, and one open converter behind
the STEP files ([evidence-classes.md](evidence-classes.md)); converter agreement is never source truth. Whether PVec
becomes the default blueprint path is `P8.7` and `N8.7`'s decision, not an assumption here.
