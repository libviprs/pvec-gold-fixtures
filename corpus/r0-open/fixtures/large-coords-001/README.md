# large-coords-001

This is a probe of the r0-open corpus revision, and it is accepted.

`source.dwg` was written by acadrust@0.5.5+d35691f as AC1032, from the authored parameters of the O1.5a/O1.6a probe record. The truth is `fixtures/known-truth/large-coords-001/expected.math.json`, which I authored before any DWG existed and which this revision never edits. No expected value comes from a DWG, a STEP file or any converter.

I had it read back by ACadSharp@3.7.1+d7dc111 (the other open family) and by the writer's own reader. Both read records are kept beside the DWG (`read.*.json`), and `comparison.json` lists every field checked, whether it was compared EXACT or under PVec numeric policy v1, and the verdict.

What this says: the DWG carries the authored mathematics as two independent open readers decode it. What it does not say: there is no STEP oracle, nothing here was converted by CAD Exchanger or ODA, and the class is KNOWN_TRUTH_EXACT for reader mapping only.
