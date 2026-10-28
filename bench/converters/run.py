"""Measure the open converter per fixture: container startup, conversion wall time, peak RSS, output size, failures.

    python3 bench/converters/run.py --image IMG --host mars [--repeats 7] [--concurrency 1] --out report.json

--converter libredwg-dwg2step measures the LibreDWG converter (image by id or digest, never built here).
Runs where the docker CLI and the daemon socket are (see bench/drive.sh). Each repeat is one throw-away
container. Inside it a small sh wrapper times the converter process and samples the converter's VmHWM from
/proc, which is its peak resident set; the container's cgroup memory.peak is recorded too, because that is the
number a --memory limit is compared with. What is reported per fixture:

  total_s       wall time of `docker run` as seen from outside
  conversion_s  wall time of the converter process inside the container (dotnet runtime start included)
  startup_s     total_s - conversion_s: creating, starting and removing the container
  peak_rss_mib  converter VmHWM; cgroup_peak_mib is the container's memory.peak
  step_bytes    size of the STEP written (0 when the converter refused)
  failure_rate  nonzero exits over repeats, with the converter's own status record as the cause

The no-op is the same image run with no arguments, which the converter rejects (exit 10) the moment its
runtime is up. Its inner time is the dotnet start cost, so conversion_s minus the no-op inner time is the
conversion proper, and its total is what a slow image would cost on every call whatever it converts.
Native only: DOCKER_PLATFORM is passed through and the report records the host architecture it ran on.
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
from runner import containers, scheduler  # noqa: E402

BINARY = {"acadsharp-dwg2step": "dwg2step-acadsharp", "libredwg-dwg2step": "dwg2step"}
CORPUS = ROOT / "corpus" / "r0-open" / "fixtures"
# Runs the converter in the background, samples its VmHWM until it exits, then reports on stderr.
WRAP = r'''
t0=$(date +%s%N)
"$@" 2>/tmp/err &
pid=$!
hwm=0
while kill -0 $pid 2>/dev/null; do
  while read -r k v u; do [ "$k" = "VmHWM:" ] && hwm=$v; done < /proc/$pid/status 2>/dev/null
done
wait $pid; rc=$?
t1=$(date +%s%N)
cg=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)
cat /tmp/err >&2
echo "BENCH rc=$rc ns=$((t1-t0)) hwm_kb=$hwm cg_bytes=$cg" >&2
exit $rc
'''


def stats(xs):
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4, method="inclusive") if len(xs) > 1 else [xs[0]] * 3
    return {"n": len(xs), "median": statistics.median(xs), "min": xs[0], "max": xs[-1], "iqr": q[2] - q[0]}


def one(image, args, dirs, mem=None, cpus=None, env=(), binary="dwg2step-acadsharp"):
    t = time.monotonic()
    r = containers.run(image, ["-c", WRAP, "sh", binary, *args], dirs, entrypoint="sh", mem=mem, cpus=cpus, extra=[x for e in env for x in ("-e", e)])
    total = time.monotonic() - t
    line = [l for l in r.stderr.splitlines() if l.startswith("BENCH ")]
    f = dict(kv.split("=") for kv in line[-1].split()[1:]) if line else {}
    return {"total": total, "rc": int(f.get("rc", r.returncode)), "inner": int(f.get("ns", 0)) / 1e9,
            "rss_mib": int(f.get("hwm_kb", 0)) / 1024, "cg_mib": int(f.get("cg_bytes", 0)) / 1048576, "stderr": r.stderr}


def cause(work):
    p = work / "primary.status.json"
    if not p.exists():
        return "no status record written"
    st = json.loads(p.read_text())
    return "%s (exit %s): %s" % (st.get("status"), st.get("exit_code"), json.dumps(st.get("error"))[:200])


def measure(image, fx, repeats, work_root, mem, cpus, env=(), binary="dwg2step-acadsharp"):
    src = CORPUS / fx
    rows = []
    for i in range(repeats):
        work = work_root / ("%s-%d" % (fx, i))
        work.mkdir(parents=True, exist_ok=True)
        r = one(image, ["--in", containers.cpath(src / "source.dwg"), "--out", containers.cpath(work / "primary.step"),
                        "--status", containers.cpath(work / "primary.status.json")], [src, work], mem, cpus, env, binary)
        r["step_bytes"] = (work / "primary.step").stat().st_size if (work / "primary.step").exists() else 0
        r["cause"] = None if r["rc"] == 0 else cause(work)
        rows.append(r)
    fails = [r for r in rows if r["rc"] != 0]
    return {
        "repeats": repeats,
        "total_s": stats([r["total"] for r in rows]),
        "conversion_s": stats([r["inner"] for r in rows]),
        "startup_s": stats([r["total"] - r["inner"] for r in rows]),
        "peak_rss_mib": stats([r["rss_mib"] for r in rows]),
        "cgroup_peak_mib": stats([r["cg_mib"] for r in rows]),
        "step_bytes": stats([r["step_bytes"] for r in rows]),
        "failure_rate": len(fails) / repeats,
        "exit_codes": sorted({r["rc"] for r in rows}),
        "cause": fails[0]["cause"] if fails else None,
    }


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--repeats", type=int, default=7)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--converter", default="acadsharp-dwg2step")
    p.add_argument("--mem")
    p.add_argument("--cpus")
    p.add_argument("--env", action="append", default=[], help="KEY=VALUE passed to the converter container (for tuning experiments)")
    p.add_argument("--fixtures", help="comma-separated subset (an experiment, not the corpus report)")
    p.add_argument("--out", required=True)
    p.add_argument("--work", default=str(ROOT / ".out-bench-converters"))
    a = p.parse_args(argv)
    if a.repeats < 5:
        p.error("at least five repeats")
    binary = BINARY[a.converter]
    limit = scheduler.limit_for(a.converter)
    if a.concurrency > limit:
        raise scheduler.LicenceLimitExceeded("concurrency %d above the limit %d" % (a.concurrency, limit))
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    arch = "x64" if containers.PLATFORM.endswith("amd64") else "arm64"
    insp = containers.docker("image", "inspect", a.image, "--format", "{{.Id}} {{.Architecture}}").stdout.split()
    load_before = Path("/proc/loadavg").read_text().split()[:3]
    noop_rows = [one(a.image, [], [work], a.mem, a.cpus, a.env, binary) for _ in range(a.repeats)]
    fixtures = {fx: measure(a.image, fx, a.repeats, work, a.mem, a.cpus, a.env, binary) for fx in (a.fixtures.split(",") if a.fixtures else sorted(p_.parent.name for p_ in CORPUS.glob("*/source.dwg")))}
    status = json.loads(next(work.glob("*/primary.status.json")).read_text())
    failures = [{"fixture": fx, "cause": m["cause"], "exit_codes": m["exit_codes"], "rate": m["failure_rate"]} for fx, m in fixtures.items() if m["failure_rate"]]
    n = sum(m["repeats"] for m in fixtures.values())
    rep = {
        "schema": "pvec-gold/bench-converter-run/1",
        "arch": arch, "native": insp[1] == containers.PLATFORM.split("/")[1], "emulated": False,
        "host": a.host, "platform": containers.PLATFORM, "docker_arch": insp[1],
        "image": a.image, "image_id": insp[0],
        "converter": a.converter, "converter_version": "%s %s" % (status["product"]["name"], status["product"]["version"]),
        "concurrency": a.concurrency, "licence_limit": limit,
        "limit_note": "an open converter has no licence; the limit is the cap in docker/converter-limits.json",
        "limit_bounded_throughput": a.concurrency >= limit,
        "mem_limit": a.mem, "cpus": a.cpus, "env": a.env, "repeats": a.repeats,
        "noop": dict(stats([r["total"] for r in noop_rows]), inner_s=stats([r["inner"] for r in noop_rows]), exit_codes=sorted({r["rc"] for r in noop_rows})),
        "failure_rate": sum(m["failure_rate"] * m["repeats"] for m in fixtures.values()) / n,
        "load_avg_before": load_before, "load_avg_after": Path("/proc/loadavg").read_text().split()[:3],
        "failures": failures, "fixtures": fixtures,
    }
    Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main(sys.argv[1:])
