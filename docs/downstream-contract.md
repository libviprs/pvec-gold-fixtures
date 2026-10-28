# Downstream test contract

For `libviprs/pvec`, `libviprs/libviprs` and `libviprs/maplibre-pvec`. This is exactly what a consumer may
depend on, and what it may not.

## What you read

1. **Signatures**: `signatures/<fixture>.signature.json` in a release (schema `pvec-gold/signature/1`,
   [fixtures/signature.md](fixtures/signature.md)). Implementation-neutral, no entity ids, no converter names.
2. **STEP for audit**: `step/<fixture>.step`. Read it to see what a converter wrote. It is a regression artifact of
   the converter named in the manifest, not a source of truth, and its `FILE_NAME` time stamp is the literal
   `<TIMESTAMP>`.
3. **The manifest**: `corpus/release/<version>/manifest.json`, which pins corpus revision, source hashes, signature
   hashes, STEP hashes, image digests, converter versions, evaluator version and numeric policy version.
4. **The hashes**: `SHA256SUMS` over every file of the release.

You pin a release by its version and the SHA-256 of its `manifest.json` (and the release's `SHA256SUMS`), and your
CI verifies them before it uses anything:

```
cd corpus/release/<version> && sha256sum -c SHA256SUMS
```

That check needs `sha256sum` and nothing else.

## What you do not need

No proprietary converter, no evaluator, no docker, and no network access to a vendor. Ordinary CI in the three
repositories reads the frozen artifacts and nothing more. `python3 -m runner.reproduce verify <dir>` re-checks a
release with python only.

## What the evidence says

Read the manifest's evidence fields before you claim anything ([evidence-classes.md](evidence-classes.md)).
Today's release candidate is `KNOWN_TRUTH_EXACT` for reader mapping only, with `oracle_scope: NONE` on the corpus
and one open converter behind the STEP files. It supports "the DWG carries these numbers" and "this converter's
output has this signature". It does not support a claim that CAD Exchanger or ODA agree, and converter agreement
is never described as source truth.

## What it does not decide

Whether PVec becomes the default blueprint path is `P8.7` and `N8.7`'s decision, recorded with numbers, and
nothing here assumes the answer. EPIC L (`libviprs/libviprs#1028`) continues to ship the tessellated path, and this
corpus serves both. The numeric thresholds are `P1.2`'s, in [numeric-policy.md](numeric-policy.md).
