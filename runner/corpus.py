"""Corpus revision r1-open: the edge, mixed-entity, degenerate, negative and real-world fixtures.

    python3 -m runner.corpus assemble RAW REAL_WORLD_RAW OPEN_RUN    build fixtures/**, matrix, manifest from a run
    python3 -m runner.corpus check [ROOT]                          every rule below, on the committed tree

What a pipeline owes, per group (docs/adr/0009 for the oracle words, ADR 0006 for quarantine):

  edge, mixed    the DWG, read by two open readers, carries the authored mathematics (the same rule as r0-open,
                 evidence_scope READER_MAPPING_ONLY). Nothing here has a STEP file yet.
  degenerate     the DWG carries an entity that cannot be a curve. The pipeline must refuse it: the refusal rule
                 (degenerate_reason) is applied to what each reader returned and must name the expected code.
  negative       one entity outside PVec v1 each. The pipeline's classification (UNSUPPORTED, IGNORED or MISSING)
                 must equal the authored one and no geometry may be accepted.
  real-world     a public drawing with a provenance record. Classed REAL_WORLD_DIFFERENTIAL, never known truth.
"""
import json
import math
import sys
import tempfile
from pathlib import Path

from . import corpus_release, numeric, qualify_probes as q, r0_open as r0

ROOT = Path(__file__).resolve().parent.parent
REVISION = "r1-open"
CLASSES = ("KNOWN_TRUTH_EXACT", "DUAL_ORACLE_EQUIVALENT", "REAL_WORLD_DIFFERENTIAL", "QUARANTINED")
OUTCOMES = ("UNSUPPORTED", "IGNORED", "MISSING")
VERDICTS = ("PUBLIC_REDISTRIBUTABLE", "PRIVATE")
SIGNATURE_SCHEMA = "pvec-gold/signature/1"

# Reader classes (ACadSharp names) a v1 mapper accepts as geometry. Anything else in a negative fixture
# that lands here is accepted geometry, which fails the run.
V1_ACCEPTED = ("Line", "Arc", "Circle", "Ellipse", "LwPolyline", "Polyline2D", "Spline", "Insert")
READER_DXF = {
    "Hatch": "HATCH", "TextEntity": "TEXT", "MText": "MTEXT", "Solid3D": "3DSOLID", "Mesh": "MESH", "Region": "REGION",
    "UnknownEntity": "ACAD_PROXY_ENTITY", "Ole2Frame": "OLE2FRAME", "Wipeout": "WIPEOUT", "TableEntity": "ACAD_TABLE",
    "RasterImage": "IMAGE", "XRef": "XREF",
}
# What the pipeline does with an entity its reader returns. An entity the reader does not return is MISSING.
POLICY = {"HATCH": "IGNORED", "TEXT": "IGNORED", "MTEXT": "IGNORED", "WIPEOUT": "IGNORED", "IMAGE": "IGNORED",
          "DIMENSION": "UNSUPPORTED", "3DSOLID": "UNSUPPORTED", "MESH": "UNSUPPORTED", "REGION": "UNSUPPORTED",
          "OLE2FRAME": "UNSUPPORTED", "ACAD_TABLE": "UNSUPPORTED", "XREF": "UNSUPPORTED", "ACAD_PROXY_ENTITY": "UNSUPPORTED"}

# group -> (directory under fixtures/, required files)
OPEN = ("acadsharp-dwg2step.status.json", "open-route.json")
COMMON = ("source.dwg", "README.md", "params.json", "read.acadrust.json", "read.acadsharp.json", "comparison.json") + OPEN
GROUPS = {
    "edge": ("edge", COMMON + ("expected.math.json",)),
    "mixed": ("mixed", COMMON + ("expected.math.json",)),
    "degenerate": ("degenerate", COMMON + ("expected.rejection.json",)),
    "negative": ("negative", ("source.dwg", "README.md", "params.json", "expected.classification.json", "census.acadsharp.json", "comparison.json") + OPEN),
    "real-world": ("real-world", ("source.dwg", "README.md", "census.acadsharp.json", "metrics.json", "comparison.json") + OPEN),
}
READERS = ("acadrust", "acadsharp")
CONVERTER = "acadsharp-dwg2step"


class ProvenanceError(Exception):
    pass


def load(p):
    return json.loads(Path(p).read_text())


def dump(obj, path):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def fixture_dirs(root, group):
    base = Path(root) / "fixtures" / GROUPS[group][0]
    return sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


# ---- negative suite --------------------------------------------------------------------------------------

def dxf_name(reader_class):
    return "DIMENSION" if reader_class.startswith("Dimension") else READER_DXF.get(reader_class)


