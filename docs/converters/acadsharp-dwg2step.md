# dwg2step-acadsharp

Route A of the open converter plan: ACadSharp's `DwgReader` decodes the DWG, a small Part 21 writer I wrote
(`tools/converters/acadsharp/Step21.cs`) produces AP242, and nothing else is involved. MIT code all the
way down, no licence, no closed-source SDK. The evaluator (`step_eval`, OCCT) never runs inside this image, so the
converter cannot be its own witness.

```
dwg2step-acadsharp --in source.dwg --out primary.step [--status primary.status.json]
```

Image: `ghcr.io/libviprs/pvec-gold-dwg2step-acadsharp`, linux/amd64 and linux/arm64, pinned by digest
(`tools/converters/acadsharp/publish.sh --dry-run` shows what a publish does; the real push is a separate
decision and needs a registry session this repository never handles).

## What is pinned

- Base images: the dotnet SDK `10.0.401-noble` and runtime `10.0.12-noble`, each by the digest of the
  multi-arch index (see the `FROM` lines in `tools/converters/acadsharp/Dockerfile`).
- ACadSharp: upstream `DomCR/ACadSharp` at `d7dc111023477d8a9fffc2153139459c95b4f345` (3.7.1), the same
  commit the r0-open cross-reader used. The build checks the clone against `ACADSHARP_COMMIT`.
- Policy: `policy/pvec-numeric-policy.v1.json` is copied into the image. The converter reads one number
  from it, `REL`, for the near-singular refusal below, and carries no threshold of its own.

## Output and status

The Part 21 subset is the one the evaluator self-test files use: `LINE`, `CIRCLE`, `ELLIPSE`,
`TRIMMED_CURVE`, `B_SPLINE_CURVE_WITH_KNOTS`, the `RATIONAL_B_SPLINE_CURVE` complex entity,
`AXIS2_PLACEMENT_3D` and `GEOMETRIC_CURVE_SET`, in a `GEOMETRICALLY_BOUNDED_WIREFRAME_SHAPE_REPRESENTATION`.
Every real is written with `E16`, 17 significant digits, which round-trips an f64 exactly.

The status record is `schema/converter-status.schema.json`, written on every run. The `converter` value is
`acadsharp-dwg2step`, the named id ADR 0009 allows. The exit codes are the shared ones:

| code | class | when |
|---|---|---|
| 0 | | ok |
| 10 | BAD_ARGUMENTS | missing `--in` or `--out`, or an unknown flag |
| 11 | INPUT_UNREADABLE | no such file, or it cannot be read |
| 12 | INPUT_MALFORMED | no `AC10xx` header, or `DwgReader` throws (CRC check on, failsafe off) |
| 13 | DWG_VERSION_UNSUPPORTED | a header ACadSharp does not read (anything but AC1014, 1015, 1018, 1021, 1024, 1027 and 1032) |
| 15 | CONVERSION_FAILED | a refusal below, an unsupported drawing unit, or nothing convertible |
| 16 | OUTPUT_NOT_WRITTEN | the file could not be written or moved into place |
| 17 | SCHEMA_NOT_AP242 | the written `FILE_SCHEMA` is not AP242 |
| 20 | INTERNAL | anything unhandled |

14 (licence) cannot happen. The output is written under `<out>.partial.<pid>` and renamed, and any stale
output is removed first, so a failed run leaves no STEP file.

## Two runs

Two runs on one DWG differ in the `FILE_NAME` time stamp (second argument) and `wall_time_seconds`, nothing
else; `runner/step_normalise.py` already treats the first as the named field. `SOURCE_DATE_EPOCH` fixes the
time stamp, which makes the STEP bytes identical.

## How INSERT chains are flattened

