"""A writer family beyond acadrust: write the r0-open probes with another open DWG writer, read them back with
three readers, and assemble corpus/writers/<family>.

    python3 -m runner.writer_family assemble BASE_DIR CORPUS_DIR --info FILE
    python3 -m runner.writer_family check CORPUS_DIR

The rule is the r0-open cross-read rule (runner/r0_open.py) with one more reader: a fixture is AGREE only if
every reader matches the authored truth and every reader decodes the same record as the first one. Anything else
quarantines the probe with the fields that differ (ADR 0006). The authored records and parameter files are the
ones r0-open uses, copied into the corpus and pinned by hash, so nothing here moves a number.

BASE_DIR is what tools/corpus/writer-<family>/run.sh pulls back: run1 (the DWGs written with the
stamped header fields pinned, their read records and write-report.json), run2 (the same again), raw1 and raw2 (the
same twice with the fields as the writer stamps them) and leave-<field> (one fixture with one stamped field left raw).
"""
import json
import sys
from pathlib import Path

from . import numeric
from .r0_open import (CAPABILITIES_OF, NO_CAPABILITY, ROOT, SCOPE, STATEMENT, diff, dump_json, downstream_disposition,
                      expected_path, honesty_problems, judge, load_json, params_group, params_path, sha256, strip)


def verdict(pol, fid, writer, own, records, corpus=None):
    """records maps reader name to its read record, or to None when that reader could not open the file. The
    reader named own is the writer family's own reader; every other record is compared with it."""
    res = {"checks": {}, "reader_vs_reader_differences": {}}
    missing = sorted(n for n, r in records.items() if r is None)
    if missing:
        res["verdict"], res["reason"] = "UNREADABLE", "MALFORMED_FIXTURE"
        res["evidence"] = "a reader could not open the DWG: " + ", ".join(missing)
        return res
    bad = []
    for name in sorted(records):
        c = judge(pol, fid, records[name], corpus)
        res["checks"][name] = c.items
        if not c.ok:
            bad.append("%s differs from the authored truth at: %s" % (name, ", ".join(i["field"] for i in c.items if not i["ok"])[:300]))
    for name in sorted(n for n in records if n != own):
        d = diff(strip(records[own]), strip(records[name]))
        if d:
            res["reader_vs_reader_differences"]["%s vs %s" % (own, name)] = d
            bad.append("%s and %s decoded different records at: %s" % (own, name, ", ".join(d)[:300]))
    if bad:
        res["verdict"], res["reason"], res["evidence"] = "DISAGREE", "UNRESOLVED_DISAGREEMENT", "; ".join(bad)
    else:
        res["verdict"], res["reason"], res["evidence"] = "AGREE", None, None
    return res


def comparison_doc(pol, fid, v):
    return {"fixture_id": fid, "numeric_policy_version": pol.version, **v}


def measure_determinism(base):
    """Count identical and differing DWGs between two runs, raw and with the stamped header fields pinned, and name
    the fields that change the bytes when left raw. Reads files only."""
    base = Path(base)

    def compare(a, b):
        ids = sorted(p.parent.name for p in (base / a).glob("*/source.dwg"))
        same = sum((base / a / i / "source.dwg").read_bytes() == (base / b / i / "source.dwg").read_bytes() for i in ids)
        return {"runs": 2, "compared": len(ids), "identical": same, "differing": len(ids) - same}

    pinned = (base / "run1" / "arc-seam-001" / "source.dwg").read_bytes()
    leave = {p.name[len("leave-"):]: (p / "arc-seam-001" / "source.dwg").read_bytes() != pinned for p in sorted(base.glob("leave-*"))}
    return {
        "raw": compare("raw1", "raw2"),
        "pinned_header": compare("run1", "run2"),
        "header_fields_that_differ": sorted(k for k, v in leave.items() if v),
        "header_fields_without_effect_in_this_measurement": sorted(k for k, v in leave.items() if not v),
        "measured_on": "arc-seam-001, with every stamped field pinned except the one named (the raw and pinned_header runs cover all fixtures)",
    }


