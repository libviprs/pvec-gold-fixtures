# Converter throughput and cost

Issue 20 (O3.1). The converter measured is the open one, `dwg2step-acadsharp` (ACadSharp 3.7.1+d7dc111), over the 30 `r0-open` DWG probes. Numbers come from `bench/converters/run.py`; the raw record is `reports/bench/converter-throughput.json`.

## Where the numbers came from

- **native x86_64**: host `mars`, docker platform `linux/amd64`, image `gold-dwg2step-acadsharp:test-amd64` (`sha256:2d97c4423580f595d37a4b1d9b9fad56fe0575901d4bce9069c0cab4796331a6`). No emulation: the image architecture the daemon reports is `amd64`.
- **native arm64**, for comparison only: host `mercury`, platform `linux/arm64`, image `gold-dwg2step-acadsharp:test-arm64` (`sha256:26b1ecdc991e8168ad9b227fe2c5756fe5b49c08c24671eca8d1d4d0664a9587`).
- No number here came from local Rosetta or any other emulation. Nothing ran on the Mac.
- Every row is 7 repeats of one throw-away container, one at a time (concurrency 1). Median and the interquartile range are reported; min and max are in the JSON.
- Licence: the converter is MIT and takes no licence. The concurrency limit applied is 8, the cap in `docker/converter-limits.json` (not a vendor licence). Concurrency 1 is below it, so the limit did not bound these numbers; it bounds the parallel runs in `orchestration-tuning.md`. The CAD Exchanger and ODA converters were not measured (no licence), see `docs/vendor-deferred.md`.
- Host load average when the run started, x86_64: 5.75 3.08 1.51; arm64: 0.08 0.14 0.15. `mars` is shared, so its absolute times carry some noise.

## What is separated from what

`total` is `docker run` as seen from outside. `conversion` is the converter process inside the container, timed there, dotnet runtime start included. `startup` is the difference: creating, starting and removing the container. The no-op is the same image run with no arguments (the converter exits 10 as soon as its runtime is up), so a slow image shows up there and not in the conversion column.

| | native x86_64 total | inner (runtime start) | native arm64 total | inner |
|---|---|---|---|---|
| no-op (ms, median) | 243 | 35 | 163 | 47 |

## Per fixture (median ms, iqr in brackets; RSS and step size as stated)

