"""Comparison helpers that take every threshold from the vendored policy file.

The numeric policy is defined once, by P1.2 in libviprs/pvec#1 (docs/NUMERIC_POLICY.md in
libviprs/pvec). This repository adopts a version of it (policy/pvec-numeric-policy.<version>.json)
and decides only which comparisons to run. There is no default policy: no file, or a file with no
version id, is an error. Rule numbers (NP-nn) are the policy's own.
"""
import glob
import json
import math
from fractions import Fraction
from pathlib import Path

from . import canon

POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
GRID_SHIFT = 0.6180339887498949   # fractional part of the golden ratio: a sampling offset, not a tolerance
REQUIRED = ("ABS", "REL", "ULP", "WEIGHT_FLOOR", "AXIS_RATIO_MAX", "MAX_ABS_COORD")


class PolicyError(RuntimeError):
    pass


class UnstableEstimate(PolicyError):
    """The adaptive refinement hit its cap. The last estimate is kept so a caller can report it as such."""

    def __init__(self, best, at, levels):
        super().__init__("deviation estimate did not stabilise within %d refinements" % levels)
        self.best, self.at, self.levels = best, at, levels


class Policy:
    def __init__(self, data, path):
        self.path = str(path)
        self.version = data["policy_version"]
        c = data["constants"]
        missing = [k for k in REQUIRED if k not in c]
        if missing:
            raise KeyError("constants.%s" % missing[0])
        self.ABS, self.REL, self.ULP = c["ABS"], c["REL"], int(c["ULP"])
        self.WEIGHT_FLOOR, self.AXIS_RATIO_MAX, self.MAX_ABS_COORD = c["WEIGHT_FLOOR"], c["AXIS_RATIO_MAX"], c["MAX_ABS_COORD"]

    # NP-04: tol(scale, mag) = max(ABS, REL * |scale|, ULP * ulp(mag)), with ulp the gap to the next f64.
    def tol(self, scale, mag):
        return max(self.ABS, self.REL * abs(scale), self.ULP * math.ulp(mag))

    # NP-05: near(a, b, scale) is a == b or |a - b| <= tol(scale, max(|a|, |b|)).
    def near(self, a, b, scale):
        if not (math.isfinite(a) and math.isfinite(b)):
            return False
        return a == b or abs(a - b) <= self.tol(scale, max(abs(a), abs(b)))

    close = near

    # NP-06: a length between points of magnitude at most mag is degenerate when it is not finite
    # or len <= max(ABS, ULP * ulp(mag)). There is no relative term.
    def degenerate_length(self, length, mag):
        return (not math.isfinite(length)) or length <= max(self.ABS, self.ULP * math.ulp(mag))

    # NP-13: unit(t) = (t - lo) / (hi - lo), refused when the domain is no wider than its own tolerance.
    def unit_parameter(self, t, lo, hi):
        if not (hi - lo > self.tol(hi - lo, max(abs(lo), abs(hi)))):
            raise PolicyError("parameter domain is empty under the policy (NP-13)")
        return float((Fraction(t) - Fraction(lo)) / (Fraction(hi) - Fraction(lo)))

    def from_unit_parameter(self, u, lo, hi):
        if not (hi - lo > self.tol(hi - lo, max(abs(lo), abs(hi)))):
            raise PolicyError("parameter domain is empty under the policy (NP-13)")
        return float(Fraction(lo) + Fraction(u) * (Fraction(hi) - Fraction(lo)))

    # NP-16: a B-spline is C^(p - m) at a knot of multiplicity m, and the two-sided derivative of
    # order k exists there if and only if k <= p - m.
    def two_sided_derivative_exists(self, order, degree, multiplicity):
        return order <= degree - multiplicity

    def adaptive_max_deviation(self, f, g, lo, hi, dist, scale, max_levels=12):
        """Max of dist(f(t), g(t)) over [lo, hi], doubling the sampling until the estimate stops
        moving by more than the policy's own tolerance (NP-04 at the given scale). The criterion is
        the policy's, not a new number; max_levels is only an iteration count, and exceeding it is an
        error. Returns (deviation, parameter_of_max, levels_used)."""
        n, prev = 8, None
        for level in range(1, max_levels + 1):
            best, at = -1.0, lo
            # The ends are always sampled. The interior grid is nested (each level keeps the last one's
            # points) but shifted by an irrational offset, so it can't land on a curve's own vertices and
            # knots at every level, which a plain k/2^m grid does for a 32-gon or a dyadic knot vector.
            ts = [lo, hi] + [lo + (hi - lo) * ((i / n + GRID_SHIFT) % 1.0) for i in range(n)]
            for t in ts:
                d = dist(f(t), g(t))
                if d > best:
                    best, at = d, t
            if prev is not None and self.near(best, prev, scale):
                return best, at, level
            prev, n = best, n * 2
        raise UnstableEstimate(best, at, max_levels)


