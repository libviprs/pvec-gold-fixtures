# Authoring a known-truth fixture

A known-truth fixture says what its DWG means before any converter has seen it. The truth comes from
parameters you choose by hand and from nothing else ([ADR 0002](../adr/0002-known-truth-authoring.md)). This guide
adds one fixture end to end, on the open route, with no licence. Every command runs in a container on a native
docker host (the first line of each block says which wrapper).

## 1. Choose the parameters

Pick the numbers first, with some asymmetry so that start, end and orientation are checkable. A line is
`tools/authoring/params/line-001.json`:

```json
{"id":"line-001","kind":"line","description":"...","start":["0.5","0.25","0"],"end":["3.75","2.5","0"]}
```

Copy the closest existing file for your kind (`line`, `circle`, `bulge_arc`, `ellipse`, `bspline`, `nurbs`,
`transform`, `layers`, and so on) to `tools/authoring/params/<your-id>.json`. Numbers are decimal strings, so
the intended `f64` is unambiguous. The id ends in a number (`-001`) and is unique.

## 2. Derive the expected record

```
tools/py.sh python3 tools/authoring/author_probes.py            # writes fixtures/known-truth/<id>/{expected.math.json,README.md}
tools/py.sh python3 tools/authoring/author_probes.py --check    # fails if what is on disk differs from the parameters
tools/py.sh python3 -m runner.expected_math fixtures/known-truth/<id>/expected.math.json
```

Derived values (sines, arc centres, ellipse axes) are computed to 60 digits and rounded once to `f64`. The record
format is [expected-math.md](expected-math.md); a decimal that does not round to its `f64_hex` is rejected.

## 3. Write the DWG and read it back

```
tools/r0-open/run.sh
```

The writer (`tools/r0-open/rust`, acadrust at a pinned commit) writes a DWG for every parameter file, twice, and
checks the two are byte-identical. ACadSharp and the writer's own reader dump what they decode. `assemble` then
compares both reads to your authored record: EXACT where the DWG stores the number verbatim, under the numeric
policy where it stores a derived value, and the fixture is accepted only if both readers agree with the truth.
If the writer cannot store your parameters exactly, the fixture is listed under `excluded` with a reason, and you
do not hide that ([acceptance-and-quarantine.md](../acceptance-and-quarantine.md)).

## 4. Convert, evaluate, normalise

```
tools/clean_host.sh mars        # builds the images in a fresh daemon and runs runner.reproduce for every accepted fixture
```

That converts the DWG to STEP with `dwg2step-acadsharp`, evaluates it with `step_eval`, normalises the record to
a signature, and checks that two conversions agree except for the named divergences
([reproducibility.md](../reproducibility.md)).

## 5. A new fixture is a new revision

`r0-open` is pinned by hash. Adding a fixture changes the bundle, so it belongs to a new revision (`corpus/CHANGELOG.md`
says what changed and why), with its own pin, and never an edit to a pinned one. Run `tools/vendor_guard.sh --tree`
before you commit.

## Proof that the guide works

