# r2-open-1 (candidate, not tagged)

The combined release of `r0-open` and `r1-open` after both open converters ran over them (59 fixtures). `manifest.json` pins the corpus manifest hash, every source hash, the STEP and signature hash per fixture and converter, the verdict hashes, the two converters and the evaluator with their local image ids, and the numeric policy. `SHA256SUMS` covers every file. Verify with `sha256sum -c SHA256SUMS`, or `python3 -m runner.r2_open verify .` from a checkout.

- It holds STEP text and signatures from native x86_64 (the frozen set; derived values differ in the last digits on arm64, see `docs/reproducibility.md`). It holds no DWG.
- 20 fixtures are listed under `refused`: both converters wrote nothing for them (the negative suite, `near-singular-001`, `singular-001`, one real-world drawing).
- Nothing was published and no tag was created. The image ids are local; publishing them needs a registry session.
