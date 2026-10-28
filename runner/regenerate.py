"""Regenerate the signatures from the DWG corpus through the open converter, under the scheduler.

    python3 -m runner.regenerate --out DIR --parallel N [--pack signatures] [--mem 1g] [--cpus 1]
        [--converter-image IMG] [--eval-image IMG] [--converter acadsharp-dwg2step]

Per fixture (a container each, concurrency capped by runner/scheduler.py and docker/converter-limits.json):
DWG -> primary.step + primary.status.json -> primary.verification.json (step_eval) -> signature.json
(runner.normalize). Resumable: rerun the same command and only unfinished fixtures run. Exit 1 if any
fixture failed. A converter refusal the status record names (exit 15) is recorded as refused, not failed.
Needs the docker CLI and the daemon's socket; see runner/containers.py for the volume convention.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import containers, normalize, numeric, scheduler, signatures, verification

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "r0-open" / "fixtures"
# Fixed so the STEP time stamp, the one field a run varies, is the same on every host and every run.
SOURCE_DATE_EPOCH = "1761523200"


def fixtures():
    return sorted(p.parent.name for p in CORPUS.glob("*/source.dwg"))


def make_job(a, run_id):
    label = "gold.run=" + run_id

    def job(fx, work, log):
        src = CORPUS / fx
        c = containers.run(a.converter_image, ["--in", containers.cpath(src / "source.dwg"), "--out", containers.cpath(work / "primary.step"),
                                               "--status", containers.cpath(work / "primary.status.json")],
                           [src, work], name="gold-%s-%s-c" % (run_id, fx), label=label, mem=a.mem, cpus=a.cpus,
                           extra=["-e", "SOURCE_DATE_EPOCH=" + SOURCE_DATE_EPOCH])
        log.write("converter exit %d" % c.returncode)
        log.write(c.stderr[-2000:])
        st = work / "primary.status.json"
        if c.returncode == 15 and st.exists() and "NEAR_SINGULAR_TRANSFORM" in st.read_text():
            raise scheduler.Refused("NEAR_SINGULAR_TRANSFORM")
        if c.returncode != 0:
            raise RuntimeError("converter exited %d%s" % (c.returncode, " (killed, probably out of memory)" if c.returncode == 137 else ""))
        e = containers.run(a.eval_image, ["step_eval", "--in", containers.cpath(work / "primary.step"), "--out", containers.cpath(work / "primary.verification.json"),
                                          "--policy-version", numeric.load_policy().version],
                           [work], name="gold-%s-%s-e" % (run_id, fx), label=label)
        log.write("step_eval exit %d" % e.returncode)
        if e.returncode != 0:
            raise RuntimeError("step_eval exited %d: %s" % (e.returncode, e.stderr[-300:]))
        sig = normalize.normalize(verification.load(work / "primary.verification.json"))
        (work / "signature.json").write_text(normalize.dumps(sig), encoding="ascii")
    return job


def pack(out, dest):
    dest = Path(dest)
    done = [fx for fx in fixtures() if (Path(out) / fx / "signature.json").exists()]
    for fx in done:
        (dest / fx).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(out) / fx / "signature.json", dest / fx / "signature.json")
        shutil.copyfile(Path(out) / fx / "primary.step", dest / fx / "primary.step")
    sig = json.loads((dest / done[0] / "signature.json").read_text())
    signatures.write_manifest(dest, done, sig["versions"])
    return done


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--parallel", type=int, default=1)
    p.add_argument("--converter", default="acadsharp-dwg2step")
    p.add_argument("--converter-image", default="gold-dwg2step-acadsharp:test-" + containers.PLATFORM.split("/")[1])
    p.add_argument("--eval-image", default="gold-stepval:" + containers.PLATFORM.split("/")[1])
    p.add_argument("--mem", default="256m")
    p.add_argument("--cpus", default="2")
    p.add_argument("--pack")
    a = p.parse_args(argv)
    out = Path(a.out)
    run_id = "%d" % os.getpid()
    t0 = time.monotonic()
    try:
        s = scheduler.run(fixtures(), make_job(a, run_id), out=out / "fixtures", state=out / "state", logs=out / "logs",
                          parallel=a.parallel, limit=scheduler.limit_for(a.converter),
                          teardown=lambda fx: containers.docker("rm", "-f", "gold-%s-%s-c" % (run_id, fx), "gold-%s-%s-e" % (run_id, fx)))
    finally:
        containers.remove_labelled("gold.run=" + run_id)
    s["wall_s"] = round(time.monotonic() - t0, 3)
    print(json.dumps({k: (sorted(v) if isinstance(v, (list, dict)) and k in ("done", "skipped") else v) for k, v in s.items()}, indent=2, sort_keys=True))
    if a.pack:
        print("packed %d signatures" % len(pack(out / "fixtures", a.pack)))
    return s["exit_code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