def produced_classification(census, expected):
    """What the pipeline makes of a reader census: one outcome per expected entity class, the geometry it
    would accept, and whether it returned nothing at all."""
    if "read_error" in census:
        return {"read_error": census["read_error"], "entities": [], "converter_emits_nothing": False, "accepted_geometry": [], "unclassified": []}
    types = [e["type"] for b in census["blocks"] for e in b["entities"]]
    counts = {}
    for t in types:
        if dxf_name(t):
            counts[dxf_name(t)] = counts.get(dxf_name(t), 0) + 1
    ents = []
    for e in expected["entities"]:
        n = counts.get(e["dwg_type"], 0)
        ents.append({"dwg_type": e["dwg_type"], "count": n, "outcome": POLICY[e["dwg_type"]] if n else "MISSING"})
    return {"entities": ents, "converter_emits_nothing": not types,
            "accepted_geometry": [t for t in types if t in V1_ACCEPTED],
            "unclassified": [t for t in types if t not in V1_ACCEPTED and not dxf_name(t)]}


def classification_problems(expected, produced):
    if "read_error" in produced:
        return ["the reader failed on the DWG: %s" % produced["read_error"]]
    out = []
    if produced["accepted_geometry"]:
        out.append("accepted geometry from a negative fixture: %s" % ", ".join(produced["accepted_geometry"]))
    if produced["unclassified"]:
        out.append("entities with no classification: %s" % ", ".join(produced["unclassified"]))
    if len(expected["entities"]) != len(produced["entities"]):
        out.append("entity count differs")
    for e, p in zip(expected["entities"], produced["entities"]):
        if e["outcome"] != p["outcome"]:
            out.append("%s: expected %s, produced %s" % (e["dwg_type"], e["outcome"], p["outcome"]))
        elif p["outcome"] != "MISSING" and e["count"] != p["count"]:
            out.append("%s: expected %d, produced %d" % (e["dwg_type"], e["count"], p["count"]))
    if expected["converter_emits_nothing"] != produced["converter_emits_nothing"]:
        out.append("converter_emits_nothing: expected %s, produced %s" % (expected["converter_emits_nothing"], produced["converter_emits_nothing"]))
    return out


def negative_comparison(d):
    d = Path(d)
    expected, census = load(d / "expected.classification.json"), load(d / "census.acadsharp.json")
    produced = produced_classification(census, expected)
    problems = classification_problems(expected, produced)
    return {"fixture_id": d.name, "reader": census.get("reader"), "expected": {"entities": expected["entities"], "converter_emits_nothing": expected["converter_emits_nothing"]},
            "produced": produced, "verdict": "MATCH" if not problems else "MISMATCH", "problems": problems}


def negative_problems(d):
    d = Path(d)
    out = ["%s: %s is missing" % (d.name, n) for n in GROUPS["negative"][1] if not (d / n).is_file()]
    if out:
        return out
    exp = load(d / "expected.classification.json")
    if (d / "expected.math.json").exists():
        out.append("%s: a negative fixture carries expected.math.json" % d.name)
    if exp["evidence_class"] != "QUARANTINED":
        out.append("%s: a negative fixture is %s, not QUARANTINED" % (d.name, exp["evidence_class"]))
    cmp_ = negative_comparison(d)
    out += ["%s: %s" % (d.name, p) for p in cmp_["problems"]]
    if load(d / "comparison.json") != cmp_:
        out.append("%s: comparison.json is stale" % d.name)
    out += ["%s: %s" % (d.name, p) for p in open_route_problems("negative", load(d / "open-route.json"))]
    return out


def all_fixture_ids(root):
    """Ids by place: negative, real-world, known truth (r1 groups and the r0-open bundle)."""
    root = Path(root)
    kt = set()
    for p in [q for g in ("known-truth", "edge", "mixed", "degenerate") for q in (root / "fixtures" / g).rglob("*")]:
        if p.is_dir() and any((p / n).is_file() for n in ("expected.math.json", "expected.rejection.json")):
            kt.add(p.name)
    r0dir = root / "corpus" / "r0-open" / "fixtures"
    if r0dir.is_dir():
        kt |= {p.name for p in r0dir.iterdir() if p.is_dir()}
    return {"negative": {p.name for p in fixture_dirs(root, "negative")}, "real-world": {p.name for p in fixture_dirs(root, "real-world")}, "known-truth": kt}


def mutual_exclusion_problems(root):
    ids = all_fixture_ids(root)
    out = []
    for a, b in (("negative", "known-truth"), ("negative", "real-world"), ("real-world", "known-truth")):
        out += ["%s is in both the %s and the %s set; promoting a capability moves its fixture out of the negative suite in the same change" % (i, a, b)
                for i in sorted(ids[a] & ids[b])]
    return out


# ---- degenerate -------------------------------------------------------------------------------------------

