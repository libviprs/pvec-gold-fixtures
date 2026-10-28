"""Time the geometric comparison stage, runner.compare_geometric.compare, per accepted fixture.

    python3 bench/validation/geometric.py --host mars --out geometric-mars.json [--repeats 7]

The stage compares a frozen signature to the fixture's known truth (expected.math.json): endpoints, the
maximum curve deviation (adaptive sampling, refined until the estimate is stable by the numeric policy),
bounding box, arc length, tangent and curvature. It needs python and the standard library only, no OCCT,
so it runs in the plain python driver on either architecture. What is recorded per fixture:

  compare_geometric_s   median, spread and range over `repeats` calls, the comparison alone (inputs already parsed)
  class                 the verdict the stage reached
  quantities            how many quantities were measured, and how many the policy's tolerance did not admit
  refinement            the deepest adaptive refinement level any quantity needed, and its sample count (null when
                        every quantity was closed form or sampled once)
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from runner import compare_geometric, expected_math, numeric, signatures  # noqa: E402

CORPUS = ROOT / "corpus" / "r0-open" / "fixtures"


def stats(xs):
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4, method="inclusive") if len(xs) > 1 else [xs[0]] * 3
    return {"n": len(xs), "median": statistics.median(xs), "min": xs[0], "max": xs[-1], "iqr": q[2] - q[0]}


def summary(rep):
    qs = [x for r in rep["entities"] for x in r["quantities"]] + rep["fixture_quantities"]
    levels = [(x["refinement_level"], x["sample_count"]) for x in qs if "refinement_level" in x]
    return {"count": len(qs), "not_admitted": sum(not x["admitted"] for x in qs),
            "refinement": {"deepest_level": max(levels)[0], "sample_count": max(levels)[1]} if levels else None}


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--signatures", default=str(ROOT / "signatures"))
    p.add_argument("--repeats", type=int, default=7)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if a.repeats < 5:
        p.error("at least five repeats")
    pol = numeric.load_policy()
    arch = "x64" if subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip() in ("x86_64", "amd64") else "arm64"
    fixtures = {}
    for fx in sorted(signatures.manifest(Path(a.signatures))["fixtures"]):
        exp = expected_math.load(CORPUS / fx / "expected.math.json")
        sig = signatures.load(Path(a.signatures), fx)
        ts = []
        for _ in range(a.repeats):
            t = time.perf_counter()
            rep = compare_geometric.compare(pol, exp, sig)
            ts.append(time.perf_counter() - t)
        fixtures[fx] = {"compare_geometric_s": stats(ts), "class": rep["class"], "entities": len(sig["entities"]),
                        "quantities": summary(rep), "repeats": a.repeats}
    total = sum(m["compare_geometric_s"]["median"] for m in fixtures.values())
    top = sorted(fixtures, key=lambda k: fixtures[k]["compare_geometric_s"]["median"], reverse=True)[:5]
    rec = {"schema": "pvec-gold/bench-geometric-run/1", "arch": arch, "native": True, "emulated": False, "host": a.host,
           "policy_version": pol.version, "repeats": a.repeats, "fixtures": fixtures, "total_median_s": total, "most_expensive": top,
           "load_avg": Path("/proc/loadavg").read_text().split()[:3]}
    Path(a.out).write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main(sys.argv[1:])
