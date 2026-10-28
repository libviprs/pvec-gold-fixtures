# pvec-gold-fixtures

A reproducible, Docker-orchestrated fixture pipeline that produces the mathematical reference
corpus read by [`pvec`](https://github.com/libviprs/pvec),
[`libviprs`](https://github.com/libviprs/libviprs) and
[`maplibre-pvec`](https://github.com/libviprs/maplibre-pvec).

**CAD Exchanger** and **ODA Drawings + ODA STEP** are mandatory independent DWG → STEP conversion
paths — and converter agreement alone is explicitly **not** treated as proof of the original DWG's
mathematical intent.

## Status

**Phase 1 is in progress.** The record format, the numeric policy adoption, the independent STEP
evaluator and the expected side of the probes are done and tested. What waits on the proprietary
converters (their images, the probe DWGs, the probe qualification) is listed in
[docs/phase1-converter-qualification.md](docs/phase1-converter-qualification.md).

There is also a candidate corpus revision that doesn't wait on the converters: `r0-open`
([corpus/r0-open](corpus/r0-open/README.md), [ADR 0008](docs/adr/0008-open-writer-known-truth-corpus.md)).
It is DWGs written by an open writer and cross-read by a second open reader, with no STEP oracle, so it is
`KNOWN_TRUTH_EXACT` for reader mapping only and doesn't turn the phase 1 exit gate green.

Three phases and 27 issues under [#1](https://github.com/libviprs/pvec-gold-fixtures/issues/1).
Phase 1 proves the methodology — including validating the STEP validator itself against hand-known
primitives — before any mass fixture generation.

## Regenerating a fixture

`docker compose run --rm fixture-runner generate [fixture-id ...]` converts `fixtures/<id>/source.dwg` with two
converter services, evaluates both outputs, normalises, compares, classifies and writes
`fixtures/<id>/generated/` (see `runner/generate.py`). Containers are torn down on every exit path. Pass
`--primary`/`--secondary` and `--oracle-scope OPEN_CONVERTERS` for the open route. The container wiring for the pvec
corpus tests is `corpus/container.pin.json` and `runner/container_wiring.py`.

## Evidence classes

The four classes (`KNOWN_TRUTH_EXACT`, `DUAL_ORACLE_EQUIVALENT`, `REAL_WORLD_DIFFERENTIAL`,
`QUARANTINED`) are defined once, in [ADR 0001](docs/adr/0001-evidence-classes.md). Everything else
refers to them by name.


Known-truth numbers avoid ambiguous rounded JSON. A documented canonical representation carries the
intended `f64`, for example `{"decimal": "0.70710678118654757", "f64_hex": "0x3fe6a09e667f3bcd"}`.

## Licensing and architecture constraints

- **The converter images are commercial and are not redistributable.** Ordinary CI in `pvec`,
  `libviprs` and `maplibre-pvec` must run with no proprietary converter present.
- **Both converter SDKs are x86_64.** Per `workspace/libviprs/CLAUDE.md`, x64 compiled code is
  exercised on the native x86_64 host rather than under local Rosetta emulation, always in
  containers, always with an explicit `--platform`, and every write-up says which results are
  native x64 and which arm64.
- No credential is written to a file, echoed, or copied to a build host.

The structural and geometric reports, the converter comparison and the generator input for real-world fixtures are described in [docs/reports](docs/reports/structural.md) and [docs/fixtures/generator-input.md](docs/fixtures/generator-input.md). What waits on a licence or another repository is in [docs/vendor-deferred.md](docs/vendor-deferred.md).

## Documentation

- [Docker workflow](docs/docker-workflow.md)
- [Converter licensing and setup](docs/converters/licensing-and-setup.md), and the [archive of the proprietary workflow](docs/converters/archive.md)
- [Known-truth fixture authoring](docs/fixtures/authoring.md)
- [Evidence classes](docs/evidence-classes.md) ([ADR 0001](docs/adr/0001-evidence-classes.md))
- [STEP evaluator design](docs/validator/step-evaluator.md)
- [Numeric comparison policy](docs/numeric-policy.md)
- [Corpus provenance and licensing](docs/provenance.md)
- [Acceptance and quarantine](docs/acceptance-and-quarantine.md)
- [Reproducibility guide](docs/reproducibility.md)
- [Downstream test contract](docs/downstream-contract.md)
- [Benchmark report](docs/benchmark-report.md)
- [Final corpus audit](reports/final-audit.md), [vendor-deferred work](docs/vendor-deferred.md), and the release candidate [`corpus/release/r0-open-1`](corpus/release/r0-open-1/RELEASE-NOTES.md)

Enable the commit guard with `git config core.hooksPath .githooks` (see the archive document).
