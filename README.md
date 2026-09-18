# pvec-gold-fixtures

A reproducible, Docker-orchestrated fixture pipeline that produces the mathematical reference
corpus read by [`pvec`](https://github.com/libviprs/pvec),
[`libviprs`](https://github.com/libviprs/libviprs) and
[`maplibre-pvec`](https://github.com/libviprs/maplibre-pvec).

**CAD Exchanger** and **ODA Drawings + ODA STEP** are mandatory independent DWG → STEP conversion
paths — and converter agreement alone is explicitly **not** treated as proof of the original DWG's
mathematical intent.

## Status

**Specification stage. There is no pipeline in this repository yet.**

Three phases and 27 issues under [#1](https://github.com/libviprs/pvec-gold-fixtures/issues/1).
Phase 1 proves the methodology — including validating the STEP validator itself against hand-known
primitives — before any mass fixture generation.

## Evidence classes

| Class | What it proves |
|---|---|
| `KNOWN_TRUTH_EXACT` | synthetic fixture with independently specified expected mathematics; the only class that proves source representation exactness |
| `DUAL_ORACLE_EQUIVALENT` | both converters agree geometrically, but the original source parameters are not independently known |
| `REAL_WORLD_DIFFERENTIAL` | real production-style DWG, for regression and provider-difference detection |
| `QUARANTINED` | unresolved disagreement, unsupported entity, approximation, malformed fixture, or a licensing/provenance problem |

Known-truth numbers avoid ambiguous rounded JSON. A documented canonical representation carries the
intended `f64`, for example `{"decimal": "0.70710678118654757", "f64_hex": "0x3fe6a09e667f3bcc"}`.

## Licensing and architecture constraints

- **The converter images are commercial and are not redistributable.** Ordinary CI in `pvec`,
  `libviprs` and `maplibre-pvec` must run with no proprietary converter present.
- **Both converter SDKs are x86_64.** Per `workspace/libviprs/CLAUDE.md`, x64 compiled code is
  exercised on the native x86_64 host rather than under local Rosetta emulation, always in
  containers, always with an explicit `--platform`, and every write-up says which results are
  native x64 and which arm64.
- No credential is written to a file, echoed, or copied to a build host.
