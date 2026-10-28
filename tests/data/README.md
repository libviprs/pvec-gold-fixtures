# tests/data

`units-feet-001.dwg` is `corpus/r0-open/fixtures/line-001/source.dwg` with the drawing unit set to feet (`INSUNITS` 2) and
nothing else changed. I made it by reading the file with the patched `dwgread`, setting `HEADER.INSUNITS` in the JSON and
writing it back with `dwgwrite --as r2004` (LibreDWG 0.14, the `pvec-oracle-libredwg` image, run in a throw-away
container). Only the resulting file is here, not the tool. It is AC1018, 1568304 bytes, sha256
`32bc481a1f0b6993529173299faf57b518c0ee66b1f480e062044782051ef295`, and writing it again gives the same bytes.

It exists because the three real-world drawings are all in inches or unitless, and the feet branch of the unit handling
needs a DWG of its own. The line is the one `line-001` authors, so the expected world coordinates are those times 0.3048.
It is not part of any corpus revision.