def degenerate_reason(e, pol=None):
    """The refusal rule, on one decoded entity (r0-open read schema, f64 bit patterns). A length is degenerate
    under NP-06 (numeric.degenerate_length), which is why a radius a reader clamps up to 1e-12 is still refused."""
    pol = pol or numeric.load_policy()
    pt = lambda p: [r0.fl(c) for c in p]
    t = e["type"]
    if t == "LINE":
        a, b = pt(e["start"]), pt(e["end"])
        if pol.degenerate_length(math.dist(a, b), max(map(abs, a + b))):
            return "DEGENERATE_ZERO_LENGTH_SEGMENT"
    elif t in ("CIRCLE", "ARC"):
        r = r0.fl(e["radius"])
        if pol.degenerate_length(r, r):
            return "DEGENERATE_ZERO_RADIUS"
    elif t == "SPLINE" and e["control_points"]:
        cps = [pt(p) for p in e["control_points"]]
        span = max(math.dist(cps[0], q) for q in cps)
        if pol.degenerate_length(span, max(abs(c) for q in cps for c in q)):
            return "DEGENERATE_COINCIDENT_CONTROL_POINTS"
    return None


def model_space(dump_):
    return {b["name"]: b["entities"] for b in dump_["blocks"]}.get("*Model_Space", [])


def rejection_problems(expected, produced):
    want = expected["expected_rejection"]["classification"]
    if produced is None:
        return ["the pipeline produced geometry, or no refusal, for a degenerate fixture (expected %s)" % want]
    if produced != want:
        return ["expected the refusal %s, produced %s" % (want, produced)]
    return []


def degenerate_comparison(d, own, cross, pol):
    exp = load(Path(d) / "expected.rejection.json")
    got = {}
    for name, rec in (("acadrust", own), ("acadsharp", cross)):
        ms = model_space(rec) if rec else []
        got[name] = degenerate_reason(ms[0], pol) if len(ms) == 1 else None
    problems = [p for name in READERS for p in rejection_problems(exp, got[name])]
    return {"fixture_id": Path(d).name, "expected_rejection": exp["expected_rejection"], "produced_rejection": got,
            "verdict": "AGREE" if not problems else "DISAGREE", "problems": problems}


# ---- mixed drawings ----------------------------------------------------------------------------------------

def check_mixed(c, exp, dump_):
    ms = model_space(dump_)
    ents, specs = exp["entities"], exp["provenance"]["parameters"]["entities"]
    c.flag("model_space_entity_count", len(ents), len(ms))
    for i, (e, s) in enumerate(zip(ents, specs)):
        if i >= len(ms):
            break
        p = "entity[%d]." % i
        if e["structure"] == "CURVE_ONLY":
            r0.check_curve(c, e, ms[i], p)
            continue
        one = {"blocks": [{"name": "*Model_Space", "entities": [ms[i]]}] + [b for b in dump_["blocks"] if b["name"] != "*Model_Space"]}
        sub = r0.Checks(c.pol)
        r0.check_transform(sub, e, s, one)
        for item in sub.items:
            c.items.append(dict(item, field=p + item["field"]))


def reader_verdict(pol, judge, own, cross):
    """The r0-open cross-read rule for a judge function: the verdict is AGREE only if both readers match the
    authored record and decode identical records."""
    if own is None or cross is None:
        return {"checks": {}, "reader_vs_reader_differences": None, "verdict": "UNREADABLE", "reason": "MALFORMED_FIXTURE",
                "evidence": "a reader could not open the DWG"}
    co, cc = judge(own), judge(cross)
    diffs = r0.diff(r0.strip(own), r0.strip(cross))
    bad = ["%s differs from the authored truth at: %s" % (name, ", ".join(i["field"] for i in c.items if not i["ok"])[:300])
           for name, c in (("cross reader", cc), ("own reader", co)) if not c.ok]
    if diffs:
        bad.append("the two readers decoded different records at: " + ", ".join(diffs)[:300])
    return {"checks": {"cross": cc.items, "own": co.items}, "reader_vs_reader_differences": diffs,
            "verdict": "DISAGREE" if bad else "AGREE", "reason": "UNRESOLVED_DISAGREEMENT" if bad else None, "evidence": "; ".join(bad) or None}


# ---- real-world --------------------------------------------------------------------------------------------

def require_verdict(fid, provenance):
    """The generation path's refusal: a fixture with no redistribution verdict cannot enter the corpus."""
    rec = provenance.get(fid)
    if rec is None:
        raise ProvenanceError("%s has no provenance record" % fid)
    v = rec.get("redistribution_verdict")
    if v not in VERDICTS:
        raise ProvenanceError("%s has no redistribution verdict (%r); it must be one of %s" % (fid, v, ", ".join(VERDICTS)))
    return v


def classify_problems(fixture_dir, claimed):
    if claimed not in CLASSES:
        return ["unknown evidence class %r" % claimed]
    if claimed == "KNOWN_TRUTH_EXACT" and not (Path(fixture_dir) / "expected.math.json").is_file():
        return ["KNOWN_TRUTH_EXACT needs an expected.math.json, and this fixture has none"]
    return []


def agreement_record(primary, secondary):
    """Converter agreement on a drawing whose source mathematics is unknown. It is interoperability evidence only."""
    return {"evidence_class": "DUAL_ORACLE_EQUIVALENT", "is_source_truth": False, "oracle_scope": "OPEN_CONVERTERS", "converters": [primary, secondary],
            "statement": "two independent open converters agree on this drawing; the original mathematics is not independently known"}


