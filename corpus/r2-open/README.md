# r2-open (candidate)

The first revision where STEP evidence exists. Every fixture of `r1-open` (which lists `r0-open`'s too) went through both open converters, `acadsharp-dwg2step` (ACadSharp, MIT) and `libredwg-dwg2step` (LibreDWG, GPL, a different decoder lineage), and `step_eval` read what they wrote. `oracle_scope` is `OPEN_CONVERTERS` (ADR 0009, ADR 0010).

- `manifest.json` has one entry per fixture: the `r1-open` entry, the evidence class and scope after the run, what it was before (`previous`), what the converters did (`step_oracle`), and the files this revision adds (`generated`). `moves` lists every fixture with the reason when it did not move.
- `fixtures/<id>/` holds `primary.step` and `secondary.step` (the FILE_NAME time stamp replaced by `<TIMESTAMP>`), both signatures, and `verdict.json`. A converter that refused has no STEP, and the manifest says so.
- The DWGs are not copied here. Each entry points at the `r0-open` or `r1-open` path and hash of its `source.dwg`.
- `KNOWN_TRUTH_EXACT` with `STEP_ORACLE` means both converters' STEP, read by the evaluator, matched the authored record exactly or as the same geometry. It still says nothing about a drawing the converters were not given.
- Common mode is unchanged from ADR 0009: one DWG specification, two thin hand-written Part 21 writers, one OCCT evaluator.

The run that produced it is `reports/reproducibility.r2-open.x64.json` (native x86_64), repeated on native arm64 in `reports/reproducibility.r2-open.arm64.json`. The audit is `reports/final-audit-r2-open.md`.
