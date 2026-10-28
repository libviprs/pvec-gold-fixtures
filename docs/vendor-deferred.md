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
