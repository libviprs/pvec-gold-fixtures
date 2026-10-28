# Vendor-deferred work

Everything in this file needs a CAD Exchanger or ODA licence, and I have neither here. Each section
says what is deferred, what I did on the open route instead (`oracle_scope: OPEN_CONVERTERS`, see
[ADR 0009](adr/0009-open-converter-oracle-scope.md)), and what a licensee has to run.

Each issue appends its own section below. Keep the headings stable so merges stay trivial.

<!-- sections -->

## Fixture runner and the corpus container (issues 13 and 53)

What runs for real: `docker compose run --rm fixture-runner generate [id ...]` (`runner/generate.py`) drives
any two converter services plus `step-validator`, with the teardown, refusal, quarantine and checksum rules
from issue 13, and the pin file, mount layout and container-unavailable check from issue 53
(`runner/container_wiring.py`, `corpus/container.pin.json`). The tests drive it against a fake docker CLI,
including a real SIGINT.

What waits on a licence or on another repository:

- A real run of `generate` with `--primary cadex-converter --secondary oda-converter` (the compose defaults,
  `--oracle-scope VENDOR_CONVERTERS`). The interrupt acceptance run (compare `docker ps -a` and `docker volume ls`
  before and after, `--check-leaks`) has to be repeated there with a real conversion in flight, because the fake
  proves the teardown call and not the converter's own signal handling.
- Digests in `corpus/container.pin.json`. Both are `null` until an image is published, which needs a registry
  session I don't have. `python3 -m runner.container_wiring check-pin corpus/container.pin.json --strict` turns red
  until they are filled, and the pvec side should run it with `--strict`.
- The ten artifacts "listed in the tracker" were not readable from this repository, so `ARTIFACTS` in
  `runner/generate.py` is the set I could justify: two STEP files, two status records, two verification records, two
  signatures, verdict, manifest, plus `checksums.sha256` over them. Reconcile with the tracker list if it differs.
- `Container::start` in `crates/pvec-hermetic`, the digest pin in the pvec repository and making `precision`
  required for the vendor revision are pvec changes and are not made here.

## Issues 15 and 54: converter classification and generator input

**CAD Exchanger and ODA (oracle_scope VENDOR_CONVERTERS).** The structural and geometric reports and the
converter classification (`runner/compare_structural.py`, `compare_geometric.py`, `compare_converters.py`)
are done and tested on signatures. What stays open is running them on signatures the licensed images
produced: neither image can be built here (no licence), so there are no vendor signatures, no vendor
converter section, and the issue's wording about "CAD Exchanger versus ODA" is not evidenced. When the
images exist, the same modules classify that pair with `oracle_scope: VENDOR_CONVERTERS`; nothing in them
looks at converter ids.

