# Corpus provenance and licensing

Every fixture carries a provenance kind and a licence verdict, and the verdict decides whether it may be in
a public release.

## Provenance kinds

- `SYNTHETIC_AUTHORED`: I authored the parameters (`tools/authoring/params/`) and a writer produced the DWG from
  them. Nothing is derived from anyone else's drawing.
- `REAL_WORLD_PUBLIC`: a public drawing with an established licence. `r1-open` has three, ACadSharp samples under
  MIT, each recorded in `corpus/provenance.json` with its licence identifier, source and verdict. A drawing whose
  licence cannot be established does not enter the corpus. The classes it does not cover are listed in that file.

## Licence verdicts

`PUBLIC_REDISTRIBUTABLE` may be in a public release. `PRIVATE` DWG bytes never are. A fixture with a licence
or provenance problem is `QUARANTINED` with reason `LICENCE_OR_PROVENANCE` (ADR 0006).

## What r0-open holds

All 30 `r0-open` fixtures are `SYNTHETIC_AUTHORED` and `PUBLIC_REDISTRIBUTABLE`. The DWGs were written by acadrust
(`libviprs/acadrust` at a pinned commit, a fork of an MIT project) and read by ACadSharp (MIT) and acadrust itself.
The repository is under the MIT licence (`LICENSE`). No file is attributed to CAD Exchanger or ODA, and nothing in a
release carries vendor bytes ([converters/archive.md](converters/archive.md) and `tools/vendor_guard.sh` keep it
that way).
