# bspline-nonunit-domain-001

A clamped quadratic B-spline whose parameter domain is [2, 5] and not [0, 1], so both domain endpoints (2 and 5) are non-trivial and a converter that rescales the knots to the unit interval shows.

I authored this edge case from `tools/authoring/corpus-params/edge/bspline-nonunit-domain-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