def readme(fid, writer, v, dwg_version, readers, disposition):
    status = "accepted" if v["verdict"] == "AGREE" else "quarantined (%s)" % v["reason"]
    extra = ""
    if disposition:
        extra = ("\nThis probe's authored truth also says it must be rejected downstream: %s. Accepting it here means only "
                 "that the DWG carries the transform exactly as authored. Do not feed it to a mapper expecting a curve.\n" % disposition)
    return (
        "# %s\n\n"
        "This is a probe of the %s writer family, and it is %s.\n\n"
        "`source.dwg` was written by %s as %s, from the authored parameters of the r0-open probe record. The truth is "
        "`expected.math.json` beside it (a copy, pinned by hash to the canonical record), which I authored before any DWG "
        "existed and which this corpus never edits. No expected value comes from a DWG, a STEP file or any converter.\n\n"
        "I had it read back by %s. The read records are kept beside the DWG (`read.*.json`), and `comparison.json` lists "
        "every field checked, whether it was compared EXACT or under PVec numeric policy v1, and the verdict.\n\n"
        "What this says: the DWG carries the authored mathematics as three open readers decode it. What it does not say: "
        "there is no STEP oracle here, and the readers share a DWG specification, so a shared misreading of it would not "
        "show.\n%s"
    ) % (fid, writer.split("@")[0], status, writer, dwg_version, ", ".join(r["reader"] for r in readers), extra)


