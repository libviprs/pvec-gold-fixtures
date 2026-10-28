"""r2-open: the first STEP_ORACLE revision, built from a two-converter `runner.generate` run (#78).

    python3 -m runner.r2_open stage OUT                       lay out OUT/fixtures/<id>/source.dwg and OUT/truth/<id>/expected.math.json
    python3 -m runner.r2_open run OUT [--label L]             stage, generate twice, compare, build corpus/r2-open and the release
    python3 -m runner.r2_open verify RELEASE_DIR              check a release against its own SHA256SUMS and pins

`run` is what tools/clean_host_r2.sh runs inside a driver container on a throw-away docker daemon. Fixtures are the
union of the r1-open manifest (which lists r0-open's too) and the r0-open manifest. Every fixture is converted by
the primary and the secondary converter (ADR 0009, 0010), and what the run saw decides whether its evidence moved
(decide). A fixture whose result does not back a move keeps its class and scope and the reason is recorded: nothing
is promoted on a hope. STEP is stored with the FILE_NAME time stamp replaced, signatures as written.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import step_normalise

ROOT = Path(__file__).resolve().parent.parent
REVISION = "r2-open"
BEGIN, END = "<!-- r2-open-moves -->", "<!-- /r2-open-moves -->"
ROLES = ("primary", "secondary")
BY_DESIGN = "QUARANTINED"
REJECTION_SCOPES = ("REJECTION_EXPECTED", "CLASSIFICATION_EXPECTED")


class Refused(Exception):
    pass


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load(p):
    return json.loads(Path(p).read_text())


def dump(doc):
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


# ---- the fixture set -------------------------------------------------------------------------

def fixture_entries(root):
    """Accepted manifest entries by id. r1-open lists r0-open's fixtures too; r0-open's own entries fill any gap."""
    root = Path(root)
    out = {}
    r0 = root / "corpus" / "r0-open" / "manifest.json"
    if r0.is_file():
        for f in load(r0)["fixtures"]:
            e = dict(f)
            e["artifacts"] = {Path(e["dwg"]["path"]).name: {"path": "corpus/r0-open/" + e["dwg"]["path"], "sha256": e["dwg"]["sha256"]}}
            if "expected" in e:
                e["artifacts"]["expected.math.json"] = {"path": "corpus/r0-open/" + e["expected"]["path"], "sha256": e["expected"]["sha256"]}
            out[e["id"]] = e
    r1 = root / "corpus" / "r1-open" / "manifest.json"
    if r1.is_file():
        for f in load(r1)["fixtures"]:
            out[f["id"]] = f
    return {i: e for i, e in sorted(out.items()) if e.get("status") == "ACCEPTED"}


def stage(root, out):
    root, out = Path(root), Path(out)
    ids = []
    for fid, e in fixture_entries(root).items():
        a = e["artifacts"]["source.dwg"]
        src = root / a["path"]
        if not src.is_file() or sha(src.read_bytes()) != a["sha256"]:
            raise Refused("%s: source.dwg is missing or does not match the manifest hash" % fid)
        (out / "fixtures" / fid).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / "fixtures" / fid / "source.dwg")
        t = e["artifacts"].get("expected.math.json")
        if t:
            (out / "truth" / fid).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / t["path"], out / "truth" / fid / "expected.math.json")
        ids.append(fid)
    return sorted(ids)


# ---- what a run saw, and what it means -------------------------------------------------------

def observe(gen):
    gen = Path(gen)
    verdict = load(gen / "verdict.json")
    refused, errors = {}, {}
    for r in ROLES:
        refused[r] = not (gen / (r + ".step")).is_file()
        st = gen / (r + ".status.json")
        errors[r] = ((load(st).get("error") or {}).get("class", "") if st.is_file() and refused[r] else "")
    return {"verdict": verdict, "refused": refused, "errors": errors}


def decide(entry, obs):
    """(fields to overwrite on the entry, the move record). The rules are in the module docstring and tested."""
    cls, scope = entry["evidence_class"], entry["evidence_scope"]
    v = obs["verdict"]
    refused = obs["refused"]
    both_refused = all(refused.values())
    f = {"oracle_scope": "OPEN_CONVERTERS", "evidence_class": cls, "evidence_scope": scope}
    why = ""
    if cls == BY_DESIGN:
        failures = [r for r in ROLES if not refused[r]]
        f["converter_failures"] = failures
        if both_refused:
            f["evidence_scope"] = "STEP_ORACLE"
        else:
            why = "%s converter drew geometry for a fixture that should be refused" % " and ".join(failures)
    elif entry.get("downstream_disposition"):
        if both_refused:
            f["evidence_scope"] = "STEP_ORACLE"
        else:
            why = "authored outcome is a rejection and %s did not refuse" % " and ".join(r for r in ROLES if not refused[r])
    elif cls == "REAL_WORLD_DIFFERENTIAL":
        if v["evidence_class"] == "DUAL_ORACLE_EQUIVALENT":
            f.update(evidence_class="DUAL_ORACLE_EQUIVALENT", evidence_scope="STEP_ORACLE")
        else:
            bits = ["%s: %s" % (r, obs["errors"][r] or "refused") for r in ROLES if refused[r]]
            why = "%s%s" % (v.get("reason") or v["evidence_class"], " (%s)" % "; ".join(bits) if bits else "")
    elif v["evidence_class"] == cls:
        f["evidence_scope"] = "STEP_ORACLE"
    else:
        why = "%s%s" % (v.get("reason") or v["evidence_class"], (": " + v["detail"]) if v.get("detail") else "")
    move = {"id": entry["id"], "from": [cls, scope], "to": [f["evidence_class"], f["evidence_scope"]], "why": why}
    return f, move


# ---- the revision ----------------------------------------------------------------------------

def read_runs(root, runs, ids):
    infos = {}
    for fid in ids:
        d = Path(runs) / fid
        if not (d / "verdict.json").is_file() or not (d / "manifest.json").is_file():
            raise Refused("%s has no generated verdict and manifest in %s" % (fid, runs))
        infos[fid] = load(d / "manifest.json")
    return infos


def common_setup(infos):
    first = None
    for fid, m in infos.items():
        setup = {"converters": [{k: c[k] for k in ("role", "service", "id", "version", "lineage", "image", "image_digest", "platform")} for c in m["converters"]],
                 "validator": m["validator"], "numeric_policy_version": m["numeric_policy_version"]}
        for c in setup["converters"]:
            if not str(c["image_digest"] or "").startswith("sha256:"):
                raise Refused("%s: converter %s has no image digest" % (fid, c["service"]))
        if not str(setup["validator"].get("image_digest") or "").startswith("sha256:"):
            raise Refused("%s: the validator has no image digest" % fid)
        if first is None:
            first = setup
        elif setup != first:
            raise Refused("%s ran with different images or policy than the other fixtures" % fid)
    if len({c["lineage"] for c in first["converters"]}) < 2:
        raise Refused("the two converters share a lineage")
    return first


def build(root, runs, out, setup_extra=None):
    root, runs, out = Path(root), Path(runs), Path(out)
    entries = fixture_entries(root)
    infos = read_runs(root, runs, list(entries))
    setup = common_setup(infos)
    versions = {k: next((m.get(k) for m in infos.values() if m.get(k)), None) for k in ("evaluator_version", "occt_version")}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    fixtures, moves = [], []
    for fid, e in entries.items():
        gen = runs / fid
        o = observe(gen)
        fields, move = decide(e, o)
        e2 = {k: v for k, v in e.items()}
        e2["previous"] = {"evidence_class": e["evidence_class"], "evidence_scope": e["evidence_scope"], "oracle_scope": e.get("oracle_scope")}
        e2.update(fields)
        e2["step_oracle"] = {"verdict": o["verdict"]["evidence_class"], "reason": o["verdict"].get("reason"), "refused": o["refused"],
                             "errors": o["errors"], "signature_differences": o["verdict"].get("signature_differences", [])}
        gdir = out / "fixtures" / fid
        gdir.mkdir(parents=True)
        gen_arts = {}
        for n in ("primary.step", "secondary.step", "primary.signature.json", "secondary.signature.json", "verdict.json"):
            if (gen / n).is_file():
                data = (gen / n).read_bytes()
                if n.endswith(".step"):
                    data = step_normalise.normalise(data.decode("utf-8")).encode("utf-8")
                (gdir / n).write_bytes(data)
                gen_arts[n] = {"path": "fixtures/%s/%s" % (fid, n), "sha256": sha(data)}
        e2["generated"] = gen_arts
        fixtures.append(e2)
        moves.append(move)
    r1 = root / "corpus" / "r1-open" / "manifest.json"
    r0 = root / "corpus" / "r0-open" / "manifest.json"
    m = {"schema_version": "pvec-gold/corpus-manifest/2", "corpus_revision": REVISION, "status": "CANDIDATE",
         "oracle_scope": "OPEN_CONVERTERS", "adr": "docs/adr/0010-open-source-only.md",
         "numeric_policy_version": setup["numeric_policy_version"], "converters": setup["converters"], "validator": setup["validator"],
         "evaluator_version": versions["evaluator_version"], "occt_version": versions["occt_version"],
         "includes": {"r1-open": {"manifest_sha256": sha(r1.read_bytes())} if r1.is_file() else None,
                      "r0-open": {"manifest_sha256": sha(r0.read_bytes())} if r0.is_file() else None},
         "step_note": "primary.step and secondary.step are stored with the FILE_NAME time stamp replaced by <TIMESTAMP>",
         "fixtures": fixtures, "moves": moves}
    (out / "manifest.json").write_text(dump(m))
    write_sums(out)
    return m


def write_sums(d):
    d = Path(d)
    names = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (d / "SHA256SUMS").write_text("".join("%s  %s\n" % (sha((d / n).read_bytes()), n) for n in names))


def verify_sums(d):
    d = Path(d)
    bad, listed = [], set()
    for line in (d / "SHA256SUMS").read_text().splitlines():
        h, n = line.split("  ", 1)
        listed.add(n)
        if not (d / n).is_file() or sha((d / n).read_bytes()) != h:
            bad.append(n)
    for p in d.rglob("*"):
        if p.is_file() and p.name != "SHA256SUMS" and str(p.relative_to(d)) not in listed:
            bad.append(str(p.relative_to(d)))
    return sorted(bad)


# ---- the changelog block ---------------------------------------------------------------------

def render_moves(m):
    moved = [x for x in m["moves"] if x["from"] != x["to"]]
    held = [x for x in m["moves"] if x["from"] == x["to"] and x["why"]]
    confirmed = len(m["moves"]) - len(moved) - len(held)
    lines = ["Run counts: %d fixtures, %d changed class or scope, %d kept with a reason, %d unchanged." % (len(m["moves"]), len(moved), len(held), confirmed), ""]
    if moved:
        lines += ["| fixture | from | to |", "|---|---|---|"]
        lines += ["| `%s` | %s / %s | %s / %s |" % (x["id"], x["from"][0], x["from"][1], x["to"][0], x["to"][1]) for x in moved]
        lines.append("")
    if held:
        lines += ["Kept as they were, with the reason the run gave:", ""]
        lines += ["- `%s` (%s / %s): %s" % (x["id"], x["from"][0], x["from"][1], x["why"]) for x in held]
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def changelog_block(text):
    a, b = text.index(BEGIN), text.index(END)
    return text[a + len(BEGIN):b].strip("\n") + "\n"


def write_changelog(root, m):
    p = Path(root) / "corpus" / "CHANGELOG.md"
    text = p.read_text()
    a, b = text.index(BEGIN), text.index(END)
    p.write_text(text[:a + len(BEGIN)] + "\n" + render_moves(m) + text[b:])


# ---- the release -----------------------------------------------------------------------------

def release(corpus, rel, name):
    corpus, rel = Path(corpus), Path(rel)
    m = load(corpus / "manifest.json")
    if rel.exists():
        shutil.rmtree(rel)
    for sub in ("signatures", "step", "verdicts"):
        (rel / sub).mkdir(parents=True)
    conv = [c["id"] for c in m["converters"]]
    ids = dict(zip(ROLES, conv))
    pins = {"signatures": {}, "step_hashes": {}, "verdicts": {}, "source_hashes": {}, "refused": {}}
    for e in m["fixtures"]:
        fid = e["id"]
        pins["source_hashes"][fid] = e["artifacts"]["source.dwg"]["sha256"]
        private = e.get("licence_verdict") == "PRIVATE"
        for role, cid in ids.items():
            if e["step_oracle"]["refused"][role]:
                pins["refused"].setdefault(fid, {})[cid] = e["step_oracle"]["errors"][role] or "refused"
                continue
            if private:
                continue
            for kind, ext, sub in (("signatures", ".signature.json", "signatures"), ("step_hashes", ".step", "step")):
                src = corpus / e["generated"][role + (".step" if kind == "step_hashes" else ".signature.json")]["path"]
                dst = rel / sub / ("%s.%s%s" % (fid, cid, ext))
                shutil.copyfile(src, dst)
                pins[kind].setdefault(fid, {})[cid] = sha(dst.read_bytes())
        if not private:
            dst = rel / "verdicts" / (fid + ".verdict.json")
            shutil.copyfile(corpus / e["generated"]["verdict.json"]["path"], dst)
            pins["verdicts"][fid] = sha(dst.read_bytes())
    doc = {"schema_version": "pvec-gold/release-manifest/2", "release": name, "status": "FROZEN_CANDIDATE_NOT_TAGGED",
           "pins": dict(pins, corpus={"revision": REVISION, "manifest_sha256": sha((corpus / "manifest.json").read_bytes())},
                        converters=m["converters"], validator=m["validator"], numeric_policy=m["numeric_policy_version"],
                        evaluator={"evaluator": m["evaluator_version"], "occt": m["occt_version"]}),
           "step_hash_note": "sha256 of the STEP text with the FILE_NAME time stamp replaced by <TIMESTAMP>"}
    (rel / "manifest.json").write_text(dump(doc))
    notes = ROOT / "corpus" / "release" / name / "RELEASE-NOTES.md"
    if notes.is_file() and not (rel / "RELEASE-NOTES.md").exists():
        shutil.copyfile(notes, rel / "RELEASE-NOTES.md")
    write_sums(rel)
    return doc


def verify_release(rel):
    rel = Path(rel)
    bad = ["sums: " + n for n in verify_sums(rel)]
    m = load(rel / "manifest.json")
    for kind, sub, ext in (("signatures", "signatures", ".signature.json"), ("step_hashes", "step", ".step")):
        for fid, per in m["pins"][kind].items():
            for cid, h in per.items():
                p = rel / sub / ("%s.%s%s" % (fid, cid, ext))
                if not p.is_file() or sha(p.read_bytes()) != h:
                    bad.append("pin %s %s %s" % (kind, fid, cid))
    for fid, h in m["pins"]["verdicts"].items():
        p = rel / "verdicts" / (fid + ".verdict.json")
        if not p.is_file() or sha(p.read_bytes()) != h:
            bad.append("pin verdicts " + fid)
    bad += ["dwg in release: %s" % p.relative_to(rel) for p in rel.rglob("*.dwg")]
    return bad


# ---- two runs --------------------------------------------------------------------------------

def divergences(a, b):
    """Differences between two generated trees, the FILE_NAME time stamp aside. The manifest.json of a fixture is
    the same inputs by construction and is compared too."""
    a, b = Path(a), Path(b)
    out = []
    ia = {p.name for p in a.iterdir() if p.is_dir()}
    ib = {p.name for p in b.iterdir() if p.is_dir()}
    for fid in sorted(ia ^ ib):
        out.append("%s: only in one run" % fid)
    for fid in sorted(ia & ib):
        names = {p.name for d in (a / fid, b / fid) for p in d.iterdir()} - {"checksums.sha256"}
        for n in sorted(names):
            pa, pb = a / fid / n, b / fid / n
            if not (pa.is_file() and pb.is_file()):
                out.append("%s/%s: only in one run" % (fid, n))
                continue
            x, y = pa.read_bytes(), pb.read_bytes()
            if n.endswith(".step"):
                x = step_normalise.normalise(x.decode("utf-8", "replace")).encode()
                y = step_normalise.normalise(y.decode("utf-8", "replace")).encode()
            elif n.endswith(".status.json") or n.endswith(".verification.json"):
                x, y = _strip_clock(x), _strip_clock(y)
            if x != y:
                out.append("%s/%s" % (fid, n))
    return out


def _strip_clock(b):
    try:
        d = json.loads(b)
    except ValueError:
        return b
    def walk(v):
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items() if k not in ("wall_time_seconds", "sha256", "path")}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v
    return json.dumps(walk(d), sort_keys=True).encode()


# ---- the driver ------------------------------------------------------------------------------

def run(out, label, fixtures_extra=()):
    from . import generate
    out = Path(out)
    ids = stage(ROOT, out / "stage")
    results = {}
    for name in ("a", "b"):
        rc = generate.main(["generate", "--fixtures", str(out / "stage" / "fixtures"), "--truth", str(out / "stage" / "truth"),
                            "--check-leaks"] + list(fixtures_extra))
        results[name] = rc
        dest = out / ("run-" + name)
        if dest.exists():
            shutil.rmtree(dest)
        for fid in ids:
            shutil.copytree(out / "stage" / "fixtures" / fid / "generated", dest / fid)
    diffs = divergences(out / "run-a", out / "run-b")
    corpus = out / "corpus" / REVISION
    m = build(ROOT, out / "run-a", corpus)
    rel = out / "release" / "r2-open-1"
    release(corpus, rel, "r2-open-1")
    problems = verify_release(rel)
    report = {"schema_version": "pvec-gold/reproducibility/2", "label": label, "revision": REVISION, "fixtures": len(ids),
              "generate_exit": results, "unlisted_divergences": diffs, "release_problems": problems,
              "converters": [{k: c[k] for k in ("id", "lineage", "image_digest", "platform", "version")} for c in m["converters"]],
              "validator": m["validator"],
              "result": "PASS" if not diffs and not problems else "FAIL"}
    (out / "reproducibility.r2-open.json").write_text(dump(report))
    print(json.dumps({"result": report["result"], "unlisted_divergences": diffs, "release_problems": problems}, indent=1))
    return 0 if report["result"] == "PASS" else 1


def main(argv):
    ap = argparse.ArgumentParser(prog="runner.r2_open")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage"); s.add_argument("out")
    r = sub.add_parser("run"); r.add_argument("out"); r.add_argument("--label", default="native")
    v = sub.add_parser("verify"); v.add_argument("dir")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            print("\n".join(stage(ROOT, a.out)))
            return 0
        if a.cmd == "verify":
            bad = verify_release(a.dir)
            print("verified" if not bad else "MISMATCH: " + ", ".join(bad))
            return 1 if bad else 0
        return run(a.out, a.label)
    except Refused as e:
        print("refused: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
