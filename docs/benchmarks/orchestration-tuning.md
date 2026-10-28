# Orchestration tuning

Issue 20 (O3.3). Measured by `bench/orchestration/run.py` through `runner.regenerate`, the entry point a real regeneration uses, on host `mars`, **native x86_64**, image `gold-dwg2step-acadsharp:test-amd64` (`sha256:2d97c4423580f595d37a4b1d9b9fad56fe0575901d4bce9069c0cab4796331a6`). Raw record: `reports/bench/orchestration.json`. Every timing here is native x86_64 on the docker host; none is emulated.

## Full-corpus wall time

The 30 `r0-open` DWGs converted, evaluated and normalised, a fresh output tree each time, 3 repeats, per-container limits 2 cpus and 256m.

| parallelism | median wall (s) | min | max | fixtures per second |
|---|---|---|---|---|
| 1 | 17.80 | 17.00 | 18.49 | 1.7 |
| 2 | 9.41 | 9.31 | 9.74 | 3.2 |
| 4 | 4.91 | 4.86 | 5.14 | 6.1 |
| 8 | 2.62 | 2.39 | 2.98 | 11.4 |

**Chosen: parallelism 8** (2.62 s for the corpus, 11.4 fixtures per second), the smallest value within 10% of the best (8 at 2.62 s). The cap for this converter is 8 (docker/converter-limits.json: a cap I set), and the table stops there. Wall time still halves with every doubling, so on this host **the cap is what bounds throughput**, not the host: I did not measure above it, so I do not know where it flattens. The scheduler refuses a request above the cap and limits its pool to it; a converter with no listed limit runs at 1.

## Per-container limits

Observed on the largest fixture (`bezier-d3-001`): peak 19.9 MiB in the cgroup, 57.8 MiB resident. The memory limit is **256 MiB**, about 13x the cgroup peak, and no converter was OOM-killed in the accepted configuration (0). These fixtures are small. A real-world drawing needs its own measurement before this limit is trusted for it.

What I tried on a four-fixture subset (`line-001,nurbs-d3-001,nested-blocks-001,polyline-001`, 9 repeats), median over the fixtures, ms:

| setting | conversion | total (`docker run`) | kept |
|---|---|---|---|
| unlimited | 137 | 387 | (baseline) |
| cpus_1 | 304 | 576 | no: conversion roughly doubles |
| cpus_2 | 136 | 407 | yes: within noise of unlimited |
| cpus_4 | 136 | 398 | no gain over 2 |
| TieredPGO_0 | 127 | 385 | no: about 7% faster conversion, under the 10% bar I set for a runtime switch |
| TieredCompilation_0 | 214 | 454 | no: slower |

