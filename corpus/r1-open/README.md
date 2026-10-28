# corpus revision r1-open

The second candidate revision. It includes `r0-open` by reference (bundle and manifest hashes in `manifest.json`)
and adds five groups, each in its own directory under `fixtures/`: `edge` (valid extreme and boundary cases),
`mixed` (one drawing with seven curve classes, nested blocks and transforms), `degenerate` (entities that must be
refused), `negative` (one entity outside PVec v1 each, with an expected classification) and `real-world` (public
drawings with a provenance record). `manifest.json` is the index, `quarantine.json` lists everything quarantined
with its reason, and `SHA256SUMS` covers the files in this directory. The per-fixture hashes are in the manifest.

Read this before you rely on it. `oracle_scope` is `NONE`: one open converter (`acadsharp-dwg2step`) has run over the
fixtures and its result is recorded in each `open-route.json`, but ADR 0009 needs two converters with different
lineages before a fixture can claim `STEP_ORACLE`, and the second one does not exist yet. `KNOWN_TRUTH_EXACT` here
means reader mapping only, exactly as in `r0-open`. Real-world fixtures are `REAL_WORLD_DIFFERENTIAL` and never
known truth. The negative and degenerate fixtures are `QUARANTINED` by design (ADR 0006).

To check it with no DWG library, no converter and no Docker:

    python3 -m runner.corpus check
    python3 -m runner.corpus_release build . OUT && python3 OUT/verify_release.py OUT
