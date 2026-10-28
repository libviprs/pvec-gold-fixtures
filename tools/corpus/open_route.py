"""Run the open converter over the corpus DWGs, evaluate each STEP with step_eval, and qualify what has a record.

Runs inside the test driver container (python, docker CLI, the host's socket) with the tree in a docker
volume; tools/corpus/open_route.sh sets that up. Nothing here runs on the machine that started it.

    GOLD_VOLUME=<volume> python3 tools/corpus/open_route.py

For every source.dwg under fixtures/{edge,mixed,degenerate,negative,real-world} it keeps the converter's
status record (always), the STEP file (when the converter wrote one) and the evaluator's verification record.
The edge and mixed groups have authored mathematics, so runner.qualify_probes classifies each entity against
it (single oracle: the open route today has one converter). The others are recorded, not judged here: the
negative and degenerate checks read the status records in runner/corpus.py.
"""
import os
import platform
import subprocess
import sys
from pathlib import Path

from runner import numeric

ROOT = Path(__file__).resolve().parent.parent.parent
VOL = os.environ["GOLD_VOLUME"]
ARCH = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), "amd64")
PLAT = "linux/" + ARCH
CONV = os.environ.get("DWG2STEP_IMAGE", "gold-dwg2step-acadsharp:qualify-" + ARCH)
EVAL = os.environ.get("STEP_VALIDATOR_IMAGE", "gold-stepval:" + ARCH)
ID = "acadsharp-dwg2step"
OUT = ROOT / ".out-corpus-open"
GROUPS = {"edge": "fixtures/edge", "mixed": "fixtures/mixed", "degenerate": "fixtures/degenerate", "negative": "fixtures/negative",
          "real-world": "fixtures/real-world"}


def docker(*a, check=True):
    r = subprocess.run(["docker", *a], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit("docker %s failed: %s" % (" ".join(a[:3]), (r.stderr or r.stdout)[-800:]))
    return r


def vpath(p):
    return "/v/" + str(Path(p).resolve().relative_to(ROOT))


def main():
    docker("build", "-q", "--platform", PLAT, "-f", str(ROOT / "tools/converters/acadsharp/Dockerfile"), "-t", CONV, str(ROOT))
    if docker("image", "inspect", EVAL, check=False).returncode:
        docker("build", "-q", "--platform", PLAT, "-f", str(ROOT / "docker/step-validator/Dockerfile"), "-t", EVAL, str(ROOT))
    pol = numeric.load_policy().version
    for group, base in GROUPS.items():
        for dwg in sorted((ROOT / base).glob("*/source.dwg")):
            d = OUT / group / dwg.parent.name
            d.mkdir(parents=True, exist_ok=True)
            r = docker("run", "--rm", "--platform", PLAT, "-v", VOL + ":/v", CONV, "--in", vpath(dwg), "--out", vpath(d / "primary.step"),
                       "--status", vpath(d / "primary.status.json"), check=False)
            print("%-11s %-34s exit %d" % (group, dwg.parent.name, r.returncode), flush=True)
            if (d / "primary.step").exists():
                docker("run", "--rm", "--platform", PLAT, "-v", VOL + ":/v", EVAL, "step_eval", "--in", vpath(d / "primary.step"),
                       "--out", vpath(d / "primary.verification.json"), "--policy-version", pol)
    for group in ("edge", "mixed"):
        r = subprocess.run([sys.executable, "-m", "runner.qualify_probes", "--probes", str(ROOT / GROUPS[group]), "--primary", ID, str(OUT / group),
                            "--lineage", ID + "=ACadSharp", "--platform", PLAT, "--out", str(ROOT / ("reports/corpus/%s-qualification.json" % group))], cwd=ROOT)
        if r.returncode:
            sys.exit(r.returncode)


main()
