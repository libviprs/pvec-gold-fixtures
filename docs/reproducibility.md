# Reproducibility guide

The test is a clean host: a native docker host with none of this repository's images cached rebuilds them from
pinned inputs, regenerates the corpus's derived artifacts with one command, and lands on the hashes in the frozen
manifest, or names exactly what diverged. This page is the procedure, the divergence list and the results.

## Procedure

```
git commit ...                                                        # the run uses a fresh checkout of HEAD (git archive)
tools/clean_host.sh mars --write-release corpus/release/r0-open-1     # first run: writes the release candidate
tools/clean_host.sh mars --against corpus/release/r0-open-1/manifest.json   # second run: must reproduce the first
tools/clean_host.sh mercury --against corpus/release/r0-open-1/manifest.json  # arm64, for comparison only
```

`tools/clean_host.sh` starts a throw-away docker-in-docker daemon on the host, so the image store really is empty
(nothing is pruned, and no other job's images are touched), copies the fresh checkout into it, builds a driver
container there, and runs the one command, `python3 -m runner.reproduce run`. That command:

1. builds `step-validator` and `dwg2step-acadsharp` from their Dockerfiles (base images by digest of the multi-arch
   index, ACadSharp by full commit, OCCT by package version);
2. pulls the writer and cross-reader images by the digests in `corpus/r0-open/manifest.json`, rewrites every
   probe DWG with acadrust (twice, byte-compared), has ACadSharp and acadrust read them back, assembles the corpus and
   checks it, and compares the bundle hash with `corpus/r0-open.pin.json`. The revision's `README.md` is hand-written
   prose, so it is copied in before the checksums are rewritten;
3. converts each accepted DWG twice, evaluates both STEP files with `step_eval`, normalises both to signatures, and
   compares the two runs;
4. compares hashes with the frozen manifest (`--against`), and writes `reports/reproducibility.json` and, with
   `--write-release`, the release directory.

The daemon, and everything in it, is removed at the end. No licence or credential is involved: every input is a
public image or public source, and nothing is written to or copied onto the host but the tree and the results.

## The divergence list

These are the only fields that legitimately differ between two runs from the same pinned inputs. Everything else must
match byte for byte, and `runner/reproduce.py` fails the run on any other difference.

- `step.FILE_NAME.time_stamp`: the converter writes the time of the run into the STEP header (second argument of
  `FILE_NAME`). Normalised to `<TIMESTAMP>` before hashing and comparing (`runner/step_normalise.py`). Setting
  `SOURCE_DATE_EPOCH` fixes it, and the run leaves it unset on purpose so the divergence is exercised.
- `status.wall_time_seconds`: the converter's own clock, in its status record.
- `status.output.path`: where the run wrote the STEP file (the two runs use different directories).
- `status.output.sha256`: the hash of the raw STEP bytes, which carry the time stamp. The STEP is compared after
  normalisation, so this field follows from the first one.
- `image.built_image_id`: the image id of a local build. Two builds from the same pinned inputs gave different ids
  (observed below). I did not chase the layer that differs; what is pinned instead is the base image digests, the source
  commits and the package versions, and the id is recorded for the record.

Signatures, verification records and the normalised STEP carry no allowed difference.

## Results

All three runs used a fresh daemon with 0 images before. The commit is the one in the PR; the pinned inputs are the
digests above. Native x64 is host `mars` (linux/amd64), arm64 is host `mercury` (linux/arm64).

| run | label | result | notes |
|---|---|---|---|
| first | native x64 | PASS | wrote the release candidate `corpus/release/r0-open-1`; regenerated bundle equals the pin (`b0e3377b...`), 0 files differ from the committed corpus, 0 unlisted divergences |
| second | native x64 | PASS | all 29 converted fixtures match the frozen source, STEP and signature hashes, `near-singular-001` refused as before; bundle equals the pin; base image digests equal |
| third | native arm64 | differs | corpus bundle and every STEP hash match; 10 of 29 signatures differ (below) |

Build, regenerate and convert-evaluate-normalise took 59 s, 84 s and 62 s on the second x64 run (two conversions per
fixture, one at a time), and 81 s, 83 s and 37 s on arm64. Built image ids differed on every run:

| run | `dwg2step-acadsharp` | `step-validator` |
|---|---|---|
| first x64 | `sha256:cd8ae705...` | `sha256:535d2244...` |
| second x64 | `sha256:43587c3a...` | `sha256:474a4af8...` |
| arm64 | `sha256:dd0a0f26...` | `sha256:7944c0aa...` |

The full records are `reports/reproducibility.json` (second x64), `reports/reproducibility.run1-x64.json` and
`reports/reproducibility.arm64.json`.

## The architecture caveat

The frozen signatures are the native x86_64 set, as `docs/downstream-contract.md` says. On arm64 the STEP files are
byte-identical, but OCCT's evaluation differs in the last digits and 12-digit rounding does not hide it for 10 of 29
fixtures: `bspline-d3-001`, `ellipse-001`, `elliptical-arc-001`, `large-coords-001`, `lwpolyline-closed-001`,
`nonunit-weight-001`, `polyline-001`, `polyline2d-001`, `rotation-irrational-001` and `translation-001`
(`docs/benchmarks/validation.md` has the fields). Reproducibility hashes are therefore x64-only; an arm64 run is
labelled as such and is not expected to match the signature hashes.

## STEP hashes

The manifest's STEP hash is the SHA-256 of the STEP text with the time stamp replaced by `<TIMESTAMP>`, and the
shipped `step/*.step` carry that literal. The signature hashes are the same as in `signatures/manifest.json`.

## What a licensee adds

The same procedure with the licensed pair is in [vendor-deferred.md](vendor-deferred.md). The vendor images are
built from the licensee's artifacts on the native x86_64 host, and their licences come from the documented secret
paths ([converters/licensing-and-setup.md](converters/licensing-and-setup.md)).
