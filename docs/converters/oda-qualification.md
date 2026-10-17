# ODA Drawings SDK and ODA STEP SDK: qualification

Status: **not qualified. Neither SDK is available**, so nothing below has been measured. This page
holds the contract the wrapper has to meet and the procedure, so that dropping the artifacts in is the
only thing left.

## What exists

- `docker/oda/Dockerfile`: pinned base image digest; the build refuses to continue unless both
  `vendor/oda/$ODA_DRAWINGS_ARTIFACT` and `vendor/oda/$ODA_STEP_ARTIFACT` exist and match their pinned
  SHA-256, and never fetches or substitutes an SDK version. `tools/check_converter_images.sh` runs the
  failure cases on the x86_64 host (all pass).
- `docker/oda/install.sh`: a placeholder that fails on purpose. It has to unpack the SDKs, build
  `docker/oda/src/oda_dwg2step.cpp` against them, and install `/usr/local/bin/oda_dwg2step`.
- `docker-compose.yml`: the `oda-converter` service with `platform: linux/amd64`, no network, a read-only
  root, all capabilities dropped, and the activation material bind-mounted read-only at run time from
  `$ODA_ACTIVATION_FILE`.
- `schema/converter-status.schema.json` and the exit-code table below.
- `tools/check_no_licence.sh` and `runner/step_normalise.py`, shared with the CAD Exchanger path.

`oda_dwg2step.cpp` isn't written. It is written against the SDK's API, which I don't have, and
writing it from memory would only look finished.

## The wrapper's contract

```
oda_dwg2step --in source.dwg --out secondary.step [--status secondary.status.json]
```

- No GUI, no interactive activation, no prompt. Activation material is read from
  `/run/secrets/oda-activation` and is never written, echoed or logged.
- Output is written under a temporary name and moved into place only on success; a failed run leaves
  no `secondary.step`, not even an older one.
- It writes the same status record as the CAD Exchanger path, with `converter: "oda"`.
- Reader notifications from the DWG side are captured into the record's `warnings`, not discarded, and
  are carried into `secondary.verification.json`'s provenance block.
- STEP schema is AP242, checked from the written `FILE_SCHEMA` the same way as in `convert_cadex.sh`.

## Exit codes

The same table as in `docs/converters/cadex-qualification.md` (0, 10 to 17, 20). The mapping from ODA
exceptions and reader notifications to these codes is the part that needs the SDK; every failure seen
on the probe corpus must land on a row, with no "unknown" row. That table gets filled in here as the
failures are observed.

| ODA exception / notification | code | class |
|---|---|---|
| (to be filled from observation) | | |

## What the real qualification has to produce

1. SDK versions, the image digest, and two consecutive builds from the same pinned inputs on MARS
   showing the same digest, or the layer that differs.
2. The error-code table filled from observed failures.
3. One DWG converted twice: byte-identical except the named fields.
4. The DWG versions read, and the DWG versions the Drawings SDK writer produces (O1.5 and O1.6 need the
   writer to author `source.dwg` from the probe parameters, and its output has to regenerate
   byte-identically except for named header fields).
5. `tools/check_no_licence.sh` on the image, and a check that no SDK binary is in the repository.
6. The membership and licence terms for container and concurrent use.
All runs are native x86_64 on MARS.

## Blockers, exactly

1. **The ODA Drawings SDK and ODA STEP SDK Linux x86_64 builds**, downloaded by an ODA member into
   `vendor/oda/`, with their SHA-256 and versions recorded as the pin. I haven't downloaded, licensed or
   paid for either, and I don't know whether the current membership level includes both, or the DWG
   writer.
2. **Activation** that can reach the container on MARS without a credential being copied onto the
   build host (same conflict as for CAD Exchanger, see its blockers).
3. **The terms** for container use, concurrency and private image distribution.
4. **The STEP SDK's export API and AP242 support**, which decide whether `oda_dwg2step.cpp` can meet
   the contract above as written.
