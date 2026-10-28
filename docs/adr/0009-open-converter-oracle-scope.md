# ADR 0009: open converter paths and oracle scope

Status: proposed. It is not frozen by the phase 1 exit gate, because it adds a way to fill the oracle
slots and doesn't change what the gate asks. Panel findings answered: 1 (agreement between two tools is
weaker than known truth, so I make the reach of the agreement a field) and 9 (I name the images that can be published).

## Context

ADR 0001 defines the evidence classes, and ADR 0003 says two converters are the oracles whose agreement
earns `DUAL_ORACLE_EQUIVALENT`. Both ADRs were first written around licensed converters, which
need a licence to rebuild anything. `libviprs/pvec#118` and `libviprs/pvec#100` can't wait on
that, so the plan is two open DWG to STEP converters: one on the ACadSharp reader (MIT) and one on the
LibreDWG reader (GPL, built in its own repository, `libviprs/pvec-oracle-libredwg`).

The risk is a corpus that reads as if an AutoCAD-class converter agreed, when two open decoders did. The
four class names are fine as they are. What is missing is a way to say who the oracles were.

## Decision

**A revision may use two open converters as its oracles**, provided they decode DWG through different
lineages (different reader code, not two builds of one). The revision's manifest names each converter:
`id`, `version`, `source_commit`, `lineage`, `links_occt` and the image digest it ran from. The ids are free
strings (`acadsharp-dwg2step`, `libredwg-dwg2step`), and the
status record's `converter` field takes the same id.

**`oracle_scope`** says how far the oracles reach, on the manifest and on every fixture:

- `NONE`: no STEP oracle ran. `r0-open` is this, and keeps it (its manifest says `oracles: none`, which
  stands for `NONE` because that manifest is pinned and I don't touch it).
- `OPEN_CONVERTERS`: the oracles are open converters, and neither converter links Open CASCADE (ADR 0004).

**`evidence_scope`** gains `STEP_ORACLE` next to `READER_MAPPING_ONLY`. A fixture with `STEP_ORACLE` needs
an `oracle_scope` other than `NONE`, and the manifest has to list at least two named converters with
distinct lineages. `DUAL_ORACLE_EQUIVALENT` likewise needs `STEP_ORACLE` evidence and an `oracle_scope` other than `NONE`.

The four class names and their ADR 0001 definitions don't change. A consumer filters on `oracle_scope` instead of reading a class as more than it says.

`runner/r0_open.py` holds the vocabulary (`ORACLE_SCOPES`, `EVIDENCE_SCOPES`) and `scope_problems`, which
checks a manifest against these rules. `runner/qualify_probes.py` takes `--primary ID DIR --secondary ID DIR`,
needs `--lineage ID=NAME` for both, refuses two equal ids or two equal lineages, writes the lineages into the
report (the gate checks them again), and keeps every verdict rule: the rules never look at the ids.
`DUAL_ORACLE_EQUIVALENT` needs `STEP_ORACLE` evidence.

**Common mode.** The common-mode statement: what the two converters share, said plainly. Both implement the same DWG specification,
so a shared misreading of it would pass (the cross-read in ADR 0008 has the same limit). Both read the
same source DWGs, written by one open writer. Both STEP serialisers are thin and hand-written, so a shared
mistake in how a curve is written to Part 21 is possible. And both outputs go through the same evaluator,
built on Open CASCADE (ADR 0004). What differs is the decoder code, which shares nothing between the two
lineages, and that is all the lineage field records. This is the open route's version of the caveat in
ADR 0003, not a way round it.

## Consequences

An `OPEN_CONVERTERS` fixture proves that two independent open decoders and an independent evaluator agree
with the authored mathematics. It says nothing about any commercial converter, and the field says so.

## Amendment (ADR 0010)

Only open converters are allowed, so `oracle_scope` has the two values `NONE` and `OPEN_CONVERTERS`. The licensed scope and the licensed converter ids are withdrawn. The common-mode statement above stands as written.
