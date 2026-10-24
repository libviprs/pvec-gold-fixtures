"""Corpus revision r0-open: compare DWG read records to the authored truth, and assemble or check the corpus.

    python3 -m runner.r0_open assemble RAW_DIR CORPUS_DIR --writer-info FILE
    python3 -m runner.r0_open check CORPUS_DIR

What this proves, and only this: a DWG that one open family wrote carries, when decoded by that
family's reader and by the other family's reader, the numbers that were authored before any DWG
existed (expected.math.json and the parameter files it names). It is a statement about the DWG
reader mapping. No STEP file, no CAD Exchanger and no ODA component is involved, and no oracle
other than the authored mathematics is used (docs/adr/0008-open-writer-known-truth-corpus.md).

Two comparison modes, recorded per field so nobody has to guess:

  EXACT   the DWG stores the authored f64 verbatim, and both readers must return the same bits.
  POLICY  the DWG stores a derived quantity (an arc's end angle, an ellipse's major axis vector and
          ratio, an INSERT's rotation angle), so the reader's value is compared to the authored one
          with PVec numeric policy v1 (NP-05 `near`). Every threshold comes from the vendored policy.

The cross-read rule: the verdict is AGREE only if the other family's reader matches the truth, the
writer family's own reader matches the truth, and the two readers' decoded records are identical.
Anything else quarantines the probe (ADR 0006).
"""
import hashlib
import json
import math
import sys
from pathlib import Path

from . import numeric

