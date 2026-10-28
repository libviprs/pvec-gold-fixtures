# Final corpus audit: r2-open

I walked the registers once by hand after the clean-host run. This replaces the scope of `reports/final-audit.md` (the dated
record of `r0-open`, which stays as it is): the corpus now has two oracles, `acadsharp-dwg2step` (ACadSharp, MIT) and
`libredwg-dwg2step` (LibreDWG, GPL, a different decoder lineage), `oracle_scope` is `OPEN_CONVERTERS` (ADR 0009, ADR 0010) and
the evidence scope is `STEP_ORACLE` wherever the run backs it. The numbers in the tables below are derived from
`corpus/r2-open/manifest.json` and `reports/r2-open/probe-qualification.json` by `runner/r2_open.py`, and
`tests/test_r2_open.py` fails when they drift.

<!-- gen:stats -->
Fixtures: **59**. Both converters ran on every one. Converter pair: `acadsharp-dwg2step` (acadsharp) and `libredwg-dwg2step` (libredwg), OCCT 7.6.3.
<!-- /gen:stats -->

**Audited:** corpus revision `r2-open` in full (59 fixtures: everything in `r0-open` and `r1-open`), the combined release
candidate `corpus/release/r2-open-1` (not tagged, nothing published), and the clean-host runs in
`reports/reproducibility.r2-open.x64.json` (native x86_64, mars) and `reports/reproducibility.r2-open.arm64.json` (native arm64,
mercury). Both runs started from a docker daemon with an empty image store and built the validator and the ACadSharp converter
from pinned inputs. The LibreDWG image is GPL and was built in `libviprs/pvec-oracle-libredwg` (main at `8aa7ab1`), then moved
into the clean daemon by `docker save | docker load` and used by id, never as a build context here.

| image (native x86_64, the frozen set) | local id |
|---|---|
| `pvec-gold/dwg2step-acadsharp:local` | `sha256:ae4defd059e3aa29cf8f4159f1d857b9c48efd1a4b300074594ff42bb7b542bb` |
| `pvec-oracle-libredwg` (`pgf78-libredwg:final`) | `sha256:3c32156802d83574cda1c62e8b44779a02723ead5e8fb2f4c9ad3ae6d1564985` |
| `pvec-gold/step-validator:local` (OCCT 7.6.3, Debian package) | `sha256:6d4ea205090901c630b77a6383b060d3706696be5541e63a324d9ea9862179b9` |

The arm64 ids are in its report. Built ids differ on every build (`docs/reproducibility.md`), so these are the ids of the audited
runs and the base pins in the Dockerfiles are what a rebuild reproduces.

## 1. Quarantine register

<!-- gen:quarantine -->
Quarantined fixtures: **18**, every one by design (negative suite and degenerate group); none has an unknown or empty reason.

| fixture | scope | refused by | converter failure |
|---|---|---|---|
| `coincident-control-points-001` | REJECTION_EXPECTED | secondary | primary |
| `dimension-001` | STEP_ORACLE | primary, secondary | none |
| `empty-001` | STEP_ORACLE | primary, secondary | none |
| `hatch-001` | STEP_ORACLE | primary, secondary | none |
| `hatch-gradient-001` | STEP_ORACLE | primary, secondary | none |
| `image-001` | STEP_ORACLE | primary, secondary | none |
| `mesh-001` | STEP_ORACLE | primary, secondary | none |
| `mtext-001` | STEP_ORACLE | primary, secondary | none |
| `ole-001` | STEP_ORACLE | primary, secondary | none |
| `proxy-001` | STEP_ORACLE | primary, secondary | none |
| `region-001` | STEP_ORACLE | primary, secondary | none |
| `solid3d-001` | STEP_ORACLE | primary, secondary | none |
| `table-001` | STEP_ORACLE | primary, secondary | none |
| `text-001` | STEP_ORACLE | primary, secondary | none |
| `wipeout-001` | STEP_ORACLE | primary, secondary | none |
| `xref-001` | STEP_ORACLE | primary, secondary | none |
| `zero-length-segment-001` | REJECTION_EXPECTED | secondary | primary |
| `zero-radius-001` | REJECTION_EXPECTED | neither | primary, secondary |
<!-- /gen:quarantine -->

