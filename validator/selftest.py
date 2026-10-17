#!/usr/bin/env python3
"""Self-test for step_eval: hand-written STEP files against hand-computed records.

    python3 validator/selftest.py --evaluator step_eval --policy policy/pvec-numeric-policy.<v>.json \
        [--dir fixtures/validator-selftest] [--out DIR] [--mutation-check]

Stored values (control points, knots, weights) must come back bit for bit. Derived values (line
ends, directions, sample points, tangents, curvature) are compared with the vendored numeric
policy at the fixture's scale, and the harness itself holds no tolerance. Exit 0 only if every
case passes (and, with --mutation-check, every mutation is caught).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from runner import canon, numeric  # noqa: E402

EXACT_KEYS = ("control_points", "knots", "weights")


def is_scalar(x):
    return isinstance(x, dict) and set(x) == {"decimal", "f64_hex"}


def scale_for(path, exp, base, width):
    """The NP-04 scale term. Unit directions compare at scale 1, a curvature at its own magnitude, a
    parameter or angle at the width of its domain, and everything else at the entity's feature size."""
    if path.endswith(".tangent") or ".tangent[" in path:
        return 1.0
    if path.endswith(".curvature"):
        return abs(canon.check_scalar(exp))
    if "parameter_domain" in path or "angle" in path or path.endswith(".parameter"):
        return width
    return base


def compare(path, exp, got, pol, scale, fails, exact=False):
    base, width = scale
    exact = exact or any(k in path for k in EXACT_KEYS)
    if is_scalar(exp):
        if not is_scalar(got):
            fails.append("%s: missing or not a scalar" % path)
        elif exact:
            if exp["f64_hex"] != got["f64_hex"]:
                fails.append("%s: stored value changed, expected %s got %s" % (path, exp["f64_hex"], got["f64_hex"]))
        elif not pol.near(canon.check_scalar(exp), canon.check_scalar(got), scale_for(path, exp, base, width)):
            fails.append("%s: expected %s got %s (outside the policy)" % (path, exp["decimal"], got["decimal"]))
    elif isinstance(exp, dict):
        if not isinstance(got, dict):
            fails.append("%s: missing" % path)
            return
        for k, v in exp.items():
            if k not in got:
                fails.append("%s.%s: missing" % (path, k))
            else:
                compare("%s.%s" % (path, k), v, got[k], pol, scale, fails, exact)
    elif isinstance(exp, list):
        if not isinstance(got, list) or len(got) != len(exp):
            fails.append("%s: expected %d items" % (path, len(exp)))
            return
        for i, v in enumerate(exp):
            compare("%s[%d]" % (path, i), v, got[i], pol, scale, fails, exact)
    elif exp != got:
        fails.append("%s: expected %r got %r" % (path, exp, got))


def run_case(evaluator, step, expected_path, pol, out_dir, schema_check):
    exp = json.loads(Path(expected_path).read_text())
    out = Path(out_dir) / (Path(step).stem + ".verification.json")
    r = subprocess.run([evaluator, "--in", str(step), "--out", str(out), "--policy-version", pol.version], capture_output=True, text=True)
    if r.returncode != 0:
        return ["step_eval exited %d: %s" % (r.returncode, r.stderr.strip())]
    got = json.loads(out.read_text())
    fails = []
    if schema_check:
        from runner import verification
        fails += verification.validate_doc(json.loads(out.read_text(), parse_float=lambda t: (_ for _ in ()).throw(ValueError(t))))
    if got.get("numeric_policy_version") != pol.version:
        fails.append("numeric_policy_version not carried through")
    for k in ("evaluator_version", "occt_version"):
        if not got.get("tool", {}).get(k):
            fails.append("tool.%s missing" % k)
    if len(got["entities"]) != 1:
        return fails + ["expected exactly one curve, got %d" % len(got["entities"])]
    ent = got["entities"][0]
    dom = ent["parameter_domain"]
    width = canon.check_scalar(dom["end"]) - canon.check_scalar(dom["start"])
    scale = (numeric.feature_scale(exp["entity"]), abs(width))
    compare("entity", exp["entity"], ent, pol, scale, fails)
    for i, cp in enumerate(exp["checkpoints"]):
        want = canon.check_scalar(cp["parameter"])
        hit = [s for s in ent["samples"] if pol.near(canon.check_scalar(s["parameter"]), want, abs(width))]
        if not hit:
            fails.append("checkpoint %d: no sample at parameter %s" % (i, cp["parameter"]["decimal"]))
            continue
        s = hit[0]
        for key in ("point", "tangent", "curvature"):
            if cp[key] is None:
                continue
            if s[key] is None:
                fails.append("checkpoint %d: %s not evaluated" % (i, key))
            else:
                compare("checkpoint[%d].%s" % (i, key), cp[key], s[key], pol, scale, fails)
    return fails


MUTATIONS = [
    ("bspline.step", "(0.,0.5,1.)", "(0.,0.51,1.)", "one interior knot moved"),
    ("rational-bspline.step", "(0.,0.5,1.)", "(0.,0.51,1.)", "one interior knot moved"),
    ("rational-bspline.step", "RATIONAL_B_SPLINE_CURVE((1.,0.5,2.,1.))", "RATIONAL_B_SPLINE_CURVE((1.,0.55,2.,1.))", "one weight moved"),
    ("rational-bspline.step", "RATIONAL_B_SPLINE_CURVE((1.,0.5,2.,1.))", "RATIONAL_B_SPLINE_CURVE((1.,1.,1.,1.))", "weights renormalised to 1"),
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluator", default="step_eval")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--dir", default=str(ROOT / "fixtures" / "validator-selftest"))
    ap.add_argument("--out")
    ap.add_argument("--mutation-check", action="store_true")
    ap.add_argument("--schema-check", action="store_true")
    a = ap.parse_args(argv)
    pol = numeric.load_policy(a.policy)
    d = Path(a.dir)
    out = Path(a.out) if a.out else Path(tempfile.mkdtemp())
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for ex in sorted(d.glob("*.expected.json")):
        step = d / json.loads(ex.read_text())["step_file"]
        fails = run_case(a.evaluator, step, ex, pol, out, a.schema_check)
        print("%s %s" % ("FAIL" if fails else "ok  ", step.name))
        for f in fails:
            print("     - %s" % f)
        bad += bool(fails)
    if a.mutation_check:
        for name, old, new, what in MUTATIONS:
            src = (d / name).read_text()
            if src.count(old) != 1:
                print("FAIL mutation %s: pattern %r not found exactly once" % (name, old))
                bad += 1
                continue
            with tempfile.TemporaryDirectory() as t:
                m = Path(t) / name
                m.write_text(src.replace(old, new))
                fails = run_case(a.evaluator, m, d / (Path(name).stem + ".expected.json"), pol, t, False)
            caught = bool(fails)
            print("%s mutation %s: %s" % ("ok  " if caught else "FAIL", name, what + (" (self-test red)" if caught else " (NOT caught: self-test stayed green)")))
            bad += not caught
    print("self-test: %s (policy %s)" % ("FAILED" if bad else "passed", pol.version))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
