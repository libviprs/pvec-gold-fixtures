"""Validate an expected.math.json: schema first, then the relations a schema cannot state.

No tolerance lives here. Everything below is either exact rational arithmetic on the stated
f64 values or a bit comparison. Comparison against converter output is a different job and takes
its numbers from the vendored policy (docs/numeric-policy.md).

    python3 -m runner.expected_math fixtures/**/expected.math.json
"""
import json
import sys
from fractions import Fraction
from pathlib import Path

from jsonschema import Draft202012Validator

from . import canon

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "expected.math.schema.json"


class ExpectedMathError(ValueError):
    pass


def _no_floats(tok):
    raise ExpectedMathError("bare JSON number %s: use a canonical scalar (integers only for counts)" % tok)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_float=_no_floats, parse_constant=_no_floats)


def _walk_scalars(node, where, out):
    if isinstance(node, dict):
        if "decimal" in node and "f64_hex" in node:
            out.append((where, node))
            return
        for k, v in node.items():
            _walk_scalars(v, "%s.%s" % (where, k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_scalars(v, "%s[%d]" % (where, i), out)


def _fr(s):
    return canon.exact(s)


def det4(m):
    """Exact determinant of a row-major 4x4 of Fractions (Laplace on the first row)."""
    def det3(a):
        return (a[0] * (a[4] * a[8] - a[5] * a[7])
                - a[1] * (a[3] * a[8] - a[5] * a[6])
                + a[2] * (a[3] * a[7] - a[4] * a[6]))
    total = Fraction(0)
    for c in range(4):
        minor = [m[r * 4 + k] for r in range(1, 4) for k in range(4) if k != c]
        total += (-1) ** c * m[c] * det3(minor)
    return total


def matmul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _check_transform(t, where, errs):
    m = [_fr(s) for s in t["matrix"]]
    if m[12:16] != [0, 0, 0, 1]:
        errs.append("%s: bottom row must be 0 0 0 1 (affine)" % where)
    d = det4(m)
    stated = canon.check_scalar(t["determinant"], where + ".determinant")
    if canon.f64_to_hex(float(d)) != canon.f64_to_hex(stated):
        errs.append("%s: determinant is not the exact determinant of the matrix rounded to f64 (exact %s)" % (where, float(d)))
    cls = t["classification"]
    if cls == "SINGULAR" and d != 0:
        errs.append("%s: classified SINGULAR but the exact determinant is not zero" % where)
    if cls != "SINGULAR" and d == 0:
        errs.append("%s: exact determinant is zero, so the classification must be SINGULAR" % where)
    if cls == "REFLECTION" and d >= 0:
        errs.append("%s: REFLECTION needs a negative determinant" % where)
    if cls in ("IDENTITY", "TRANSLATION", "ROTATION", "UNIFORM_SCALE") and d <= 0:
        errs.append("%s: %s needs a positive determinant" % (where, cls))
    return m, d


def _check_curve(c, where, errs):
    cls, g = c["class"], c["geometry"]
    dom = c["parameter_domain"]
    s, e = _fr(dom["start"]), _fr(dom["end"])
    if not s < e:
        errs.append("%s: parameter_domain must have start < end" % where)
    cl = c["closure"]
    spline = cls in ("bspline", "nurbs")
    if spline and cl["closed_by_knots"] != cl["periodic"]:
        errs.append("%s: closed_by_knots and periodic must agree for a spline" % where)
    if not spline and cls not in ("circle", "ellipse") and (cl["closed_by_knots"] or cl["periodic"]):
        errs.append("%s: only splines, circles and ellipses may be periodic" % where)
    if cls in ("circle", "ellipse") and not cl["periodic"]:
        errs.append("%s: a full %s is periodic" % (where, cls))
    if cls == "line":
        if g["start"] == g["end"]:
            errs.append("%s: zero-length line" % where)
    elif cls == "polyline":
        if len(g["bulges"]) != len(g["vertices"]):
            errs.append("%s: bulges must have one entry per vertex" % where)
    elif cls in ("circle", "circular_arc"):
        if _fr(g["radius"]) <= 0:
            errs.append("%s: radius must be positive" % where)
    elif cls in ("ellipse", "elliptical_arc"):
        a, b = _fr(g["semi_major"]), _fr(g["semi_minor"])
        if not (a >= b > 0):
            errs.append("%s: need semi_major >= semi_minor > 0" % where)
    elif cls == "bezier":
        if len(g["control_points"]) != g["degree"] + 1:
            errs.append("%s: a Bezier of degree p has p+1 control points" % where)
    elif spline:
        n, p = len(g["control_points"]), g["degree"]
        ks = g["knots"]
        vals = [_fr(k["value"]) for k in ks]
        if any(not (vals[i] < vals[i + 1]) for i in range(len(vals) - 1)):
            errs.append("%s: distinct knot values must be strictly increasing" % where)
        mults = [k["multiplicity"] for k in ks]
        total = sum(mults)
        if cl["periodic"]:
            if total != n + 1:
                errs.append("%s: periodic relation is sum(multiplicities) == control_points + 1, got %d vs %d" % (where, total, n + 1))
            if mults[0] != mults[-1]:
                errs.append("%s: periodic knot vector needs equal first and last multiplicity" % where)
            if any(m > p for m in mults):
                errs.append("%s: periodic multiplicity exceeds degree" % where)
            if n < p:
                errs.append("%s: periodic spline needs control_points >= degree" % where)
        else:
            if total != n + p + 1:
                errs.append("%s: sum(multiplicities) %d != control_points + degree + 1 = %d" % (where, total, n + p + 1))
            if any(m > p + 1 for m in (mults[0], mults[-1])) or any(m > p for m in mults[1:-1]):
                errs.append("%s: a knot multiplicity is too large" % where)
            if n < p + 1:
                errs.append("%s: need control_points >= degree + 1" % where)
            else:
                expanded = [v for v, m in zip(vals, mults) for _ in range(m)]
                if len(expanded) == n + p + 1 and not (s >= expanded[p] and e <= expanded[n]):
                    errs.append("%s: parameter_domain lies outside the valid knot span" % where)
        if cl["closed_by_endpoint"] and g["control_points"][0] != g["control_points"][-1]:
            errs.append("%s: closed_by_endpoint needs identical first and last control points" % where)
        if cls == "nurbs":
            w = [_fr(x) for x in g["weights"]]
            if len(w) != n:
                errs.append("%s: weights length %d != control points %d" % (where, len(w), n))
            if any(x <= 0 for x in w):
                errs.append("%s: weights must be positive" % where)
            if g["weights_all_unit"] != all(x == 1 for x in w):
                errs.append("%s: weights_all_unit does not match the weights" % where)


def required_exclusions(ent):
    """Parameters (f64) at which a fixture's own geometry has a C0 join, so derivatives must not be
    compared there. Derived from the stated knots and vertices only, no tolerance involved."""
    g, cls = ent["geometry"], ent["class"]
    if cls in ("bspline", "nurbs"):
        p = g["degree"]
        ks = g["knots"]
        span = ks if ent["closure"]["periodic"] else ks[1:-1]
        return [canon.check_scalar(k["value"]) for k in span if k["multiplicity"] >= p]
    if cls == "polyline":
        # open: interior vertices; closed: every vertex of the unrolled domain except its two ends
        last = len(g["vertices"]) if ent["closure"]["closed_by_endpoint"] else len(g["vertices"]) - 1
        return [float(i) for i in range(1, last)]
    return []


def semantic_check(doc):
    errs = []
    scalars = []
    _walk_scalars(doc, "$", scalars)
    for where, s in scalars:
        try:
            canon.check_scalar(s, where)
        except canon.CanonError as e:
            errs.append(str(e))
    if errs:
        return errs  # nothing below is meaningful with unreadable scalars
    if _fr(doc["units"]["scale_to_canonical"]) <= 0:
        errs.append("units.scale_to_canonical must be positive")
    ids = [e["id"] for e in doc["entities"]]
    if len(set(ids)) != len(ids):
        errs.append("duplicate entity id")
    for ent in doc["entities"]:
        w = "entities[%s]" % ent["id"]
        _check_curve(ent, w, errs)
        if "world" in ent:
            _check_curve(ent["world"], w + ".world", errs)
        tfs = []
        if "transform" in ent:
            tfs.append(("transform", ent["transform"]))
        chain = ent.get("transform_chain")
        if chain:
            for i, t in enumerate(chain["transforms"]):
                tfs.append(("transform_chain.transforms[%d]" % i, t))
            tfs.append(("transform_chain.composed", chain["composed"]))
        if "transform" in ent and chain:
            errs.append("%s: give transform or transform_chain, not both" % w)
        mats = {}
        for name, t in tfs:
            mats[name] = _check_transform(t, "%s.%s" % (w, name), errs)
        if chain:
            prod = mats["transform_chain.transforms[0]"][0]
            for i in range(1, len(chain["transforms"])):
                prod = matmul(prod, mats["transform_chain.transforms[%d]" % i][0])
            comp = mats["transform_chain.composed"][0]
            if [canon.f64_to_hex(float(x)) for x in prod] != [canon.f64_to_hex(float(x)) for x in comp]:
                errs.append("%s: composed is not the exact product T0*T1*...*Tn (parent left) rounded to f64" % w)
        has_t = bool(tfs)
        if ent["structure"] == "CURVE_ONLY" and has_t:
            errs.append("%s: CURVE_ONLY entity carries a transform" % w)
        if ent["structure"] != "CURVE_ONLY" and not has_t:
            errs.append("%s: %s needs a transform" % (w, ent["structure"]))
        top = chain["composed"] if chain else ent.get("transform")
        top_cls = top["classification"] if top else None
        rej = ent.get("rejection")
        if has_t:
            if rej and "world" in ent:
                errs.append("%s: a rejection carries no expected curve" % w)
            if not rej and "world" not in ent:
                errs.append("%s: transformed entity needs a world result or a rejection" % w)
        elif rej or "world" in ent:
            errs.append("%s: world/rejection only make sense with a transform" % w)
        if top_cls in ("SINGULAR", "NEAR_SINGULAR"):
            want = "SINGULAR_TRANSFORM" if top_cls == "SINGULAR" else "NEAR_SINGULAR_TRANSFORM"
            if not rej or rej["classification"] != want:
                errs.append("%s: a %s transform must carry rejection.classification %s" % (w, top_cls, want))
        elif rej and rej["classification"] in ("SINGULAR_TRANSFORM", "NEAR_SINGULAR_TRANSFORM"):
            errs.append("%s: singular rejection on a non-singular transform" % w)
        if top_cls == "REFLECTION" and "orientation" not in ent:
            errs.append("%s: a reflection must record orientation" % w)
        if top_cls == "NON_UNIFORM_SCALE" and ent["class"] == "circle" and ent.get("world", {}).get("class") != "ellipse":
            errs.append("%s: a circle under non-uniform scale must be expected as an ellipse" % w)
    listed = set()
    for x in doc.get("derivative_exclusions", []):
        if x["entity"] not in ids:
            errs.append("derivative_exclusions names unknown entity %s" % x["entity"])
        listed.add((x["entity"], x["parameter"]["f64_hex"]))
    for ent in doc["entities"]:
        for p in required_exclusions(ent):
            if (ent["id"], canon.f64_to_hex(p)) not in listed:
                errs.append("entity %s has a C0 join at parameter %r that derivative_exclusions does not list" % (ent["id"], p))
    seen = set()
    for a in doc["assertions"]:
        if a["id"] in seen:
            errs.append("duplicate assertion id %s" % a["id"])
        seen.add(a["id"])
        if a["entity"] not in ids:
            errs.append("assertion %s names unknown entity %s" % (a["id"], a["entity"]))
    return errs


def validate_doc(doc):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = [("schema: %s: %s" % ("/".join(str(p) for p in e.absolute_path), e.message))
            for e in Draft202012Validator(schema).iter_errors(doc)]
    if errs:
        return errs
    return semantic_check(doc)


def validate_file(path):
    try:
        doc = load(path)
    except (ExpectedMathError, json.JSONDecodeError) as e:
        return [str(e)]
    return validate_doc(doc)


def main(argv):
    bad = 0
    for p in argv:
        errs = validate_file(p)
        if errs:
            bad += 1
            print("FAIL %s" % p)
            for e in errs:
                print("  - %s" % e)
        else:
            print("ok   %s" % p)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
