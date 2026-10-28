# tests/data

`units-feet-001.dwg` is `corpus/r0-open/fixtures/line-001/source.dwg` with the drawing unit set to feet (`INSUNITS` 2) and
nothing else changed. I read the file with ACadSharp's `DwgReader` (the pinned commit `d7dc111`), set `Header.InsUnits`
to `Feet` and wrote it back with its `DwgWriter` as AC1015 (the version of its writer that its own reader gets back), in a throw-away container. Only the file is here, not the
tool. It is 20965 bytes, sha256 `fec6c768dc9b074daf48bd65060892b74b2e5c6c1dabc6377802454fad946423`.

It exists because the three real-world drawings are in inches or unitless, and the feet branch of the unit handling needs a
DWG of its own. The line is the one `line-001` authors, so the expected world coordinates are those times 0.3048. It is
not part of any corpus revision.
