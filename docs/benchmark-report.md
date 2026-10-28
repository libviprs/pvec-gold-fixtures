# Benchmark report

The measurements are in `docs/benchmarks/`, written with the benchmark work (issue 20). This page collects the
headline numbers and adds the clean-host timings. Every number says whether it is native x64 or arm64, and none came
from Rosetta or any emulation. The converter measured is the open one, `dwg2step-acadsharp`; the licensed converters
were not measured because they are not available here ([vendor-deferred.md](vendor-deferred.md)).

| measurement | native x64 (mars) | native arm64 (mercury) | detail |
|---|---|---|---|
| one conversion, inner, per fixture | about 135 ms median | about 158 ms median | [converter-throughput.md](benchmarks/converter-throughput.md) |
| container start and teardown | 243 ms total for a no-op | 163 ms | the same page |
| peak memory of a conversion | 19.9 MiB cgroup, 57.8 MiB resident, largest fixture | | [orchestration-tuning.md](benchmarks/orchestration-tuning.md) |
| whole corpus (30 DWGs) at parallelism 8 | 2.62 s median | | the same page |
| evaluation of one STEP file (`step_eval` load) | about 15 ms | about 13 ms | [validation.md](benchmarks/validation.md) |
| clean host, build both images from nothing | 59 s | 81 s | [reproducibility.md](reproducibility.md) |
| clean host, rewrite all DWGs and read them back | 84 s | 83 s | the same page |
| clean host, 29 fixtures converted twice, evaluated, normalised | 62 s | 37 s | the same page |

Not measured, and said so in the benchmark pages: the adaptive geometric comparison (the stage does not exist yet),
and anything for CAD Exchanger or ODA.
