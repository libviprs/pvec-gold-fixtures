# corpus revision r0-open

The open-writer known-truth corpus: 26 probe DWGs written by acadrust's `DwgWriter` (AC1032) from the
O1.5a/O1.6a probe parameters, each read back by ACadSharp's reader and by acadrust's own reader.
`manifest.json` is the index, `quarantine.json` lists the three probes the writer couldn't store exactly,
and `SHA256SUMS` covers every file here. The rules are in
[ADR 0008](../../docs/adr/0008-open-writer-known-truth-corpus.md).

Read this before you rely on it. There is no STEP oracle: no STEP file was produced, read or compared, and
nothing in this revision was written or converted by CAD Exchanger or ODA. The class `KNOWN_TRUTH_EXACT` is
used for reader mapping only (`evidence_scope: READER_MAPPING_ONLY`). It says that two independent open DWG
readers decode these files to the mathematics I authored before any DWG existed, exactly where a DWG stores
the number verbatim and within PVec numeric policy v1 where it stores a derived value. It does not say how a
converter, a STEP path or an AutoCAD-class application would treat them.

To check it with no DWG library, no converter and no Docker:

    python3 -m runner.r0_open check corpus/r0-open
