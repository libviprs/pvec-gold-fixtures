# closed-by-endpoint-001

This is a probe of the ACadSharp writer family, and it is accepted.

`source.dwg` was written by ACadSharp@3.7.1+d7dc111 as AC1032, from the authored parameters of the r0-open probe record. The truth is `expected.math.json` beside it (a copy, pinned by hash to the canonical record), which I authored before any DWG existed and which this corpus never edits. No expected value comes from a DWG, a STEP file or any converter.

I had it read back by ACadSharp@3.7.1+d7dc111, acadrust@0.5.5+d35691f, LibreDWG. The read records are kept beside the DWG (`read.*.json`), and `comparison.json` lists every field checked, whether it was compared EXACT or under PVec numeric policy v1, and the verdict.

What this says: the DWG carries the authored mathematics as three open readers decode it. What it does not say: there is no STEP oracle here, and the readers share a DWG specification, so a shared misreading of it would not show.