Model space is walked and every INSERT is expanded, nested ones included, with the affine map
`p -> W (R S (p - base) + insert_point)` composed outermost first (`W` is the arbitrary-axis matrix of the
INSERT's normal). Nothing is left as an instance, so STEP's uniform-scale-only
`CARTESIAN_TRANSFORMATION_OPERATOR_3D` is never needed.

- A line maps its two ends. A spline maps its poles. Knots and weights are untouched.
- A circle or arc under a path where every INSERT scales its three axes by one magnitude stays a circle with
  radius `r * |s|`. Under anything else it becomes an ellipse built from the two mapped conjugate
  semi-diameters, with the principal axes found by rotating the parameter. A non-uniformly scaled circle is
  the authored ellipse, never a circle.
- A reflection (an odd number of negative scales) flips the placement frame: the normal and the reference
  axis are mirrored, the parameter range is kept. The arc still starts where the source arc started and the
  evaluator reports the sense the other way round.
- A bulge becomes a circular arc through the two vertices. A negative bulge is written counter-clockwise
  from the second vertex to the first, which is the authored "equivalent arc".
- Polylines arrive as one `LINE` or arc edge per segment, closed ones with the implicit closing segment.
- Refused with exit 15: an INSERT chain whose composed 2D map has `|ad - bc| <= REL * big^2` (NP-19), named
  `NEAR_SINGULAR_TRANSFORM` in the message; MINSERT arrays; nesting deeper than 64 or a block that contains
  itself; a spline with fit points only.
- Other entity types (text, hatches, dimensions) are skipped, and the count per type goes into `warnings`.
  The r0-open probes contain none.

Drawing units: metre, unitless (written as metre and warned about), millimetre, centimetre and kilometre are
declared in the STEP context and values are never rescaled. Inches and feet stop with exit 15 until someone
needs them.

## What OCCT did that I did not expect

- A STEP line's parameter runs over the `VECTOR` magnitude, so the trim is `(0, 1)`, not `(0, length)`.
  The evaluator still reports the line over `[0, length]`, because the OCCT reader folds the magnitude into
  the parameter, so the line's `parameter_domain` is not a stored value and the test does not compare it.
- A cubic Bezier comes back from the reader as a B-spline with two knots of multiplicity 4, whether it is
  written as `BEZIER_CURVE` or as `B_SPLINE_CURVE_WITH_KNOTS`. The evaluator can only say `bspline` for it;
  poles and degree are the stored values and they match bit for bit.
- A B-spline written with `closed_curve = .T.` is rebuilt by the OCCT reader as a periodic spline, and a
  clamped spline whose first and last pole coincide loses a pole that way. The converter writes `.F.` for
  clamped splines and `.T.` only for a wrapped periodic spline (see below), where the rebuilt periodic form
  is the point.
- A periodic DWG spline stores one knot per span boundary and no wrapped poles. It is written as the same
  curve over one period: the first `d` poles repeated and the knot vector extended by the period.

The evaluator note about closed periodic splines (`docs/validator/step-evaluator.md`, open points) is
answered by the run records, not by this file.

## Local build digests

Built locally on 2026-10-28, nothing pushed. These are the image ids (config digests) of the single-platform
builds, not a registry index digest, which only exists once someone publishes:

| platform | host | image id |
|---|---|---|
| linux/amd64 | mars | `sha256:2d97c4423580f595d37a4b1d9b9fad56fe0575901d4bce9069c0cab4796331a6` |
| linux/arm64 | mercury | `sha256:b4ac1756db767942fa5f21b005977c6942431a4978b66a27e0d92fcf12f2167b` |

The two builds share the base digests in the Dockerfile and produce byte-identical STEP files.

## Running the tests

```
tools/converters/acadsharp/test.sh mars       # native x86_64
tools/converters/acadsharp/test.sh mercury    # native arm64
```

The script puts the tree in a throw-away docker volume, builds the converter image and the step-validator
image there, runs `tests/test_acadsharp_converter.py` from a driver container that has the host's docker
socket, and removes the volume. `--done` also removes the images.
