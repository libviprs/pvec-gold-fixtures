# CAD Exchanger Batch: qualification

Status: **not qualified. The vendor artifact isn't available**, so nothing below has been
measured. This page holds the procedure and the interface the install step has to meet, so that
dropping the artifact in is the only thing left. It doesn't hold any number I haven't measured.

## What exists

- `docker/cadex/Dockerfile`: pinned base image digest; the build refuses to continue unless
  `vendor/cadex/$CADEX_ARTIFACT` exists and matches `CADEX_SHA256`, and never fetches or substitutes
  an artifact. `tools/check_converter_images.sh` runs the failure cases on the x86_64 host (missing
  build args, missing artifact, wrong hash, and a correct pin on a dummy file reaching the install
  placeholder). All pass.
- `docker/cadex/install.sh`: a placeholder that fails on purpose. It has to install the artifact into
  `/opt/cadex` and write two commands: `/opt/cadex/bin/convert-cmd <in.dwg> <out.step>` (exit 0, or one
  of 11 to 16 below) and `/opt/cadex/bin/product-version` (one line). Those two lines are the only
  place the vendor's command line appears.
- `tools/convert_cadex.sh`: the entrypoint. Atomic output (written under a temporary name and moved
  only after it checks out, with any older `primary.step` removed first), a status record for every run
  (`schema/converter-status.schema.json`), the declared `FILE_SCHEMA` read straight from the STEP
  header and required to be AP242, input and output SHA-256, wall time. Tested against stub vendor
  commands in `tests/test_convert_wrapper.py` (10 tests).
- `runner/step_normalise.py`: byte comparison of two STEP files except the named nondeterministic
  fields. The only default field is the `FILE_NAME` time stamp. Anything else the converter varies has
  to be named here after it has been observed.
- `docker-compose.yml`: the `cadex-converter` service with `platform: linux/amd64`, no network, a read-only
  root, all capabilities dropped, and the licence bind-mounted read-only at run time from
  `$CADEX_LICENSE_FILE`.
- `tools/check_no_licence.sh`: scans an image's history and every layer, plus any log, for licence
  material (private key blocks, `licence_key=...`-shaped assignments), printing where and how many but
  never the text. It reports no match on the step-validator image (one allowlisted path: GnuTLS embeds its own self-test keys in libgnutls, listed with the reason in `tools/licence-allowlist.txt`), and fires on history, layer files and key blocks on a throw-away image
  with a made-up `licence_key=` line in it.

## Exit codes

Shared with the ODA converter, and recorded in `schema/converter-status.schema.json`:

| code | class | meaning |
|---|---|---|
| 0 | | ok |
| 10 | `BAD_ARGUMENTS` | usage |
| 11 | `INPUT_UNREADABLE` | input missing or unreadable |
| 12 | `INPUT_MALFORMED` | not a valid DWG |
| 13 | `DWG_VERSION_UNSUPPORTED` | a DWG version the product doesn't read |
| 14 | `LICENCE_UNAVAILABLE` | licence missing, expired, or over its concurrency limit |
| 15 | `CONVERSION_FAILED` | anything else the converter reports |
| 16 | `OUTPUT_NOT_WRITTEN` | reported success but no STEP file, or not a STEP file |
| 17 | `SCHEMA_NOT_AP242` | the produced file declares a different schema |
| 20 | `INTERNAL` | the wrapper itself |

## What the real qualification has to produce

Everything here is a to-do until the artifact exists, and each result gets labelled native x64
(the licensed product is x86_64 only, so every run is on MARS) or arm64 (there is none).

1. Product and build version, the image digest, and two consecutive builds from the same pinned
   inputs on MARS showing the same digest, or the layer that differs.
2. A DWG converted twice: byte-identical STEP except the named fields, with those field names listed.
3. A malformed DWG: non-zero exit, a parseable record, no `primary.step`.
4. `tools/check_no_licence.sh` on the image and on the run logs, result recorded.
5. Log and status stability across repeated runs.
6. The DWG versions accepted.
7. The licence findings.

## Blockers, exactly

1. **The CAD Exchanger Batch Linux x86_64 build**, supplied by the licensee into `vendor/cadex/`, with
   its SHA-256 and product build recorded as the pin. I haven't downloaded, licensed or paid for it.
2. **A licence that can reach the container on MARS** without a credential being copied onto the
   build host. The standing rule is that nothing of that kind is copied there, which conflicts with a
   licence file that has to be present on the host to be bind-mounted. Either the licensee puts it on
   MARS through a path they control, or the product uses a licence server (which means changing
   `network_mode: none` for this one service), and that decision belongs to the licensee.
3. **The terms**, which I can't read: whether container use, concurrent runs and private distribution
   of the built image are allowed, and whether DWG import is part of the licensed edition. The
   document's licence section is to be filled from the actual agreement.
4. **The command line** for DWG to STEP AP242 in the Batch build, and its error behaviour, for
   `convert-cmd`.
