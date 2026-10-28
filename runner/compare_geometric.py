"""The geometric-equivalence report: does the signature trace the same geometry as the known truth?

    python3 -m runner.compare_geometric EXPECTED.math.json SIGNATURE.json OUT.json

This is the other half of panel finding 4. A curve with other parameters can be the same geometry, and
that is measured here instead of assumed: endpoints, the maximum deviation between the two curves
(adaptive sampling, refined until the estimate is stable by the numeric policy's own criterion, in both
directions), the bounding box, arc length, and unit tangent and curvature at the signature's samples.

Every number carries its unit, the parameter at which it occurred (a unit parameter in [0, 1] on the
curve that was sampled) and the tolerance that admitted it, which is the numeric policy's NP-04 triple
and nothing this module chose. The two places where a measurement has its own error (arc length by
polygon extrapolation, curvature by finite differences) record that error next to the tolerance and
admit a value only within the sum.

Derivatives are not compared at a C0 knot, at a polyline vertex, or within the finite-difference stencil
of a knot that is not smooth enough for the order asked. Each such parameter is listed by name per
entity, never skipped as a blanket. The class is GEOMETRIC_EXACT_REPARAMETERIZED when everything is
admitted and BOUNDED_APPROXIMATION, with the measured bound, otherwise. Neither word says anything
about structural exactness or about how a drawing looks.
"""
import argparse
import json
import math
import platform
import sys
from pathlib import Path

from . import canon, curves, expected_math as em, normalize, numeric
from .compare_structural import ReportRefused, bare, expected_view, pair, scale_of
from .qualify_probes import GEOMETRIC, BOUNDED, SAMPLES, Placed, core, deviation, matrix_floats, refine_maximum

SCHEMA_VERSION = "pvec-gold/geometric-report/1"
UNSUPPORTED, MISSING = "UNSUPPORTED", "MISSING"
H = 1.0 / 1024            # unit-parameter step of the finite-difference stencils; their own error is measured and recorded
ARC_N = 2048
CLOSED_FORM_CURVATURE = ("line", "circle", "circular_arc")


def placed(rec, local=False):
    return Placed(core(rec), None if local else matrix_floats(rec["transform"]))


def q(name, dev, unit, at, tol, **extra):
    d = {"quantity": name, "deviation": float(dev), "unit": unit, "at_unit_parameter": float(at), "tolerance": float(tol),
         "admitted": bool(dev <= tol)}
    d.update(extra)
    return d


def polygon_length(p, n):
    pts = [p.at(i / n) for i in range(n + 1)]
    return sum(curves.dist(a, b) for a, b in zip(pts, pts[1:]))


def arc_length(p):
    """Polygon length at n and 2n, extrapolated; the gap between the two bounds the estimate's own error."""
    l1, l2 = polygon_length(p, ARC_N), polygon_length(p, 2 * ARC_N)
    return l2 + (l2 - l1) / 3.0, abs(l2 - l1)


def extent(p):
    """(min, max) per axis with the parameter of each extreme, refined around the best sample."""
    pts = p.samples()
    out = []
    for a in range(3):
        lo_i = min(range(len(pts)), key=lambda i: pts[i][a])
        hi_i = max(range(len(pts)), key=lambda i: pts[i][a])
        hi, hu = refine_maximum(lambda u: p.at(u)[a], hi_i / SAMPLES, 1.0 / SAMPLES)
        lo, lu = refine_maximum(lambda u: -p.at(u)[a], lo_i / SAMPLES, 1.0 / SAMPLES)
        out.append(((-lo, lu), (hi, hu)))
    return out


def union_extent(ps):
    es = [extent(p) for p in ps]
    return [(min((e[a][0] for e in es), key=lambda x: x[0]), max((e[a][1] for e in es), key=lambda x: x[0])) for a in range(3)]


