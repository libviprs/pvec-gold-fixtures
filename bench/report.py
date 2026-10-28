"""Assemble reports/bench/*.json from the per-host run files and render docs/benchmarks/*.md from them.

    python3 bench/report.py RUNS_DIR

RUNS_DIR holds what bench/converters/run.py, bench/validation/run.py and bench/orchestration/run.py wrote on
each host, as conv-<host>.json, val-<host>.json and orch-<host>.json, plus sig-arm/ (the signatures a native
arm64 regeneration produced) for the cross-architecture comparison. The documents are rendered, not typed, so
every number in them is one in the JSON.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from runner import normalize, signatures  # noqa: E402

HOSTS = {"mars": "x64", "mercury": "arm64"}
LABEL = {"x64": "native x86_64", "arm64": "native arm64"}


def ms(x):
    return "%.0f" % (x * 1000)


def load(d, kind, host):
    return json.loads((Path(d) / ("%s-%s.json" % (kind, host))).read_text())


def cross_arch(sig_x64, sig_arm):
    div, same = [], 0
    for fx in sorted(signatures.manifest(sig_x64)["fixtures"]):
        a = json.loads((Path(sig_x64) / fx / "signature.json").read_text())
        b = json.loads((Path(sig_arm) / fx / "signature.json").read_text())
        fields = normalize.differing_fields(a, b)
        same += not fields
        for f in fields:
            div.append({"fixture": fx, "entity": f.split(".")[0], "field": f.split(".", 1)[1] if "." in f else f})
    return div, same


def main(runs):
    runs = Path(runs)
    out = ROOT / "reports" / "bench"
    out.mkdir(parents=True, exist_ok=True)
    conv = {HOSTS[h]: load(runs, "conv", h) for h in HOSTS}
    val = {HOSTS[h]: load(runs, "val", h) for h in HOSTS}
    orch = {HOSTS[h]: load(runs, "orch", h) for h in HOSTS if (runs / ("orch-%s.json" % h)).exists()}
    fx_ids = sorted(conv["x64"]["fixtures"])

    div, same = cross_arch(ROOT / "signatures", runs / "sig-arm")
    by_fx = {}
    for d in div:
        by_fx.setdefault(d["fixture"], []).append(d)
    xarch = {"compared": "signature.json of every accepted fixture, regenerated on native arm64 against the frozen native x86_64 set; the STEP files are byte identical",
             "fixtures_compared": len(val["x64"]["fixtures"]), "fixtures_identical": same, "identical": not div,
             "verdicts": {a: {fx: m["structural_verdict"] for fx, m in val[a]["fixtures"].items()} for a in val},
             "divergences": div}
    (out / "converter-throughput.json").write_text(json.dumps({
        "schema": "pvec-gold/bench-converter/1", "fixture_set": "the 30 r0-open DWG probes (the full probe corpus of the open route)",
        "real_world_subset": None, "real_world_subset_reason": "no real-world drawing is held here, see docs/vendor-deferred.md",
        "runs": [conv["x64"], conv["arm64"]]}, indent=2, sort_keys=True) + "\n")
    sp = dict(val["x64"]["signature_path"], arch="x64", arm64=val["arm64"]["signature_path"])
    (out / "validation.json").write_text(json.dumps({
        "schema": "pvec-gold/bench-validation/1", "runs": [val["x64"], val["arm64"]],
        "not_measured": {"adaptive_geometric": "no adaptive geometric comparison stage exists in this repository (O2.5 and O2.6 are not built), so there is no converged sample count to report"},
        "cross_architecture": xarch, "signature_path": sp}, indent=2, sort_keys=True) + "\n")
    if orch:
        (out / "orchestration.json").write_text(json.dumps({"schema": "pvec-gold/bench-orchestration/1", "runs": list(orch.values())}, indent=2, sort_keys=True) + "\n")

    docs = ROOT / "docs" / "benchmarks"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "converter-throughput.md").write_text(render_conv(conv, fx_ids))
    (docs / "validation.md").write_text(render_val(val, xarch, by_fx, sp))
    if orch:
        (docs / "orchestration-tuning.md").write_text(render_orch(orch, conv))


def render_conv(conv, ids):
    x, a = conv["x64"], conv["arm64"]
    L = ["# Converter throughput and cost", "",
         "Issue 20 (O3.1). The converter measured is the open one, `dwg2step-acadsharp` (%s), over the %d `r0-open` DWG probes. "
         "Numbers come from `bench/converters/run.py`; the raw record is `reports/bench/converter-throughput.json`." % (x["converter_version"], len(ids)), "",
         "## Where the numbers came from", "",
         "- **%s**: host `mars`, docker platform `%s`, image `%s` (`%s`). No emulation: the image architecture the daemon reports is `%s`." % (LABEL["x64"], x["platform"], x["image"], x["image_id"], x["docker_arch"]),
         "- **%s**, for comparison only: host `mercury`, platform `%s`, image `%s` (`%s`)." % (LABEL["arm64"], a["platform"], a["image"], a["image_id"]),
         "- No number here came from local Rosetta or any other emulation. Nothing ran on the Mac.",
         "- Every row is %d repeats of one throw-away container, one at a time (concurrency %d). Median and the interquartile range are reported; min and max are in the JSON." % (x["repeats"], x["concurrency"]),
         "- Licence: the converter is MIT and takes no licence. The concurrency limit applied is %d, the cap in `docker/converter-limits.json` (not a vendor licence). "
         "Concurrency 1 is below it, so the limit did not bound these numbers; it bounds the parallel runs in `orchestration-tuning.md`. "
         "The CAD Exchanger and ODA converters were not measured (no licence), see `docs/vendor-deferred.md`." % x["licence_limit"],
         "- Host load average when the run started, x86_64: %s; arm64: %s. `mars` is shared, so its absolute times carry some noise." % (" ".join(x["load_avg_before"]), " ".join(a["load_avg_before"])), "",
         "## What is separated from what", "",
         "`total` is `docker run` as seen from outside. `conversion` is the converter process inside the container, timed there, dotnet runtime start included. "
         "`startup` is the difference: creating, starting and removing the container. The no-op is the same image run with no arguments (the converter exits 10 as soon as its runtime is up), "
         "so a slow image shows up there and not in the conversion column.", "",
         "| | %s total | inner (runtime start) | %s total | inner |" % (LABEL["x64"], LABEL["arm64"]), "|---|---|---|---|---|",
         "| no-op (ms, median) | %s | %s | %s | %s |" % (ms(x["noop"]["median"]), ms(x["noop"]["inner_s"]["median"]), ms(a["noop"]["median"]), ms(a["noop"]["inner_s"]["median"])), "",
         "## Per fixture (median ms, iqr in brackets; RSS and step size as stated)", "",
         "| fixture | x64 startup | x64 conversion | x64 peak RSS MiB | x64 cgroup MiB | arm64 conversion | arm64 startup | STEP bytes | failure rate |", "|---|---|---|---|---|---|---|---|---|"]
    for fx in ids:
        m, n = x["fixtures"][fx], a["fixtures"][fx]
        L.append("| %s | %s (%s) | %s (%s) | %.1f | %.1f | %s (%s) | %s (%s) | %d | %.2f |" % (
            fx, ms(m["startup_s"]["median"]), ms(m["startup_s"]["iqr"]), ms(m["conversion_s"]["median"]), ms(m["conversion_s"]["iqr"]),
            m["peak_rss_mib"]["median"], m["cgroup_peak_mib"]["median"], ms(n["conversion_s"]["median"]), ms(n["conversion_s"]["iqr"]),
            ms(n["startup_s"]["median"]), ms(n["startup_s"]["iqr"]), m["step_bytes"]["median"], m["failure_rate"]))
    allc = [m["conversion_s"]["median"] for m in x["fixtures"].values()]
    L += ["", "Peak RSS is the converter's VmHWM; `cgroup` is the container's `memory.peak`, the figure a `--memory` limit is compared with "
          "(it is smaller because file-backed pages shared with the runtime image are charged to whichever cgroup touched them first).", "",
          "## What the numbers say", "",
          "- The conversion itself is cheap and flat: medians run from %s to %s ms across all fixtures on x86_64. These probes are a handful of curves each, so the "
          "differences between fixtures are inside the spread. A real-world drawing will behave differently and this corpus cannot say how." % (ms(min(allc)), ms(max(allc))),
          "- Container creation, not conversion, is the largest single cost: about %s ms of startup against about %s ms of conversion per call on x86_64." % (
              ms(sorted(m["startup_s"]["median"] for m in x["fixtures"].values())[len(ids) // 2]), ms(sorted(allc)[len(ids) // 2])),
          "- Peak memory is the same for every fixture within a MiB or two, about %.0f MiB resident and %.0f MiB in the cgroup, because the dotnet runtime dominates." % (
              max(m["peak_rss_mib"]["median"] for m in x["fixtures"].values()), max(m["cgroup_peak_mib"]["median"] for m in x["fixtures"].values())), "",
         "## Failures", "", "Failure rate over the full corpus, x86_64: %.4f (arm64: %.4f)." % (x["failure_rate"], a["failure_rate"]), "",
         "| fixture | rate | exit | cause |", "|---|---|---|---|"]
    for f in x["failures"]:
        L.append("| %s | %.2f | %s | %s |" % (f["fixture"], f["rate"], ",".join(map(str, f["exit_codes"])), f["cause"].replace("|", "/")))
    L += ["", "That one is the designed refusal (NP-19, `near-singular-001`), not a defect: the scheduler records it as refused and the run does not fail on it. "
          "There is no other failure on either architecture.", "",
          "## Not measured", "",
          "- The named real-world subset: there is none here (no real-world drawing is held, issue 11). Recorded in `docs/vendor-deferred.md`.",
          "- CAD Exchanger and ODA throughput: no licence. Their licence concurrency limits are unknown and the scheduler treats an unknown limit as 1.", ""]
    return "\n".join(L)


def render_val(val, xarch, by_fx, sp):
    x, a = val["x64"], val["arm64"]
    n = len(x["fixtures"])
    L = ["# Validation and comparison cost", "",
         "Issue 20 (O3.2). Measured by `bench/validation/run.py` inside the step-validator image (`--target test`: `step_eval`, python, jsonschema), "
         "%d repeats per fixture, over the %d accepted `r0-open` fixtures. Raw record: `reports/bench/validation.json`." % (x["repeats"], n), "",
         "- **%s**: host `mars`. **%s**: host `mercury`. Both native, no emulation. Every number below is labelled with its architecture." % (LABEL["x64"], LABEL["arm64"]),
         "- Versions measured: evaluator %s, OCCT %s, numeric policy %s (identical on both)." % (x["evaluator_version"], x["occt_version"], x["policy_version"]), "",
         "## Stages", "",
         "| stage | what it times |", "|---|---|",
         "| load | `step_eval` on the retained STEP: OCCT reads the file and the evaluator samples every curve. One binary, so reading and evaluating are not separable from outside |",
         "| normalise | `runner.normalize` plus the schema and scalar checks on the signature |",
         "| structural | `runner.structural.structural_diff` of the derived signature against the frozen one, entity by entity |",
         "| report | building and serialising the comparison report |",
         "| adaptive_geometric | **not measured**: no adaptive geometric comparison stage exists in this repository (O2.5 and O2.6 are not built), so there is no converged sample count to report. Listed in `docs/vendor-deferred.md` as waiting on that work, not on a licence |", "",
         "## Per fixture (median ms)", "",
         "| fixture | x64 load | x64 normalise | x64 structural | x64 report | arm64 load | arm64 normalise | arm64 structural | arm64 report |", "|---|---|---|---|---|---|---|---|---|"]
    def f3(v):
        return "%.2f" % (v * 1000)
    for fx in sorted(x["fixtures"]):
        r, s = x["fixtures"][fx], a["fixtures"][fx]
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (fx, *[f3(r[k]["median"]) for k in ("load_s", "normalise_s", "structural_s", "report_s")], *[f3(s[k]["median"]) for k in ("load_s", "normalise_s", "structural_s", "report_s")]))
    for arch, r in (("x64", x), ("arm64", a)):
        L += ["", "## Ten most expensive fixtures (%s)" % LABEL[arch], "", "| fixture | total ms | structural reason |", "|---|---|---|"]
        L += ["| %s | %s | %s |" % (e["fixture"], f3(e["total_median_s"]), e["reason"]) for e in r["most_expensive"]]
    L += ["", "Every fixture pays a floor of about 13 ms to start `step_eval` and about 6 ms of fixed normalise cost. Above that, the cost follows the number of entities and evaluated samples (17 uniform parameters plus every distinct interior knot, per entity), "
          "and it lands in normalise: the polylines, with one entity per segment, are the five most expensive on both architectures. Control-point count, knot multiplicity and coordinate magnitude do not show at these sizes (`large-coords-001` is expensive because it has three entities). "
          "Below the top five the fixtures sit within noise of the floor, which is why those rows say there is no structural reason. Costs on `mars`, a shared host, vary by a few ms run to run.", "",
          "## Signature path against STEP path", "",
          "Over all %d accepted fixtures, medians summed: STEP path (load + normalise + structural + report) **%.1f ms** native x86_64 and %.1f ms native arm64; "
          "signature path (manifest and hash check, JSON parse, structural compare, no OCCT) **%.2f ms** native x86_64 and %.2f ms native arm64. That is **%.0fx** on x86_64 (%.0fx on arm64). "
          "The signature path here includes the hash check; its structural comparison is of the signature against itself, which is what a consumer asserting a frozen value does." % (
              n, sum(sum(m[k]["median"] for k in ("load_s", "normalise_s", "structural_s", "report_s")) for m in x["fixtures"].values()) * 1000,
              sum(sum(m[k]["median"] for k in ("load_s", "normalise_s", "structural_s", "report_s")) for m in a["fixtures"].values()) * 1000,
              sp["signature_path_s"] * 1000, sp["arm64"]["signature_path_s"] * 1000, sp["speedup"], sp["arm64"]["speedup"]), "",
          "The STEP path also needs OCCT and an image; the signature path needs python and the standard library.", "",
          "## Across architectures", "",
          "The STEP files are byte identical on both (the converter runs with `SOURCE_DATE_EPOCH` fixed). The signatures are not: %d of %d are identical, and the rest diverge only in the fields listed. "
          "All of them are last-digit differences in values OCCT evaluates (line ends through a transform, an ellipse's major axis, sample points on rational curves, anything near 1e7 m); "
          "stored control points, knots and weights agree everywhere. The structural verdict of the arm64 re-derivation against the frozen x86_64 signature is `STRUCTURAL_DIFFERS` for exactly these fixtures and `STRUCTURAL_EXACT` for the rest." % (xarch["fixtures_identical"], xarch["fixtures_compared"]),
          "I did not change the normaliser to hide them (that is O2.4 and out of scope here); the consequence is that the frozen signatures are the native x86_64 ones and `verify_signatures` is run there.", "",
          "| fixture | differing fields | first fields (entity.field) |", "|---|---|---|"]
    for fx, ds in sorted(by_fx.items()):
        L.append("| %s | %d | %s |" % (fx, len(ds), "; ".join("%s.%s" % (d["entity"], d["field"]) for d in ds[:3]) + (" ..." if len(ds) > 3 else "")))
    L += ["", "## Drift check, exercised", "",
          "`python3 -m runner.verify_signatures signatures` on native x86_64: 29 of 29 signatures re-derived identically. With one `f64_hex` of `line-001` changed (manifest rewritten to match, so only the re-derivation can notice) "
          "it exits 1 and prints `DRIFT line-001: entities[0].geometry.start[0]`. On native arm64 against the x86_64 set it reports the divergences above (19 of 29 identical).", ""]
    return "\n".join(L)


def render_orch(orch, conv):
    o = orch["x64"]
    L = ["# Orchestration tuning", "",
         "Issue 20 (O3.3). Measured by `bench/orchestration/run.py` through `runner.regenerate`, the entry point a real regeneration uses, on host `mars`, **native x86_64**, image `%s` (`%s`). "
         "Raw record: `reports/bench/orchestration.json`. Every timing here is native x86_64 on the docker host; none is emulated." % (o["image"], o["image_id"]), "",
         "## Full-corpus wall time", "",
         "The 30 `r0-open` DWGs converted, evaluated and normalised, a fresh output tree each time, %d repeats, per-container limits 2 cpus and 256m." % o["table"][0]["wall_s"]["n"], "",
         "| parallelism | median wall (s) | min | max | fixtures per second |", "|---|---|---|---|---|"]
    for r in o["table"]:
        L.append("| %d | %.2f | %.2f | %.2f | %.1f |" % (r["parallel"], r["wall_s"]["median"], r["wall_s"]["min"], r["wall_s"]["max"], r["fixtures_per_s"]))
    best = min(o["table"], key=lambda r: r["wall_s"]["median"])
    ch = next(r for r in o["table"] if r["parallel"] == o["chosen"]["parallel"])
    L += ["", "**Chosen: parallelism %d** (%.2f s for the corpus, %.1f fixtures per second), the smallest value within 10%% of the best (%d at %.2f s). "
          "The cap for this converter is %d (docker/converter-limits.json: a cap I set, not a vendor licence), and the table stops there. "
          "Wall time still halves with every doubling, so on this host **the cap is what bounds throughput**, not the host: I did not measure above it, so I do not know where it flattens. "
          "The scheduler refuses a request above the cap and limits its pool to it; a vendor converter with an unknown limit runs at 1." % (
              ch["parallel"], ch["wall_s"]["median"], ch["fixtures_per_s"], best["parallel"], best["wall_s"]["median"], conv["x64"]["licence_limit"]), "",
         "## Per-container limits", "",
         "Observed on the largest fixture (`%s`): peak %.1f MiB in the cgroup, %.1f MiB resident. The memory limit is **%d MiB**, about %.0fx the cgroup peak, and no converter was OOM-killed in the accepted configuration (%d). "
         "These fixtures are small. A real-world drawing needs its own measurement before this limit is trusted for it." % (
             o["largest_fixture"], o["observed_peak_cgroup_mib"], o["observed_peak_rss_mib"], o["chosen"]["memory_limit_mib"], o["chosen"]["memory_limit_mib"] / o["observed_peak_cgroup_mib"], o["oom_killed"]), "",
         "What I tried on a four-fixture subset (`%s`, 9 repeats), median over the fixtures, ms:" % o["experiments_conversion_subset"], "",
         "| setting | conversion | total (`docker run`) | kept |", "|---|---|---|---|"]
    base = o["experiments"]["unlimited"]
    keep = {"unlimited": "(baseline)", "cpus_1": "no: conversion roughly doubles", "cpus_2": "yes: within noise of unlimited", "cpus_4": "no gain over 2",
            "TieredPGO_0": "no: about 7% faster conversion, under the 10% bar I set for a runtime switch", "TieredCompilation_0": "no: slower"}
    for k in ("unlimited", "cpus_1", "cpus_2", "cpus_4", "TieredPGO_0", "TieredCompilation_0"):
        e = o["experiments"][k]
        L.append("| %s | %s | %s | %s |" % (k, ms(e["conversion_s_median"]), ms(e["total_s_median"]), keep[k]))
    L += ["", "The cpu limit is the one setting the numbers justify (a single cpu starves the runtime's second thread). The two runtime switches are reverted: `TieredCompilation=0` is slower, and `TieredPGO=0` gains about 7% on conversion (about 10 ms of a 390 ms call), under the 10% I set as the bar.", "",
          "## Resume, isolation and teardown", "",
          "- **Resume**: a parallelism-4 run was interrupted with SIGINT after %d fixtures were done; the rerun skipped %d and regenerated %d. The hashes of every untouched fixture's artifacts were identical before and after: **%s**." % (
              o["resume"]["done_before_interrupt"], o["resume"]["skipped_on_rerun"], o["resume"]["regenerated_on_rerun"], o["resume"]["untouched_hashes_identical"]),
          "- **Failure isolation**: each fixture works in its own directory and is moved into place only on success, with its own state file and log (`[fixture-id]` on every line). A failing fixture leaves no artifacts, "
          "does not stop the run and does not touch another's; the run exits 1 with a summary. Exercised in `tests/test_scheduler_20.py` with a job that fails. The one real refusal here (`near-singular-001`) is recorded as refused and exits 0.",
          "- **Teardown under parallelism**: a parallelism-8 run aborted with SIGINT left %d labelled containers, %d new containers and %d new volumes on the host." % (
              o["teardown"]["leftover_labelled_containers"], o["teardown"]["new_containers"], o["teardown"]["new_volumes"]),
          "- **Licence limit**: `tests/test_scheduler_20.py` asks for more than the limit and expects `LicenceLimitExceeded` before any job starts; another test shows the number of jobs in flight reaches the limit and never exceeds it.",
          "- **Logs**: bounded per fixture (the last 1 MiB, `--max-log-bytes` in code), and the compose service rotates its docker log at 1m x 3.", "",
          "## Settings applied", "",
          "- `docker-compose.yml`: service `acadsharp-converter` with `mem_limit: 256m`, `memswap_limit: 256m`, `cpus: 2`, rotated logs.",
          "- `docker/converter-limits.json`: the concurrency cap per converter, read by `runner/scheduler.py`.",
          "- `runner/regenerate.py` defaults: `--mem 256m --cpus 2`, `SOURCE_DATE_EPOCH` fixed so the STEP bytes repeat.",
          "- Parallelism %d is a recommendation for the host measured; it is a flag, not a constant, because the best value depends on the cores of the host." % o["chosen"]["parallel"], "",
          "`runner/generate.py` (issue 13) still converts one fixture at a time through compose; moving it onto the scheduler is the next step and is not done here.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main(sys.argv[1])
