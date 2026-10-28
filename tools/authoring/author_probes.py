#!/usr/bin/env python3
"""Derive every known-truth expected.math.json (and README) from the hand-chosen parameters.

    python3 tools/authoring/author_probes.py           write fixtures/known-truth/...
    python3 tools/authoring/author_probes.py --check   fail if what is on disk differs

The inputs are tools/authoring/params/**/*.json. They are chosen in advance and are the only
source of any expected value. Nothing here reads a STEP file or any converter output.

Derived values (sines, cosines, arc centres, ellipse axes) are computed to 60 digits with mpmath
and rounded once to f64 through a 40 digit decimal string. Inputs given as decimal strings are
rounded to f64 directly, which is what a DWG writer would store.
"""
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from mpmath import atan, atan2, cos, matrix, mp, mpf, pi, sin, sqrt, svd_r

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runner import canon, expected_math as em  # noqa: E402

mp.dps = 60
PARAMS = ROOT / "tools" / "authoring" / "params"
OUT = ROOT / "fixtures" / "known-truth"
SCRIPT = "tools/authoring/author_probes.py"
CL0 = {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}


def S(x):
    if isinstance(x, (str, int, Fraction, float)):
        return canon.scalar(x)
    return canon.scalar(D(x))


def D(x):
    return mp.nstr(clean(x), 40)


def clean(x):
    """Round away arithmetic noise: derived values are kept to 45 decimal places, so an exact zero
    that came out as a residue in the sixtieth digit is zero again."""
    q = mpf(10) ** -45
    return mp.nint(x / q) * q


def P(v):
    return [S(c) for c in v]


def dom(a, b):
    return {"start": S(a), "end": S(b)}


def V(v):
    return [mpf(c) for c in v]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    return sqrt(sum(c * c for c in a))


# ---- curves -------------------------------------------------------------------------------

def build_curve(s):
    c = s["class"]
    n = s.get("normal", ["0", "0", "1"])
    x = s.get("x_axis", ["1", "0", "0"])
    two_pi = 2 * pi
    if c == "line":
        return {"class": c, "geometry": {"start": P(s["start"]), "end": P(s["end"])},
                "parameter_domain": dom("0", "1"), "closure": dict(CL0)}
    if c == "polyline":
        vs = s["vertices"]
        closed = s.get("closed", False)
        cl = dict(CL0, closed_by_endpoint=True) if closed else dict(CL0)
        return {"class": c, "geometry": {"vertices": [P(v) for v in vs], "bulges": [S(b) for b in s.get("bulges", ["0"] * len(vs))]},
                "parameter_domain": dom("0", str(len(vs) if closed else len(vs) - 1)), "closure": cl}
    if c == "circle":
        return {"class": c, "geometry": {"center": P(s["center"]), "normal": P(n), "x_axis": P(x), "radius": S(s["radius"])},
                "parameter_domain": dom("0", two_pi),
                "closure": {"closed_by_endpoint": True, "closed_by_knots": False, "periodic": True}}
    if c == "circular_arc":
        return {"class": c, "geometry": {"center": P(s["center"]), "normal": P(n), "x_axis": P(x), "radius": S(s["radius"]),
                                         "start_angle": S(s["start_angle"]), "sweep_angle": S(s["sweep_angle"])},
                "parameter_domain": dom(s["start_angle"], mpf(s["start_angle"]) + mpf(s["sweep_angle"])), "closure": dict(CL0)}
    if c in ("ellipse", "elliptical_arc"):
        g = {"center": P(s["center"]), "normal": P(n), "major_axis": P(s["major_axis"]),
             "semi_major": S(s["semi_major"]), "semi_minor": S(s["semi_minor"])}
        if c == "ellipse":
            return {"class": c, "geometry": g, "parameter_domain": dom("0", two_pi),
                    "closure": {"closed_by_endpoint": True, "closed_by_knots": False, "periodic": True}}
        g["start_angle"], g["sweep_angle"] = S(s["start_angle"]), S(s["sweep_angle"])
        return {"class": c, "geometry": g, "parameter_domain": dom(s["start_angle"], mpf(s["start_angle"]) + mpf(s["sweep_angle"])),
                "closure": dict(CL0)}
    if c == "bezier":
        return {"class": c, "geometry": {"degree": s["degree"], "control_points": [P(p) for p in s["control_points"]]},
                "parameter_domain": dom("0", "1"), "closure": dict(CL0)}
    if c in ("bspline", "nurbs"):
        g = {"degree": s["degree"], "control_points": [P(p) for p in s["control_points"]],
             "knots": [{"value": S(v), "multiplicity": m} for v, m in s["knots"]]}
        if c == "nurbs":
            g["weights"] = [S(w) for w in s["weights"]]
            g["weights_all_unit"] = all(float(w) == 1.0 for w in s["weights"])
        per = s.get("periodic", False)
        return {"class": c, "geometry": g,
                "parameter_domain": dom(s["knots"][0][0], s["knots"][-1][0]),
                "closure": {"closed_by_endpoint": s.get("closed_by_endpoint", False), "closed_by_knots": per, "periodic": per}}
    raise SystemExit("unknown class %s" % c)


