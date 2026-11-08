# layout-plot-settings-inch-001

A layout with plot settings in inches: ANSI B (11 by 17 inches, stored as 279.4 by 431.8 millimetres), no rotation, plot scale 1:96, margins 0.25 all round, plot origin (0.5, 0.75), lineweights printed and the acad.ctb style table named. One viewport and a paper-space border line. Every plot setting has to survive.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
