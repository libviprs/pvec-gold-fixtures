# viewport-clipped-bounded-001

The same line and viewport, but the clip is recorded as bounded only: a reader that reports just the bounding box of the clip is right, and one that reports the polygon is also right. Nothing may report a clip outside the bounds.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
