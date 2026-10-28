# tiny-extent-001

A valid straight segment 5e-9 m long (3e-9, 4e-9), well under any drawing tolerance but not zero, so a pipeline that snaps short segments to nothing shows. It is not the degenerate case: the end points differ.

I authored this edge case from `tools/authoring/corpus-params/edge/tiny-extent-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