def provenance(root):
    p = Path(root) / "corpus" / "provenance.json"
    return load(p)["fixtures"] if p.is_file() else {}


def private_records(root):
    p = Path(root) / "corpus" / "provenance.json"
    return load(p).get("private", {}) if p.is_file() else {}


def private_path_problems(root):
    """PRIVATE sources are id and hash only: no DWG under the fixture id, and no DWG anywhere whose hash is a private one."""
    root = Path(root)
    out = []
    for fid, rec in provenance(root).items():
        if rec.get("redistribution_verdict") == "PRIVATE":
            out += ["%s is PRIVATE and its DWG bytes are in the repository: %s" % (fid, p.relative_to(root))
                    for base in (root / "fixtures").rglob(fid) if base.is_dir() for p in base.rglob("*.dwg")]
    for pid, rec in private_records(root).items():
        hashes = set(rec.get("files", {}).values())
        for p in (root / "fixtures").rglob("*.dwg"):
            if pid in p.parts or r0.sha256(p) in hashes:
                out.append("%s is PRIVATE and its DWG bytes are in the repository: %s" % (pid, p.relative_to(root)))
    return out


def real_world_metrics(census, discipline):
    s = census["summary"]
    return {"discipline": discipline, "dwg_version": census["dwg_version"], "entity_count": s["entity_count"], "class_histogram": s["class_histogram"],
            "max_block_depth": s["max_block_depth"], "spline_count": s["spline_count"], "max_abs_coordinate": s["max_abs_coordinate"],
            "largest_extent_side": s["extent"]["largest_side"] if s["extent"] else None}


# ---- the open-converter run ----------------------------------------------------------------------------------------

def open_route_verdict(group, step_emitted, curves):
    """What the converter's output means for a group that has an expected refusal."""
    if group == "negative":
        return "STEP_EMITTED" if step_emitted else "NO_STEP_EMITTED"
    if group == "degenerate":
        return "CONVERTER_EMITTED_GEOMETRY" if step_emitted and curves else "REFUSED"
    return None


def open_route_problems(group, rec):
    if group == "negative" and rec.get("verdict") != "NO_STEP_EMITTED":
        return ["the open converter wrote a STEP file for a negative fixture, which is accepted geometry"]
    return []


def open_route_failures(root):
    """Degenerate fixtures the converter did not refuse. They are findings about the converter, listed and not hidden."""
    return sorted(d.name for d in fixture_dirs(root, "degenerate") if load(d / "open-route.json")["verdict"] != "REFUSED")


def match_entities(pol, exp, ver, status):
    """Classify each expected entity of a multi-entity drawing against its best distinct STEP curve."""
    pool = list(ver["entities"]) if ver else []
    out = []
    for ent in exp["entities"]:
        if not pool:
            out.append(q.classify_entity(pol, ent, None if ver is None else {"entities": []}, status))
            continue
        scored = [(q.RANK[c["class"]], i, c) for i, a in enumerate(pool) for c in [q.classify_entity(pol, ent, {"entities": [a]}, status)]]
        _, i, best = min(scored, key=lambda t: (t[0], t[1]))
        pool.pop(i)
        out.append(best)
    return out


def brief(cell):
    ev = cell["evidence"]
    return {k: ev[k] for k in ("reason", "max_deviation", "direction") if k in ev}


def open_route_record(group, d, run, pol):
    """Copy the converter's artifacts for one fixture into its directory and derive open-route.json."""
    d, run = Path(d), Path(run)
    for name, src in ((CONVERTER + ".status.json", "primary.status.json"), (CONVERTER + ".step", "primary.step"),
                      (CONVERTER + ".verification.json", "primary.verification.json")):
        if (run / src).is_file():
            (d / name).write_bytes((run / src).read_bytes())
        elif (d / name).exists():
            (d / name).unlink()
    ver, status = q.load_outputs(run.parent, run.name, "primary")
    emitted = (d / (CONVERTER + ".step")).is_file()
    curves = len(ver["entities"]) if ver else 0
    rec = {"converter": CONVERTER, "product": status.get("product"), "oracle_scope": "OPEN_CONVERTERS", "single_oracle": True,
           "exit_code": status["exit_code"], "status": status["status"], "step_emitted": emitted, "curves_evaluated": curves,
           "numeric_policy_version": pol.version}
    if status.get("error"):
        rec["error"] = status["error"]
    if group == "real-world":
        rec["differential"] = "SINGLE_OPEN_CONVERTER_ONLY"
    verdict = open_route_verdict(group, emitted, curves)
    if verdict:
        rec["verdict"] = verdict
    if group in ("edge", "mixed"):
        exp = load(d / "expected.math.json")
        cells = match_entities(pol, exp, ver, status) if group == "mixed" else q.qualify_probe(pol, exp, {CONVERTER: (ver, status)})[CONVERTER]
        rec["classes"] = [{"entity": e["id"], "class": c["class"], **brief(c)} for e, c in zip(exp["entities"], cells)]
        rec["worst_class"] = max((c["class"] for c in cells), key=lambda k: q.RANK[k])
    return rec