def bounds_quantity(want, got, tol_for):
    worst, at = 0.0, 0.0
    for a in range(3):
        for side in (0, 1):
            d = abs(want[a][side][0] - got[a][side][0])
            if d >= worst:
                worst, at = d, want[a][side][1]
    mag = max(abs(w[s][0]) for w in want for s in (0, 1))
    return q("bounds", worst, "metre", at, tol_for(mag))


# ---- derivatives -----------------------------------------------------------------------------------------

def derivative_exclusions(v):
    """The parameters at which a derivative is not compared for the expected entity, named with the reason."""
    g, out = v["geometry"], []
    if v["class"] in ("bspline", "nurbs"):
        p = g["degree"]
        for kn in g["knots"][1:-1]:
            if kn["multiplicity"] >= p:
                out.append({"parameter": kn["value"], "reason": "C0 knot: multiplicity %d is at least the degree %d (NP-14)" % (kn["multiplicity"], p)})
    elif v["class"] == "polyline":
        for i in range(1, len(g["vertices"]) - 1):
            out.append({"parameter": normalize.stored(float(i)), "reason": "C0 join at polyline vertex %d" % i})
    return out


def rough_points(v, order):
    """Unit parameters near which the curve is not C^order: knots with p - m < order, polyline vertices."""
    d0, d1 = (canon.check_scalar(v["parameter_domain"][k]) for k in ("start", "end"))
    span = d1 - d0
    pts = []
    if v["class"] in ("bspline", "nurbs"):
        p = v["geometry"]["degree"]
        pts = [(canon.check_scalar(k["value"]) - d0) / span for k in v["geometry"]["knots"][1:-1] if p - k["multiplicity"] < order]
    elif v["class"] == "polyline":
        pts = [(i - d0) / span for i in range(1, len(v["geometry"]["vertices"]) - 1)]
    return pts


def tangent(p, u, h=H):
    a, b, c, d = (p.at(u + o * h) for o in (-2, -1, 1, 2))
    r = [(-w + 8 * x - 8 * y + z) / (12 * h) for w, x, y, z in zip(d, c, b, a)]
    n = curves._norm(r)
    return [x / n for x in r]


def curvature(p, u, h):
    pts = [p.at(u + o * h) for o in (-2, -1, 0, 1, 2)]
    d1 = [(-pts[4][i] + 8 * pts[3][i] - 8 * pts[1][i] + pts[0][i]) / (12 * h) for i in range(3)]
    d2 = [(-pts[4][i] + 16 * pts[3][i] - 30 * pts[2][i] + 16 * pts[1][i] - pts[0][i]) / (12 * h * h) for i in range(3)]
    return curves._norm(curves._cross(d1, d2)) / curves._norm(d1) ** 3


def nearest_unit(p, point):
    pts = p.samples()
    i = min(range(len(pts)), key=lambda k: curves.dist(pts[k], point))
    a, b = max(i - 1, 0) / SAMPLES, min(i + 1, SAMPLES) / SAMPLES
    gold = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = b - gold * (b - a), a + gold * (b - a)
    fc, fd = curves.dist(p.at(c), point), curves.dist(p.at(d), point)
    for _ in range(80):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - gold * (b - a)
            fc = curves.dist(p.at(c), point)
        else:
            a, c, fc = c, d, fd
            d = a + gold * (b - a)
            fd = curves.dist(p.at(d), point)
    return (a + b) / 2


