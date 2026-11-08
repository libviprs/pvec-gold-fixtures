# no-plot-layer-001

A no-plot layer NOPLOT (the Defpoints idea) holding one line in model space and one in paper space, beside a line on layer 0 in each. One plain viewport shows model space. The plot flag of each layer has to survive.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
