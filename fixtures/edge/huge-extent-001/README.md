# huge-extent-001

A circle of radius 2.5e6 m centred 1.5e6 m east and 2.2e6 m south of the origin, so the drawing extent is above 1e6 in both directions and the centre alone is beyond the exact integer range a float32 keeps.

I authored this edge case from `tools/authoring/corpus-params/edge/huge-extent-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
