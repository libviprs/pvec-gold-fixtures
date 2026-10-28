# mixed-entity-001

Seven entities in one model space: a line, a circle, a circular arc, an ellipse, a bulged polyline and a rational B-spline are stored as they are, and a line is reached through three nested block instances (translate, rotate, non-uniform scale) while a circle is reached through one uniform scale. Eight entity records, seven curve classes, two block chains.

I authored this drawing from `tools/authoring/corpus-params/mixed/mixed-entity-001.json`; `expected.math.json` is derived from those parameters alone by `tools/authoring/author_corpus.py`. The curve classes are circle, circular_arc, ellipse, line, nurbs, polyline. Two entities sit behind block instances: a line behind three nested levels (translate, rotate, non-uniform scale) and a circle behind one uniform scale. The DWG is written from the record's `f64_hex` numbers by tools/corpus/writer and read back by two readers (`READER_MAPPING_ONLY`).