def bulge_equivalent_arc(s):
    p0, p1, b = V(s["p0"]), V(s["p1"]), mpf(s["bulge"])
    d = [p1[0] - p0[0], p1[1] - p0[1]]
    chord = sqrt(d[0] ** 2 + d[1] ** 2)
    u = [d[0] / chord, d[1] / chord]
    left = [-u[1], u[0]]
    r = chord * (1 + b * b) / (4 * abs(b))
    off = chord * (1 - b * b) / (4 * b)
    mid = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2]
    cen = [mid[0] + left[0] * off, mid[1] + left[1] * off]
    # DWG and PVec arcs run counter-clockwise only. A negative bulge is the same arc walked the other
    # way, so the record carries the counter-clockwise arc (start at the polyline's second vertex) and
    # the entity says its parameter direction is reversed against the source.
    pa = p0 if b > 0 else p1
    a0 = atan2(pa[1] - cen[1], pa[0] - cen[0])
    if a0 < 0:
        a0 += 2 * pi
    sweep = 4 * atan(abs(b))
    return {"class": "circular_arc",
            "geometry": {"center": [S(cen[0]), S(cen[1]), S("0")], "normal": P(["0", "0", "1"]), "x_axis": P(["1", "0", "0"]),
                         "radius": S(r), "start_angle": S(a0), "sweep_angle": S(sweep)},
            "parameter_domain": dom(a0, a0 + sweep), "closure": dict(CL0)}


# ---- transforms ---------------------------------------------------------------------------

def mat_from_op(op):
    k = op["op"]
    I = [mpf(int(i % 5 == 0)) for i in range(16)]
    if k == "translate":
        m = list(I)
        m[3], m[7], m[11] = V(op["v"])
        return m
    if k == "rotate_z":
        if "angle_rad" in op:
            c, sn = cos(mpf(op["angle_rad"])), sin(mpf(op["angle_rad"]))
        else:
            c, sn = V(op["cos_sin"])
        m = list(I)
        m[0], m[1], m[4], m[5] = c, -sn, sn, c
        return m
    if k == "scale":
        m = list(I)
        m[0], m[5], m[10] = V(op["s"])
        return m
    if k == "matrix":
        return V(op["m"])
    raise SystemExit("unknown op %s" % k)


def mmul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def apply(A, p):
    return [A[r * 4] * p[0] + A[r * 4 + 1] * p[1] + A[r * 4 + 2] * p[2] + A[r * 4 + 3] for r in range(3)]


def lin(A, v):
    return [A[r * 4] * v[0] + A[r * 4 + 1] * v[1] + A[r * 4 + 2] * v[2] for r in range(3)]


def transform_record(m_mp, cls):
    sc = [S(x) for x in m_mp]
    fr = [canon.exact(s) for s in sc]
    return {"convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": sc,
            "determinant": S(em.det4(fr)), "classification": cls}, fr


