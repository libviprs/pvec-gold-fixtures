# Deferred until the vendor converters, or until a pvec change

What I could do for real on the open route is done. These parts need something this side does not have.
Each section names the issue it came from.

## Issues #15 and #54: converter classification and generator input

**CAD Exchanger and ODA (oracle_scope VENDOR_CONVERTERS).** The structural and geometric reports and the
converter classification (`runner/compare_structural.py`, `compare_geometric.py`, `compare_converters.py`)
are done and tested on signatures. What stays open is running them on signatures the licensed images
produced: neither image can be built here (no licence), so there are no vendor signatures, no vendor
converter section, and the issue's wording about "CAD Exchanger versus ODA" is not evidenced. When the
images exist, the same modules classify that pair with `oracle_scope: VENDOR_CONVERTERS`; nothing in them
looks at converter ids.

**The secondary open converter has not produced a signature.** The primary is the ACadSharp-lineage
`dwg2step-acadsharp`. The secondary is the LibreDWG-lineage converter from `libviprs/pvec-oracle-libredwg`
(GPL-3.0), whose image is still in a draft PR. `r0-open` has `oracle_scope: NONE` and no STEP, and there is
no real-world corpus yet (that is issue #11), so I did not generate `primary.signature.json` and
`secondary.signature.json` for any corpus fixture. The tests use real step_eval signatures of the committed
self-test STEP files, from both architectures, and signatures built from the known-truth probes.

**Real-world artifacts need a pvec change.** The gold-fixtures half of #54 is the generator input
(`docs/fixtures/generator-input.md`). The generator side is code in `libviprs/pvec`, which I did not edit:

- `pvec-testkit` needs a second input next to the record one: read a `*.generator-input.json`, validate it
  against `schema/generator-input.schema.json`, and produce the same `Plan` from `signature`, so the
  writer path and the refusal rules are shared.
- It stamps the generator version into the provenance fields it already writes, plus `oracle_revision`.
- The determinism, digest and bit-for-bit tests need repeating over the real-world fixtures once those
  exist; the byte-determinism of the input itself is tested here.

**Per-converter blocks.** The issue asked for a structural block inside `primary.verification.json`. I
write `primary.structural.json` and `primary.geometric.json` beside it, because the verification record has
its own schema. Say if you want them folded in.