def derivative_quantities(pol, v, local, produced, flip):
    """Tangent and curvature at the signature's samples. Returns (quantities, excluded samples)."""
    qs, excluded = [], []
    for s in produced.get("samples", []):
        par = s["parameter"]
        if s.get("derivative_exclusion"):
            excluded.append({"parameter": par, "reason": "the signature excludes this sample: %s" % s["derivative_exclusion"]})
            continue
        u = nearest_unit(local, [canon.check_scalar(c) for c in s["point"]])
        for name, order, value in (("tangent", 1, s.get("tangent")), ("curvature", 2, s.get("curvature"))):
            if value is None:
                continue
            near = [k for k in rough_points(v, order) if abs(k - u) <= 2 * H]
            if u < 2 * H or u > 1 - 2 * H or near:
                why = "inside the stencil of a domain end" if not near else "inside the stencil of a knot or vertex that is not C%d" % order
                excluded.append({"parameter": par, "reason": "%s not compared: %s" % (name, why)})
                continue
            if name == "tangent":
                t, t2 = tangent(local, u), tangent(local, u, 2 * H)
                got = [canon.check_scalar(c) for c in value]
                if flip:
                    t = [-x for x in t]
                dev = curves.dist(t, got)
                err = curves.dist(t, [-x for x in t2] if flip else t2)
                qs.append(q("tangent", dev, "dimensionless (unit vector)", u, pol.tol(1.0, 1.0), estimator_error=err))
            else:
                if v["class"] == "line":
                    k0, err = 0.0, 0.0
                elif v["class"] in ("circle", "circular_arc"):
                    k0, err = 1.0 / canon.check_scalar(v["geometry"]["radius"]), 0.0
                else:
                    k0 = curvature(local, u, H)
                    err = abs(k0 - curvature(local, u, 2 * H))
                got = canon.check_scalar(value)
                tol = pol.tol(max(abs(k0), 1.0), max(abs(k0), abs(got), 1.0))
                dev = abs(k0 - got)
                qs.append(q("curvature", dev, "1/metre", u, tol + err, estimator_error=err))
    return qs, excluded


# ---- entities --------------------------------------------------------------------------------------------

def compare_pair(pol, ent_id, v, produced, j):
    base = {"entity": ent_id, "matched": True, "signature_index": j, "derivative_exclusions": derivative_exclusions(v)}
    try:
        pe, ps = placed(v), placed(produced)
    except curves.CurveError as e:
        return dict(base, equivalent=False, quantities=[], error=str(e), samples_excluded=[], curvature={"compared": False}), [], []
    want = core(v)
    scale = numeric.feature_scale(want)
    mag = max(abs(c) for p in pe.samples() + ps.samples() for c in p)
    tol = pol.tol(scale, mag)
    s0, s1, a0, a1 = pe.at(0.0), pe.at(1.0), ps.at(0.0), ps.at(1.0)
    fwd = max(curves.dist(s0, a0), curves.dist(s1, a1))
    rev = max(curves.dist(s0, a1), curves.dist(s1, a0))
    reversed_ = rev < fwd
    b0, b1 = (a1, a0) if reversed_ else (a0, a1)
    qs = [q("endpoint_start", curves.dist(s0, b0), "metre", 0.0, tol), q("endpoint_end", curves.dist(s1, b1), "metre", 1.0, tol)]
    d1, at1, st1, l1 = deviation(pol, pe, [ps], scale)
    d2, at2, st2, l2 = deviation(pol, ps, [pe], scale)
    (dev, at, stable, lvl), side = ((d1, at1, st1, l1), "EXPECTED_TO_PRODUCED") if d1 >= d2 else ((d2, at2, st2, l2), "PRODUCED_TO_EXPECTED")
    qs.append(q("curve_deviation", dev, "metre", at, tol, converged=stable, refinement_level=lvl,
                sample_count=2 + 8 * 2 ** (lvl - 1), measured_in=side))
    le, ee = arc_length(pe)
    lp, ep = arc_length(ps)
    qs.append(q("arc_length", abs(le - lp), "metre", 1.0, pol.tol(max(le, lp), max(le, lp)) + ee + ep, estimator_error=ee + ep))
    dq, excluded = derivative_quantities(pol, v, placed(v, True), produced, reversed_)
    qs += dq
    base.update(equivalent=all(x["admitted"] for x in qs), direction="REVERSED" if reversed_ else "SAME", quantities=qs,
                samples_excluded=excluded,
                curvature={"compared": any(x["quantity"] == "curvature" for x in qs),
                           "excluded_parameters": [e["parameter"] for e in base["derivative_exclusions"]]})
    return base, [pe], [ps]