def world_curve(base, A, expect):
    c = base["class"]
    if expect == "line":
        return {"class": "line", "geometry": {"start": P(apply(A, V(base["start"]))), "end": P(apply(A, V(base["end"])))},
                "parameter_domain": dom("0", "1"), "closure": dict(CL0)}
    n, x = V(base.get("normal", ["0", "0", "1"])), V(base.get("x_axis", ["1", "0", "0"]))
    cen, r = V(base["center"]), mpf(base["radius"])
    if expect == "similarity":
        y = cross(n, x)
        xp, yp = lin(A, x), lin(A, y)
        sc = norm(xp)
        xh, yh = [t / sc for t in xp], [t / sc for t in yp]
        nh = cross(xh, yh)
        spec = {"class": c, "center": [D(t) for t in apply(A, cen)], "radius": D(r * sc)}
        out = build_curve(dict(spec, normal=[D(t) for t in nh], x_axis=[D(t) for t in xh],
                               **({"start_angle": base["start_angle"], "sweep_angle": base["sweep_angle"]} if c == "circular_arc" else {})))
        return out
    if expect == "ellipse":
        a2 = matrix([[A[0], A[1]], [A[4], A[5]]])
        U, Sv, _ = svd_r(a2)
        u = [U[0, 0], U[1, 0]]
        if u[0] < 0 or (u[0] == 0 and u[1] < 0):
            u = [-u[0], -u[1]]
        return build_curve({"class": "ellipse", "center": [D(t) for t in apply(A, cen)],
                            "major_axis": [D(u[0]), D(u[1]), "0"],
                            "semi_major": D(Sv[0] * r), "semi_minor": D(Sv[1] * r)})
    raise SystemExit("bad expect %s" % expect)


def build_transform_fixture(s):
    base = s["base"]
    rec = build_curve(base)
    ent = {"id": s["id"], **rec, "structure": "INSTANCE_PLUS_TRANSFORM"}
    mats = [mat_from_op(o) for o in s["ops"]]
    recs, frs = [], []
    for m, o in zip(mats, s["ops"]):
        t, fr = transform_record(m, o["classification"])
        recs.append(t)
        frs.append(fr)
    A = mats[0]
    for m in mats[1:]:
        A = mmul(A, m)
    if len(recs) == 1:
        ent["transform"] = recs[0]
        top = recs[0]
    else:
        prod = frs[0]
        for fr in frs[1:]:
            prod = em.matmul(prod, fr)
        comp, _ = transform_record(prod, s["composed_classification"])
        ent["transform_chain"] = {"order": "OUTERMOST_FIRST", "transforms": recs, "composed": comp}
        top = comp
    exp = s["expect"]
    asserts = [("SOURCE_MAPPING", "TRANSFORM_PRESERVED", "Checked in the source mapping, not in the artifact (pvec ADR 0017: PVec is curve-only): the mapping reads the instance plus the stated transform and keeps the matrix and determinant as written while it flattens the instance to the world-space curve.")]
    det_neg = canon.exact(top["determinant"]) < 0
    if exp == "reject":
        ent["rejection"] = dict(s["rejection"])
        asserts.append(("STRUCTURAL", "REJECTED", "The pipeline must report %s (%s) and emit no curve for this entity." % (s["rejection"]["classification"], s["rejection"]["disposition"])))
    else:
        ent["world"] = world_curve(base, A, exp)
        isline = base["class"] == "line"
        ent["orientation"] = {"parameter_direction": "START_TO_END",
                              "sense_about_normal": "NOT_APPLICABLE" if isline or exp == "ellipse" else ("CW" if det_neg else "CCW")}
        asserts.append(("GEOMETRIC", "WORLD_SPACE_RESULT", "The world-space curve is the stated %s." % ent["world"]["class"]))
        if exp == "ellipse":
            asserts.append(("STRUCTURAL", "CLASS_PRESERVED", "A circle under non-uniform scale is an ellipse with the stated axes; a circle is wrong, not merely different."))
        if det_neg:
            asserts.append(("STRUCTURAL", "ORIENTATION_PRESERVED", "The determinant is negative; parameter direction runs start to end and the sense about the source normal flips. A silent reversal fails."))
    extra = ""
    if len(recs) > 1 and exp == "line":
        Arev = mats[-1]
        for m in reversed(mats[:-1]):
            Arev = mmul(Arev, m)
        good = [mp.nstr(clean(t), 17) for pt in ("start", "end") for t in apply(A, V(base[pt]))]
        rev = [mp.nstr(clean(t), 17) for pt in ("start", "end") for t in apply(Arev, V(base[pt]))]
        extra = ("\n## Multiplication order\n\nThe stated chain is outermost first and composes with the parent on the left, so the world "
                 "matrix is M0 * M1 * ... * Mn. The line's start and end land at (%s, %s, %s) and (%s, %s, %s).\n"
                 "Composing in the other order (Mn * ... * M0) puts them at (%s, %s, %s) and (%s, %s, %s), a different place, "
                 "so a converter that flattens in the wrong order is caught.\n" % tuple(good + rev))
    return ent, asserts, extra