**The secondary open converter has not produced a signature.** The primary is the ACadSharp-lineage
`dwg2step-acadsharp`. The secondary is the LibreDWG-lineage converter from `libviprs/pvec-oracle-libredwg`
(GPL-3.0), whose image is still in a draft PR. `r0-open` has `oracle_scope: NONE` and no STEP, and there is
no real-world corpus yet (that is issue #11), so I did not generate `primary.signature.json` and
`secondary.signature.json` for any corpus fixture. The tests use real step_eval signatures of the committed
self-test STEP files, from both architectures, and signatures built from the known-truth probes.

**Real-world artifacts need a pvec change.** The gold-fixtures half of #54 is the generator input
(`docs/fixtures/generator-input.md`). The generator side is code in `libviprs/pvec`, which I did not edit:

- `pvec-testkit` needs a second input next to the record one: read a `*.generator-input.json`, validate it
  against `schema/generator-input.schema.json`, and produce the same `Plan` from `signature`, so the
  writer path and the refusal rules are shared.
- It stamps the generator version into the provenance fields it already writes, plus `oracle_revision`.
- The determinism, digest and bit-for-bit tests need repeating over the real-world fixtures once those
  exist; the byte-determinism of the input itself is tested here.

**Per-converter blocks.** The issue asked for a structural block inside `primary.verification.json`. I
write `primary.structural.json` and `primary.geometric.json` beside it, because the verification record has
its own schema. Say if you want them folded in.

## Converter qualification, the pathological and transform probes, and the exit gate (issues 2 and 6)

What runs for real: the open converter `acadsharp-dwg2step` converts the 30 `r0-open` DWGs, `step_eval` evaluates the STEP,
`runner/qualify_probes.py` classifies every probe (`reports/phase1/probe-qualification.json`), and the exit gate is green for
`OPEN_CONVERTERS` with one oracle (`reports/phase1/exit-gate.txt`, `tools/qualify/open_route.sh mars`). ADRs 0001 to 0007 are frozen.

What waits on a licence or a second open converter:

- CAD Exchanger Batch and the ODA Drawings and STEP SDKs: the images, their licence findings, concurrency limits, reproducible
  digests, error-code tables and the `docs/converters/*-qualification.md` results stay as they are (issue 2, the first half). Nothing
  was built or run for them.
- The second oracle. ADR 0003 wants two converters with distinct lineages, and the open route has one. The LibreDWG converter
  (`libviprs/pvec-oracle-libredwg`) will add the second column; running `runner.qualify_probes` with `--secondary` then adds
  the discrepancy check, and only then can a cell earn `DUAL_ORACLE_EQUIVALENT`. The vendor pair would run the same command with
  `--oracle-scope VENDOR_CONVERTERS`.
- `source.dwg` written by the ODA Drawings SDK writer for every probe row, and byte-identical regeneration from the authoring
  script under that writer (issue 6). The open writer's DWGs are the corpus today (ADR 0008), with the header differences named
  in `corpus/r0-open`.
- `shear-001`, `general-affine-001` and `singular-001` have no DWG: the open writer has no matrix-carrying INSERT and rewrites a
  zero scale. A vendor writer that can carry them would unblock the `affine_transform` capability, which is `BLOCKED` for exactly
  that reason.
- The discrimination criterion run on vendor STEP output. The open-route version mutates the expected and evaluator records
  (`tests/test_probes.py`) and passes; injecting a weight-to-1 renormalisation, a knot collapse and a reparameterisation into real
  converter output needs a converter that can be made to do that, which is the vendor pair.
- ADR 0004's independence claim against the CAD Exchanger and ODA component lists, and the ADR 0007 image checks (no licence in
  layers, no key in logs).
- Superseding `r0-open` with a vendor-qualified revision in `corpus/CHANGELOG.md` (issue 42's third criterion).

## Issue #20: benchmarks, orchestration tuning and signature artifacts

What runs for real, on the open route (`dwg2step-acadsharp` plus `step_eval`): converter throughput and cost on native
x86_64 (`mars`) and native arm64 (`mercury`), validation cost per stage on both, the scheduler with its licence cap,
resume and teardown, the compose limits, and the signature packaging with the re-derivation job. The numbers are in
`docs/benchmarks/` and `reports/bench/`.

What waits on a licence or on other work:

- CAD Exchanger and ODA throughput, startup, peak memory and failure rate. Neither image can be built here. A licensee
  runs `bench/converters/run.py --image <vendor image> --converter cadex|oda` on the NAS host (native x86_64 only), and
  puts the vendor's real concurrency limit in `docker/converter-limits.json`. Until then those entries are `null`, and
  `runner/scheduler.py` runs an unlisted or null converter at 1, so an unknown limit is never read as unlimited.
- The vendor orchestration table (parallelism 1, 2, 4, 8 up to the licence limit) and the vendor memory limit. Both depend on
  the vendor limit and on the vendor peak RSS, which I cannot observe. The `acadsharp-converter` limits (256m, 2 cpus) say
  nothing about them.
- The named real-world subset. No real-world drawing is held in this repository (issue 11), so the throughput report has the
  probe corpus only. Peak memory in particular is untested on a drawing larger than a few curves.
- The adaptive geometric comparison stage of the validation benchmark and its converged sample count. This one waits on
  work, not on a licence: the comparison stage (O2.5, O2.6) does not exist yet. `bench/validation/run.py` has four stages
  and says so.
- The signatures are frozen from the open converter's STEP, not from a vendor's. A vendor revision re-runs
  `python3 -m runner.regenerate` with the vendor image and `python3 -m runner.verify_signatures` on the NAS host.
- Cross-architecture signature identity is not achieved (10 of 29 differ in last digits, named in
  `docs/benchmarks/validation.md`). Fixing it means changing normalisation, which is O2.4 and not done here.