| fixture | x64 startup | x64 conversion | x64 peak RSS MiB | x64 cgroup MiB | arm64 conversion | arm64 startup | STEP bytes | failure rate |
|---|---|---|---|---|---|---|---|---|
| arc-seam-001 | 273 (70) | 135 (4) | 57.1 | 18.8 | 157 (5) | 117 (3) | 2350 | 0.00 |
| bezier-d3-001 | 169 (33) | 134 (12) | 57.4 | 19.3 | 160 (3) | 119 (11) | 2393 | 0.00 |
| bspline-d3-001 | 154 (14) | 131 (4) | 57.5 | 19.2 | 158 (3) | 116 (8) | 2787 | 0.00 |
| bspline-d5-001 | 240 (18) | 137 (6) | 57.4 | 19.2 | 161 (2) | 119 (3) | 2998 | 0.00 |
| bulge-arc-001 | 148 (16) | 135 (5) | 57.3 | 19.1 | 158 (2) | 116 (7) | 2352 | 0.00 |
| bulge-arc-neg-001 | 146 (23) | 131 (4) | 57.3 | 19.1 | 158 (5) | 120 (8) | 2352 | 0.00 |
| circle-001 | 166 (20) | 129 (8) | 57.2 | 19.0 | 158 (3) | 117 (6) | 2351 | 0.00 |
| closed-by-endpoint-001 | 336 (66) | 141 (12) | 57.3 | 19.2 | 157 (4) | 115 (4) | 2788 | 0.00 |
| closed-periodic-001 | 188 (38) | 134 (3) | 57.3 | 19.3 | 162 (2) | 115 (6) | 3213 | 0.00 |
| ellipse-001 | 282 (123) | 135 (7) | 56.9 | 19.3 | 156 (2) | 114 (3) | 2375 | 0.00 |
| elliptical-arc-001 | 247 (113) | 132 (4) | 57.1 | 19.2 | 157 (5) | 113 (6) | 2375 | 0.00 |
| large-coords-001 | 240 (99) | 136 (5) | 57.2 | 19.2 | 158 (2) | 116 (5) | 3039 | 0.00 |
| layer-state-001 | 291 (30) | 136 (5) | 57.1 | 19.2 | 157 (6) | 118 (3) | 3040 | 0.00 |
| line-001 | 260 (41) | 135 (11) | 56.9 | 19.0 | 156 (4) | 119 (8) | 2237 | 0.00 |
| lwpolyline-closed-001 | 316 (144) | 133 (5) | 57.4 | 19.2 | 157 (2) | 118 (5) | 3445 | 0.00 |
| near-singular-001 | 202 (113) | 177 (7) | 57.3 | 19.4 | 158 (3) | 120 (5) | 0 | 1.00 |
| nested-blocks-001 | 306 (153) | 145 (28) | 57.2 | 19.0 | 160 (3) | 121 (9) | 2238 | 0.00 |
| nonuniform-scale-circle-001 | 167 (107) | 136 (5) | 57.0 | 18.8 | 158 (1) | 121 (6) | 2375 | 0.00 |
| nonuniform-scale-rotated-001 | 163 (60) | 134 (5) | 57.1 | 19.1 | 159 (2) | 119 (7) | 2375 | 0.00 |
| nonunit-weight-001 | 164 (59) | 137 (5) | 57.6 | 19.1 | 160 (3) | 118 (11) | 2786 | 0.00 |
| nurbs-d2-offconic-001 | 229 (106) | 150 (20) | 57.3 | 19.3 | 160 (3) | 118 (5) | 2786 | 0.00 |
| nurbs-d3-001 | 246 (64) | 193 (84) | 57.5 | 19.1 | 162 (2) | 118 (14) | 2916 | 0.00 |
| polyline-001 | 198 (109) | 140 (10) | 57.3 | 19.1 | 160 (2) | 120 (7) | 3445 | 0.00 |
| polyline2d-001 | 175 (38) | 134 (3) | 57.4 | 19.2 | 160 (2) | 117 (10) | 3445 | 0.00 |
| reflection-001 | 181 (8) | 135 (8) | 57.2 | 19.2 | 159 (4) | 115 (3) | 2353 | 0.00 |
| repeated-knot-c0-001 | 192 (67) | 146 (17) | 57.3 | 19.3 | 159 (2) | 118 (7) | 2736 | 0.00 |
| rotation-irrational-001 | 170 (5) | 134 (8) | 57.3 | 19.1 | 158 (2) | 119 (3) | 2238 | 0.00 |
| tiny-radius-001 | 235 (107) | 132 (7) | 56.9 | 19.0 | 157 (3) | 116 (4) | 2350 | 0.00 |
| translation-001 | 191 (79) | 140 (59) | 57.3 | 19.1 | 159 (5) | 116 (7) | 2238 | 0.00 |
| uniform-scale-001 | 179 (50) | 143 (25) | 57.2 | 19.0 | 161 (7) | 118 (3) | 2351 | 0.00 |

Peak RSS is the converter's VmHWM; `cgroup` is the container's `memory.peak`, the figure a `--memory` limit is compared with (it is smaller because file-backed pages shared with the runtime image are charged to whichever cgroup touched them first).

## What the numbers say

- The conversion itself is cheap and flat: medians run from 129 to 193 ms across all fixtures on x86_64. These probes are a handful of curves each, so the differences between fixtures are inside the spread. A real-world drawing will behave differently and this corpus cannot say how.
- Container creation, not conversion, is the largest single cost: about 198 ms of startup against about 135 ms of conversion per call on x86_64.
- Peak memory is the same for every fixture within a MiB or two, about 58 MiB resident and 19 MiB in the cgroup, because the dotnet runtime dominates.

## Failures

Failure rate over the full corpus, x86_64: 0.0333 (arm64: 0.0333).

| fixture | rate | exit | cause |
|---|---|---|---|
| near-singular-001 | 1.00 | 15 | ERROR (exit 15): {"code": 15, "class": "CONVERSION_FAILED", "message": "NEAR_SINGULAR_TRANSFORM: the composed map of block PROBE_NEAR_SINGULAR_001_L1 has /ad - bc/ = 1E-12 with big = 1 (PVec numeric policy NP-19)"} |

That one is the designed refusal (NP-19, `near-singular-001`), not a defect: the scheduler records it as refused and the run does not fail on it. There is no other failure on either architecture.

## Not measured

- The named real-world subset: there is none here (no real-world drawing is held, issue 11). Recorded in `docs/vendor-deferred.md`.
- CAD Exchanger and ODA throughput: no licence. Their licence concurrency limits are unknown and the scheduler treats an unknown limit as 1.
