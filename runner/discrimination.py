"""Discrimination on real converter output (issue 67).

    python3 -m runner.discrimination [--evaluator step_eval] [--out reports/phase1/discrimination.json]

Take the STEP text each open converter wrote for the B-spline probes, change it in one of three ways, run the
mutated file through step_eval and the probe classifier, and record whether the structural class moved:

  weights-to-1    every rational weight set to 1 (a renormalisation that flattens the weights)
  knot-collapse   the first interior knot merged into the next one (multiplicity added, knot count down by one)
  reparameterise  every knot scaled by 2 (same curve, different parameter domain)

The mutations edit the Part 21 text and nothing else, so the file is still what the converter wrote apart from
one curve entity. validator/selftest.py --mutation-check does the same for the hand-written evaluator files.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from . import expected_math as em, numeric, qualify_probes as qp, step_eval, verification

ROOT = Path(__file__).resolve().parent.parent
CONVERTERS = ("acadsharp-dwg2step", "libredwg-dwg2step")
MUTATIONS = ("weights-to-1", "knot-collapse", "reparameterise")
KNOTS = re.compile(r"\(([0-9]+(?:,[0-9]+)*)\),\(([-+0-9.eE]+(?:,[-+0-9.eE]+)*)\),(\.[A-Z_]+\.)\)")
WEIGHTS = re.compile(r"(RATIONAL_B_SPLINE_CURVE\(\()([^)]*)(\)\))")


def step_path(conv, probe):
    if conv == "acadsharp-dwg2step":
        return ROOT / "signatures" / probe / "primary.step"
    return ROOT / "fixtures" / "discrimination" / conv / (probe + ".step")


def probes():
    """The probes both converters have a B-spline for: the ones the mutations can say anything about."""
    names = None
    for c in CONVERTERS:
        have = {p.name for p in (ROOT / "signatures").iterdir() if p.is_dir() and "B_SPLINE" in (p / "primary.step").read_text()} \
            if c == "acadsharp-dwg2step" else {p.stem for p in step_path(c, "x").parent.glob("*.step")}
        names = have if names is None else names & have
    return sorted(names)


def knot_spec(text):
    m = KNOTS.search(text)
    return [int(x) for x in m.group(1).split(",")], [float(x) for x in m.group(2).split(",")]


def _num(x):
    return repr(float(x))


def _knots(text, edit):
    m = KNOTS.search(text)
    mults, knots = [int(x) for x in m.group(1).split(",")], [float(x) for x in m.group(2).split(",")]
    new = edit(mults, knots)
    if new is None:
        return None
    mults, knots = new
    rep = "(%s),(%s),%s)" % (",".join(str(x) for x in mults), ",".join(_num(x) for x in knots), m.group(3))
    return text[:m.start()] + rep + text[m.end():]


def mutate(name, text):
    """The mutated text, or None when the file has nothing the mutation applies to."""
    if name == "weights-to-1":
        m = WEIGHTS.search(text)
        if not m:
            return None
        ones = ",".join("1." for _ in m.group(2).split(","))
        return text[:m.start(2)] + ones + text[m.end(2):]
    if name == "reparameterise":
        return _knots(text, lambda mu, kn: (mu, [2.0 * k for k in kn]))
    if name == "knot-collapse":
        def collapse(mu, kn):
            if len(kn) < 4 or mu[0] == 1 or mu[-1] == 1:   # needs a clamped curve with two distinct interior knots
                return None
            return [mu[0], mu[1] + mu[2]] + mu[3:], [kn[0], kn[2]] + kn[3:]
        return _knots(text, collapse)
    raise ValueError(name)


def classify(pol, expected_doc, step, evaluator):
    """The probe's class for one STEP file: step_eval, then the same classifier the qualification report uses."""
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "v.json"
        errs = step_eval.run(step, out, evaluator)
        if errs:
            return "EVALUATOR_ERROR", errs
        res = qp.qualify_probe(pol, expected_doc, {"c": (verification.load(out), None)})["c"]
    return qp.probe_class(res), []


def run(evaluator="step_eval"):
    pol = numeric.load_policy()
    report = {}
    for conv in CONVERTERS:
        report[conv] = {}
        for p in probes():
            exp = em.load(ROOT / "fixtures" / "known-truth" / p / "expected.math.json")
            src = step_path(conv, p).read_text()
            with tempfile.TemporaryDirectory() as t:
                base_file = Path(t) / "base.step"
                base_file.write_text(src)
                base, _ = classify(pol, exp, base_file, evaluator)
                row = {"baseline": base, "mutations": {}}
                for mut in MUTATIONS:
                    text = mutate(mut, src)
                    if text is None:
                        row["mutations"][mut] = {"applies": False, "changed": False, "class": base}
                        continue
                    f = Path(t) / (mut + ".step")
                    f.write_text(text)
                    klass, errs = classify(pol, exp, f, evaluator)
                    row["mutations"][mut] = {"applies": True, "class": klass, "changed": klass != base}
                    if errs:
                        row["mutations"][mut]["errors"] = errs
            report[conv][p] = row
    return report


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluator", default="step_eval")
    ap.add_argument("--out", default="reports/phase1/discrimination.json")
    a = ap.parse_args(argv)
    rep = run(a.evaluator)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for conv, rows in rep.items():
        for mut in MUTATIONS:
            names = [p for p, r in rows.items() if r["mutations"][mut]["changed"]]
            print("%-20s %-15s changed %d: %s" % (conv, mut, len(names), ", ".join(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
