# paper-space-multi-viewport-001

One paper-space layout with twenty rectangular viewports in a grid, each looking at a different part of the same model-space line. The count and each viewport's rectangle and view have to survive.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