All of these are quarantined on purpose: the fifteen negative fixtures, the empty drawing among them (`UNSUPPORTED_ENTITY`, both
converters refuse them and write no STEP) and the three degenerate fixtures (`MALFORMED_FIXTURE`). The degenerate group is the
one place where the converters disagree with the authored expectation: a converter drew geometry for a fixture that should be
refused, which the table lists as a converter failure and the changelog carries forward. I retain the quarantine for all 18.
`shear-001` and `general-affine-001` are `PROFILE_ONLY` records with no DWG (#69), and nothing is excluded for lack of a writer
any more: `singular-001` now has a DWG (#70) and both converters refuse it, as its record says they must.

## 2. Approximation register

Probe cells: 32 converter probes, two converters each. 24 cells per converter are `GEOMETRIC_EXACT_REPARAMETERIZED`, 8 are
`STRUCTURAL_EXACT` (B-splines and NURBS, bit for bit), 2 are `UNSUPPORTED` with the expectation met (the rejection probes).
Approximation claims: **0**. No `BOUNDED_APPROXIMATION` is in the release.

**The geometric comparator (the 14 of 29 that #77 recorded).** I looked at it, and it was the comparator, not either converter.
The same signatures were exact in the structural comparison and in `runner.qualify_probes`. Four gaps in
`runner/compare_geometric.py`, each with a test in `tests/test_geometric_gap_78.py`:

- A tangent is measured with a five-point stencil whose own error was recorded and never added to the tolerance (curvature did
  add it). It is added now.
- Derived values are written to 12 significant digits (`normalize.DERIVED_DIGITS`), so at coordinates of 1e7 a signature
  carries 1e-4 of rounding that the absolute NP-04 tolerance could not allow for. Positional quantities are admitted within
  the policy tolerance plus half a unit of the last kept digit, recorded per quantity as `signature_rounding`.
- A polyline the converter wrote as several lines was held against the first line only (`large-coords-001`,
  `lwpolyline-closed-001`, and the bulge arcs, whose record carries an equivalent-arc companion with no partner). When counts
  differ the sets are compared (both directions, bounds), and the report says `compared_as_sets`.
- The expected tangent and curvature were evaluated on the curve without its transform, while the signature's samples are in
  world space, so every transformed fixture failed. They are evaluated on the placed curve now.

After the changes 27 of 29 are `GEOMETRIC_EXACT_REPARAMETERIZED`. Two stay `BOUNDED_APPROXIMATION` and I left them: `nurbs-d3-001`
(curvature off by 2.4e-7 above a tolerance of 9.6e-3, so the finite-difference estimate at a high-curvature sample is the limit)
and `tiny-radius-001` (tangent off by 1.8e-8 on a radius of 1e-9, where the 12-digit sample point cannot locate its parameter).
Both are limits of the measurement, not of the converters, and the STEP-side exactness of both fixtures is established by the
structural comparison and by both converters agreeing.

## 3. Negative-suite and unsupported-type register

The fifteen negative fixtures (the empty drawing is one of them) were converted by both converters. Both refused every one with exit 15 and no
STEP, which matches each record's expected `UNSUPPORTED`, `IGNORED` or `MISSING`, so they moved to `STEP_ORACLE` while staying
`QUARANTINED`. Both converters also refuse `near-singular-001` (`NEAR_SINGULAR_TRANSFORM`) and `singular-001`
(`SINGULAR_TRANSFORM`), the two rejection probes, and both are confirmed. The converters' own documented refusals (MINSERT arrays,
nesting deeper than 64) are not exercised by a fixture here.

Held back in the table above are the fixtures the run did not back:

<!-- gen:held -->
Held back (no move), with the run's reason: **5**.

- `arch-aecobjects-001`: UNSUPPORTED_ENTITY (primary: CONVERSION_FAILED; secondary: CONVERSION_FAILED)
- `general-sample-ac1032-001`: UNRESOLVED_DISAGREEMENT
- `layer-state-001`: APPROXIMATION
- `mixed-entity-001`: APPROXIMATION
- `tiny-extent-001`: UNSUPPORTED_ENTITY
<!-- /gen:held -->

`layer-state-001` and `mixed-entity-001` are held for the same reason, and the two converters give identical numbers on both, so
neither converter is the odd one out. The probe classifier pairs curves one to one and the converters write a different number of
curves than the record lists (3 against the drawing's off and frozen layers, which have no STEP form, and 10 for the flattened
block chain of the mixed drawing), so every cell lands in `BOUNDED_APPROXIMATION` with a bound of several metres. This is the
same entity-count pairing gap I fixed in `compare_geometric` section 2, still present in `runner/qualify_probes.py`. I did not change
the classifier that decides the capability table in this PR, and neither fixture is a capability probe.

`tiny-extent-001` is a real disagreement between the converters, and the one I would look at next: the 5e-9 m segment is valid (its end
points differ), `libredwg-dwg2step` converts it exactly (`GEOMETRIC_EXACT_REPARAMETERIZED`), and `acadsharp-dwg2step` writes no curve
for it ("converter output contains no curve"), so the run labels it `UNSUPPORTED_ENTITY` and the fixture does not move. That is
the ACadSharp converter dropping a short segment, a converter policy, and it is recorded, not fixed here.

## 4. Provenance register

56 fixtures are `SYNTHETIC_AUTHORED` and 3 are `REAL_WORLD_PUBLIC` (ACadSharp's samples, MIT), all 59
`PUBLIC_REDISTRIBUTABLE`, none `PRIVATE`. The release holds no DWG at all. The real-world drawings were recorded again for this
revision, after both converters learnt inches and feet (#67, #68):

- `blocks-dynamic-linear-001`: both converters convert it and the signatures agree, so it is `DUAL_ORACLE_EQUIVALENT`, the first
  fixture to reach that class.
- `general-sample-ac1032-001`: both convert it and the signatures disagree in 19077 fields. That is a real finding about the pair
  on a real drawing (one of them splits or orders the entities differently), and it is held at `REAL_WORLD_DIFFERENTIAL`. I did not
  chase which converter is right.
- `arch-aecobjects-001`: both converters exit 15. That is an open-source limit (the drawing's content is outside v1), recorded as
  such, and it is held.

LibreDWG-written R2000 and R2004 DWGs (`corpus/writers/libredwg-r2000`, `libredwg-r2004`, #72) are not in this revision: they are
writer-family evidence for the three-reader rule, not fixtures. See section 7 for their size in git.

## 5. Capability table, from two oracles

<!-- gen:capabilities -->
| capability | status | acadsharp-dwg2step | libredwg-dwg2step | probes |
|---|---|---|---|---|
| line | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 1 |
| polyline | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 4 |
| circle | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 2 |
| ellipse | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 1 |
| trimmed_curve | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 2 |
| composite_curve | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 2 |
| bezier | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 1 |
| bspline | CERTIFIED | STRUCTURAL_EXACT | STRUCTURAL_EXACT | 5 |
| nurbs | CERTIFIED | STRUCTURAL_EXACT | STRUCTURAL_EXACT | 3 |
| affine_transform | CERTIFIED | GEOMETRIC_EXACT_REPARAMETERIZED | GEOMETRIC_EXACT_REPARAMETERIZED | 11 |
<!-- /gen:capabilities -->

Every capability is `CERTIFIED`, including `affine_transform`, which was `BLOCKED` for as long as `singular-001` had no DWG and
the shear probes had no writer. It is certified now because the chain probes (#69) and `singular-001` (#70) exist and both
converters land them. The report is `reports/r2-open/probe-qualification.json`, also copied to
`reports/phase1/probe-qualification.json` (two oracles, native x86_64).

## 6. Evidence classes after the run

<!-- gen:register -->
| evidence class | evidence scope | fixtures |
|---|---|---|
| DUAL_ORACLE_EQUIVALENT | STEP_ORACLE | 1 |
| KNOWN_TRUTH_EXACT | READER_MAPPING_ONLY | 3 |
| KNOWN_TRUTH_EXACT | STEP_ORACLE | 35 |
| QUARANTINED | REJECTION_EXPECTED | 3 |
| QUARANTINED | STEP_ORACLE | 15 |
| REAL_WORLD_DIFFERENTIAL | READER_CENSUS_ONLY | 2 |
<!-- /gen:register -->

## 7. Reproducibility and the things I measured but did not change

- Two generate runs in the same clean daemon agree on every artifact except the STEP time stamp and the converters' clocks (no
  unlisted divergence), on x86_64 and on arm64. The release verifies with the standard library only.
- STEP bytes are identical across x86_64 and arm64 for all 41 fixtures that have STEP. Signatures differ in their derived last
  digits for 14 of 39 (same cause as before: OCCT's values from the Debian package), and the frozen set is the x86_64 one.
- **OCCT from source.** Bitwise identical signatures across architectures at full scale, and identical to the frozen ones. See the recommendation in section 8.
- **LibreDWG R2004 outputs in git.** `corpus/writers/libredwg-r2004` holds 213 files and 47.8 MB (about 46 MB of DWG, which does
  not compress); `libredwg-r2000` is 1.2 MB and `acadsharp` 1.3 MB. ACadSharp at its pin cannot open the R2004 files, so all of
  them are quarantined. I recommend moving the R2004 DWGs out of the tree and keeping ids and hashes only (the manifest and
  `SHA256SUMS` stay), regenerated by `tools/corpus/writer-libredwg/write-run.sh`. I did not do it in this PR.
- The r2-open corpus and release are 15 MB and 14 MB on disk, nearly all of it `general-sample-ac1032-001` (two signatures of
  4 to 5 MB and a verdict of 1.5 MB). It is text and compresses well.

## 8. Recommendation: should the validator image ship OCCT from source?

I recommend shipping it, as its own follow-up change, and I did not switch it here (`docker/step-validator/Dockerfile` and
`docker-compose.yml` are unchanged). The spike is in `docs/validator/occt-from-source.md`. I repeated it at full scale: the whole
`r2-open` clean-host run (59 fixtures, two converters, 78 signatures) with `Dockerfile.occt-src` as the validator, on native
x86_64 (mars) and native arm64 (mercury), both PASS with no unlisted divergence.

| comparison over the 78 signatures (and 80 STEP files) | identical signatures | identical STEP |
|---|---|---|
| Debian OCCT, x86_64 against arm64 | 53 of 78 | 80 of 80 |
| OCCT from source, x86_64 against arm64 | **78 of 78** | 80 of 80 |
| Debian x86_64 against source x86_64 (the frozen set) | **78 of 78** | 80 of 80 |

So switching changes no frozen signature, and removes the 25 last-digit differences across architectures completely, which the
policy comparison tolerated but a bitwise consumer could not. What it costs: a 3 to 7 minute OCCT build (its own cacheable stage),
and we stop getting Debian's patched OCCT, so a bump of the pinned tarball (`V7_6_3`, SHA-256 checked in the build) becomes our job. I
would keep the numeric-policy comparison as the contract anyway (#74) and treat bitwise identity as a bonus the image provides. The
condition I would put on the follow-up is one more run like this one after any OCCT bump.

## 9. Decisions

The quarantine decisions in section 1 and the held fixtures in section 3 are mine as the auditor. spdrman clears or confirms them
by merging this audit. Nothing was published, no tag was created, and the digests in `corpus/container.pin.json` stay `null`
until the images are published, which needs a registry session.
