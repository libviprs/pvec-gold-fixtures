"""Measure and prove the orchestration settings: wall time per parallelism, resume, teardown, resource limits.

    python3 bench/orchestration/run.py --host mars --conv-report .conv.json --out orchestration.json
    [--converter libredwg-dwg2step --mem 512m --cap-basis TEXT]   the image is the one the conv report measured

Runs where the docker CLI and socket are (bench/drive.sh). Everything goes through runner.regenerate, the
same entry point a real regeneration uses, so the numbers are the scheduler's own.

  table        the full corpus regenerated at parallelism 1, 2, 4 and 8 (repeated, a fresh output tree each time)
  experiments  per-container cpu limits and runtime switches on a four-fixture subset, to see what is worth setting
  resume       a run interrupted part way, then rerun: only unfinished fixtures run, untouched ones hash the same
  teardown     a parallel run aborted with SIGINT: no container carrying the run label and no new volume survives
"""
import argparse
import hashlib
import json
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from runner import scheduler  # noqa: E402
CPUS = "2"
SUBSET = "line-001,nurbs-d3-001,nested-blocks-001,polyline-001"


def regen(out, parallel, base, extra=()):
    return subprocess.Popen([sys.executable, "-m", "runner.regenerate", "--out", str(out), "--parallel", str(parallel), "--cpus", CPUS, *base, *extra],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def summary(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def docker_ls(*a):
    return set(subprocess.run(["docker", *a], capture_output=True, text=True).stdout.split())


def tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def done_count(state):
    return sum(1 for p in Path(state).glob("*.json") if '"done"' in p.read_text())


def wait_for(state, n, timeout=60):
    t = time.monotonic()
    while done_count(state) < n and time.monotonic() - t < timeout:
        time.sleep(0.05)


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--conv-report", required=True)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--work", default=str(ROOT / ".out-orch"))
    p.add_argument("--converter", default="acadsharp-dwg2step")
    p.add_argument("--eval-image", help="step_eval image, passed to runner.regenerate (default: its own)")
    p.add_argument("--mem", default="256m")
    p.add_argument("--cap-basis", default="a cap I set", help="why the cap in docker/converter-limits.json is what it is")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    mem = a.mem
    work = Path(a.work)
    conv = json.loads(Path(a.conv_report).read_text())
    base = ["--converter", a.converter, "--mem", mem, "--converter-image", conv["image"]] + (["--eval-image", a.eval_image] if a.eval_image else [])
    arch = conv["arch"]

    table, oom, other_failures = [], 0, []
    for par in (1, 2, 4, 8):
        walls = []
        for i in range(a.reps):
            proc = regen(work / ("t%d-%d" % (par, i)), par, base)
            s = summary(proc.communicate()[0])
            walls.append(s["wall_s"])
            oom += sum("out of memory" in v for v in s["failed"].values())
            other_failures += list(s["failed"])
            assert list(s["refused"]) == ["near-singular-001"], s["refused"]
        n = len(s["done"]) + len(s["refused"])
        table.append({"parallel": par, "wall_s": {"n": len(walls), "median": statistics.median(walls), "min": min(walls), "max": max(walls)},
                      "fixtures": n, "fixtures_per_s": n / statistics.median(walls)})
    best = min(r["wall_s"]["median"] for r in table)
    chosen = next(r["parallel"] for r in table if r["wall_s"]["median"] <= best * 1.10)

    # The dotnet runtime switches only mean something for the dotnet converter.
    runs = [("unlimited", []), ("cpus_1", ["--cpus", "1", "--mem", mem]), ("cpus_2", ["--cpus", "2", "--mem", mem]), ("cpus_4", ["--cpus", "4", "--mem", mem])]
    if a.converter == "acadsharp-dwg2step":
        runs += [("TieredPGO_0", ["--env", "DOTNET_TieredPGO=0"]), ("TieredCompilation_0", ["--env", "DOTNET_TieredCompilation=0"])]
    experiments = {}
    for name, args in runs:
        o = work / ("exp-%s.json" % name)
        subprocess.run([sys.executable, "bench/converters/run.py", "--image", conv["image"], "--host", a.host, "--repeats", "9", "--fixtures", SUBSET,
                        "--converter", a.converter, "--out", str(o), "--work", str(work / "exp"), *args], cwd=ROOT, check=True, capture_output=True)
        r = json.loads(o.read_text())
        experiments[name] = {"conversion_s_median": statistics.median(m["conversion_s"]["median"] for m in r["fixtures"].values()),
                             "total_s_median": statistics.median(m["total_s"]["median"] for m in r["fixtures"].values())}

    # resume: interrupt at parallelism 4 once a few fixtures are done, then rerun
    out = work / "resume"
    proc = regen(out, 4, base)
    wait_for(out / "state", 6)
    proc.send_signal(signal.SIGINT)
    proc.communicate()
    before = {p_.name: tree(p_) for p_ in (out / "fixtures").iterdir() if not p_.name.startswith(".")}
    proc = regen(out, 4, base)
    s = summary(proc.communicate()[0])
    after = {fx: tree(out / "fixtures" / fx) for fx in before}
    resume = {"done_before_interrupt": len(before), "skipped_on_rerun": len(s["skipped"]), "regenerated_on_rerun": len(s["done"]) + len(s["refused"]),
              "untouched_hashes_identical": before == after, "skipped_exactly_the_finished": sorted(s["skipped"]) == sorted(before) or set(before) <= set(s["skipped"])}

    # teardown: abort a parallel run, then look for survivors
    # The docker host is shared, so a raw before/after diff would count other people's containers. The runner names its
    # containers gold-<run id>-... and labels them gold.run=<run id>; those are the ones a leak could be.
    ctr0 = docker_ls("ps", "-aq", "--filter", "name=gold-")
    proc = regen(work / "abort", 8, base)
    time.sleep(0.6)
    proc.send_signal(signal.SIGINT)
    proc.communicate()
    leftover_c = docker_ls("ps", "-aq", "--filter", "label=gold.run") 
    teardown = {"signal": "SIGINT at parallelism 8", "leftover_labelled_containers": len(leftover_c), "new_containers": len(docker_ls("ps", "-aq", "--filter", "name=gold-") - ctr0),
                "new_volumes": len(docker_ls("volume", "ls", "-q", "--filter", "label=gold.run"))}

    rep = {
        "schema": "pvec-gold/bench-orchestration-run/1", "arch": arch, "host": a.host, "native": True, "emulated": False,
        "converter": a.converter, "cap": scheduler.limit_for(a.converter), "cap_basis": a.cap_basis,
        "image": conv["image"], "image_id": conv["image_id"], "table": table, "chosen": {"parallel": chosen, "cpus": float(CPUS), "memory_limit_mib": int(mem.rstrip("m")),
                                                                                    "rule": "smallest parallelism within 10% of the best median wall"},
        "experiments_conversion_subset": SUBSET, "experiments": experiments,
        "observed_peak_rss_mib": max(m["peak_rss_mib"]["max"] for m in conv["fixtures"].values()),
        "observed_peak_cgroup_mib": max(m["cgroup_peak_mib"]["max"] for m in conv["fixtures"].values()),
        "largest_fixture": max(conv["fixtures"], key=lambda k: conv["fixtures"][k]["cgroup_peak_mib"]["max"]),
        "oom_killed": oom, "unexpected_failures": other_failures, "resume": resume, "teardown": teardown,
        "leftover_containers": teardown["leftover_labelled_containers"] + teardown["new_containers"], "leftover_volumes": teardown["new_volumes"],
        "load_avg": Path("/proc/loadavg").read_text().split()[:3],
    }
    Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main(sys.argv[1:])