# ---- capability matrix --------------------------------------------------------------------------------------

PROFILE = {"repository": "libviprs/pvec", "document": "docs/ISO_PROFILE.md", "commit": "1bb79deae4d97dfcb2a5ad4c120e1bffb7d215d5",
           "document_sha256": "0c8f2aa44794466c93d71d4745c35c269976b225a8ce73004ac029aa32993c4e"}
SECTIONS = {"point": 1, "direction": 2, "axis_placement_2d": 3, "line": 4, "polyline": 5, "circle": 6, "ellipse": 7, "trimmed_curve": 8,
            "composite_curve": 9, "bezier": 10, "bspline": 11, "nurbs": 12, "affine_transform": 13}
# Fixtures that exercise a capability beyond the r0-open table (r0.CAPABILITIES_OF). The three primitives
# (point, direction, axis placement) are used by every curve; these are the fixtures that state them plainly.
EXTRA = {
    "point": ["line-001", "polyline-001", "large-coords-001"],
    "direction": ["ellipse-001", "circle-001", "nonuniform-scale-rotated-001"],
    "axis_placement_2d": ["circle-001", "ellipse-001", "arc-seam-001"],
    "line": ["tiny-extent-001", "mixed-entity-001"],
    "polyline": ["mixed-entity-001"],
    "circle": ["huge-extent-001", "mixed-entity-001"],
    "ellipse": ["mixed-entity-001"],
    "trimmed_curve": ["arc-tiny-sweep-001", "mixed-entity-001"],
    "composite_curve": ["mixed-entity-001"],
    "bspline": ["bspline-nonunit-domain-001"],
    "nurbs": ["mixed-entity-001"],
    "affine_transform": ["mixed-entity-001"],
}
REFUSED = {"line": ["zero-length-segment-001"], "circle": ["zero-radius-001"], "bspline": ["coincident-control-points-001"]}


def evidence_index(root):
    """id -> (evidence_class, evidence_scope) over the r0-open manifest and the r1-open manifest."""
    idx = {}
    for p in (Path(root) / "corpus" / "r0-open" / "manifest.json", Path(root) / "corpus" / REVISION / "manifest.json"):
        if p.is_file():
            for f in load(p)["fixtures"]:
                idx[f["id"]] = (f["evidence_class"], f.get("evidence_scope"))
    return idx


def step_evidence(root, fid):
    """The open converter's result for a fixture, from its own open-route.json or the phase 1 qualification report."""
    root = Path(root)
    for g in ("edge", "mixed"):
        p = root / "fixtures" / g / fid / "open-route.json"
        if p.is_file():
            r = load(p)
            return {"converter": CONVERTER, "class": r["worst_class"], "source": str(p.relative_to(root))}
    rp = root / "reports" / "phase1" / "probe-qualification.json"
    if rp.is_file():
        cells = load(rp)["probes"].get(fid, {}).get(CONVERTER)
        if cells:
            return {"converter": CONVERTER, "class": max((c["class"] for c in cells), key=lambda k: q.RANK[k]), "source": "reports/phase1/probe-qualification.json"}
    return None


def build_matrix(root):
    idx = evidence_index(root)
    rows = []
    for cap in sorted(SECTIONS, key=SECTIONS.get):
        ids = sorted(set(i for i, caps in r0.CAPABILITIES_OF.items() if cap in caps) | set(EXTRA.get(cap, [])))
        rows.append({"capability": cap, "profile_section": SECTIONS[cap],
                     "fixtures": [{"id": i, "evidence_class": idx[i][0], "evidence_scope": idx[i][1], "step_evidence": step_evidence(root, i)} for i in ids if i in idx],
                     "refusals": [{"id": i, "expected": "REJECT"} for i in REFUSED.get(cap, [])]})
    return {"schema_version": "pvec-gold/capability-matrix/1", "corpus_revision": REVISION, "profile": PROFILE,
            "numeric_policy_version": numeric.load_policy().version,
            "evidence_note": "KNOWN_TRUTH_EXACT here is reader mapping only (evidence_scope READER_MAPPING_ONLY). step_evidence is the one open converter's class for the fixture (null where it has not run); one converter is a single oracle, so no row reaches STEP_ORACLE (ADR 0009).",
            "rows": rows}


def matrix_problems(matrix, root):
    root = Path(root)
    out = []
    for r in matrix["rows"]:
        if not r["fixtures"] and not r.get("blocked"):
            out.append("%s: no fixture and no blocked entry" % r["capability"])
        for f in r["fixtures"]:
            hits = list((root / "fixtures").rglob("%s/expected.math.json" % f["id"])) + list((root / "corpus" / "r0-open" / "fixtures").glob("%s/expected.math.json" % f["id"]))
            if f["evidence_class"] == "KNOWN_TRUTH_EXACT" and not hits:
                out.append("%s: %s is KNOWN_TRUTH_EXACT with no authored expected.math.json" % (r["capability"], f["id"]))
    return out


# ---- fixtures, manifest, quarantine --------------------------------------------------------------------------

