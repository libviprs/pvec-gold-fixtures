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
- The converters refuse all three real-world drawings in `r1-open` (inches and feet, fit-point-only splines), so none can be `DUAL_ORACLE_EQUIVALENT`. Lifting that is #68.
- The real-world set is three public drawings. More from openly licensed sources is #76. AutoCAD-written bytes enter only through that set, with provenance.
- `r0-open` is written by acadrust only. A second family, ACadSharp's `DwgWriter`, is in `corpus/writers/acadsharp`, and LibreDWG's R2000 and R2004 writer is #72. Every `r1-open` DWG regenerates byte for byte.

## Signatures across architectures

STEP bytes match on native x86_64 and native arm64, but 10 of 29 signatures differ in the last digits (`docs/benchmarks/validation.md`). Separating stored bits from derived values is #74, and an OCCT build with floating-point contraction off is the spike in #75. The frozen set is native x86_64 until then.

## Benchmarks

Both converters are measured on native x86_64 (`docs/benchmarks/converter-throughput.md`, `orchestration-tuning.md`), and `docker/converter-limits.json` has a cap for each. The LibreDWG converter has no arm64 numbers because no arm64 image of it is held here. The geometric comparison stage is timed on both architectures in `docs/benchmarks/validation.md`. All of it is on the 30 small probes, so none of it says how a real drawing behaves.

## Images and the next revision

The digests in `corpus/container.pin.json` stay `null` until the open images (`dwg2step-acadsharp`, `step-validator`, and the LibreDWG one from its repository) are published, which needs a registry session. `r2-open`, the first `STEP_ORACLE` revision with a clean-host run, a new audit and a combined release, is #78.

## Dropped

A writer the downstream CAD world actually uses is the one requirement that only a licensed tool could meet, and it is dropped (ADR 0010).
