#!/usr/bin/env python3
"""Write fixtures/validator-selftest/*.expected.json from values I worked out by hand.

Nothing here reads step_eval output. Each case below carries the derivation in words, and the
numbers are exact rationals or well-known constants (sin/cos to 25+ digits) that I wrote down
before the evaluator ran. Rational values are rounded once to f64 by Fraction, which is correctly
rounded.
"""
import json
import sys
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runner import canon  # noqa: E402

OUT = ROOT / "fixtures" / "validator-selftest"


def s(x):
    return canon.scalar(x)


def p(*v):
    return [s(c) for c in v]


Z = "0"
CLOSE0 = {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}
CLOSE_FULL = {"closed_by_endpoint": True, "closed_by_knots": False, "periodic": True}
TWO_PI = "6.283185307179586"
S5 = "0.4472135954999579"   # 1/sqrt(5)
S5x2 = "0.8944271909999159"  # 2/sqrt(5)


def cp(param, point, tangent=None, curv=None):
    return {"parameter": s(param), "point": p(*point), "tangent": p(*tangent) if tangent else None, "curvature": s(curv) if curv is not None else None}


CASES = {
    "line": dict(
        derivation="LINE through (1,2,3) with unit direction (0.6, 0.8, 0) (0.36 + 0.64 = 1), trimmed to parameters 0..5. "
                   "P(t) = (1 + 0.6t, 2 + 0.8t, 3), so the ends are (1,2,3) and (4,6,3), the midpoint t=2.5 is (2.5,4,3), "
                   "the tangent is the direction itself, and a line has curvature 0.",
        entity=dict(**{"class": "line"}, geometry={"start": p(1, 2, 3), "end": p(4, 6, 3)}, parameter_domain={"start": s("0"), "end": s("5")}, closure=CLOSE0),
        checkpoints=[cp("0", (1, 2, 3), (F(3, 5), F(4, 5), 0), "0"), cp("2.5", (F(5, 2), 4, 3), (F(3, 5), F(4, 5), 0), "0"), cp("5", (4, 6, 3), (F(3, 5), F(4, 5), 0), "0")]),
    "circle": dict(
        derivation="CIRCLE radius 2 centred (1,2,3) in the plane z=3, x axis (1,0,0): P(t) = (1 + 2cos t, 2 + 2sin t, 3), "
                   "tangent (-sin t, cos t, 0), curvature 1/r = 0.5. At t = 0, pi/2, pi, 3pi/2 the cos/sin values are 1,0,-1,0 and 0,1,0,-1.",
        entity=dict(**{"class": "circle"}, geometry={"center": p(1, 2, 3), "normal": p(0, 0, 1), "x_axis": p(1, 0, 0), "radius": s("2")},
                    parameter_domain={"start": s("0"), "end": s(TWO_PI)}, closure=CLOSE_FULL),
        checkpoints=[cp("0", (3, 2, 3), (0, 1, 0), "0.5"), cp("1.5707963267948966", (1, 4, 3), (-1, 0, 0), "0.5"),
                     cp("3.141592653589793", (-1, 2, 3), (0, -1, 0), "0.5"), cp("4.71238898038469", (1, 0, 3), (1, 0, 0), "0.5")]),
    "ellipse": dict(
        derivation="ELLIPSE semi-major 4 along x, semi-minor 2, centred (1,2,3): P(t) = (1 + 4cos t, 2 + 2sin t, 3). "
                   "Curvature is ab / (a^2 sin^2 t + b^2 cos^2 t)^(3/2): at t=0 it is a/b^2 = 4/4 = 1, at t=pi/2 it is b/a^2 = 2/16 = 1/8.",
        entity=dict(**{"class": "ellipse"}, geometry={"center": p(1, 2, 3), "normal": p(0, 0, 1), "major_axis": p(1, 0, 0), "semi_major": s("4"), "semi_minor": s("2")},
                    parameter_domain={"start": s("0"), "end": s(TWO_PI)}, closure=CLOSE_FULL),
        checkpoints=[cp("0", (5, 2, 3), (0, 1, 0), "1"), cp("1.5707963267948966", (1, 4, 3), (-1, 0, 0), "0.125"),
                     cp("3.141592653589793", (-3, 2, 3), (0, -1, 0), "1"), cp("4.71238898038469", (1, 0, 3), (1, 0, 0), "0.125")]),
    "trimmed-arc": dict(
        derivation="The circle above (radius 2, centre (1,2,3)) trimmed to parameters 0.5..2, so start angle 0.5 and sweep 1.5. "
                   "With cos(0.5)=0.87758256189037271611628158, sin(0.5)=0.47942553860420300027328794, cos(2)=-0.41614683654714238699756823, "
                   "sin(2)=0.90929742682568169539601987: P(0.5) = (2.75516512378074543223, 2.95885107720840600055, 3) and "
                   "P(2) = (0.16770632690571522600, 3.81859485365136339079, 3); tangent (-sin, cos); curvature 0.5.",
        entity=dict(**{"class": "circular_arc"}, geometry={"center": p(1, 2, 3), "normal": p(0, 0, 1), "x_axis": p(1, 0, 0), "radius": s("2"), "start_angle": s("0.5"), "sweep_angle": s("1.5")},
                    parameter_domain={"start": s("0.5"), "end": s("2")}, closure=CLOSE0),
        checkpoints=[cp("0.5", ("2.75516512378074543223", "2.95885107720840600055", 3), ("-0.4794255386042030002732879", "0.8775825618903727161162816", 0), "0.5"),
                     cp("2", ("0.16770632690571522600", "3.81859485365136339079", 3), ("-0.9092974268256816953960199", "-0.4161468365471423869975682", 0), "0.5")]),
    "bspline": dict(
        derivation="Cubic B-spline, 5 control points (0,0) (1,2) (3,2) (4,0) (6,1), knots 0 (x4), 0.5 (x1), 1 (x4); 4+1+4 = 9 = 5+3+1. "
                   "The ends interpolate the end control points and the end tangents point along P1-P0 = (1,2) and P4-P3 = (2,1). "
                   "At the simple interior knot u=0.5, de Boor with alphas 1/2, 1/2, 0 gives 1/4 P1 + 1/2 P2 + 1/4 P3 = (2.75, 1.5).",
        entity=dict(**{"class": "bspline"}, geometry={"degree": 3, "control_points": [p(0, 0, 0), p(1, 2, 0), p(3, 2, 0), p(4, 0, 0), p(6, 1, 0)],
                                                      "knots": [{"value": s("0"), "multiplicity": 4}, {"value": s("0.5"), "multiplicity": 1}, {"value": s("1"), "multiplicity": 4}]},
                    parameter_domain={"start": s("0"), "end": s("1")}, closure=CLOSE0),
        checkpoints=[cp("0", (0, 0, 0), (S5, S5x2, 0)), cp("0.5", ("2.75", "1.5", 0)), cp("1", (6, 1, 0), (S5x2, S5, 0))]),
    "rational-bspline": dict(
        derivation="The worked example of docs/fixtures/expected-math.md: quadratic, control points (0,0) (1,2) (3,2.5) (4,0), weights 1, 0.5, 2, 1, "
                   "knots 0 (x3), 0.5, 1 (x3). Homogeneous points (w x, w y, w): P0w=(0,0,1), P1w=(0.5,1,0.5), P2w=(6,5,2), P3w=(4,0,1). "
                   "On [0,0.5] the Bezier points are B0=P0w, B1=P1w, B2=(P1w+P2w)/2=(3.25,3,1.25). At the knot u=0.5 the point is B2, "
                   "so (3.25/1.25, 3/1.25) = (2.6, 2.4). At u=0.25 it is (B0 + 2B1 + B2)/4 = (1.0625, 1.25, 0.8125), i.e. (17/13, 20/13). "
                   "With all weights 1 the knot point would be (2, 2.25), so a renormalised weight-1 form is distinguishable.",
        entity=dict(**{"class": "nurbs"}, geometry={"degree": 2, "control_points": [p(0, 0, 0), p(1, 2, 0), p(3, "2.5", 0), p(4, 0, 0)],
                                                    "knots": [{"value": s("0"), "multiplicity": 3}, {"value": s("0.5"), "multiplicity": 1}, {"value": s("1"), "multiplicity": 3}],
                                                    "weights": [s("1"), s("0.5"), s("2"), s("1")], "weights_all_unit": False},
                    parameter_domain={"start": s("0"), "end": s("1")}, closure=CLOSE0),
        checkpoints=[cp("0", (0, 0, 0), (S5, S5x2, 0)), cp("0.25", (F(17, 13), F(20, 13), 0)), cp("0.5", ("2.6", "2.4", 0)),
                     cp("1", (4, 0, 0), ("0.3713906763541037", "-0.9284766908852594", 0))]),
}


def main():
    for name, c in CASES.items():
        doc = {"schema_version": "pvec-gold/validator-selftest/1", "step_file": name + ".step",
               "hand_derivation": c["derivation"], "entity": c["entity"], "checkpoints": c["checkpoints"]}
        (OUT / (name + ".expected.json")).write_text(json.dumps(doc, indent=2) + "\n")


if __name__ == "__main__":
    main()