# ---- fixtures -----------------------------------------------------------------------------

STRUCT_CLAIMS = {
    "line": ["CLASS_PRESERVED"],
    "polyline": ["CLASS_PRESERVED", "VERTEX_ORDER_PRESERVED"],
    "circle": ["CLASS_PRESERVED"],
    "circular_arc": ["CLASS_PRESERVED"],
    "ellipse": ["CLASS_PRESERVED"],
    "elliptical_arc": ["CLASS_PRESERVED"],
    "bezier": ["CLASS_PRESERVED", "DEGREE_PRESERVED", "CONTROL_POINTS_PRESERVED"],
    "bspline": ["CLASS_PRESERVED", "DEGREE_PRESERVED", "CONTROL_POINTS_PRESERVED", "KNOTS_PRESERVED"],
    "nurbs": ["CLASS_PRESERVED", "DEGREE_PRESERVED", "CONTROL_POINTS_PRESERVED", "KNOTS_PRESERVED", "WEIGHTS_PRESERVED"],
}
CLAIM_TEXT = {
    "CLASS_PRESERVED": "The semantic class stays %s; it is not rewritten into another class.",
    "VERTEX_ORDER_PRESERVED": "Vertices keep identity and order.",
    "DEGREE_PRESERVED": "The degree is not elevated or reduced.",
    "CONTROL_POINTS_PRESERVED": "The control points are kept, not resampled.",
    "KNOTS_PRESERVED": "Knot values and multiplicities are kept, none collapsed or inserted.",
    "WEIGHTS_PRESERVED": "Weights are kept as stated, not renormalised.",
}


def exclusions_for(ents):
    out = []
    for e in ents:
        for p in em.required_exclusions(e):
            out.append({"entity": e["id"], "parameter": canon.scalar(p),
                        "reason": "POLYLINE_VERTEX" if e["class"] == "polyline" else "C0_KNOT"})
    return out


