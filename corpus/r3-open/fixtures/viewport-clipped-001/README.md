# viewport-clipped-001

One model-space line seen through one paper-space viewport that is clipped to a non-rectangular polygon. The clip polygon is stored exactly, so a reader has to keep the boundary and not only the rectangle around it.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