ROOT = Path(__file__).resolve().parent.parent
KT = ROOT / "fixtures" / "known-truth"
PARAMS = ROOT / "tools" / "authoring" / "params"
READ_SCHEMA = "pvec-gold/r0-open-dwg-read/1"
REVISION = "r0-open"
SCOPE = "READER_MAPPING_ONLY"
STATEMENT = (
    "KNOWN_TRUTH_EXACT here means one thing: the DWG bytes, decoded by two independent open readers, carry the "
    "authored mathematics, exactly where the DWG stores it verbatim and within PVec numeric policy v1 where it "
    "stores a derived value. There is no STEP oracle: no STEP file was produced, read or compared, and nothing "
    "here says how any converter treats these drawings."
)
TYPE_OF = {"line": "LINE", "circle": "CIRCLE", "circular_arc": "ARC", "ellipse": "ELLIPSE",
           "elliptical_arc": "ELLIPSE", "polyline": "LWPOLYLINE", "bezier": "SPLINE", "bspline": "SPLINE",
           "nurbs": "SPLINE"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fl(h):
    return numeric.canon.hex_to_f64(h)


def ef(s):
    return fl(s["f64_hex"])


def family(name_at_version):
    return name_at_version.split("@", 1)[0]


def load_json(p):
    return json.loads(Path(p).read_text())


def dump_json(obj, path):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def expected_path(fid):
    hits = list(KT.rglob("%s/expected.math.json" % fid))
    assert len(hits) == 1, fid
    return hits[0]


def params_path(fid):
    hits = [p for p in PARAMS.rglob("*.json") if load_json(p)["id"] == fid]
    assert len(hits) == 1, fid
    return hits[0]


class Checks:
    def __init__(self, pol):
        self.pol, self.items = pol, []

    def exact(self, name, want, got):
        ok = isinstance(got, float) and want == got
        self.items.append({"field": name, "mode": "EXACT", "expected": numeric.canon.f64_to_hex(want),
                           "read": numeric.canon.f64_to_hex(got) if isinstance(got, float) else repr(got), "ok": bool(ok)})

    def near(self, name, want, got, scale):
        ok = self.pol.near(want, got, scale)
        self.items.append({"field": name, "mode": "POLICY", "expected": numeric.canon.f64_to_hex(want),
                           "read": numeric.canon.f64_to_hex(got), "ok": bool(ok)})

    def flag(self, name, want, got):
        self.items.append({"field": name, "mode": "EXACT", "expected": want, "read": got, "ok": want == got})

    def vec(self, name, want, got):
        for i, (w, g) in enumerate(zip(want, got)):
            self.exact("%s[%d]" % (name, i), w, g)

    def vec_near(self, name, want, got, scale):
        for i, (w, g) in enumerate(zip(want, got)):
            self.near("%s[%d]" % (name, i), w, g, scale)

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def v3(x):
    return [fl(c) for c in x]


def pt(x):
    return [ef(c) for c in x]


def wrap_angle(a):
    two_pi = 2 * math.pi
    return a - two_pi if a >= two_pi else a


def check_curve(c, e, d, prefix):
    """e is the expected entity (local geometry), d the dumped entity."""
    cls, g = e["class"], e["geometry"]
    want_type = TYPE_OF[cls]
    c.flag(prefix + "type", want_type, d["type"])
    if d["type"] != want_type:
        return
    if cls == "line":
        c.vec(prefix + "start", pt(g["start"]), v3(d["start"]))
        c.vec(prefix + "end", pt(g["end"]), v3(d["end"]))
    elif cls in ("circle", "circular_arc"):
        c.vec(prefix + "center", pt(g["center"]), v3(d["center"]))
        c.exact(prefix + "radius", ef(g["radius"]), fl(d["radius"]))
        c.vec(prefix + "normal", pt(g["normal"]), v3(d["normal"]))
        if cls == "circular_arc":
            start, sweep = ef(g["start_angle"]), ef(g["sweep_angle"])
            c.exact(prefix + "start_angle", start, fl(d["start_angle"]))
            c.near(prefix + "end_angle", wrap_angle(start + sweep), fl(d["end_angle"]), 1.0)
    elif cls in ("ellipse", "elliptical_arc"):
        a, b = ef(g["semi_major"]), ef(g["semi_minor"])
        m = pt(g["major_axis"])
        c.vec(prefix + "center", pt(g["center"]), v3(d["center"]))
        c.vec(prefix + "normal", pt(g["normal"]), v3(d["normal"]))
        c.vec_near(prefix + "major_axis_vector", [x * a for x in m], v3(d["major_axis"]), a)
        c.near(prefix + "axis_ratio", b / a, fl(d["ratio"]), 1.0)
        if cls == "ellipse":
            c.exact(prefix + "start_param", 0.0, fl(d["start_param"]))
            c.near(prefix + "end_param", 2 * math.pi, fl(d["end_param"]), 1.0)
        else:
            s = ef(g["start_angle"])
            c.exact(prefix + "start_param", s, fl(d["start_param"]))
            c.near(prefix + "end_param", s + ef(g["sweep_angle"]), fl(d["end_param"]), 1.0)
    elif cls == "polyline":
        vs, bs = g["vertices"], g["bulges"]
        c.flag(prefix + "vertex_count", len(vs), len(d["vertices"]))
        if len(vs) == len(d["vertices"]):
            for i, (v, bu, r) in enumerate(zip(vs, bs, d["vertices"])):
                c.exact("%svertex[%d].x" % (prefix, i), ef(v[0]), fl(r[0]))
                c.exact("%svertex[%d].y" % (prefix, i), ef(v[1]), fl(r[1]))
                c.exact("%svertex[%d].z(elevation)" % (prefix, i), ef(v[2]), fl(d["elevation"]))
                c.exact("%svertex[%d].bulge" % (prefix, i), ef(bu), fl(r[2]))
        c.flag(prefix + "closed", False, d["closed"])
    else:  # bezier, bspline, nurbs
        c.flag(prefix + "degree", g["degree"], d["degree"])
        cps = g["control_points"]
        c.flag(prefix + "control_point_count", len(cps), len(d["control_points"]))
        if len(cps) == len(d["control_points"]):
            for i, (p, r) in enumerate(zip(cps, d["control_points"])):
                c.vec("%scontrol_point[%d]" % (prefix, i), pt(p), v3(r))
        if cls == "bezier":
            lo, hi = ef(e["parameter_domain"]["start"]), ef(e["parameter_domain"]["end"])
            knots = [lo] * (g["degree"] + 1) + [hi] * (g["degree"] + 1)
        else:
            knots = [ef(k["value"]) for k in g["knots"] for _ in range(k["multiplicity"])]
        c.flag(prefix + "knot_count", len(knots), len(d["knots"]))
        if len(knots) == len(d["knots"]):
            for i, (k, r) in enumerate(zip(knots, d["knots"])):
                c.exact("%sknot[%d]" % (prefix, i), k, fl(r))
        c.flag(prefix + "rational", cls == "nurbs", d["rational"])
        ws = [ef(w) for w in g["weights"]] if cls == "nurbs" else []
        c.flag(prefix + "weight_count", len(ws), len(d["weights"]))
        if len(ws) == len(d["weights"]):
            for i, (w, r) in enumerate(zip(ws, d["weights"])):
                c.exact("%sweight[%d]" % (prefix, i), w, fl(r))
        cl = e["closure"]
        c.flag(prefix + "closed(by knots)", bool(cl["closed_by_knots"]), d["closed"])
        c.flag(prefix + "periodic", bool(cl["periodic"]), d["periodic"])
        c.flag(prefix + "fit_points", 0, d["fit_point_count"])


# ---- transforms: the INSERT chain ----------------------------------------------------------

def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def insert_matrix(ins):
    """T(insert point) * Rz(rotation) * S(scale), the INSERT's own composition."""
    p, s, r = v3(ins["insert_point"]), v3(ins["scale"]), fl(ins["rotation"])
    cs, sn = math.cos(r), math.sin(r)
    t = [[1, 0, 0, p[0]], [0, 1, 0, p[1]], [0, 0, 1, p[2]], [0, 0, 0, 1]]
    rz = [[cs, -sn, 0, 0], [sn, cs, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    sc = [[s[0], 0, 0, 0], [0, s[1], 0, 0], [0, 0, s[2], 0], [0, 0, 0, 1]]
    return matmul(matmul(t, rz), sc)


def flat(m):
    return [x for row in m for x in row]


def apply(m, p):
    return [sum(m[i][k] * p[k] for k in range(3)) + m[i][3] for i in range(3)]


def decimal_f(s):
    return float(s)


def check_matrix(c, name, want16, got_m):
    want = [ef(x) for x in want16]
    scale = max(abs(x) for x in want) or 1.0
    for i, (w, g) in enumerate(zip(want, flat(got_m))):
        if w == g:
            c.exact("%s[%d]" % (name, i), w, g)
        else:
            c.near("%s[%d]" % (name, i), w, g, scale)


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def check_world(c, e, m, local):
    w = e.get("world")
    if not w:
        return
    cls, g = w["class"], w["geometry"]
    if cls == "line":
        for k in ("start", "end"):
            c.vec_near("world." + k, pt(g[k]), apply(m, pt(local[k])), math.dist(pt(g["start"]), pt(g["end"])))
        return
    ctr = apply(m, pt(local["center"]))
    c.vec_near("world.center", pt(g["center"]), ctr, ef(g.get("radius", g.get("semi_major", {"f64_hex": "0x3ff0000000000000"}))))
    a, b, cc, d = m[0][0], m[0][1], m[1][0], m[1][1]
    r = ef(local["radius"])
    if cls in ("circle", "circular_arc"):
        sing = math.sqrt(abs(a * d - b * cc))
        c.near("world.radius(|det|^1/2 of the xy block, a similarity)", ef(g["radius"]), r * sing, ef(g["radius"]))
    elif cls == "ellipse":
        s1 = a * a + b * b + cc * cc + d * d
        s2 = math.sqrt((a * a + b * b - cc * cc - d * d) ** 2 + 4 * (a * cc + b * d) ** 2)
        big, small = math.sqrt((s1 + s2) / 2) * r, math.sqrt(max((s1 - s2) / 2, 0.0)) * r
        c.near("world.semi_major", ef(g["semi_major"]), big, ef(g["semi_major"]))
        c.near("world.semi_minor", ef(g["semi_minor"]), small, ef(g["semi_major"]))
        phi = 0.5 * math.atan2(2 * (a * b + cc * d), (a * a + cc * cc) - (b * b + d * d))
        axis = unit([a * math.cos(phi) + b * math.sin(phi), cc * math.cos(phi) + d * math.sin(phi)])
        want = pt(g["major_axis"])[:2]
        if axis[0] * want[0] + axis[1] * want[1] < 0:
            axis = [-axis[0], -axis[1]]
        c.vec_near("world.major_axis_direction(sign-free)", want, axis, 1.0)


def check_transform(c, e, doc_params, d):
    """d is the whole dump. The chain is read back from the DWG: model space holds one INSERT and each
    nested block holds the next, the innermost holds the base entity."""
    blocks = {b["name"]: b["entities"] for b in d["blocks"]}
    ops = doc_params["ops"]
    nested = len(ops) > 1  # a transform_chain is carried as one INSERT level per op
    levels = len(ops) if nested else 1
    ms = blocks.get("*Model_Space", [])
    c.flag("model_space_entity_count", 1, len(ms))
    if len(ms) != 1:
        return
    chain, cur = [], ms[0]
    for i in range(levels):
        c.flag("level%d.type" % (i + 1), "INSERT", cur["type"])
        if cur["type"] != "INSERT":
            return
        chain.append(cur)
        inner = blocks.get(cur["block"])
        c.flag("level%d.block_found" % (i + 1), True, inner is not None)
        if inner is None or len(inner) != 1:
            c.flag("level%d.block_entity_count" % (i + 1), 1, None if inner is None else len(inner))
            return
        cur = inner[0]
    check_curve(c, e, cur, "base.")
    # Authored op values per level, outermost first. Translation and scale are stored verbatim.
    groups = [[o] for o in ops] if nested else [ops]
    for i, (ins, grp) in enumerate(zip(chain, groups)):
        want_t, want_s = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
        for o in grp:
            if o["op"] == "translate":
                want_t = [decimal_f(x) for x in o["v"]]
            elif o["op"] == "scale":
                want_s = [decimal_f(x) for x in o["s"]]
        p = "level%d." % (i + 1)
        c.vec(p + "insert_point", want_t, v3(ins["insert_point"]))
        c.vec(p + "scale", want_s, v3(ins["scale"]))
        c.vec(p + "normal", [0.0, 0.0, 1.0], v3(ins["normal"]))
        for o in grp:
            if o["op"] == "rotate_z":
                ang = decimal_f(o["angle_rad"]) if "angle_rad" in o else math.atan2(decimal_f(o["cos_sin"][1]), decimal_f(o["cos_sin"][0]))
                (c.exact if "angle_rad" in o else (lambda n, w, g: c.near(n, w, g, 1.0)))(p + "rotation", ang, fl(ins["rotation"]))
        if not any(o["op"] == "rotate_z" for o in grp):
            c.exact(p + "rotation", 0.0, fl(ins["rotation"]))
    mats = [insert_matrix(i) for i in chain]
    if "transform_chain" in e:
        tc = e["transform_chain"]
        for i, (t, m) in enumerate(zip(tc["transforms"], mats)):
            check_matrix(c, "level%d.matrix" % (i + 1), t["matrix"], m)
        comp = mats[0]
        for m in mats[1:]:
            comp = matmul(comp, m)
        check_matrix(c, "composed.matrix", tc["composed"]["matrix"], comp)
    else:
        comp = mats[0]
        check_matrix(c, "matrix", e["transform"]["matrix"], comp)
    check_world(c, e, comp, e["geometry"])


def judge(pol, fid, dump):
    """Check one read record against the authored truth. Returns the list of checks."""
    exp = load_json(expected_path(fid))
    params = load_json(params_path(fid))
    e = exp["entities"][0]
    c = Checks(pol)
    if dump.get("schema") != READ_SCHEMA:
        c.flag("schema", READ_SCHEMA, dump.get("schema"))
        return c
    if e["structure"] == "CURVE_ONLY":
        ms = {b["name"]: b["entities"] for b in dump["blocks"]}.get("*Model_Space", [])
        c.flag("model_space_entity_count", 1, len(ms))
        if len(ms) == 1:
            check_curve(c, e, ms[0], "")
    else:
        check_transform(c, e, params, dump)
    return c


def strip(d):
    return {k: v for k, v in d.items() if k != "reader"}


def diff(a, b, path=""):
    out = []
    if type(a) is not type(b):
        return [path or "."]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s/%s" % (path, k))
            else:
                out += diff(a[k], b[k], "%s/%s" % (path, k))
    elif isinstance(a, list):
        if len(a) != len(b):
            return [path + " (length)"]
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, "%s[%d]" % (path, i))
    elif a != b:
        out.append(path)
    return out


def verdict(pol, fid, writer, own, cross):
    """The cross-read rule. own is the writer family's reader record, cross the other family's.
    Either may be None when that reader could not open the file."""
    res = {"checks": {}, "reader_vs_reader_differences": None}
    if cross is None or own is None:
        res["verdict"], res["reason"] = "UNREADABLE", "MALFORMED_FIXTURE"
        res["evidence"] = "a reader could not open the DWG: %s" % ("cross reader" if cross is None else "own reader")
        return res
    co, cc = judge(pol, fid, own), judge(pol, fid, cross)
    res["checks"] = {"cross": cc.items, "own": co.items}
    res["reader_vs_reader_differences"] = diff(strip(own), strip(cross))
    bad = []
    if not cc.ok:
        bad.append("cross reader differs from the authored truth at: " + ", ".join(i["field"] for i in cc.items if not i["ok"])[:300])
    if not co.ok:
        bad.append("writer family's own reader differs from the authored truth at: " + ", ".join(i["field"] for i in co.items if not i["ok"])[:300])
    if res["reader_vs_reader_differences"]:
        bad.append("the two readers decoded different records at: " + ", ".join(res["reader_vs_reader_differences"])[:300])
    if bad:
        res["verdict"], res["reason"], res["evidence"] = "DISAGREE", "UNRESOLVED_DISAGREEMENT", "; ".join(bad)
    else:
        res["verdict"], res["reason"], res["evidence"] = "AGREE", None, None
    return res


# ---- assemble and check --------------------------------------------------------------------

def readme(fid, writer, cross_reader, v, dwg_version):
    status = "accepted" if v["verdict"] == "AGREE" else "quarantined (%s)" % v["reason"]
    return (
        "# %s\n\n"
        "This is a probe of the r0-open corpus revision, and it is %s.\n\n"
        "`source.dwg` was written by %s as %s, from the authored parameters of the O1.5a/O1.6a probe record. "
        "The truth is `%s`, which I authored before any DWG existed and which this revision never edits. "
        "No expected value comes from a DWG, a STEP file or any converter.\n\n"
        "I had it read back by %s (the other open family) and by the writer's own reader. Both read records are "
        "kept beside the DWG (`read.*.json`), and `comparison.json` lists every field checked, whether it was "
        "compared EXACT or under PVec numeric policy v1, and the verdict.\n\n"
        "What this says: the DWG carries the authored mathematics as two independent open readers decode it. "
        "What it does not say: there is no STEP oracle, nothing here was converted by CAD Exchanger or ODA, and "
        "the class is KNOWN_TRUTH_EXACT for reader mapping only.\n"
    ) % (fid, status, writer, dwg_version, expected_rel(fid), cross_reader)


def expected_rel(fid):
    return str(expected_path(fid).relative_to(ROOT))


def assemble(raw, corpus, info):
    pol = numeric.load_policy()
    raw, corpus = Path(raw), Path(corpus)
    rep = load_json(raw / "write-report.json")
    writer, dwg_version = rep["writer"], rep["dwg_version"]
    cross_reader = info["cross_reader"]
    fixtures, excluded, quarantined = [], [], []
    for item in rep["fixtures"]:
        fid = item["id"]
        if item["status"] == "SKIPPED":
            excluded.append({"id": fid, "reason": item["reason"], "evidence": item["evidence"], "file": None})
            continue
        src = raw / fid
        out = corpus / "fixtures" / fid
        out.mkdir(parents=True, exist_ok=True)
        dwg = src / "source.dwg"
        (out / "source.dwg").write_bytes(dwg.read_bytes())
        own = load_json(src / "acadrust.read.json") if (src / "acadrust.read.json").exists() else None
        cross = load_json(src / "acadsharp.read.json") if (src / "acadsharp.read.json").exists() else None
        for name, rec in (("read.acadrust.json", own), ("read.acadsharp.json", cross)):
            if rec is not None:
                dump_json(rec, out / name)
        v = verdict(pol, fid, writer, own, cross)
        dump_json({"fixture_id": fid, "numeric_policy_version": pol.version, **v}, out / "comparison.json")
        (out / "README.md").write_text(readme(fid, writer, cross_reader, v, dwg_version))
        accepted = v["verdict"] == "AGREE"
        entry = {
            "id": fid,
            "group": params_group(fid),
            "evidence_class": "KNOWN_TRUTH_EXACT" if accepted else "QUARANTINED",
            "evidence_scope": SCOPE,
            "oracles": "none",
            "status": "ACCEPTED" if accepted else "QUARANTINED",
            "provenance": "SYNTHETIC_AUTHORED",
            "licence_verdict": "PUBLIC_REDISTRIBUTABLE",
            "dwg": {"path": "fixtures/%s/source.dwg" % fid, "sha256": sha256(out / "source.dwg"), "dwg_version": dwg_version, "writer": writer},
            "expected": {"path": expected_rel(fid), "sha256": sha256(expected_path(fid))},
            "parameter_file": {"path": str(params_path(fid).relative_to(ROOT)), "sha256": sha256(params_path(fid))},
            "cross_read": {"reader": cross_reader, "record": "fixtures/%s/read.acadsharp.json" % fid, "sha256": sha256(out / "read.acadsharp.json") if cross is not None else None, "verdict": v["verdict"]},
            "own_read": {"reader": info["own_reader"], "record": "fixtures/%s/read.acadrust.json" % fid, "sha256": sha256(out / "read.acadrust.json") if own is not None else None},
            "comparison": {"path": "fixtures/%s/comparison.json" % fid, "sha256": sha256(out / "comparison.json")},
        }
        if not accepted:
            entry["quarantine"] = {"reason": v["reason"], "evidence": v["evidence"]}
            quarantined.append({"id": fid, "reason": v["reason"], "evidence": v["evidence"]})
        fixtures.append(entry)
    fixtures.sort(key=lambda f: f["id"])
    excluded.sort(key=lambda f: f["id"])
    manifest = {
        "schema_version": "pvec-gold/corpus-manifest/1",
        "corpus_revision": REVISION,
        "status": "CANDIDATE",
        "oracles": "none",
        "step_oracle": "none",
        "evidence_scope": SCOPE,
        "evidence_statement": STATEMENT,
        "adr": "docs/adr/0008-open-writer-known-truth-corpus.md",
        **numeric.policy_stamp(pol),
        "writer": writer,
        "writer_source": info["writer_source"],
        "cross_readers": [{"reader": cross_reader, "source": info["cross_reader_source"]}],
        "own_readers": [{"reader": info["own_reader"], "source": info["writer_source"]}],
        "dwg_version": dwg_version,
        "container_images": info["images"],
        "determinism": info.get("determinism"),
        "converters": "none",
        "evaluator": "none (no STEP evaluator ran; there is no STEP output)",
        "fixtures": fixtures,
    }
    dump_json(manifest, corpus / "manifest.json")
    dump_json({"corpus_revision": REVISION, "quarantined": quarantined, "excluded": excluded}, corpus / "quarantine.json")
    write_sums(corpus)
    return manifest


def params_group(fid):
    return load_json(params_path(fid)).get("group", "curves")


def write_sums(corpus):
    corpus = Path(corpus)
    names = sorted(str(p.relative_to(corpus)) for p in corpus.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (corpus / "SHA256SUMS").write_text("".join("%s  %s\n" % (sha256(corpus / n), n) for n in names))


def check(corpus):
    """Recompute every verdict from the stored read records. No DWG library, no converter, no Docker."""
    pol = numeric.load_policy()
    corpus = Path(corpus)
    m = load_json(corpus / "manifest.json")
    problems = []
    if m.get("numeric_policy_version") != pol.version:
        problems.append("numeric policy version differs from the vendored policy")
    for line in (corpus / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if sha256(corpus / name) != digest:
            problems.append("SHA256SUMS mismatch: " + name)
    for f in m["fixtures"]:
        fid = f["id"]
        if sha256(ROOT / f["expected"]["path"]) != f["expected"]["sha256"]:
            problems.append("%s: expected.math.json changed since the corpus was assembled" % fid)
        own = load_json(corpus / f["own_read"]["record"])
        cross = load_json(corpus / f["cross_read"]["record"])
        for rec in (own, cross):
            if rec["dwg_sha256"] != f["dwg"]["sha256"]:
                problems.append("%s: a read record is for a different DWG" % fid)
        v = verdict(pol, fid, m["writer"], own, cross)
        if v["verdict"] != f["cross_read"]["verdict"]:
            problems.append("%s: recomputed verdict %s, manifest says %s" % (fid, v["verdict"], f["cross_read"]["verdict"]))
    return problems


def main(argv):
    if len(argv) >= 3 and argv[0] == "assemble":
        info = load_json(argv[argv.index("--writer-info") + 1])
        mf = assemble(argv[1], argv[2], info)
        print("assembled %d fixtures: %d accepted" % (len(mf["fixtures"]), sum(f["status"] == "ACCEPTED" for f in mf["fixtures"])))
        return 0
    if len(argv) == 2 and argv[0] == "check":
        problems = check(argv[1])
        for p in problems:
            print("FAIL", p)
        print("r0-open check: %s" % ("FAILED" if problems else "ok"))
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
