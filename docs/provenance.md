# Corpus provenance and licensing

Every fixture carries a provenance kind and a licence verdict, and the verdict decides whether it may be in
a public release.

## Provenance kinds

- `SYNTHETIC_AUTHORED`: I authored the parameters (`tools/authoring/params/`) and a writer produced the DWG from
  them. Nothing is derived from anyone else's drawing.
- Real-world drawings: not in the corpus yet. Issue #11 (O2.1/O2.2) is still open, and there is no
  `corpus/provenance.json`. When real drawings arrive, each needs a licence identifier and a redistribution
  verdict before it can be in a release; one without them is left out and the audit records it.

## Licence verdicts

`PUBLIC_REDISTRIBUTABLE` may be in a public release. `PRIVATE` DWG bytes never are. A fixture with a licence
or provenance problem is `QUARANTINED` with reason `LICENCE_OR_PROVENANCE` (ADR 0006).

## What r0-open holds

All 30 accepted fixtures are `SYNTHETIC_AUTHORED` and `PUBLIC_REDISTRIBUTABLE`. The DWGs were written by acadrust
(`libviprs/acadrust` at a pinned commit, a fork of an MIT project) and read by ACadSharp (MIT) and acadrust itself.
The repository is under the MIT licence (`LICENSE`). No file is attributed to CAD Exchanger or ODA, and nothing in a
release carries vendor bytes ([converters/archive.md](converters/archive.md) and `tools/vendor_guard.sh` keep it
that way).
