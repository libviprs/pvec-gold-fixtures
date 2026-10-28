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
