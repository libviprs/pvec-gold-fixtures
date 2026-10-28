# arc-tiny-sweep-001

An arc of radius 1000 m that starts exactly at angle 0 and sweeps only 1e-6 rad, so its end sits on the same side of the 0/2pi seam as its start and the chord is about a millimetre.

I authored this edge case from `tools/authoring/corpus-params/edge/arc-tiny-sweep-001.json`, and `expected.math.json` is derived from those parameters alone by `tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers (tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only (`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it.
