# r0-open-1 (candidate, not tagged)

The open-scope release of corpus revision `r0-open`: 29 signatures and STEP files from `dwg2step-acadsharp`, and
`near-singular-001` listed as refused. `manifest.json` pins corpus revision and bundle hash, source hashes, signature
hashes, STEP hashes, image references, converter versions, evaluator version and numeric policy version. `SHA256SUMS`
covers every file. Pin the version and the manifest's SHA-256, then run `sha256sum -c SHA256SUMS`.

## Why it was frozen

- Benchmarks (native x64, mars): a conversion takes about 135 ms inside the container, the 30-DWG corpus converts,
  evaluates and normalises in 2.62 s at parallelism 8, and a `step_eval` load takes about 15 ms
  (`docs/benchmark-report.md`). Native arm64 (mercury): about 158 ms and about 13 ms.
- Clean host (`docs/reproducibility.md`): two native x64 runs in fresh docker daemons with no cached images both
  rebuilt both images, rewrote all DWGs to the pinned bundle hash, and reproduced every source, STEP and signature
  hash in this manifest, with no divergence outside the listed five. The arm64 run matched all STEP hashes and the
  bundle, and differed in 10 of 29 signatures, which is why the signatures here are the x64 set.
- Audit (`reports/final-audit.md`): 0 quarantined, 3 exclusions retained, 0 approximation claims, 30 synthetic
  fixtures all `PUBLIC_REDISTRIBUTABLE`, every capability `KNOWN_TRUTH_EXACT` for reader mapping only. The STEP-side
  bounds are unmeasured, and that is stated there.

## What it does not contain, and how that is checked

- No `PRIVATE` DWG bytes and no DWG at all: the release carries signatures and STEP text, and every source is a
  synthetic authored probe.
- No vendor binary, licence file or key-shaped string: `tools/vendor_guard.sh --tree` is clean on the tree.
- No licence material from any run: no credential was written to a file, echoed or copied to a build host.
- Nothing was published and no tag was created.

## Using it

No converter, evaluator or docker is needed to verify it. See `docs/downstream-contract.md`.

Exercised once: the release directory was unpacked in an alpine container on mars (native x64) started with
`--network none`, with no converter or evaluator, and `sha256sum -c SHA256SUMS` reported every file OK.
