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

## Clean-host run, audit, freeze, archive and the documentation set (issues 24 and 27)

What runs for real, on the open route (`oracle_scope: OPEN_CONVERTERS`, one open converter so far): a clean-host
rebuild on MARS (`tools/clean_host.sh`), the corpus's DWGs rewritten from the authored parameters, converted
twice, evaluated and normalised, and compared against a frozen manifest (`corpus/release/r0-open-1/`). The
final audit (`reports/final-audit.md`) walks the four registers for `r0-open`. The vendor guard
(`tools/vendor_guard.sh`), the archive document and the documentation set are done in full, because none of them
needs a licence.

What waits on a licence, for a licensee to run:

- A clean-host run of the `VENDOR_CONVERTERS` path: rebuild `cadex-converter` and `oda-converter` from the
  licensee's artifacts on the native x86_64 host (the build commands are in `docs/converters/archive.md`), with
  the licence paths from `docs/converters/licensing-and-setup.md`, then run `docker compose run --rm
  fixture-runner generate` and compare against a manifest whose `converters` pin names the vendor builds.
  `tools/clean_host.sh` is the model; its driver would call `generate` where it now calls `runner.reproduce`.
- The end-to-end rebuild of both licensed images from the repository plus an entitlement (issue 27's third
  criterion). The Dockerfiles' failure paths are exercised (`tools/check_converter_images.sh`), the success path
  is not, because `install.sh` in both is a placeholder until an artifact exists. No native x64 result for it
  is recorded because there is none.
- Exact vendor versions and SHA-256 pins for the archive document. The licensee fills them in at first build.
- A `DUAL_ORACLE_EQUIVALENT` certification row and any `VENDOR_CONVERTERS` fixture in the audit's
  capability table. The table says which capabilities rest on what today, and the vendor rows stay empty.
- The vendor-written release (`corpus/release/<version>/` with vendor converter pins), a different manifest from
  the open one, signed off after the vendor audit.
