# ADR 0008: open-writer known-truth corpus

Status: proposed, and a panel decision. It is not frozen by the phase 1 exit gate, because it is a way
round that gate's blockers and not part of it. Panel findings answered: 1 (an agreement between two
tools is weaker than known truth, so I say exactly how weak this one is) and 2 (the truth is authored
before any DWG exists).

## Context

Epic O (#1) is blocked. Every task that needs a DWG waits on a licensed DWG writer or a licensed STEP
converter, and none of them is qualified, so O1.5 and O1.6 have
`expected.math.json` records and no `source.dwg` anywhere. The downstream repositories (`pvec`,
`libviprs`, `maplibre-pvec`) need something real to read, and a corpus that can be built today by an
open writer is better than a pipeline that waits on a licence.

The catch is that an open writer proves much less than the pipeline in #1 was designed to prove, and I
don't want the corpus to look stronger than it is.

## Decision

I build corpus revision `r0-open`, a candidate revision (O2.9 is the freeze, and this isn't it), from
DWGs written by an open writer, and I state its limits in the manifest itself.

**Writer.** `acadrust`'s `DwgWriter`, pinned to one commit of `libviprs/acadrust`, writing DWG version
AC1032. The manifest records `writer: acadrust@<version>` and where the source came from. A probe the
writer can't store exactly is not written as a lookalike: it is excluded and listed with the reason
(`UNSUPPORTED_ENTITY`, ADR 0006). In the first run those are `shear-001` and `general-affine-001`, and
`singular-001`. For the first two the honest statement is narrow: there is no single INSERT form, since one
INSERT carries translation, one rotation and three scales and no shear. A three-level nested INSERT chain
(rotate, scale, rotate) could carry the 2x2 part through a singular value decomposition, but the factors would
be derived values (compared under policy, not EXACT), and these probes' own truth is a rejection outcome that no
reader-mapping check can exercise, so I did not attempt it. `singular-001` is different: acadrust's scale
setter rewrites a zero scale to 1e-12, which would turn it into another probe. (I also read ACadSharp's
`Insert.XScale` setter, which refuses zero by throwing, so I don't expect that family to store it either. That is
a reading of its source, not a run.)

**Truth.** The `expected.math.json` records and parameter files that O1.5a and O1.6a already recorded.
They were authored before any DWG existed and r0-open never edits them. The manifest holds each file's
SHA-256, and `python3 -m runner.r0_open check` fails if either changes. The writer takes the exact f64
bits from the records' `f64_hex` fields, and the transform operations from the decimal strings of the
parameter files. That has a consequence I'd rather state than hide: the writer's input is the truth, so
the check can't catch a mistake in the authoring. It checks the path from the authored numbers through a
DWG file and back out of two decoders that were written separately.

**Cross-read rule.** Every probe DWG written by one open family is also read by the other family's
reader: acadrust-written files are read by ACadSharp's reader (upstream ACadSharp built from source at a
pinned commit, which is the C# the `acadsharp-rs` crate wraps, without `libviprs-dep`'s NativeAOT build),
and a file written by ACadSharp's writer would be read by acadrust's reader. A probe is `AGREE` only if
all three of these hold:

1. the other family's reader returns the authored mathematics,
2. the writer family's own reader returns it too, and
3. the two readers' decoded records of the DWG are identical, field for field.

If one fails, the probe is `QUARANTINED` with `UNRESOLVED_DISAGREEMENT` and the evidence (the fields
that differ). If the other family's reader can't open the file, it is quarantined as `MALFORMED_FIXTURE`.
The two readers are independent in code and not in specification: both implement the same DWG specification
(and acadrust's writer cites ACadSharp in places). So the cross-read is a common-mode-limited check. It catches
round-trip loss, and a decoder bug that one reader has and the other doesn't, but not a shared misreading of the
specification, which both would decode the same way and which would therefore never show up as a difference. I don't claim more than that anywhere in the corpus.

A probe is never accepted on the writer's say-so, and never accepted because the two readers agree with
each other while both differ from the truth. Both read records are stored with the DWG, so the verdict is
recomputed from them, without a DWG library, by `runner/r0_open.py check`.

**Two comparison modes, per field.** `EXACT` where the DWG stores the authored f64 verbatim (points,
radii, control points, knots, weights, bulges, scales, insert points) and both readers must return the
same bits. `POLICY` where the DWG stores a derived value (an arc's end angle, an ellipse's major axis
vector and ratio, an INSERT's rotation angle), compared with PVec numeric policy v1 (`near`, NP-05). The
mode is written next to every field in `comparison.json`. The world-space results of the transform
probes are computed by the harness from the read-back chain and compared with the record, so they say
nothing about what a reader reports.

**What the corpus says about itself, and what is forbidden.**

- The manifest says `oracles: none` and `step_oracle: none`. No STEP file exists in the revision, and
  none may be added to it.
- Nothing is attributed to a licensed tool, in any file or field. Their outputs and their writer
  are absent from this revision, and any mention is of what is missing.
- No fixture is `DUAL_ORACLE_EQUIVALENT` (ADR 0003). That class needs two converters, and there are none.
- The class of an accepted fixture is `KNOWN_TRUTH_EXACT` with the scope field `evidence_scope:
  READER_MAPPING_ONLY`. ADR 0001 defines `KNOWN_TRUTH_EXACT` as authored mathematics plus a converted output
  that agrees. This revision has no converted output, so the scope field is what narrows the claim, and
  the manifest and every fixture README say so in words: there is no STEP oracle. A consumer that needs
  STEP exactness must not take it from this revision.
- Every artifact names the container image digest that produced it (writer image and reader image), and
  every result is from native x86_64 (MARS).

**What it contains.** Every curve and transform probe from O1.5a and O1.6a that a DWG can carry, plus four
probes added with it, each with its record authored first by `tools/authoring/author_probes.py`: a negative
bulge (`bulge-arc-neg-001`, whose derived counter-clockwise arc, with its orientation reversed against the source,
is checked from the read-back vertices and bulge), a closed lightweight polyline (`lwpolyline-closed-001`), an
old-style 2D `POLYLINE` entity (`polyline2d-001`), and a drawing with an off layer and a frozen layer
(`layer-state-001`). Each manifest entry names the PVec v1 capabilities it exercises (or says it exercises none,
as for layer state, whose use is libviprs policy).

**Pinning.** `corpus/r0-open` is self-contained: besides the DWGs and read records it holds a hash-pinned copy of
each authored record and parameter file (equal to the canonical files under `fixtures/known-truth` and
`tools/authoring/params`, which `check` verifies when they are present). `corpus/r0-open.pin.json` pins the
directory as a deterministic tar (`python3 -m runner.r0_open bundle corpus/r0-open OUT.tar`) by sha256, beside the
manifest's hash and the numeric policy version. The tag `corpus-r0-open` is for whoever merges, on the merge commit.
The revision stays a candidate: O2.9 is the freeze.

**Rejection probes.** `near-singular-001` carries a rejection outcome in its record (`NEAR_SINGULAR_TRANSFORM`,
quarantine) and is accepted here, because what is checked is that the DWG carries the transform as authored. The
manifest says so in `downstream_disposition`, and so does its README: a mapper must not emit a curve for it.

## What this unblocks, and what it doesn't

It gives the downstream repositories real DWGs, with authored truth for what a DWG reader should return,
which is what a DWG reader mapping test needs. It does not say how any converter or STEP path treats these
drawings, that the authored mathematics is what an AutoCAD-class application would draw from them, or
anything about the STEP evaluator. The STEP-side part of O1.5 and O1.6 (STEP verdicts, regeneration under more than one writer, the
discrimination criteria that inject into STEP outputs) is now covered by `r2-open` under ADR 0010, which
supersedes the earlier plan tracked in #42. A later revision supersedes `r0-open`, with
`corpus/CHANGELOG.md` explaining each fixture's class change.

## Consequences

`r0-open` can be rebuilt by anyone with Docker (`tools/r0-open/run.sh`), and read by anyone with Python
(`runner/r0_open.py check`). The honesty rules are executable: `tests/test_r0_open.py` fails if a STEP file
appears, a licensed tool is named as a producer, a fixture takes the `DUAL_ORACLE_EQUIVALENT` class, or a verdict
doesn't recompute. A second open writer (ACadSharp's `DwgWriter`, read by acadrust) is the natural next
revision, and it would test the other direction of the rule.

## Amendment (ADR 0010)

The blockers named in the context are licensed tools, and ADR 0010 drops them from the requirements. The open writer is therefore the plan, and the open converters of ADR 0009 are the oracles.
