# Open route status

Everything here is open source, under ADR 0010. This page lists what the open route does not cover yet, what replaces each gap, and where it is tracked. Nothing on it waits on a licence.

## What runs today

The open converter `acadsharp-dwg2step` converts the 30 `r0-open` DWGs, `step_eval` evaluates the STEP, `runner/qualify_probes.py` classifies every probe (`reports/phase1/probe-qualification.json`), and the phase 1 exit gate is green for `OPEN_CONVERTERS` with one oracle (`reports/phase1/exit-gate.txt`). The corpus revisions `r0-open` and `r1-open`, the negative suite, the benchmarks and the clean-host rebuild of `r0-open` all run on the open writer and converter.

## The second oracle

The LibreDWG converter (#65, real run in #66) lives in `libviprs/pvec-oracle-libredwg` (GPL-3.0-or-later, image consumed by digest or local id, never a build context here). Its column is in `reports/phase1/probe-qualification.json` (oracle_count 2, every cell classified for both converters), and a real two-converter `generate` run, with the interrupt check, is recorded in `docs/reports/generate-real-run.md`.

## Discrimination on real converter output

The open-route version mutates the expected and evaluator records (`tests/test_probes.py`) and passes. Injecting a weight renormalisation, a knot collapse and a reparameterisation into the STEP each converter really wrote is #67.

## Corpus gaps

- `shear-001` and `general-affine-001` have no DWG, because a single INSERT cannot carry shear. Chain probes and profile-only tags are #69. `singular-001` needs a writer that stores a zero scale, which is #70. Until then `affine_transform` stays `BLOCKED`.
- Both converters now convert `blocks-dynamic-linear-001` (inches, scaled to metre) and `general-sample-ac1032-001` (inches, one fit-point-only spline skipped per entity). `arch-aecobjects-001` still exits 15 in both: its only model-space entity is an AEC wall object, and the lines and polylines sit in blocks nothing inserts, so there is no curve to write. The `r1-open` records under `fixtures/real-world/` are the frozen run with the old converter and are re-recorded by the next revision, not here.
- The real-world set is three public drawings. More from openly licensed sources is #76. AutoCAD-written bytes enter only through that set, with provenance.
- `r0-open` is written by acadrust. Two more writer families are in `corpus/writers` (see its README): ACadSharp's `DwgWriter` (AC1032, 30 of 30 AGREE) and LibreDWG's `dwgwrite` as R2000 (30 of 30 AGREE) and R2004 (30 of 30 quarantined, only because ACadSharp at its pin cannot open LibreDWG's R2004 files). Every `r1-open` DWG regenerates byte for byte.

## Signatures across architectures

STEP bytes match on native x86_64 and native arm64, but 10 of 29 signatures differ in the last digits (`docs/benchmarks/validation.md`). Separating stored bits from derived values is #74, and an OCCT build with floating-point contraction off is the spike in #75. The frozen set is native x86_64 until then.

## Benchmarks

Both converters are measured on native x86_64 (`docs/benchmarks/converter-throughput.md`, `orchestration-tuning.md`), and `docker/converter-limits.json` has a cap for each. The LibreDWG converter has no arm64 numbers because no arm64 image of it is held here. The geometric comparison stage is timed on both architectures in `docs/benchmarks/validation.md`. All of it is on the 30 small probes, so none of it says how a real drawing behaves.

## Images and the next revision

The digests in `corpus/container.pin.json` stay `null` until the open images (`dwg2step-acadsharp`, `step-validator`, and the LibreDWG one from its repository) are published, which needs a registry session. `r2-open` (#78) is built: the first `STEP_ORACLE` revision, its clean-host run on x86_64 and arm64, the audit `reports/final-audit-r2-open.md` and the combined release candidate `corpus/release/r2-open-1` (not tagged). Every capability is `CERTIFIED` from two oracles, `affine_transform` included.

## Dropped

A writer the downstream CAD world actually uses is the one requirement that only a licensed tool could meet, and it is dropped (ADR 0010).
