# singular-001

A line under scale (1, 0, 1), determinant exactly 0. The authored outcome is rejection (`SINGULAR_TRANSFORM`, `REJECT`), and a pipeline that emits geometry for it fails. `expected.math.json` is the record I authored before any DWG existed (a copy of `fixtures/known-truth/transforms/singular-001`), and this drawing is the first one that holds it.

A DWG stores an INSERT scale as a plain double, so the file can say 0.0. The writers refuse it: acadrust's setters rewrite it to 1e-12 and ACadSharp throws, which is why `r0-open` lists this probe as excluded (and still does). I wrote this file with acadrust at `eacbc9f` (`Insert::set_scale_unchecked`, libviprs/acadrust#52) through `tools/corpus/singular`, from the parameter file's own numbers. Two writes are byte-identical.

Three readers decode it: acadrust at the same commit (its reader now keeps a stored zero), ACadSharp at `d7dc111` with `tools/converters/acadsharp/patches/0001-insert-keep-zero-scale.patch` (upstream master dropped the same guard), and LibreDWG's `dwgdump`. All three return the y scale as the bits `0x0000000000000000`, compared EXACT, and decode the same record, so the verdict is AGREE.

Both converters refuse it with exit 15 and write no STEP: `acadsharp-dwg2step` as `SINGULAR_TRANSFORM` and `libredwg-dwg2step` as a singular INSERT matrix. The evidence is reader mapping and refusal only (`READER_MAPPING_ONLY`); a mapper must not emit a curve for this entity.
