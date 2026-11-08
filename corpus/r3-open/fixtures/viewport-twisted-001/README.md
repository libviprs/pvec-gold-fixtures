# viewport-twisted-001

One plan viewport twisted by 30 degrees about its view direction, looking at one model-space line. The twist, the view and the rectangle have to survive; the sign of the twist is what a reader has to get right.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