def write_sums(corpus):
    corpus = Path(corpus)
    names = sorted(str(p.relative_to(corpus)) for p in corpus.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (corpus / "SHA256SUMS").write_text("".join("%s  %s\n" % (sha256(corpus / n), n) for n in names))
    return names


def assemble(base, corpus, info):
    pol = numeric.load_policy()
    base, corpus = Path(base), Path(corpus)
    raw = base / "run1"
    rep = load_json(raw / "write-report.json")
    writer, dwg_version = rep["writer"], rep["dwg_version"]
    readers = info["readers"]
    own = info["own_reader"]
    fixtures, excluded, quarantined = [], [], []
    for item in rep["fixtures"]:
        fid = item["id"]
        if item["status"] == "SKIPPED":
            excluded.append({"id": fid, "reason": item["reason"], "evidence": item["evidence"], "file": None})
            continue
        src, out = raw / fid, corpus / "fixtures" / fid
        out.mkdir(parents=True, exist_ok=True)
        (out / "source.dwg").write_bytes((src / "source.dwg").read_bytes())
        (out / "expected.math.json").write_bytes(expected_path(fid).read_bytes())
        (out / "params.json").write_bytes(params_path(fid).read_bytes())
        records = {}
        for r in readers:
            f = src / r["file"]
            records[r["name"]] = load_json(f) if f.exists() else None
            if records[r["name"]] is not None:
                dump_json(records[r["name"]], out / ("read.%s.json" % r["name"].lower()))
        v = verdict(pol, fid, writer, own, records, corpus)
        dump_json(comparison_doc(pol, fid, v), out / "comparison.json")
        exp = load_json(out / "expected.math.json")
        disp = downstream_disposition(exp)
        (out / "README.md").write_text(readme(fid, writer, v, dwg_version, readers, disp))
        accepted = v["verdict"] == "AGREE"
        caps = CAPABILITIES_OF.get(fid, [])
        entry = {
            "id": fid,
            "group": params_group(fid),
            "capabilities": caps,
            "evidence_class": "KNOWN_TRUTH_EXACT" if accepted else "QUARANTINED",
            "evidence_scope": SCOPE,
            "oracles": "none",
            "status": "ACCEPTED" if accepted else "QUARANTINED",
            "provenance": "SYNTHETIC_AUTHORED",
            "licence_verdict": "PUBLIC_REDISTRIBUTABLE",
            "dwg": {"path": "fixtures/%s/source.dwg" % fid, "sha256": sha256(out / "source.dwg"), "dwg_version": dwg_version, "writer": writer},
            "expected": {"path": "fixtures/%s/expected.math.json" % fid, "sha256": sha256(out / "expected.math.json"), "canonical_path": str(expected_path(fid).relative_to(ROOT))},
            "parameter_file": {"path": "fixtures/%s/params.json" % fid, "sha256": sha256(out / "params.json"), "canonical_path": str(params_path(fid).relative_to(ROOT))},
            "reads": [{"name": r["name"], "reader": records[r["name"]]["reader"] if records[r["name"]] else r["reader"],
                       "record": "fixtures/%s/read.%s.json" % (fid, r["name"].lower()),
                       "sha256": sha256(out / ("read.%s.json" % r["name"].lower())) if records[r["name"]] else None} for r in readers],
            "cross_read": {"verdict": v["verdict"]},
            "comparison": {"path": "fixtures/%s/comparison.json" % fid, "sha256": sha256(out / "comparison.json")},
        }
        if not caps:
            entry["capabilities_note"] = NO_CAPABILITY.get(fid, "no PVec v1 capability is exercised")
        if disp:
            entry["downstream_disposition"] = disp
        if not accepted:
            entry["quarantine"] = {"reason": v["reason"], "evidence": v["evidence"]}
            quarantined.append({"id": fid, "reason": v["reason"], "evidence": v["evidence"]})
        fixtures.append(entry)
    fixtures.sort(key=lambda f: f["id"])
    excluded.sort(key=lambda f: f["id"])
    manifest = {
        "schema_version": "pvec-gold/writer-family-manifest/1",
        "writer_family": info["family"],
        "of_corpus": "r0-open",
        "status": "CANDIDATE",
        "oracles": "none",
        "step_oracle": "none",
        "evidence_scope": SCOPE,
        "evidence_statement": STATEMENT.replace("two independent open readers", "three open readers"),
        "adr": "docs/adr/0008-open-writer-known-truth-corpus.md",
        **numeric.policy_stamp(pol),
        "writer": writer,
        "writer_source": info["writer_source"],
        "own_reader": own,
        "readers": [{"name": r["name"], "reader": r["reader"], "source": r["source"], "role": r["role"]} for r in readers],
        "dwg_version": dwg_version,
        "container_images": info["images"],
        "determinism": measure_determinism(base),
        "self_contained": "this directory holds every DWG, every read record and a hash-pinned copy of each authored record and parameter file; nothing outside it is needed to run `check`",
        "fixtures": fixtures,
    }
    dump_json(manifest, corpus / "manifest.json")
    dump_json({"writer_family": info["family"], "quarantined": quarantined, "excluded": excluded}, corpus / "quarantine.json")
    write_sums(corpus)
    return manifest


def check(corpus):
    """Recompute every verdict, and every comparison.json, from the stored read records. No DWG library, no
    converter, no Docker."""
    pol = numeric.load_policy()
    corpus = Path(corpus)
    m = load_json(corpus / "manifest.json")
    problems = []
    if m.get("numeric_policy_version") != pol.version:
        problems.append("numeric policy version differs from the vendored policy")
    sums = {}
    for line in (corpus / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
        if not (corpus / name).is_file() or sha256(corpus / name) != digest:
            problems.append("SHA256SUMS mismatch: " + name)
    for p in sorted(corpus.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS" and str(p.relative_to(corpus)) not in sums:
            problems.append("file not covered by SHA256SUMS: " + str(p.relative_to(corpus)))
    problems += honesty_problems(corpus)
    own = m["own_reader"]
    for f in m["fixtures"]:
        fid = f["id"]
        d = corpus / "fixtures" / fid
        if sha256(corpus / f["dwg"]["path"]) != f["dwg"]["sha256"]:
            problems.append("%s: source.dwg bytes differ from the manifest dwg.sha256" % fid)
        if f["dwg"]["writer"] != m["writer"]:
            problems.append("%s: the fixture names a different writer from the manifest" % fid)
        for key in ("expected", "parameter_file", "comparison"):
            if sha256(corpus / f[key]["path"]) != f[key]["sha256"]:
                problems.append("%s: %s differs from the manifest hash" % (fid, f[key]["path"]))
        for key in ("expected", "parameter_file"):
            canon = ROOT / f[key]["canonical_path"]
            if canon.is_file() and sha256(canon) != f[key]["sha256"]:
                problems.append("%s: the canonical %s changed since the corpus was assembled" % (fid, f[key]["canonical_path"]))
        records = {}
        for r in f["reads"]:
            if r["sha256"] is None:
                records[r["name"]] = None
                continue
            if sha256(corpus / r["record"]) != r["sha256"]:
                problems.append("%s: %s record differs from the manifest hash" % (fid, r["name"]))
            records[r["name"]] = load_json(corpus / r["record"])
            if records[r["name"]]["dwg_sha256"] != f["dwg"]["sha256"]:
                problems.append("%s: the %s record is for a different DWG" % (fid, r["name"]))
        v = verdict(pol, fid, m["writer"], own, records, corpus)
        if v["verdict"] != f["cross_read"]["verdict"]:
            problems.append("%s: recomputed verdict %s, manifest says %s" % (fid, v["verdict"], f["cross_read"]["verdict"]))
        if load_json(d / "comparison.json") != json.loads(json.dumps(comparison_doc(pol, fid, v))):
            problems.append("%s: comparison.json differs from the comparison recomputed from the read records" % fid)
    return problems


def main(argv):
    if len(argv) >= 3 and argv[0] == "assemble":
        info = load_json(argv[argv.index("--info") + 1])
        mf = assemble(argv[1], argv[2], info)
        print("assembled %d fixtures: %d accepted" % (len(mf["fixtures"]), sum(f["status"] == "ACCEPTED" for f in mf["fixtures"])))
        return 0
    if len(argv) == 2 and argv[0] == "check":
        problems = check(argv[1])
        for p in problems:
            print("FAIL", p)
        print("writer family check: %s" % ("FAILED" if problems else "ok"))
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
