"""Run step_eval with the adopted policy version stamped in, and check what comes out.

    python3 -m runner.step_eval IN.step OUT.verification.json [--evaluator step_eval]
"""
import subprocess
import sys

from . import numeric, verification


def run(step, out, evaluator="step_eval"):
    pol = numeric.load_policy()
    r = subprocess.run([evaluator, "--in", str(step), "--out", str(out), "--policy-version", pol.version], capture_output=True, text=True)
    if r.returncode != 0:
        return ["step_eval exited %d: %s" % (r.returncode, r.stderr.strip())]
    errs = verification.validate_doc(verification.load(out))
    doc = verification.load(out)
    if doc["numeric_policy_version"] != pol.version:
        errs.append("policy version not stamped")
    return errs


if __name__ == "__main__":
    ev = sys.argv[sys.argv.index("--evaluator") + 1] if "--evaluator" in sys.argv else "step_eval"
    e = run(sys.argv[1], sys.argv[2], ev)
    for x in e:
        print("FAIL " + x)
    sys.exit(1 if e else 0)