def load_policy(path=None, directory=None):
    if path is None:
        found = sorted(glob.glob(str(Path(directory or POLICY_DIR) / "pvec-numeric-policy.*.json")))
        if not found:
            raise PolicyError("no vendored policy file (policy/pvec-numeric-policy.<version>.json); refusing to guess one")
        if len(found) > 1:
            raise PolicyError("more than one vendored policy file: %s" % ", ".join(found))
        path = found[0]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PolicyError("cannot read policy %s: %s" % (path, e))
    v = data.get("policy_version") if isinstance(data, dict) else None
    if not isinstance(v, str) or not v.strip():
        raise PolicyError("policy %s has no policy_version; refusing to run" % path)
    try:
        return Policy(data, path)
    except (KeyError, TypeError, ValueError) as e:
        raise PolicyError("policy %s is missing %s" % (path, e))


def policy_stamp(pol):
    """The field every comparison.json, *.verification.json and corpus manifest carries."""
    return {"numeric_policy_version": pol.version}


def to_canonical(value, scale_to_canonical):
    """Exact units normalisation: value * scale in rational arithmetic, rounded once to f64."""
    return float(Fraction(value) * Fraction(scale_to_canonical))


class DerivativeExclusions:
    """Per-fixture, enumerated: {(entity_id, parameter): reason}. Never applied globally."""

    def __init__(self, entries=()):
        self._m = {}
        for e in entries:
            self._m[(e["entity"], float(e["parameter"]))] = e["reason"]

    def excluded(self, entity, t):
        return (entity, float(t)) in self._m

    def filter(self, entity, params):
        return [t for t in params if not self.excluded(entity, t)]

    def require_listed(self, entity, c0_parameters):
        """A fixture with a C0 join must list the excluded parameter; otherwise fail."""
        missing = [t for t in c0_parameters if not self.excluded(entity, t)]
        if missing:
            raise PolicyError("entity %s has C0 parameters %s that the fixture does not list as derivative exclusions" % (entity, missing))


def c0_parameters(knots, degree):
    """Interior knot values at which a spline is only C0 (full multiplicity, NP-14). knots: [(value, multiplicity)]."""
    return [v for (v, m) in knots[1:-1] if m >= degree]


# ---- the "scale term" of NP-04: the size of the feature being compared ------------------------

def _pt(p):
    return [canon.check_scalar(c) for c in p]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def feature_scale(entity):
    """NP-04 says the scale is the size of the feature being compared: a segment's length, an arc's
    radius. For an ellipse I use the semi-major axis, for a polyline its longest segment, and for a
    Bezier or spline the diagonal of its control points' bounding box. That last choice is mine, not
    the policy's."""
    c, g = entity["class"], entity["geometry"]
    if c == "line":
        return _dist(_pt(g["start"]), _pt(g["end"]))
    if c in ("circle", "circular_arc"):
        return canon.check_scalar(g["radius"])
    if c in ("ellipse", "elliptical_arc"):
        return canon.check_scalar(g["semi_major"])
    if c == "polyline":
        vs = [_pt(v) for v in g["vertices"]]
        return max(_dist(a, b) for a, b in zip(vs, vs[1:]))
    if c in ("bezier", "bspline", "nurbs"):
        ps = [_pt(p) for p in g["control_points"]]
        lo = [min(p[i] for p in ps) for i in range(3)]
        hi = [max(p[i] for p in ps) for i in range(3)]
        return _dist(lo, hi)
    raise PolicyError("no feature scale for class %r" % (c,))