The cpu limit is the one setting the numbers justify (a single cpu starves the runtime's second thread). The two runtime switches are reverted: `TieredCompilation=0` is slower, and `TieredPGO=0` gains about 7% on conversion (about 10 ms of a 390 ms call), under the 10% I set as the bar.

## Resume, isolation and teardown

- **Resume**: a parallelism-4 run was interrupted with SIGINT after 8 fixtures were done; the rerun skipped 8 and regenerated 22. The hashes of every untouched fixture's artifacts were identical before and after: **True**.
- **Failure isolation**: each fixture works in its own directory and is moved into place only on success, with its own state file and log (`[fixture-id]` on every line). A failing fixture leaves no artifacts, does not stop the run and does not touch another's; the run exits 1 with a summary. Exercised in `tests/test_scheduler_20.py` with a job that fails. The one real refusal here (`near-singular-001`) is recorded as refused and exits 0.
- **Teardown under parallelism**: a parallelism-8 run aborted with SIGINT left 0 labelled containers, 0 new containers and 0 new volumes on the host.
- **Licence limit**: `tests/test_scheduler_20.py` asks for more than the limit and expects `LicenceLimitExceeded` before any job starts; another test shows the number of jobs in flight reaches the limit and never exceeds it.
- **Logs**: bounded per fixture (the last 1 MiB, `--max-log-bytes` in code), and the compose service rotates its docker log at 1m x 3.

## Settings applied

- `docker-compose.yml`: service `acadsharp-converter` with `mem_limit: 256m`, `memswap_limit: 256m`, `cpus: 2`, rotated logs.
- `docker/converter-limits.json`: the concurrency cap per converter, read by `runner/scheduler.py`.
- `runner/regenerate.py` defaults: `--mem 256m --cpus 2`, `SOURCE_DATE_EPOCH` fixed so the STEP bytes repeat.
- Parallelism 8 is a recommendation for the host measured; it is a flag, not a constant, because the best value depends on the cores of the host.

`runner/generate.py` (issue 13) still converts one fixture at a time through compose; moving it onto the scheduler is the next step and is not done here.

<!-- second-converter -->
## Both converters

Issue 77. The same harness (`bench/orchestration/run.py`, through `runner.regenerate`), host `mars`, **native x86_64**, 3 repeats, per-container limits 2 cpus; ACadSharp at 256m, `libredwg-dwg2step` at 512m (the compose limits). Wall time to convert, evaluate and normalise the 30 `r0-open` DWGs:

| parallelism | acadsharp-dwg2step median wall (s) | fixtures per second | libredwg-dwg2step median wall (s) | fixtures per second |
|---|---|---|---|---|
| 1 | 17.80 | 1.7 | 17.25 | 1.7 |
| 2 | 9.41 | 3.2 | 6.30 | 4.8 |
| 4 | 4.91 | 6.1 | 3.22 | 9.3 |
| 8 | 2.62 | 11.4 | 2.00 | 15.0 |

## libredwg-dwg2step

Image `g77-libredwg:local` (`sha256:df38155d4d343f75e465e8c190f8734a7b83de1f261849f0377a31a544f970c5`). Raw record: `reports/bench/libredwg-orchestration.json`. Step_eval ran from the step-validator test image (local tag g77-stepval:amd64, id sha256:b2d9634dbed9).

**Chosen: parallelism 8** (2.00 s for the corpus, 15.0 fixtures per second), the smallest value within 10% of the best. **Cap: 8** in `docker/converter-limits.json`. I set the cap to 8, the top of the range I measured. Wall time still falls at 8 (see the table), so the cap and not the host bounds throughput, and I did not measure above it. No licence is involved.

**Memory**: largest fixture `large-coords-001`, peak 11.4 MiB in the cgroup and 18.7 MiB resident. The limit is **512 MiB** (`mem_limit` of the `libredwg-converter` service), about 45x the cgroup peak; 0 containers were OOM-killed. That is generous for these probes, and a real drawing needs its own measurement, so I did not lower it.

Cpu limit, four-fixture subset (`line-001,nurbs-d3-001,nested-blocks-001,polyline-001`, 9 repeats), median over the fixtures, ms:

| setting | conversion | total (`docker run`) |
|---|---|---|
| unlimited | 30 | 202 |
| cpus_1 | 30 | 182 |
| cpus_2 | 30 | 189 |
| cpus_4 | 32 | 206 |

The converter is single threaded, so a cpu limit changes nothing measurable (differences are inside the spread). I kept 2, as for the other converter, because a second cpu is what `dwgread` and the python start would use if they overlapped, and it costs nothing here. There are no runtime switches to try.

- **Resume**: a parallelism-4 run interrupted with SIGINT after 8 fixtures were done; the rerun skipped 8 and regenerated 22. Untouched fixtures hashed identically before and after: **True**.
- **Teardown under parallelism**: a parallelism-8 run aborted with SIGINT left 0 labelled containers, 0 new `gold-` containers and 0 volumes labelled by the run. `mars` is shared, so I count only what the runner names or labels; a raw before and after diff of the host would count other people's containers.
- **Refusal**: `near-singular-001` is refused by both converters with `NEAR_SINGULAR_TRANSFORM` (exit 15) and recorded as refused, not failed. Unexpected failures: 0.
- `runner.regenerate --converter libredwg-dwg2step --converter-image IMAGE` runs the binary `dwg2step` of the image (it has no entrypoint) and defaults to 512m.
<!-- /second-converter -->
