"""r3-open: the viewport, paper-space and large-industrial fixtures (#96).

    python3 -m runner.r3_open assemble RUN_DIR [--generator-sample SHA] [--sample-count N]
    python3 -m runner.r3_open check

`assemble` takes the directory the open writer wrote (`write-report.json` and one `<id>/source.dwg` plus
`<id>/acadrust.read.json` per fixture, from tools/r0-open/rust) and builds corpus/r3-open. A fixture is accepted
only when the reader's dump matches the authored record: the viewport count, every paper rectangle and every view
by exact f64 bits, and the clip polygon vertex for vertex (for a bounded-only clip, the reader's polygon, if it
reports one, has to stay inside the authored bounds). Nothing but the standard library is used, so it runs on the
host that has the files; `check` re-derives the same verdicts, the SHA256SUMS, the generator hash, the sample hash and the r2-open include hash from what is committed.

The large industrial drawing is never committed as a DWG. Its manifest entry carries the generator, its seed, the
entity count and a size class, and the sample hash of the first SAMPLE entities so a consumer can confirm its
generator run is the one this revision means.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVISION = "r3-open"
KT = ROOT / "fixtures" / "viewports"
GENERATOR = "tools/authoring/gen_large_industrial.py"
IDS = ("viewport-clipped-001", "viewport-clipped-bounded-001", "paper-space-multi-viewport-001",
       # #101: the print-profile probes.
       "viewport-twisted-001", "viewport-frozen-layer-001", "viewport-non-plan-001", "viewport-hide-plot-001",
       "no-plot-layer-001", "layout-plot-settings-mm-001", "layout-plot-settings-inch-001")
PLAN = [0, 0, 0x3ff0000000000000]
LARGE = {"id": "large-industrial-001", "entity_count": 1000000, "seed": 96, "sample_count": 1000}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def bits(s):
    return int(s["f64_hex"], 16)


def hexbits(h):
    return int(h, 16)


def compare(expected, read):
    """Mismatches between the authored record and what the reader saw, as strings (empty means accepted)."""
    want, got = expected["viewports"], read["viewports"]
    bad = []
    if len(want) != len(got):
        return ["viewport count: authored %d, read %d" % (len(want), len(got))]
    for i, (w, g) in enumerate(zip(want, got)):
        where = "viewport %s" % w["id"]
        pairs = [("paper.center.x", bits(w["paper"]["center"][0]), hexbits(g["center"][0])),
                 ("paper.center.y", bits(w["paper"]["center"][1]), hexbits(g["center"][1])),
                 ("paper.width", bits(w["paper"]["width"]), hexbits(g["width"])),
                 ("paper.height", bits(w["paper"]["height"]), hexbits(g["height"])),
                 ("view.center.x", bits(w["view"]["center"][0]), hexbits(g["view_center"][0])),
                 ("view.center.y", bits(w["view"]["center"][1]), hexbits(g["view_center"][1])),
                 ("view.height", bits(w["view"]["height"]), hexbits(g["view_height"]))]
        for name, a, b in pairs:
            if a != b:
                bad.append("%s: %s authored 0x%016x, read 0x%016x" % (where, name, a, b))
        # The view centre is relative to the view target, so the record's centre is only the model point
        # it names when the target is at the origin (#102).
        target = g.get("view_target")
        if target is None:
            bad.append("%s: the reader dump has no view_target" % where)
        elif any(hexbits(t) != 0 for t in target):
            bad.append("%s: view_target is not the origin: %s" % (where, target))
        # #101: the view direction (plan unless authored), the twist (zero unless authored), the layers frozen in
        # the viewport, hide_plot and the VIEWPORT entity's own layer.
        want_dir = [bits(c) for c in w["view"]["direction"]] if "direction" in w["view"] else PLAN
        if [hexbits(c) for c in g.get("view_direction", [])] != want_dir:
            bad.append("%s: view_direction differs from the authored one" % where)
        want_twist = bits(w["view"]["twist"]) if "twist" in w["view"] else 0
        if g.get("twist") is None or hexbits(g["twist"]) != want_twist:
            bad.append("%s: twist authored 0x%016x, read %s" % (where, want_twist, g.get("twist")))
        if "frozen_layers" not in g or sorted(g["frozen_layers"]) != sorted(w.get("frozen_layers", [])):
            bad.append("%s: frozen_layers authored %s, read %s" % (where, w.get("frozen_layers", []), g.get("frozen_layers")))
        if g.get("hide_plot") != w.get("hide_plot", False):
            bad.append("%s: hide_plot authored %s, read %s" % (where, w.get("hide_plot", False), g.get("hide_plot")))
        if g.get("layer") != w.get("entity_layer", "0"):
            bad.append("%s: the VIEWPORT's layer authored %s, read %s" % (where, w.get("entity_layer", "0"), g.get("layer")))
        clip = w.get("clip")
        poly = g.get("clip_polygon")
        if clip is None:
            if poly:
                bad.append("%s: the reader found a clip the record does not have" % where)
            continue
        if clip["bounded_only"]:
            if poly:
                lo_x, lo_y, hi_x, hi_y = (bits(x) for x in clip["bounds"])
                # compare as floats: bounds are f64 bits of whole numbers here, and ordering is what matters
                import struct

                def f(u):
                    return struct.unpack(">d", u.to_bytes(8, "big"))[0]
                for x, y in poly:
                    if not (f(lo_x) <= f(hexbits(x)) <= f(hi_x) and f(lo_y) <= f(hexbits(y)) <= f(hi_y)):
                        bad.append("%s: a clip vertex lies outside the authored bounds" % where)
                        break
        else:
            authored = [[bits(c) for c in p] for p in clip["polygon"]]
            read_poly = [[hexbits(c) for c in p] for p in (poly or [])]
            if authored != read_poly:
                bad.append("%s: the clip polygon differs from the authored one" % where)
    return bad + compare_print(expected, read)


def compare_print(expected, read):
    """#101: the layer table's plot flags, every authored line on its layer and in its space, and the layout's
    plot settings, by exact bits."""
    bad = []
    layers = {l["name"]: l for l in read.get("layers", [])}
    for l in expected.get("layers", []):
        r = layers.get(l["name"])
        if r is None:
            bad.append("layer %s: the reader found no such layer" % l["name"])
            continue
        for k in ("plottable", "on", "frozen"):
            if r.get(k) != l[k]:
                bad.append("layer %s: %s authored %s, read %s" % (l["name"], k, l[k], r.get(k)))
    # Every authored line is read back once, on its layer, in its space, and nothing else is there: model
    # lines in *Model_Space, paper lines in the block of the viewports' layout.
    model = next((b["entities"] for b in read.get("blocks", []) if b["name"] == "*Model_Space"), [])
    blocks = {v.get("block") for v in read.get("viewports", [])}
    paper = [r for r in read.get("paper_entities", []) if r.get("block") in blocks]
    if len(paper) != len(read.get("paper_entities", [])):
        bad.append("paper space holds entities outside the viewports' layout")
    for space, pool in (("MODEL", model), ("PAPER", paper)):
        want = sorted((e.get("layer", {}).get("name", "0"), [bits(c) for c in e["geometry"]["start"]], [bits(c) for c in e["geometry"]["end"]])
                      for e in expected["entities"] if e.get("space", "MODEL") == space)
        got = sorted((r.get("layer"), [hexbits(c) for c in r["start"]], [hexbits(c) for c in r["end"]]) if r.get("type") == "LINE"
                     else (r.get("type"), [], []) for r in pool)
        if want != got:
            bad.append("%s space: authored lines %s, read %s" % (space.lower(), want, got))
    lp = expected.get("layout_plot")
    if lp:
        r = next((x for x in read.get("layouts", []) if x["name"] == lp["layout"]), None)
        if r is None:
            return bad + ["layout %s: the reader found no such layout" % lp["layout"]]
        for k in ("paper_size", "paper_units", "rotation", "print_lineweights", "plot_style_sheet"):
            if r.get(k) != lp[k]:
                bad.append("layout %s: %s authored %r, read %r" % (lp["layout"], k, lp[k], r.get(k)))
        for k in ("paper_width", "paper_height", "scale_numerator", "scale_denominator"):
            if hexbits(r[k]) != bits(lp[k]):
                bad.append("layout %s: %s authored 0x%016x, read %s" % (lp["layout"], k, bits(lp[k]), r[k]))
        for k in ("margins", "origin"):
            if [hexbits(x) for x in r[k]] != [bits(x) for x in lp[k]]:
                bad.append("layout %s: %s differ from the authored ones" % (lp["layout"], k))
    return bad


def dump(doc):
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def readme(fid, kind_text):
    return ("# %s\n\n%s\n\nThe record is `expected.math.json`, authored from its parameter file by "
            "`tools/authoring/author_probes.py` and never from a reader or converter output. `source.dwg` was "
            "written by the open writer (acadrust, `tools/r0-open/rust`) from the record's f64 bits, and "
            "`read.acadrust.json` is what acadrust's reader found in it. Only one reader has looked at this "
            "drawing so far, and no STEP converter has (STEP cannot express a viewport), so the scope is "
            "`READER_MAPPING_ONLY`.\n" % (fid, kind_text))


def assemble(run, out, sample_sha=None):
    run, out = Path(run), Path(out)
    report = json.loads((run / "write-report.json").read_text())
    status = {f["id"]: f for f in report["fixtures"]}
    fixtures, problems = [], []
    for fid in IDS:
        st = status.get(fid)
        if not st or st["status"] != "WRITTEN":
            problems.append("%s was not written: %s" % (fid, st))
            continue
        expected = json.loads((KT / fid / "expected.math.json").read_text())
        read = json.loads((run / fid / "acadrust.read.json").read_text())
        bad = compare(expected, read)
        if bad:
            problems.append("%s: %s" % (fid, "; ".join(bad)))
            continue
        d = out / "fixtures" / fid
        d.mkdir(parents=True, exist_ok=True)
        files = {"source.dwg": (run / fid / "source.dwg").read_bytes(),
                 "expected.math.json": (KT / fid / "expected.math.json").read_bytes(),
                 "read.acadrust.json": (run / fid / "acadrust.read.json").read_bytes(),
                 "README.md": readme(fid, expected["provenance"]["parameters"]["description"]).encode()}
        for n, b in files.items():
            (d / n).write_bytes(b)
        fixtures.append({"id": fid, "group": "viewports", "evidence_class": "KNOWN_TRUTH_EXACT",
                         "evidence_scope": "READER_MAPPING_ONLY", "oracle_scope": "NONE",
                         "licence_verdict": "PUBLIC_REDISTRIBUTABLE", "provenance": "SYNTHETIC_AUTHORED",
                         "status": "ACCEPTED", "dwg_version": report["dwg_version"], "readers": ["acadrust"],
                         "dwg_sha256": st["dwg_sha256"],
                         "artifacts": {n: {"path": "corpus/%s/fixtures/%s/%s" % (REVISION, fid, n), "sha256": sha(b)}
                                       for n, b in sorted(files.items())}})
    if problems:
        raise SystemExit("not assembling r3-open:\n  " + "\n  ".join(problems))
    d = out / "fixtures" / LARGE["id"]
    d.mkdir(parents=True, exist_ok=True)
    params = dump({"generator": GENERATOR, "seed": LARGE["seed"], "count": LARGE["entity_count"]})
    rd = ("# large-industrial-001\n\nA synthetic industrial site of one million entities (pipe-run lines, valve circles, elbow "
          "arcs and cable-tray polylines on a 2 km by 1 km grid). It is generated, never committed as a DWG: run "
          "`python3 %s --count %d --seed %d --out large-industrial-001.json`. The output is a pure function of seed "
          "and count, and `sample_sha256` in the manifest is the hash of the same command run with `--count %d`.\n"
          % (GENERATOR, LARGE["entity_count"], LARGE["seed"], LARGE["sample_count"]))
    (d / "params.json").write_text(params)
    (d / "README.md").write_text(rd)
    arts = {n: {"path": "corpus/%s/fixtures/%s/%s" % (REVISION, LARGE["id"], n), "sha256": sha((d / n).read_bytes())}
            for n in ("README.md", "params.json")}
    fixtures.append({"id": LARGE["id"], "group": "large", "evidence_class": "KNOWN_TRUTH_EXACT",
                     "evidence_scope": "GENERATED_AT_USE", "oracle_scope": "NONE",
                     "licence_verdict": "PUBLIC_REDISTRIBUTABLE", "provenance": "SYNTHETIC_AUTHORED",
                     "status": "ACCEPTED", "size_class": "large", "entity_count": LARGE["entity_count"],
                     "generator": GENERATOR, "generator_sha256": sha((ROOT / GENERATOR).read_bytes()),
                     "seed": LARGE["seed"], "sample_count": LARGE["sample_count"], "sample_sha256": sample_sha,
                     "artifacts": arts})
    r2 = ROOT / "corpus" / "r2-open" / "manifest.json"
    manifest = {"schema_version": "pvec-gold/corpus-manifest/1", "corpus_revision": REVISION, "status": "CANDIDATE",
                "writer": report["writer"], "dwg_version": report["dwg_version"], "numeric_policy_version": "PVec numeric policy v1",
                "oracle_scope": "NONE",
                "oracle_note": "No STEP oracle ran on this revision: a STEP file cannot express a viewport or a paper-space layout.",
                "includes": {"r2-open": {"manifest_sha256": sha(r2.read_bytes())}},
                "fixtures": fixtures}
    (out / "manifest.json").write_text(dump(manifest))
    (out / "README.md").write_text(
        "# r3-open (candidate)\n\nAdds the viewport, paper-space and large-industrial fixtures libviprs#1055 and #1064 "
        "need (#96) on top of `r2-open`, which it includes unchanged.\n\n"
        "## Record shape\n\nA fixture with viewports carries a `viewports` array in `expected.math.json`: per viewport `id`, "
        "`layout`, `paper` (`center`, `width`, `height`, in paper space), `view` (`center`, `height`, the model-space window; the target is the origin, so the centre is the model point at the middle of the viewport) and, "
        "when it is clipped, `clip` (`polygon` in paper space, `bounded_only`, `bounds`). `bounded_only` means a reader may "
        "report the polygon or only its bounding box, and may not report anything outside `bounds`. A paper-space layout is "
        "the set of viewports that share a `layout` name. Assertions use `VIEWPORT_COUNT_PRESERVED` and `VIEWPORT_CLIP_PRESERVED`.\n\n"
        "The print-profile probes (#101) add a `layers` table with plot flags, lines on named layers in model and paper space "
        "(`space: PAPER`), and per viewport a view `direction` and `twist` (radians), `frozen_layers`, `hide_plot` and "
        "`entity_layer`, plus the layout's plot settings in `layout_plot`. Their claims are `VIEWPORT_VIEW_PRESERVED`, "
        "`VIEWPORT_FREEZE_PRESERVED`, `VIEWPORT_PLOT_STATE_PRESERVED`, `LAYER_PLOT_STATE_PRESERVED` and "
        "`LAYOUT_PLOT_SETTINGS_PRESERVED`.\n\n"
        "The large fixture has no DWG, only a generator and a size class (`size_class: large`).\n")
    write_sums(out)


def write_sums(d):
    lines = []
    for p in sorted(Path(d).rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append("%s  %s" % (sha(p.read_bytes()), p.relative_to(d)))
    (Path(d) / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def generator_sample(count, seed):
    """sha256 of the generator's output for `count` entities, run the way a consumer would run it."""
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "sample.json"
        subprocess.run([sys.executable, "-I", str(ROOT / GENERATOR), "--count", str(count), "--seed", str(seed),
                        "--out", str(out)], check=True, capture_output=True)
        return sha(out.read_bytes())


