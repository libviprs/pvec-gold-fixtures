# OCCT built from source with contraction off (spike, issue 75)

The question: is the last-digit difference between x86_64 and arm64 in `step_eval` output caused by the Debian
OCCT package being compiled with the compiler's default floating-point contraction? GCC on aarch64 fuses
multiply-adds (FMA) by default and on x86_64 it does not, and `step_eval` itself already builds with
`-ffp-contract=off` while the library under it did not.

## What I built

`docker/step-validator/Dockerfile.occt-src` is the shipped validator with one change: OCCT 7.6.3 comes from the
pinned tarball `V7_6_3` (SHA-256 `3f95808e2c5060c5b5001770b5e42c7d9a849b23d925272bc70a5a2377413aa9`, checked in the
build) compiled with `-O2 -ffp-contract=off` in C and C++, and only the toolkits `step_eval` links, plus what they
need (no Visualization, OCAF or Draw). Same base image digest, same `step_eval`. The shipped `Dockerfile` is not
changed: this is a spike, and the answer decides whether it should be.

Built natively, one image per architecture: `gold-o75:amd64` on mars (`sha256:e64a4451...`, OCCT stage 181 s with 10
jobs) and `gold-o75:arm64` on mercury (`sha256:c6e9d212...`, 411 s with 5 jobs). Local images only, nothing pushed.

## What I compared

`validator/derive_set.py` runs `step_eval` over the six self-test files (`fixtures/validator-selftest`) and the 29
retained signature STEP files and keeps the raw output. `validator/spike_compare.py` diffs two such directories:
`validator/compare_platforms.py` on every `f64_hex` of the self-test records, and the signatures byte for byte, also
against the frozen `signatures/`. The Debian image is `docker/step-validator/Dockerfile --target test`.

| pair | self-test values (1219) | signatures byte identical |
|---|---|---|
| Debian OCCT, x86_64 against arm64 (the baseline) | 11 diverge | 19 of 29 |
| source OCCT, x86_64 against arm64 | 0 diverge | 29 of 29 |
| Debian x86_64 against source arm64 | 0 diverge | 29 of 29 |
| Debian x86_64 against source x86_64 | 0 diverge | 29 of 29 |
| frozen signatures against source x86_64 and source arm64 | not applicable | 29 of 29 and 29 of 29 |

The baseline row reproduces the numbers in `docs/validator/step-evaluator.md` and `docs/benchmarks/validation.md`
exactly (11 of 1219, all in `rational-bspline`; the same ten fixtures differ).

## Result

The FMA guess was right. With contraction off in the library, the six self-test files and all 29 signatures are
bit-identical across native x86_64 and native arm64, and identical to the frozen set. Building from source on x86_64
changes nothing against the Debian package, so the pin is not hiding a different library. glibc's libm is not a
remaining source here: the two images share the Debian 12 base and the results already agree to the last bit.

## What it means

Issue 74 made the contract robust: stored bits are compared bitwise and derived values under the numeric policy, so
an arm64 run passes with the Debian library. This spike shows the stronger thing is also available: with the source
build, no tolerance is needed for these 29 fixtures. I have not switched the shipped image, because it costs a 3 to 7
minute OCCT build (cacheable as its own stage) and the policy comparison is the right contract regardless. If bitwise
signatures across architectures are ever wanted, `Dockerfile.occt-src` is the way, and it has been measured.