def fixture_artifact_problems(root, group, fid, status):
    base, required = GROUPS[group]
    d = Path(root) / "fixtures" / base / fid
    missing = [n for n in required if not (d / n).is_file()]
    return ["%s %s (%s): %s is missing, so the fixture cannot be accepted" % (group, fid, status, n) for n in missing]


def fixture_entry(root, group, d, prov):
    root = Path(root)
    fid = d.name
    rel = d.relative_to(root)
    arts = {p.name: {"path": str(p.relative_to(root)), "sha256": r0.sha256(p)} for p in sorted(d.iterdir()) if p.is_file()}
    entry = {"id": fid, "group": group, "status": "ACCEPTED", "licence_verdict": "PUBLIC_REDISTRIBUTABLE", "provenance": "SYNTHETIC_AUTHORED",
             "evidence_scope": r0.SCOPE, "oracle_scope": "NONE", "artifacts": arts}
    cmp_ = load(d / "comparison.json")
    if group in ("edge", "mixed"):
        ok = cmp_["verdict"] == "AGREE"
        entry["evidence_class"] = "KNOWN_TRUTH_EXACT" if ok else "QUARANTINED"
        entry["dwg_version"] = load(d / "read.acadsharp.json")["dwg_version"]
        if not ok:
            entry["quarantine"] = {"reason": cmp_["reason"], "evidence": cmp_["evidence"]}
    elif group == "degenerate":
        rec = load(d / "expected.rejection.json")
        entry["evidence_class"] = "QUARANTINED"
        entry["evidence_scope"] = "REJECTION_EXPECTED"
        entry["quarantine"] = {"reason": rec["quarantine_reason"], "evidence": "intentionally degenerate; the expected outcome is %s and no geometry. %s run: %s"
                                % (rec["expected_rejection"]["classification"], CONVERTER, load(d / "open-route.json")["verdict"])}
        entry["dwg_version"] = load(d / "read.acadsharp.json")["dwg_version"]
    elif group == "negative":
        rec = load(d / "expected.classification.json")
        entry["evidence_class"] = "QUARANTINED"
        entry["evidence_scope"] = "CLASSIFICATION_EXPECTED"
        entry["quarantine"] = {"reason": rec["quarantine_reason"], "evidence": "%s: %s" % (rec["outcome"], rec["reason"])}
        entry["dwg_version"] = load(d / "census.acadsharp.json")["dwg_version"]
    else:
        p = prov[fid]
        entry["evidence_class"] = "REAL_WORLD_DIFFERENTIAL"
        entry["evidence_scope"] = "READER_CENSUS_ONLY"
        entry["provenance"] = "REAL_WORLD_PUBLIC"
        entry["licence_verdict"] = require_verdict(fid, prov)
        entry["licence"] = p["licence"]
        entry["dwg_version"] = load(d / "metrics.json")["dwg_version"]
    return entry


def build_manifest(root, info):
    root = Path(root)
    pol = numeric.load_policy()
    prov = provenance(root)
    r0m = load(root / "corpus" / "r0-open" / "manifest.json")
    fixtures = []
    for f in r0m["fixtures"]:
        base = root / "corpus" / "r0-open" / "fixtures" / f["id"]
        e = {"id": f["id"], "group": f["group"], "status": f["status"], "evidence_class": f["evidence_class"], "evidence_scope": f["evidence_scope"],
             "oracle_scope": "NONE", "licence_verdict": f["licence_verdict"], "provenance": f["provenance"], "dwg_version": f["dwg"]["dwg_version"],
             "artifacts": {p.name: {"path": str(p.relative_to(root)), "sha256": r0.sha256(p)} for p in sorted(base.iterdir()) if p.is_file()}}
        if "quarantine" in f:
            e["quarantine"] = f["quarantine"]
        fixtures.append(e)
    for group in GROUPS:
        for d in fixture_dirs(root, group):
            fixtures.append(fixture_entry(root, group, d, prov))
    fixtures.sort(key=lambda f: (f["group"], f["id"]))
    r0pin = load(root / "corpus" / "r0-open.pin.json")
    return {
        "schema_version": "pvec-gold/corpus-manifest/1", "corpus_revision": REVISION, "status": "CANDIDATE",
        "adr": "docs/adr/0009-open-converter-oracle-scope.md", **numeric.policy_stamp(pol),
        "signature_schema_version": SIGNATURE_SCHEMA, "oracle_scope": "NONE",
        "oracle_note": "No STEP oracle has run on this revision. Its fixtures are evidence_scope READER_MAPPING_ONLY, REJECTION_EXPECTED, CLASSIFICATION_EXPECTED or READER_CENSUS_ONLY, and the open-converter run (oracle_scope OPEN_CONVERTERS, ADR 0009) adds STEP_ORACLE evidence in a later revision.",
        "converters": "none", "evaluator": "none (no STEP evaluator ran; there is no STEP output)",
        "writer": info["writer"], "writer_source": info["writer_source"], "readers": info["readers"], "container_images": info["images"],
        "determinism": info["determinism"], "dwg_version": info["dwg_version"],
        "includes": {"r0-open": {"bundle_sha256": r0pin["bundle_sha256"], "manifest_sha256": r0pin["manifest_sha256"]}},
        "profile": PROFILE, "fixtures": fixtures,
    }


