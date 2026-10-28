# ADR 0010: open-source only, and the end of the vendor route

Status: accepted. Supersedes the licensed-tool clauses of ADRs 0002, 0003, 0004, 0007, 0008 and 0009, and each of those carries an amendment pointing here. Panel findings answered: 1 and 9, the same two ADR 0009 answered, now with the licensed path gone instead of deferred.

## Context

The epic was written around CAD Exchanger and the ODA SDKs as mandatory converters. Nobody here holds an entitlement and none of them was ever run. Meanwhile the open route caught up: one open converter is qualified, and a second one on a different decoder lineage is reviewed and waiting to merge. Keeping a `VENDOR_CONVERTERS` scope, two placeholder images and a list of deferred vendor work around describes work that isn't going to happen, and it makes the corpus read as if the open result were a stand-in for something better.

## Decision

Only open-source software, under an OSI-approved licence, takes part in producing, converting, evaluating or checking a fixture. Licensed or non-redistributable tools are out of the requirements. They aren't deferred.

- `oracle_scope` has two values, `NONE` and `OPEN_CONVERTERS`. `VENDOR_CONVERTERS` is removed from the vocabulary, the schemas and the checks. No committed artifact ever carried it.
- The oracles of a revision are the open converters its manifest names, with id, version, source commit, lineage, `links_occt` (false) and image digest, as ADR 0009 says. There are two lineages today: ACadSharp (MIT) and LibreDWG (GPL-3.0-or-later, built and published from its own repository).
- DWGs are written by open writers named per fixture in the manifest. acadrust (MPL-2.0) is the first. ACadSharp's writer and LibreDWG's r2000/r2004 writer may be added, each cross-read by the other family.
- Every image is open, multi-arch where the code allows, rebuilt from pinned inputs and consumed by digest. There is no secret, licence file or activation material anywhere in the pipeline, so the only rule left from ADR 0007 is that none may ever appear, and the guard that enforces it stays.
- A requirement that could only be met by a licensed tool is dropped, and the drop is written down. Today that is one sentence: "a writer the downstream CAD world actually uses". AutoCAD-written bytes enter only through the real-world corpus, with provenance.

## Consequences

The vendor images, their wrapper, their qualification pages, the archive document and the vendor-deferred list go (issues 63 and 64). The corpus's claims don't get stronger by this: an `OPEN_CONVERTERS` fixture still says that two independent open decoders and an independent evaluator agree with the authored mathematics, and says nothing about any commercial product. What changes is that this is now the whole claim, not the interim one.

The closed epic issues that carry the old "Licensing and platform" paragraphs stay closed and unedited. This ADR is what supersedes them.
