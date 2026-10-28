# Writer families

`corpus/r0-open` is written by acadrust. The directories here hold the same 30 probes written by other open DWG
writers, so a reader or a converter is not only ever tested on one writer's bytes. The authored truth is the same
for every family (`fixtures/known-truth` and `tools/authoring/params`), and each family carries a hash-pinned copy.

## acadsharp

I wrote these with upstream ACadSharp's `DwgWriter` (pin `d7dc111`, `tools/corpus/writer-acadsharp`) as AC1032. Three
readers decoded every file: ACadSharp itself, acadrust and LibreDWG's `dwgdump`. A probe is accepted only when all
three match the authored truth and decode the same record (`runner/writer_family.py`); otherwise it is quarantined with
the fields that differ. All 30 written probes are accepted. Shear, general-affine and singular are excluded for the
same reason as in r0-open, with the reasons in `quarantine.json`.

Determinism, measured by writing every probe twice: as ACadSharp writes them, 0 of 30 are identical, because it stamps
seven header fields on every file that change the bytes (create and update times, universal update time, the
fingerprint and version GUIDs, and the summary info created and modified dates). With those fields pinned to
constants, 30 of 30 are identical, and the committed DWGs are those. Pinning them changes no geometry. The field list
is in `manifest.json` under `determinism`, measured by leaving each one raw in turn.

To rebuild: `LIBREDWG_IMAGE=<image id or digest> tools/corpus/writer-acadsharp/run.sh`.

## libredwg-r2000 and libredwg-r2004

I wrote these with LibreDWG's `dwgwrite` (0.14, from the `pvec-oracle-libredwg` image, run as a separate process; the
image is GPL and is only used by id or digest, never built from this repository). `tools/corpus/writer-libredwg/author.py`
turns the authored `expected.math.json` records and the parameter files into LibreDWG JSON (the shape `dwgread -O JSON`
prints, with the doubles as exact binary64 text, so no value goes through DXF decimals), starting from the tables and
dictionaries of an empty drawing of the target version. `dwgwrite --as r2000` and `--as r2004` write the DWGs, and the
manifest records `dwg_version` per fixture (AC1015 and AC1018).

Only R2000 and R2004 are covered, because that is what the tool can write: `dwgwrite --as r2007` prints "not capable of
encoding versions r2007" and still exits 0 with an AC1024 file, which `author.py` treats as a failure and `check` would
catch through the read records' `dwg_version`, and the LibreDWG manual says r2010 to r2018 still fail CRC and audit
checks, so I do not use them. The same three readers decode every file (LibreDWG's own `dwgdump`, acadrust, ACadSharp).

Results, written twice with identical bytes (30 of 30 in both versions, no header field pinned):

- `libredwg-r2000`: 30 of 30 AGREE under the three-reader rule.
- `libredwg-r2004`: 30 of 30 are quarantined, all for one reason. ACadSharp at `d7dc111` cannot open any of them (its
  AC18 file header reader throws on a duplicate empty section name), while LibreDWG and acadrust match the authored
  truth and each other on every one. I did not work around the reader. Each `R2004` DWG is about 1.5 MB, which is how
  `dwgwrite` lays the file out; I could not make it smaller by dropping sections of the JSON.

`dwgdump` could not read R2000 entity lists at first (LibreDWG's JSON has `first_entity` and `next_entity` links there,
not an `entities` array); that is fixed in `pvec-oracle-libredwg` #7, and the image used here includes it.

To rebuild: `LIBREDWG_IMAGE=<image id or digest> tools/corpus/writer-libredwg/run.sh`.
