"""Comparison helpers that take every threshold from the vendored policy file.

The numeric policy is defined once, by P1.2 in libviprs/pvec#1. This repository adopts a version
of it (policy/pvec-numeric-policy.<version>.json, copied verbatim) and decides only which
comparisons to run. There is no default policy: no file, or a file with no version id, is an error.

Assumed shape of the vendored file, which is the one place to adapt when P1.2's real field names
land (see docs/numeric-policy.md):

    policy_version      non-empty string, required
    tolerance.absolute  number
    tolerance.relative  number
    tolerance.ulp       integer
    scale_term          name of the scale the relative term multiplies
    adaptive.stable_relative_change, adaptive.max_levels
"""
import glob
import json
import math
import struct
import sys
from fractions import Fraction
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"


class PolicyError(RuntimeError):
    pass


class Policy:
    def __init__(self, data, path):
        self.path = str(path)
        self.version = data["policy_version"]
        t = data["tolerance"]
        self._abs, self._rel, self._ulp = t["absolute"], t["relative"], int(t["ulp"])
        self.scale_term = data["scale_term"]
        a = data["adaptive"]
        self._stable, self._levels = a["stable_relative_change"], int(a["max_levels"])

    def close(self, a, b, scale):
        """True when a and b agree under the scale-aware triple: ULP distance, absolute, or relative*scale."""
        if a == b:
            return True
        if ulp_distance(a, b) <= self._ulp:
            return True
        d = abs(a - b)
        return d <= self._abs or d <= self._rel * abs(scale)

    def adaptive_max_deviation(self, f, g, lo, hi, dist):
        """Max of dist(f(t), g(t)) over [lo, hi], refining the sampling until the estimate is
        stable by the policy's own criterion (relative change between levels), or failing loudly
        if it never is. Returns (deviation, parameter_of_max, levels_used)."""
        n, prev = 8, None
        for level in range(1, self._levels + 1):
            best, at = -1.0, lo
            for i in range(n + 1):
                t = lo + (hi - lo) * i / n
                d = dist(f(t), g(t))
                if d > best:
                    best, at = d, t
            if prev is not None:
                change = abs(best - prev) / max(abs(best), abs(prev), sys.float_info.min) if best or prev else 0.0
                if change <= self._stable:
                    return best, at, level
            prev, n = best, n * 2
        raise PolicyError("deviation estimate did not stabilise within the policy's refinement limit")


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


def _ordered(x):
    """Map a finite double to an integer that is monotone in the double's value."""
    (i,) = struct.unpack(">q", struct.pack(">d", x))
    return i if i >= 0 else -(i & 0x7FFFFFFFFFFFFFFF)


def ulp_distance(a, b):
    if not (math.isfinite(a) and math.isfinite(b)):
        raise ValueError("non-finite value in comparison")
    return abs(_ordered(a) - _ordered(b))


def to_canonical(value, scale_to_canonical):
    """Exact units normalisation: value * scale in rational arithmetic, rounded once to f64."""
    return float(Fraction(value) * Fraction(scale_to_canonical))


def to_unit_parameter(t, domain):
    """Map t in [start, end] to [0, 1], so two parameterisations can be sampled at the same points."""
    s, e = domain
    return float((Fraction(t) - Fraction(s)) / (Fraction(e) - Fraction(s)))


def from_unit_parameter(u, domain):
    s, e = domain
    return float(Fraction(s) + Fraction(u) * (Fraction(e) - Fraction(s)))


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
    """Interior knot values at which a spline is only C0 (multiplicity >= degree). knots: [(value, multiplicity)]."""
    return [v for (v, m) in knots[1:-1] if m >= degree]


def _scale_for(self, values):
    """The scale the relative term multiplies, as the policy names it."""
    if self.scale_term == "max_abs_coordinate_of_fixture":
        return max((abs(v) for v in values), default=0.0)
    raise PolicyError("scale term %r is not implemented here" % (self.scale_term,))


Policy.scale_for = _scale_for
