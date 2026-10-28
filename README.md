# pvec-gold-fixtures

A reproducible, Docker-orchestrated fixture pipeline that produces the mathematical reference
corpus read by [`pvec`](https://github.com/libviprs/pvec),
[`libviprs`](https://github.com/libviprs/libviprs) and
[`maplibre-pvec`](https://github.com/libviprs/maplibre-pvec).

Two open converters of distinct lineage (ACadSharp and LibreDWG) are the independent DWG → STEP conversion
paths, and converter agreement alone is explicitly **not** treated as proof of the original DWG's
mathematical intent. Only open-source software takes part ([ADR 0010](docs/adr/0010-open-source-only.md)).

## Status

**Phase 1 is in progress.** The record format, the numeric policy adoption, the independent STEP
evaluator and the expected side of the probes are done and tested. The exit gate is green for one open
converter, and what is still open on the open route (the second oracle above all) is in
[docs/open-route-status.md](docs/open-route-status.md) and
[docs/phase1-converter-qualification.md](docs/phase1-converter-qualification.md).

There is also a candidate corpus revision that needs no STEP converter: `r0-open`
([corpus/r0-open](corpus/r0-open/README.md), [ADR 0008](docs/adr/0008-open-writer-known-truth-corpus.md)).
It is DWGs written by an open writer and cross-read by a second open reader, with no STEP oracle, so it is
`KNOWN_TRUTH_EXACT` for reader mapping only and doesn't turn the phase 1 exit gate green.

The next candidate, `r1-open` ([corpus/r1-open](corpus/r1-open/README.md)), adds edge, mixed-entity, degenerate, negative
and real-world fixtures with a capability matrix and a public release set; `python3 -m runner.corpus check` re-checks it.

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

## Licences and architectures

- **This repository is MIT.** The ACadSharp converter image is MIT too. The LibreDWG converter is GPL-3.0-or-later,
  so its image is built and published from its own repository and consumed here by digest. Ordinary CI in `pvec`,
  `libviprs` and `maplibre-pvec` runs with no converter present.
- **Both architectures are supported where the code allows.** x64 compiled code is exercised on the native
  x86_64 host rather than under local Rosetta emulation, always in containers, always with an explicit
  `--platform`, and every write-up says which results are native x64 and which arm64.
- No credential is written to a file, echoed, or copied to a build host.

The structural and geometric reports, the converter comparison and the generator input for real-world fixtures are described in [docs/reports](docs/reports/structural.md) and [docs/fixtures/generator-input.md](docs/fixtures/generator-input.md). What is still open on the open route is in [docs/open-route-status.md](docs/open-route-status.md).

## Documentation

- [Docker workflow](docs/docker-workflow.md)
- [Converter images and setup](docs/converters/images-and-setup.md)
- [Known-truth fixture authoring](docs/fixtures/authoring.md)
- [Evidence classes](docs/evidence-classes.md) ([ADR 0001](docs/adr/0001-evidence-classes.md))
- [STEP evaluator design](docs/validator/step-evaluator.md)
- [Numeric comparison policy](docs/numeric-policy.md)
- [Corpus provenance and licensing](docs/provenance.md)
- [Acceptance and quarantine](docs/acceptance-and-quarantine.md)
- [Reproducibility guide](docs/reproducibility.md)
- [Downstream test contract](docs/downstream-contract.md)
- [Benchmark report](docs/benchmark-report.md)
- [Final corpus audit](reports/final-audit.md), [open route status](docs/open-route-status.md), and the release candidate [`corpus/release/r0-open-1`](corpus/release/r0-open-1/RELEASE-NOTES.md)

Enable the commit guard with `git config core.hooksPath .githooks` (see [converter images and setup](docs/converters/images-and-setup.md)).