def build_fixture(path):
    raw = path.read_bytes()
    s = json.loads(raw)
    rel = str(path.relative_to(ROOT))
    extra = ""
    if s["kind"] == "transform":
        ent, asserts, extra = build_transform_fixture(s)
        ents = [ent]
        assertions = asserts
        asserts_by = [(ent["id"], a) for a in asserts]
    elif s["kind"] == "layers":
        ents, asserts_by = [], []
        for item in s["layers"]:
            rec = build_curve(dict(item["curve"], **{"class": "line"}))
            eid = "%s.%s" % (s["id"], item["name"].lower().replace("_", "-"))
            ents.append({"id": eid, **rec, "structure": "CURVE_ONLY",
                         "layer": {"name": item["name"], "on": item["on"], "frozen": item["frozen"]}})
            asserts_by.append((eid, ("STRUCTURAL", "LAYER_STATE_PRESERVED",
                                     "The entity stays on layer %s, which is %s and %s; it is neither dropped nor moved to another layer."
                                     % (item["name"], "on" if item["on"] else "off", "frozen" if item["frozen"] else "thawed"))))
    elif s["kind"] == "bulge_arc":
        poly = build_curve({"class": "polyline", "vertices": [s["p0"], s["p1"]], "bulges": [s["bulge"], "0"]})
        arc = bulge_equivalent_arc(s)
        arc_ent = {"id": s["id"] + "-equivalent-arc", **arc, "structure": "CURVE_ONLY"}
        if mpf(s["bulge"]) < 0:
            arc_ent["orientation"] = {"parameter_direction": "REVERSED_AGAINST_SOURCE", "sense_about_normal": "CW"}
        ents = [{"id": s["id"], **poly, "structure": "CURVE_ONLY"}, arc_ent]
        asserts_by = [(s["id"], ("STRUCTURAL", "VERTEX_ORDER_PRESERVED", "Two vertices with bulge %s kept as a bulge segment, not split or flattened." % s["bulge"])),
                      (s["id"] + "-equivalent-arc", ("GEOMETRIC", "WORLD_SPACE_RESULT", "The arc the bulge describes: neither a quarter nor a half circle."))]
    else:
        rec = build_curve(dict(s, **{"class": s["kind"]}))
        ents = [{"id": s["id"], **rec, "structure": "CURVE_ONLY"}]
        asserts_by = [(s["id"], ("STRUCTURAL", c, CLAIM_TEXT[c] % s["kind"] if c == "CLASS_PRESERVED" else CLAIM_TEXT[c])) for c in STRUCT_CLAIMS[s["kind"]]]
        asserts_by.append((s["id"], ("GEOMETRIC", "PARAMETERIZATION_PRESERVED", "The parameter domain is kept; a reparameterised equivalent counts as geometric only.")))
        cl = rec["closure"]
        if s["kind"] in ("bspline", "nurbs") and (cl["closed_by_endpoint"] or cl["closed_by_knots"]):
            asserts_by.append((s["id"], ("STRUCTURAL", "CLOSURE_KIND_PRESERVED", "Closed by %s, not by %s." % (
                ("endpoint coincidence", "knot periodicity") if cl["closed_by_endpoint"] else ("knot periodicity", "endpoint coincidence")))))
    if s["kind"] == "transform":
        asserts_by = [(ent["id"], a) for a in asserts]
    doc = {
        "schema_version": "pvec-gold/expected.math/1",
        "fixture_id": s["id"],
        "evidence_class": "KNOWN_TRUTH_EXACT",
        "units": {"name": "metre", "canonical": "metre", "scale_to_canonical": S("1")},
        "provenance": {"derivation": "AUTHORING_PARAMETERS", "authoring_script": SCRIPT, "parameter_file": rel,
                       "parameter_file_sha256": hashlib.sha256(raw).hexdigest(), "parameters": s},
        "entities": ents,
        "assertions": [{"id": "a%d" % (i + 1), "kind": k, "entity": eid, "claim": c, "statement": t} for i, (eid, (k, c, t)) in enumerate(asserts_by)],
    }
    ex = exclusions_for(ents)
    if ex:
        doc["derivative_exclusions"] = ex
    errs = em.validate_doc(json.loads(json.dumps(doc), parse_float=em._no_floats))
    if errs:
        raise SystemExit("%s does not validate:\n  %s" % (s["id"], "\n  ".join(errs)))
    readme = readme_for(s, rel, extra)
    return Path(s.get("group", "")) / s["id"], json.dumps(doc, indent=2) + "\n", readme


def readme_for(s, rel, extra):
    if "profile_only" in s:
        po = s["profile_only"]
        return ("# %s\n\n%s\n\n"
                "I authored this record from `%s`, and `expected.math.json` is derived from those parameters alone by `%s`. "
                "No expected value comes from `primary.step` or `secondary.step`, and none ever should.\n\n"
                "This is a profile only probe and it has no `source.dwg`. %s\n\n"
                "The drawing for the same map is `%s` under `fixtures/edge`. It keeps this record's matrix as its chain matrix, "
                "so the two stay comparable, and it is the probe that exercises `affine_transform` through a DWG.\n%s"
                % (s["id"], s["description"], rel, SCRIPT, po["reason"], po["chain_probe"], extra))
    return ("# %s\n\n%s\n\n"
            "I authored this probe from `%s`, and `expected.math.json` is derived from those parameters alone by "
            "`%s`. No expected value comes from `primary.step` or `secondary.step`, and none ever should.\n\n"
            "`source.dwg` isn't here yet. It gets written from the same parameters by the open writer named in the corpus manifest, "
            "so this directory has the record without the drawing.\n%s"
            % (s["id"], s["description"], rel, SCRIPT, extra))


def all_fixtures():
    for p in sorted(PARAMS.rglob("*.json")):
        yield build_fixture(p)


def main(argv):
    check = "--check" in argv
    bad = 0
    for rel, expected, readme in all_fixtures():
        d = OUT / rel
        for name, text in (("expected.math.json", expected), ("README.md", readme)):
            f = d / name
            if check:
                if not f.exists() or f.read_text() != text:
                    print("stale: %s" % f)
                    bad += 1
            else:
                d.mkdir(parents=True, exist_ok=True)
                f.write_text(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
