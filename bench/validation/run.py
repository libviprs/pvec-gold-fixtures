"""Measure the validation stages per fixture, in the step-validator test image (step_eval, python, jsonschema).

    python3 bench/validation/run.py --host mars --signatures signatures --out validation.json [--repeats 7]

Stages, each timed on its own over `repeats` runs per accepted fixture:

  load         step_eval on the retained STEP file: OCCT reads the file and the evaluator samples every curve
               (one binary, so reading and evaluating cannot be told apart from outside; this is both)
  normalise    runner.normalize: the verification record to a signature, plus the schema and scalar checks
  structural   runner.structural.structural_diff of the derived signature against the frozen one, entity by entity
  report       the comparison report built and serialised

The adaptive geometric comparison is not measured: no such stage exists in this repository yet (it belongs to
the comparison policy work, O2.5 and O2.6), so there is no sample count to report, and the report says so. The
signature path is timed
against the STEP path over the whole accepted set: the signature path is runner.signatures.load (manifest
versions, hash check, JSON parse; no OCCT) plus the structural comparison, which is what a consumer asserting
a frozen value does. The STEP path is load + normalise + structural.
"""
import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from runner import normalize, numeric, signatures, structural, verification  # noqa: E402


def stats(xs):
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4, method="inclusive") if len(xs) > 1 else [xs[0]] * 3
    return {"n": len(xs), "median": statistics.median(xs), "min": xs[0], "max": xs[-1], "iqr": q[2] - q[0]}


def timed(fn):
    t = time.perf_counter()
    v = fn()
    return time.perf_counter() - t, v


def shape(sig):
    """The structural facts that make a fixture expensive."""
    poles = knot_mult = 0
    mag = 0.0
    samples = 0
    for e in sig["entities"]:
        g = e["geometry"]
        poles = max(poles, len(g.get("control_points", [])))
        knot_mult = max([knot_mult] + [k["multiplicity"] for k in g.get("knots", [])])
        samples += len(e.get("samples", []))
        for node in (g.get("control_points", []) + [g[k] for k in ("start", "end", "center") if k in g]):
            for c in node:
                mag = max(mag, abs(float(c["decimal"])))
    return {"entities": len(sig["entities"]), "samples": samples, "max_control_points": poles, "max_knot_multiplicity": knot_mult, "max_abs_coordinate_m": mag}


def reason(sh, med):
    parts = ["%d entities and %d evaluated samples" % (sh["entities"], sh["samples"])]
    if sh["max_control_points"]:
        parts.append("up to %d control points" % sh["max_control_points"])
    if sh["max_knot_multiplicity"] > 1:
        parts.append("knot multiplicity up to %d" % sh["max_knot_multiplicity"])
    if sh["max_abs_coordinate_m"] >= 1e4:
        parts.append("coordinates up to %.3g m" % sh["max_abs_coordinate_m"])
    if sh["entities"] <= 1:
        parts.append("no structural reason: one entity, within noise of the per-file floor (step_eval start and the fixed normalise cost)")
    return ", ".join(parts)


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--signatures", default=str(ROOT / "signatures"))
    p.add_argument("--repeats", type=int, default=7)
    p.add_argument("--evaluator", default="step_eval")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if a.repeats < 5:
        p.error("at least five repeats")
    root = Path(a.signatures)
    pol = numeric.load_policy().version
    fixtures, tmp = {}, Path(tempfile.mkdtemp(prefix="valbench"))
    arch = "x64" if subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip() in ("x86_64", "amd64") else "arm64"
    for fx in sorted(signatures.manifest(root)["fixtures"]):
        step, frozen = root / fx / "primary.step", signatures.load(root, fx)
        t = {"load_s": [], "normalise_s": [], "structural_s": [], "report_s": [], "signature_path_s": []}
        for _ in range(a.repeats):
            rec_path = tmp / "v.json"
            d, r = timed(lambda: subprocess.run([a.evaluator, "--in", str(step), "--out", str(rec_path), "--policy-version", pol], capture_output=True, text=True))
            if r.returncode != 0:
                raise SystemExit("step_eval failed on %s: %s" % (fx, r.stderr))
            t["load_s"].append(d)
            rec = verification.load(rec_path)

            def norm():
                sig = normalize.normalize(rec)
                errs = normalize.validate_doc(sig)
                assert not errs, errs
                return sig
            d, sig = timed(norm)
            t["normalise_s"].append(d)
            d, diffs = timed(lambda: [structural.structural_diff(x, y) for x, y in zip(frozen["entities"], sig["entities"])])
            t["structural_s"].append(d)
            d, _ = timed(lambda: (tmp / "report.json").write_text(normalize.dumps({"fixture": fx, "entities": len(sig["entities"]), "differences": [x for x in diffs if x], "verdict": "STRUCTURAL_EXACT" if not any(diffs) else "STRUCTURAL_DIFFERS"})))
            t["report_s"].append(d)

            def sigpath():
                s = signatures.load(root, fx, expect_schema=normalize.SCHEMA_VERSION, expect_policy=pol)
                return [structural.structural_diff(x, y) for x, y in zip(s["entities"], frozen["entities"])]
            d, _ = timed(sigpath)
            t["signature_path_s"].append(d)
        sh = shape(frozen)
        fixtures[fx] = dict({k: stats(v) for k, v in t.items()}, shape=sh, structural_verdict="STRUCTURAL_EXACT" if not any(diffs) else "STRUCTURAL_DIFFERS", repeats=a.repeats)
    ev = verification.load(tmp / "v.json")
    total = {fx: sum(m[s]["median"] for s in ("load_s", "normalise_s", "structural_s", "report_s")) for fx, m in fixtures.items()}
    top = sorted(total, key=total.get, reverse=True)[:10]
    step_path = sum(total.values())
    sig_path = sum(m["signature_path_s"]["median"] for m in fixtures.values())
    rep = {
        "schema": "pvec-gold/bench-validation-run/1", "arch": arch, "native": True, "emulated": False, "host": a.host,
        "evaluator_version": ev["tool"]["evaluator_version"], "occt_version": ev["tool"]["occt_version"], "policy_version": pol,
        "repeats": a.repeats, "fixtures": fixtures,
        "most_expensive": [dict(fixture=fx, total_median_s=total[fx], reason=reason(fixtures[fx]["shape"], total[fx])) for fx in top],
        "signature_path": {"subset": "all %d accepted r0-open fixtures" % len(fixtures), "step_path_s": step_path, "signature_path_s": sig_path, "speedup": step_path / sig_path},
        "load_avg": Path("/proc/loadavg").read_text().split()[:3],
    }
    Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main(sys.argv[1:])
