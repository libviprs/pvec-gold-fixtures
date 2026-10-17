"""An independent evaluator for the curve records in expected.math.json and *.verification.json.

Plain Python floats, no Open CASCADE. It exists so classification (runner/qualify_probes.py) can
evaluate both an expected record and a converter's normalised record by one implementation that
shares nothing with the OCCT-based step_eval. It has no tolerance.

Conventions: a record's own parameter_domain is its native parameter. `unit(u)` maps u in [0, 1]
onto that domain. A periodic spline follows docs/fixtures/expected-math.md: the unique poles wrap,
and the pole that is active first at the start of the domain is pole 0.
"""
import math

from . import canon


def _v(p):
    return [canon.check_scalar(c) for c in p]


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _add(a, b):
    return [x + y for x, y in zip(a, b)]


def _mul(a, s):
    return [x * s for x in a]


def _norm(a):
    return math.sqrt(sum(x * x for x in a))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = _norm(a)
    return [x / n for x in a]


def dist(a, b):
    return _norm(_sub(a, b))


class CurveError(ValueError):
    pass


def _flat_knots(ks):
    return [canon.check_scalar(k["value"]) for k in ks for _ in range(k["multiplicity"])]


def _span(knots, p, n, t):
    """Index k with knots[k] <= t < knots[k+1], clamped to the last non-empty span; n = last pole index."""
    if t >= knots[n + 1]:
        return n
    lo, hi = p, n + 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if t < knots[mid]:
            hi = mid
        else:
            lo = mid
    return lo


def _deboor(p, knots, pts, t):
    n = len(pts) - 1
    k = _span(knots, p, n, t)
    d = [list(pts[j + k - p]) for j in range(p + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            den = knots[j + 1 + k - r] - knots[j + k - p]
            a = 0.0 if den == 0 else (t - knots[j + k - p]) / den
            d[j] = [(1.0 - a) * x + a * y for x, y in zip(d[j - 1], d[j])]
    return d[p]


class Curve:
    def __init__(self, rec):
        self.cls = rec["class"]
        self.g = rec["geometry"]
        dom = rec["parameter_domain"]
        self.d0, self.d1 = canon.check_scalar(dom["start"]), canon.check_scalar(dom["end"])
        self.closure = rec["closure"]
        c = self.cls
        if c == "line":
            self.a, self.b = _v(self.g["start"]), _v(self.g["end"])
        elif c == "polyline":
            self.vs = [_v(v) for v in self.g["vertices"]]
            self.bs = [canon.check_scalar(b) for b in self.g["bulges"]]
        elif c in ("circle", "circular_arc"):
            self.c0, self.n, self.x = _v(self.g["center"]), _unit(_v(self.g["normal"])), _unit(_v(self.g["x_axis"]))
            self.y = _cross(self.n, self.x)
            self.r = canon.check_scalar(self.g["radius"])
        elif c in ("ellipse", "elliptical_arc"):
            self.c0, self.n, self.x = _v(self.g["center"]), _unit(_v(self.g["normal"])), _unit(_v(self.g["major_axis"]))
            self.y = _cross(self.n, self.x)
            self.ra, self.rb = canon.check_scalar(self.g["semi_major"]), canon.check_scalar(self.g["semi_minor"])
        elif c == "bezier":
            self.ps = [_v(p) for p in self.g["control_points"]]
        elif c in ("bspline", "nurbs"):
            self._init_spline()
        else:
            raise CurveError("cannot evaluate class %r" % c)

    def _init_spline(self):
        g = self.g
        self.p = g["degree"]
        pts = [_v(q) for q in g["control_points"]]
        w = [canon.check_scalar(x) for x in g["weights"]] if self.cls == "nurbs" else [1.0] * len(pts)
        hom = [[x * wi for x in q] + [wi] for q, wi in zip(pts, w)]
        ks = g["knots"]
        if not self.closure["periodic"]:
            self.knots, self.hom = _flat_knots(ks), hom
            return
        n, p = len(pts), self.p
        if ks[0]["multiplicity"] != 1:
            raise CurveError("periodic splines with a repeated first knot are not evaluated here")
        flat = _flat_knots(ks)[:n]
        period = canon.check_scalar(ks[-1]["value"]) - flat[0]
        ext = [flat[j % n] + (j // n) * period for j in range(-p, n + p + 1)]
        self.knots = ext
        self.hom = [hom[i % n] for i in range(n + p)]
        self.period_shift = None

    def unit(self, u):
        return self.point(self.d0 + u * (self.d1 - self.d0))

    def point(self, t):
        c = self.cls
        if c == "line":
            u = (t - self.d0) / (self.d1 - self.d0)
            return [a + u * (b - a) for a, b in zip(self.a, self.b)]
        if c == "polyline":
            return self._polyline(t)
        if c in ("circle", "circular_arc"):
            return [o + self.r * (math.cos(t) * xa + math.sin(t) * ya) for o, xa, ya in zip(self.c0, self.x, self.y)]
        if c in ("ellipse", "elliptical_arc"):
            return [o + self.ra * math.cos(t) * xa + self.rb * math.sin(t) * ya for o, xa, ya in zip(self.c0, self.x, self.y)]
        if c == "bezier":
            u = (t - self.d0) / (self.d1 - self.d0)
            pts = [list(q) for q in self.ps]
            while len(pts) > 1:
                pts = [[(1 - u) * x + u * y for x, y in zip(pts[i], pts[i + 1])] for i in range(len(pts) - 1)]
            return pts[0]
        h = _deboor(self.p, self.knots, self.hom, t)
        return [x / h[3] for x in h[:3]]

    def _polyline(self, t):
        n = len(self.vs)
        i = min(max(int(math.floor(t)), 0), n - 2)
        u = t - i
        a, b, bulge = self.vs[i], self.vs[i + 1], self.bs[i]
        if bulge == 0.0:
            return [x + u * (y - x) for x, y in zip(a, b)]
        chord = dist(a, b)
        d = _sub(b, a)
        uv = [d[0] / chord, d[1] / chord]
        left = [-uv[1], uv[0]]
        off = chord * (1 - bulge * bulge) / (4 * bulge)
        cen = [(a[0] + b[0]) / 2 + left[0] * off, (a[1] + b[1]) / 2 + left[1] * off]
        r = chord * (1 + bulge * bulge) / (4 * abs(bulge))
        a0 = math.atan2(a[1] - cen[1], a[0] - cen[0])
        sweep = 4 * math.atan(bulge)
        ang = a0 + u * sweep
        return [cen[0] + r * math.cos(ang), cen[1] + r * math.sin(ang), a[2] + u * (b[2] - a[2])]


def apply_transform(m16, p):
    """Row-major 4x4 acting on column vectors, as in expected.math.json."""
    return [m16[r * 4] * p[0] + m16[r * 4 + 1] * p[1] + m16[r * 4 + 2] * p[2] + m16[r * 4 + 3] for r in range(3)]