def check(d=None, manifest=None):
    d = Path(d or ROOT / "corpus" / REVISION)
    m = manifest if manifest is not None else json.loads((d / "manifest.json").read_text())
    bad = []
    r2 = ROOT / "corpus" / "r2-open" / "manifest.json"
    if m["includes"]["r2-open"]["manifest_sha256"] != sha(r2.read_bytes()):
        bad.append("includes.r2-open.manifest_sha256 is not the hash of corpus/r2-open/manifest.json")
    for f in m["fixtures"]:
        if "generator" not in f:
            continue
        if f["generator_sha256"] != sha((ROOT / f["generator"]).read_bytes()):
            bad.append("%s: generator_sha256 is not the hash of %s" % (f["id"], f["generator"]))
        if f["sample_sha256"] != generator_sample(f["sample_count"], f["seed"]):
            bad.append("%s: sample_sha256 is not what the generator writes for %d entities at seed %d"
                       % (f["id"], f["sample_count"], f["seed"]))
    for f in m["fixtures"]:
        for n, a in f["artifacts"].items():
            p = ROOT / a["path"]
            if not p.is_file() or sha(p.read_bytes()) != a["sha256"]:
                bad.append("%s/%s does not match the manifest" % (f["id"], n))
        if f["id"] in IDS:
            r = ROOT / f["artifacts"]["read.acadrust.json"]["path"]
            bad += ["%s: %s" % (f["id"], x) for x in compare(
                json.loads((KT / f["id"] / "expected.math.json").read_text()), json.loads(r.read_text()))]
    for line in (d / "SHA256SUMS").read_text().splitlines():
        h, name = line.split("  ", 1)
        if sha((d / name).read_bytes()) != h:
            bad.append("SHA256SUMS: %s changed" % name)
    for p in d.rglob("*.dwg"):
        if p.name.startswith("large-industrial"):
            bad.append("a large-industrial DWG is committed: %s" % p)
    return bad


def main(argv):
    if argv[:1] == ["assemble"]:
        sample = argv[argv.index("--generator-sample") + 1] if "--generator-sample" in argv else None
        assemble(argv[1], ROOT / "corpus" / REVISION, sample)
        return 0
    if argv[:1] == ["check"]:
        bad = check()
        print("\n".join(bad) if bad else "r3-open ok")
        return 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