def compare(pol, expected_doc, sig):
    if expected_doc is None:
        raise ReportRefused("no expected.math.json for this fixture: a geometric report compares a signature to known truth, "
                            "and I will not compare two converters to each other under that name")
    k = scale_of(expected_doc)
    ents = [e for e in expected_doc["entities"] if "rejection" not in e]
    return compare_views(pol, expected_doc["fixture_id"], [e["id"] for e in ents], [bare(expected_view(e, k)) for e in ents], sig)


def compare_views(pol, fixture_id, ids, views, sig):
    """The comparison proper, on entities written the way a signature writes them (the expected record, or the
    primary signature when two converters are compared with no known truth)."""
    produced = [bare(e) for e in sig["entities"]]
    idx = pair(views, produced)
    rows, pes, pss, fixture_q = [], [], [], []
    for eid, v, j in zip(ids, views, idx):
        if j is None:
            rows.append({"entity": eid, "matched": False, "signature_index": None, "equivalent": False, "quantities": [],
                         "derivative_exclusions": derivative_exclusions(v), "samples_excluded": [], "curvature": {"compared": False}})
            continue
        row, a, b = compare_pair(pol, eid, v, produced[j], j)
        rows.append(row)
        pes += a
        pss += b
    left = [j for j in range(len(produced)) if j not in idx]
    if pes and pss:
        scale = max(numeric.feature_scale(core(v)) for v in views)
        mag = max(abs(c) for p in pes + pss for pt in p.samples() for c in pt)
        tol = pol.tol(scale, mag)
        fixture_q.append(bounds_quantity(union_extent(pes), union_extent(pss), lambda m: pol.tol(scale, m)))
        if left or any(not r["matched"] for r in rows):   # counts differ: the sets are compared as sets
            pl = [placed(produced[j]) for j in range(len(produced))]
            pe_all = [placed(v) for v in views]
            ex = [deviation(pol, p, pl, scale) for p in pe_all] + [deviation(pol, p, pe_all, scale) for p in pl]
            dev, at, stable, lvl = max(ex, key=lambda x: x[0])
            fixture_q.append(q("union_curve_deviation", dev, "metre", at, tol, converged=stable, refinement_level=lvl,
                               sample_count=2 + 8 * 2 ** (lvl - 1)))
    allq = [x for r in rows for x in r["quantities"]] + fixture_q
    if not produced:
        klass = MISSING
    elif any(r.get("error") for r in rows):
        klass = UNSUPPORTED
    elif allq and all(x["admitted"] for x in allq) and (all(r["matched"] for r in rows) or any(x["quantity"] == "union_curve_deviation" for x in fixture_q)) and not (left and not fixture_q):
        klass = GEOMETRIC
    else:
        klass = BOUNDED
    rep = {"schema_version": SCHEMA_VERSION, "fixture_id": fixture_id, "numeric_policy_version": pol.version,
           "signature_schema_version": sig["schema_version"], "stage": {"name": "compare_geometric", "architecture": platform.machine()},
           "class": klass, "unmatched_produced": left, "entities": rows, "fixture_quantities": fixture_q}
    if klass == BOUNDED:
        rep["bound"] = max([x["deviation"] for x in allq] or [0.0])
    return rep


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("expected")
    ap.add_argument("signature")
    ap.add_argument("out")
    a = ap.parse_args(argv)
    pol = numeric.load_policy()
    exp = em.load(a.expected) if Path(a.expected).exists() else None
    try:
        rep = compare(pol, exp, json.loads(Path(a.signature).read_text()))
    except ReportRefused as e:
        print("REFUSED " + str(e))
        return 2
    Path(a.out).write_text(normalize.dumps(rep))
    print("%s %s" % (rep["fixture_id"], rep["class"]))
    return 0 if rep["class"] == GEOMETRIC else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
