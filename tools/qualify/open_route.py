"""Convert every r0-open DWG with the open converter, evaluate the STEP with step_eval, and qualify.

Runs inside the test driver container (python, docker CLI, the host's socket) with the tree in a docker
volume; tools/qualify/open_route.sh sets that up. Nothing here runs on the machine that started it.

    GOLD_VOLUME=<volume> python3 tools/qualify/open_route.py
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
OUT = ROOT / ".out-qualify"


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
    for dwg in sorted((ROOT / "corpus/r0-open/fixtures").glob("*/source.dwg")):
        d = OUT / dwg.parent.name
        d.mkdir(parents=True, exist_ok=True)
        r = docker("run", "--rm", "--platform", PLAT, "-v", VOL + ":/v", CONV, "--in", vpath(dwg), "--out", vpath(d / "primary.step"),
                   "--status", vpath(d / "primary.status.json"), check=False)
        print("%-34s exit %d" % (dwg.parent.name, r.returncode), flush=True)
        if (d / "primary.step").exists():
            docker("run", "--rm", "--platform", PLAT, "-v", VOL + ":/v", EVAL, "step_eval", "--in", vpath(d / "primary.step"),
                   "--out", vpath(d / "primary.verification.json"), "--policy-version", pol)
    r = subprocess.run([sys.executable, "-m", "runner.qualify_probes", "--primary", ID, str(OUT), "--lineage", ID + "=ACadSharp",
                        "--excluded", str(ROOT / "corpus/r0-open/quarantine.json"), "--platform", PLAT,
                        "--out", str(ROOT / "reports/phase1/probe-qualification.json")], cwd=ROOT)
    sys.exit(r.returncode)


main()
