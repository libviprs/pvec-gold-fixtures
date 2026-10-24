"""The phase 1 exit gate: three named checks, all of which must be green.

    python3 -m runner.phase1_gate [--report reports/phase1/probe-qualification.json] [--evaluator step_eval]

1. probe-classification   every probe is classified for every converter in the O1.8 report, every cell
                          cites its evidence, and the report carries the adopted policy version.
2. evaluator-selftest     the hand-known primitives are reproduced and the mutations are caught.
3. expected-math-roundtrip  every expected.math.json validates, and the worked example round-trips
                          through the evaluator's output field for field.

Checks 2 and 3 need the step_eval binary (the step-validator image). Without it they report "not run"
and the gate is red: a gate that can't see the evaluator hasn't passed.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import expected_math as em, numeric, qualify_probes as q, structural, verification

ROOT = Path(__file__).resolve().parent.parent


def check_probe_classification(report_path):
    p = Path(report_path)
    if not p.exists():
        return ["%s does not exist: the probes have not been qualified against both converters" % report_path]
    rep = json.loads(p.read_text())
    errs = []
    if rep.get("numeric_policy_version") != numeric.load_policy().version:
        errs.append("report carries policy version %r, adopted %r" % (rep.get("numeric_policy_version"), numeric.load_policy().version))
    expected = {}
    for f in sorted((ROOT / "fixtures" / "known-truth").rglob("expected.math.json")):
        d = em.load(f)
        if q.is_converter_probe(d):
            expected[d["fixture_id"]] = [e["id"] for e in d["entities"]]
    for pid, ents in expected.items():
        per = rep.get("probes", {}).get(pid)
        if not per:
            errs.append("probe %s is not in the report" % pid)
            continue
        for conv in q.CONVERTERS:
            cells = {c["entity"]: c for c in per.get(conv, [])}
            for eid in ents:
                c = cells.get(eid)
                if c is None:
                    errs.append("%s/%s/%s has no cell" % (pid, conv, eid))
                elif c["class"] not in q.RANK or not c.get("evidence"):
                    errs.append("%s/%s/%s has no class or no evidence" % (pid, conv, eid))
                elif c["class"] == q.BOUNDED and not {"bound", "at_unit_parameter"} <= set(c["evidence"]):
                    errs.append("%s/%s/%s is a bounded approximation without its bound and parameter" % (pid, conv, eid))
    return errs


def check_evaluator_selftest(evaluator):
    if not shutil.which(evaluator):
        return ["step_eval not found (%s): evaluator self-test not run" % evaluator]
    pol = sorted((ROOT / "policy").glob("pvec-numeric-policy.*.json"))[0]
    r = subprocess.run([sys.executable, str(ROOT / "validator" / "selftest.py"), "--evaluator", evaluator, "--policy", str(pol), "--mutation-check"],
                       capture_output=True, text=True)
    return [] if r.returncode == 0 else ["self-test failed:\n" + r.stdout[-1500:] + r.stderr[-500:]]


def check_roundtrip(evaluator):
    errs = []
    files = sorted((ROOT / "fixtures" / "known-truth").rglob("expected.math.json")) + [ROOT / "docs" / "fixtures" / "examples" / "rational-bspline.expected.math.json"]
    for f in files:
        errs += ["%s: %s" % (f.relative_to(ROOT), e) for e in em.validate_file(f)]
    if not shutil.which(evaluator):
        return errs + ["step_eval not found (%s): evaluator round trip not run" % evaluator]
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "o.json"
        r = subprocess.run([evaluator, "--in", str(ROOT / "fixtures" / "validator-selftest" / "rational-bspline.step"), "--out", str(out),
                            "--policy-version", numeric.load_policy().version], capture_output=True, text=True)
        if r.returncode != 0:
            return errs + ["step_eval failed on the worked example: " + r.stderr.strip()]
        got = verification.load(out)["entities"][0]
        ex = em.load(files[-1])["entities"][0]
        d = structural.structural_diff(ex, got)
        if d:
            errs.append("worked example does not round-trip: " + ", ".join(d[:5]))
    return errs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "reports" / "phase1" / "probe-qualification.json"))
    ap.add_argument("--evaluator", default="step_eval")
    a = ap.parse_args(argv)
    checks = [("probe-classification", check_probe_classification(a.report)),
              ("evaluator-selftest", check_evaluator_selftest(a.evaluator)),
              ("expected-math-roundtrip", check_roundtrip(a.evaluator))]
    bad = 0
    for name, errs in checks:
        print("%s %s" % ("GREEN" if not errs else "RED  ", name))
        for e in errs[:6]:
            print("       - " + e)
        if len(errs) > 6:
            print("       ... %d more" % (len(errs) - 6))
        bad += bool(errs)
    print("phase 1 exit gate: %s" % ("RED" if bad else "GREEN"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