def build_quarantine(root, manifest):
    r0q = load(Path(root) / "corpus" / "r0-open" / "quarantine.json")
    q = [{"id": f["id"], "group": f["group"], "reason": f["quarantine"]["reason"], "evidence": f["quarantine"]["evidence"]}
         for f in manifest["fixtures"] if f["evidence_class"] == "QUARANTINED"]
    return {"corpus_revision": REVISION, "quarantined": q, "excluded": r0q["excluded"]}


def write_sums(rev):
    names = sorted(p.name for p in Path(rev).iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (Path(rev) / "SHA256SUMS").write_text("".join("%s  %s\n" % (r0.sha256(Path(rev) / n), n) for n in names))


README = """# corpus revision r1-open

The second candidate revision. It includes `r0-open` by reference (bundle and manifest hashes in `manifest.json`)
and adds five groups, each in its own directory under `fixtures/`: `edge` (valid extreme and boundary cases),
`mixed` (one drawing with seven curve classes, nested blocks and transforms), `degenerate` (entities that must be
refused), `negative` (one entity outside PVec v1 each, with an expected classification) and `real-world` (public
drawings with a provenance record). `manifest.json` is the index, `quarantine.json` lists everything quarantined
with its reason, and `SHA256SUMS` covers the files in this directory. The per-fixture hashes are in the manifest.

Read this before you rely on it. `oracle_scope` is `NONE`: one open converter (`acadsharp-dwg2step`) has run over the
fixtures and its result is recorded in each `open-route.json`, but ADR 0009 needs two converters with different
lineages before a fixture can claim `STEP_ORACLE`, and the second one does not exist yet. `KNOWN_TRUTH_EXACT` here
means reader mapping only, exactly as in `r0-open`. Real-world fixtures are `REAL_WORLD_DIFFERENTIAL` and never
known truth. The negative and degenerate fixtures are `QUARANTINED` by design (ADR 0006).

To check it with no DWG library, no converter and no Docker:

    python3 -m runner.corpus check
    python3 -m runner.corpus_release build . OUT && python3 OUT/verify_release.py OUT
"""


# ---- assemble ---------------------------------------------------------------------------------------------------

def assemble(raw, rw_raw, open_run, info, root=ROOT):
    root, raw, rw_raw, open_run = Path(root), Path(raw), Path(rw_raw), Path(open_run)
    pol = numeric.load_policy()
    authoring = root / "tools" / "authoring"
    params = {p.stem: p for g in ("edge", "mixed", "degenerate") for p in (authoring / "corpus-params" / g).glob("*.json")}
    excluded = []
    for group in ("edge", "mixed", "degenerate"):
        rep = load(raw / group / "write-report.json")
        for item in rep["fixtures"]:
            fid = item["id"]
            if item["status"] == "SKIPPED":
                excluded.append({"id": fid, "reason": item["reason"], "evidence": item["evidence"], "file": None})
                continue
            src, out = raw / group / fid, root / "fixtures" / GROUPS[group][0] / fid
            out.mkdir(parents=True, exist_ok=True)
            (out / "source.dwg").write_bytes((src / "source.dwg").read_bytes())
            (out / "params.json").write_bytes(params[fid].read_bytes())
            own, cross = load(src / "read.acadrust.json"), load(src / "read.acadsharp.json")
            r0.dump_json(own, out / "read.acadrust.json")
            r0.dump_json(cross, out / "read.acadsharp.json")
            if group == "degenerate":
                dump(degenerate_comparison(out, own, cross, pol), out / "comparison.json")
                continue
            exp = load(out / "expected.math.json")
            if group == "edge":
                with tempfile.TemporaryDirectory() as t:
                    stage = Path(t) / "fixtures" / fid
                    stage.mkdir(parents=True)
                    (stage / "expected.math.json").write_bytes((out / "expected.math.json").read_bytes())
                    (stage / "params.json").write_bytes((out / "params.json").read_bytes())
                    v = r0.verdict(pol, fid, info["writer"], own, cross, Path(t))
            else:
                v = reader_verdict(pol, lambda d: _judge_mixed(pol, exp, d), own, cross)
            dump(r0.comparison_doc(pol, fid, v), out / "comparison.json")
    for d in fixture_dirs(root, "negative"):
        src = raw / "negative" / d.name
        (d / "source.dwg").write_bytes((src / "source.dwg").read_bytes())
        (d / "census.acadsharp.json").write_bytes((src / "census.acadsharp.json").read_bytes())
        dump(negative_comparison(d), d / "comparison.json")
    prov = provenance(root)
    for fid in sorted(prov):
        require_verdict(fid, prov)
        d = root / "fixtures" / "real-world" / fid
        d.mkdir(parents=True, exist_ok=True)
        src = rw_raw / fid
        census = load(src / "census.acadsharp.json")
        if prov[fid]["redistribution_verdict"] == "PUBLIC_REDISTRIBUTABLE":
            (d / "source.dwg").write_bytes((src / "source.dwg").read_bytes())
        (d / "census.acadsharp.json").write_bytes((src / "census.acadsharp.json").read_bytes())
        m = real_world_metrics(census, prov[fid]["discipline"])
        dump(m, d / "metrics.json")
        dump({"fixture_id": fid, "evidence_class": "REAL_WORLD_DIFFERENTIAL", "evidence_scope": "READER_CENSUS_ONLY",
              "differential": "PENDING_OPEN_CONVERTERS", "converter_agreement": None,
              "note": "No converter output exists for this drawing yet. When two open converters agree on it the agreement is recorded as DUAL_ORACLE_EQUIVALENT and is not source truth (agreement_record in runner/corpus.py)."}, d / "comparison.json")
        (d / "README.md").write_text("# %s\n\n%s drawing, %d entities, DWG %s, from %s under %s. %s\n\nI keep it for regression and for spotting differences between providers. It has no authored mathematics, so it is never `KNOWN_TRUTH_EXACT`; the class is `REAL_WORLD_DIFFERENTIAL`. Provenance and the licence basis are in `corpus/provenance.json`.\n"
                                      % (fid, prov[fid]["discipline"], m["entity_count"], m["dwg_version"], prov[fid]["origin"], prov[fid]["licence"], prov[fid].get("note", "")))
    for group in GROUPS:
        for d in fixture_dirs(root, group):
            dump(open_route_record(group, d, open_run / group / d.name, pol), d / "open-route.json")
    manifest = build_manifest(root, info)
    rev = root / "corpus" / REVISION
    rev.mkdir(parents=True, exist_ok=True)
    dump(manifest, rev / "manifest.json")
    q = build_quarantine(root, manifest)
    q["excluded"] = q["excluded"] + sorted(excluded, key=lambda e: e["id"])
    dump(q, rev / "quarantine.json")
    (rev / "README.md").write_text(README)
    write_sums(rev)
    dump(build_matrix(root), root / "corpus" / "capability-matrix.json")
    return manifest


def _judge_mixed(pol, exp, dump_):
    c = r0.Checks(pol)
    if dump_.get("schema") != r0.READ_SCHEMA:
        c.flag("schema", r0.READ_SCHEMA, dump_.get("schema"))
    else:
        check_mixed(c, exp, dump_)
    return c


# ---- check ------------------------------------------------------------------------------------------------------

def check(root=ROOT):
    root = Path(root)
    out = []
    for g in GROUPS:
        for d in fixture_dirs(root, g):
            out += fixture_artifact_problems(root, g, d.name, "ACCEPTED")
    for d in fixture_dirs(root, "negative"):
        out += negative_problems(d)
    for g in ("edge", "mixed", "degenerate"):
        for d in fixture_dirs(root, g):
            v = load(d / "comparison.json")["verdict"] if (d / "comparison.json").is_file() else None
            if v != "AGREE":
                out.append("%s %s: comparison verdict is %s" % (g, d.name, v))
    out += mutual_exclusion_problems(root)
    prov = provenance(root)
    for d in fixture_dirs(root, "real-world"):
        try:
            require_verdict(d.name, prov)
        except ProvenanceError as e:
            out.append(str(e))
        cls = load(d / "comparison.json")["evidence_class"] if (d / "comparison.json").is_file() else None
        out += classify_problems(d, cls)
        if cls == "KNOWN_TRUTH_EXACT":
            out.append("%s: a real-world fixture is never KNOWN_TRUTH_EXACT" % d.name)
    out += private_path_problems(root)
    out += matrix_problems(load(root / "corpus" / "capability-matrix.json"), root)
    rev = root / "corpus" / REVISION
    m = load(rev / "manifest.json")
    for f in m["fixtures"]:
        for name, a in f["artifacts"].items():
            if not (root / a["path"]).is_file() or r0.sha256(root / a["path"]) != a["sha256"]:
                out.append("manifest: %s %s does not match" % (f["id"], name))
    for line in (rev / "SHA256SUMS").read_text().splitlines():
        h, name = line.split("  ", 1)
        if r0.sha256(rev / name) != h:
            out.append("SHA256SUMS: %s does not verify" % name)
    with tempfile.TemporaryDirectory() as t:
        corpus_release.build_release(root, Path(t) / "release")
        out += corpus_release.verify_release(Path(t) / "release")
    return out


def main(argv):
    if argv[:1] == ["assemble"] and len(argv) == 4:
        info = load(ROOT / "tools" / "corpus" / "writer-info.json")
        assemble(argv[1], argv[2], argv[3], info)
        return 0
    if argv[:1] == ["check"]:
        problems = check(argv[1] if len(argv) > 1 else ROOT)
        for p in problems:
            print(p)
        print("corpus OK" if not problems else "%d problem(s)" % len(problems))
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
