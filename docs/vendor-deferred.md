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

## Issues 15 and 54: converter classification and generator input: converter classification and generator input

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
