# layout-plot-settings-mm-001

A layout with plot settings in millimetres: ISO A3 (420 by 297), landscape rotation code 1, plot scale 1:50, margins 5, 6, 7 and 8 mm (left, bottom, right, top), plot origin (10, 12) mm, lineweights not printed and the monochrome.ctb style table named. One viewport and a paper-space border line. Every plot setting has to survive.

The record is `expected.math.json`, authored from its parameter file by `tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and `read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is `READER_MAPPING_ONLY`.
