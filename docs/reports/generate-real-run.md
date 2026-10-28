# A real generate run with both open converters

I ran `docker compose run --rm fixture-runner generate` for real on 2026-10-28, with `acadsharp-converter` (ACadSharp) and `libredwg-converter` (LibreDWG) as the pair, `step-validator` as the evaluator, and `bspline-d3-001` as the named fixture. It ran on native x86_64 (mars). Nothing was pushed to a registry, and the images are by local id.

The runner needs a docker daemon where its leak check means something, and mars runs a lot of other work, so I used a throw-away `docker:27-dind` daemon (removed afterwards) with the images loaded into it. Inside it, `docker ps -a` and `docker volume ls` start empty and stay that way, so a leak can only be mine.

| Image | Id |
|---|---|
| `pvec-gold/dwg2step-acadsharp:local` | `sha256:2d97c4423580f595d37a4b1d9b9fad56fe0575901d4bce9069c0cab4796331a6` |
| `pvec-oracle-libredwg` (built from `libviprs/pvec-oracle-libredwg` main, GPL, never a build context here) | `sha256:f8f387bc0b9e50e48242f17e2ba9225c96c3f7e2ee14f3e48edf2cfbce52a1f7` |
| `pvec-gold/step-validator:local` | `sha256:2a0b8c4f29331f5b477398feb38e1a6d2a0428ce1c3e2d8dea753fe3fd64cf9d` |

## The clean run

```
$ LIBREDWG_IMAGE=pvec-oracle-libredwg:green FIXTURE_DIR=/repo/gen-fixtures \
    docker compose run --rm fixture-runner generate --check-leaks bspline-d3-001
stage hash bspline-d3-001 on x86_64
stage truth bspline-d3-001 on present
stage convert-primary bspline-d3-001 on native x64
stage convert-secondary bspline-d3-001 on native x64
stage validate-primary bspline-d3-001 on native x64
stage validate-secondary bspline-d3-001 on native x64
stage normalise bspline-d3-001 on native x64
stage compare bspline-d3-001 on x86_64
bspline-d3-001: KNOWN_TRUTH_EXACT
leak check: docker ps -a and docker volume ls are as they were
0 of 1 fixtures quarantined
```

Exit 0. `generated/` holds primary.step, secondary.step, primary.status.json, secondary.status.json, primary.verification.json,
secondary.verification.json, primary.signature.json, secondary.signature.json, verdict.json, manifest.json and checksums.sha256.
The verdict is `KNOWN_TRUTH_EXACT`, both cells `STRUCTURAL_EXACT` over 47 fields, the two signatures are byte for byte the same
file (`0a77cfac...`), and the manifest names both converters, their lineages (acadsharp, libredwg), the image ids above and OCCT 7.6.3.

## The interrupt with a conversion in flight

I started `generate bspline-d3-001 line-001` as a named container (`g66-runner`), polled `docker ps` until a converter container was
running, and sent SIGINT to the runner with `docker kill --signal=INT`.

```
converter container running when the signal was sent: pvec-gold-fixtures-acadsharp-converter-run-7e8fac8ff153
g66-runner exit: 130
stage convert-primary bspline-d3-001 on native x64
interrupted: containers torn down
docker ps -a:        (empty)
docker volume ls:    (empty)
```

So no container and no volume were left, including the converter that was mid-conversion.

## What the real run found

Three things the fake docker in `tests/test_generate.py` could not show, each fixed with the red test first:

- The LibreDWG image has no entrypoint (`dwg2step` and `dwgdump` are commands in it), but the runner passes `--in --out --status`
  straight to the service. `docker-compose.yml` now gives `libredwg-converter` the entrypoint `dwg2step`.
- The runner calls `docker compose config` from inside its container, so a `LIBREDWG_IMAGE` set on the host never reached it and
  it looked for the default tag. Compose now hands `LIBREDWG_IMAGE` and `LIBREDWG_PLATFORM` to `fixture-runner`.
- `compose down --volumes --remove-orphans` inside the runner also removes the runner (it is a one-off container of the same
  project), SIGTERMs it halfway through its own teardown, and a clean run came back as exit 130 without reaching the leak check.
  Inside the runner, teardown now removes the project's other containers and volumes by label and leaves its own container alone.
  Outside a container it still runs `compose down`.

Not done here: the digests in `corpus/container.pin.json` stay `null` until someone with a registry session publishes the images
(#66 only asked for the run), and the `Container::start` wiring is a pvec issue.
