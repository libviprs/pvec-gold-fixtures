"""Classify each converter's output for each probe, and roll the cells up per PVec capability.

    python3 -m runner.qualify_probes --probes fixtures/known-truth --primary ID DIR --secondary ID DIR \
        --lineage ID=NAME --lineage ID=NAME --out reports/phase1/probe-qualification.json [--resolved FILE]

ID is the converter's name in the report (for example acadsharp-dwg2step, libredwg-dwg2step, cadex or oda).
DIR holds <probe-id>/primary.verification.json (+ primary.status.json) for the primary converter and
<probe-id>/secondary.verification.json (+ secondary.status.json) for the secondary one. With --lineage for
both ids is required: two converters of one lineage, or two equal ids, are refused as a dual oracle (ADR 0009),
and the report records the lineages so a verdict always shows whose decoders produced it.
Comparison reads the normalised evaluator records, never STEP text, and every threshold comes from the
vendored policy. The verdict rules do not look at the ids.

Classes: STRUCTURAL_EXACT, GEOMETRIC_EXACT_REPARAMETERIZED, BOUNDED_APPROXIMATION, MISSING,
UNSUPPORTED. UNEXPECTED_GEOMETRY is a failure marker outside those five, for a probe whose expected
outcome is a rejection and where the converter emitted a curve anyway.
"""
import argparse
import json
import math
import sys
from pathlib import Path

from . import canon, curves, expected_math as em, numeric, structural, verification
from .r0_open import ORACLE_SCOPES, VENDOR_NAME, lineage_problems

STRUCTURAL_EXACT = "STRUCTURAL_EXACT"
GEOMETRIC = "GEOMETRIC_EXACT_REPARAMETERIZED"
BOUNDED = "BOUNDED_APPROXIMATION"
MISSING = "MISSING"
UNSUPPORTED = "UNSUPPORTED"
UNEXPECTED = "UNEXPECTED_GEOMETRY"
RANK = {STRUCTURAL_EXACT: 0, GEOMETRIC: 1, BOUNDED: 2, UNSUPPORTED: 3, MISSING: 4, UNEXPECTED: 5}
EXACT = (STRUCTURAL_EXACT, GEOMETRIC)

# PVec v1 capabilities (docs/ISO_PROFILE.md in libviprs/pvec) and the probes that cover them.
CAPABILITIES = {
    "line": ["line-001"],
    "polyline": ["polyline-001", "large-coords-001", "lwpolyline-closed-001", "polyline2d-001"],
    "circle": ["circle-001", "tiny-radius-001"],
    "ellipse": ["ellipse-001"],
    "trimmed_curve": ["arc-seam-001", "elliptical-arc-001"],
    "composite_curve": ["bulge-arc-001", "bulge-arc-neg-001"],
    "bezier": ["bezier-d3-001"],
    "bspline": ["bspline-d3-001", "bspline-d5-001", "repeated-knot-c0-001", "closed-by-endpoint-001", "closed-periodic-001"],
    "nurbs": ["nurbs-d3-001", "nurbs-d2-offconic-001", "nonunit-weight-001"],
    "affine_transform": ["translation-001", "rotation-irrational-001", "uniform-scale-001", "nonuniform-scale-circle-001",
                         "nonuniform-scale-rotated-001", "reflection-001", "shear-001", "general-affine-001",
                         "nested-blocks-001", "near-singular-001", "singular-001"],
}
CONVERTERS = {"cadex": "primary", "oda": "secondary"}   # the ids of the licensed pair; the default when a report names none
SAMPLES = 256   # sampling resolution for nearest-point search; refinement below does the precision work
GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0


def core(rec):
    return {k: rec[k] for k in ("class", "geometry", "parameter_domain", "closure")}


class Placed:
    """A curve record with the row-major matrix that places it in world space, and sampled points."""

    def __init__(self, rec, m16=None):
        self.rec = rec
        self.curve = curves.Curve(rec)
        self.m = m16
        self._pts = None

    def at(self, u):
        p = self.curve.unit(min(max(u, 0.0), 1.0))
        return curves.apply_transform(self.m, p) if self.m else p

    def samples(self):
        if self._pts is None:
            self._pts = [self.at(i / SAMPLES) for i in range(SAMPLES + 1)]
        return self._pts

    def nearest(self, q):
        pts = self.samples()
        ds = [curves.dist(p, q) for p in pts]
        # On a closed curve the first and last samples are one point, so the nearest sample can be a tie
        # and the true nearest point sits next to either of them. Refine around every tied sample.
        near = [k for k, d in enumerate(ds) if d <= min(ds) * (1 + 1e-9)]
        best = None
        for i in near:
            cand = self._refine(q, i)
            if best is None or curves.dist(cand, q) < curves.dist(best, q):
                best = cand
        return best

    def _refine(self, q, i):
        lo, hi = max(i - 1, 0) / SAMPLES, min(i + 1, SAMPLES) / SAMPLES
        f = lambda u: curves.dist(self.at(u), q)  # noqa: E731
        a, b = lo, hi
        c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
        fc, fd = f(c), f(d)
        for _ in range(80):
            if fc < fd:
                b, d, fd = d, c, fc
                c = b - GOLDEN * (b - a)
                fc = f(c)
            else:
                a, c, fc = c, d, fd
                d = a + GOLDEN * (b - a)
                fd = f(d)
        u = (a + b) / 2
        best = self.at(u)
        for cand in (lo, hi, i / SAMPLES):
            if curves.dist(self.at(cand), q) < curves.dist(best, q):
                best = self.at(cand)
        return best


def nearest_on_all(placed, q):
    return min((p.nearest(q) for p in placed), key=lambda r: curves.dist(r, q))


def matrix_floats(t):
    return [canon.check_scalar(s) for s in t["matrix"]]


def expected_world(ent):
    """(record in world space, transform record or None, placed-form for local geometry)"""
    if "world" in ent:
        return ent["world"]
    return core(ent)


def actual_placed(doc):
    out, unsupported = [], []
    for e in doc["entities"]:
        if e["class"] == "unsupported":
            unsupported.append(e["geometry"]["occt_type"])
            continue
        try:
            out.append(Placed(core(e), matrix_floats(e["transform"])))
        except curves.CurveError as ex:
            unsupported.append(str(ex))
    return out, unsupported


def refine_maximum(h, at, width):
    """Golden-section search for the local maximum of h around the best sampled parameter."""
    a, b = max(at - width, 0.0), min(at + width, 1.0)
    c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    hc, hd = h(c), h(d)
    for _ in range(60):
        if hc > hd:
            b, d, hd = d, c, hc
            c = b - GOLDEN * (b - a)
            hc = h(c)
        else:
            a, c, hc = c, d, hd
            d = a + GOLDEN * (b - a)
            hd = h(d)
    u = (a + b) / 2
    return h(u), u


def deviation(pol, src, targets, scale):
    """Max distance from points of src to the union of targets, refined until stable by the policy."""
    f = lambda u: src.at(u)  # noqa: E731
    g = lambda u: nearest_on_all(targets, src.at(u))  # noqa: E731
    h = lambda u: curves.dist(f(u), g(u))  # noqa: E731
    try:
        dev, at, lvl = pol.adaptive_max_deviation(f, g, 0.0, 1.0, curves.dist, scale, max_levels=7)
        stable, width = True, 1.0 / (8 * 2 ** (lvl - 1))
    except numeric.UnstableEstimate as e:
        dev, at, stable, width = e.best, e.at, False, 1.0 / (8 * 2 ** (e.levels - 1))
    dev2, at2 = refine_maximum(h, at, width)
    return (dev2, at2, stable) if dev2 > dev else (dev, at, stable)


def classify_entity(pol, ent, actual_doc, status):
    """One cell for one expected entity against one converter's output."""
    expects_rejection = "rejection" in ent
    if actual_doc is None:
        if status and status.get("status") == "ERROR":
            reason = "converter reported %s: %s" % (status["error"]["class"], status["error"]["message"])
            return cell(UNSUPPORTED, {"reason": reason}, expects_rejection)
        return cell(MISSING, {"reason": "no converter output artifacts for this probe"}, expects_rejection)
    placed, unsupported = actual_placed(actual_doc)
    if expects_rejection:
        if placed or unsupported:
            return cell(UNEXPECTED, {"reason": "converter emitted %d curve(s) for an input whose expected outcome is a rejection" % (len(placed) + len(unsupported))}, True)
        return cell(MISSING, {"reason": "no geometry emitted, as expected"}, True)
    if not placed:
        if unsupported:
            return cell(UNSUPPORTED, {"reason": "converter output has only curves this evaluator cannot place: %s" % ", ".join(unsupported)}, False)
        return cell(MISSING, {"reason": "converter output contains no curve"}, False)
    want = expected_world(ent)
    exp = Placed(want)
    scale = numeric.feature_scale(want)
    mag = max(abs(c) for p in exp.samples() + [q for a in placed for q in a.samples()] for c in p)
    tol = pol.tol(scale, mag)
    sdiff = None
    if len(placed) == 1 and not unsupported:
        a = actual_doc["entities"][0]
        sdiff = structural.structural_diff(core(ent) if "world" not in ent else core(ent), core(a))
        if "world" in ent:
            # an instance plus transform: local geometry and the composed matrix must both survive
            t = ent.get("transform") or ent["transform_chain"]["composed"]
            same_matrix = [x["f64_hex"] for x in t["matrix"]] == [x["f64_hex"] for x in a["transform"]["matrix"]]
            if not same_matrix:
                sdiff = sdiff + ["transform"]
        elif a["transform"]["classification"] != "IDENTITY":
            sdiff = sdiff + ["transform (expected a bare curve)"]
        if not sdiff:
            return cell(STRUCTURAL_EXACT, {"fields_compared": len(structural.fields(core(a)))}, None)
    d1, at1, st1 = deviation(pol, exp, placed, scale)
    worst, where, stable, which = d1, at1, st1, "EXPECTED_TO_ACTUAL"
    for a in placed:
        d2, at2, st2 = deviation(pol, a, [exp], scale)
        if d2 > worst:
            worst, where, stable, which = d2, at2, st2, "ACTUAL_TO_EXPECTED"
    ev = {"structural_diff": sdiff if sdiff is not None else ["different number of curves: %d" % len(placed)],
          "max_deviation": worst, "at_unit_parameter": where, "measured_in": which, "estimate_stable": stable,
          "scale": scale, "magnitude": mag}
    if worst <= tol:
        if len(placed) == 1:
            s0, s1 = exp.at(0.0), exp.at(1.0)
            a0, a1 = placed[0].at(0.0), placed[0].at(1.0)
            fwd = curves.dist(s0, a0) <= tol and curves.dist(s1, a1) <= tol
            rev = curves.dist(s0, a1) <= tol and curves.dist(s1, a0) <= tol
            ev["direction"] = "SAME" if fwd else ("REVERSED" if rev else "UNDETERMINED")
        return cell(GEOMETRIC, ev, None)
    return cell(BOUNDED, dict(ev, bound=worst), None)


def cell(klass, evidence, expects_rejection):
    c = {"class": klass, "evidence": evidence}
    if expects_rejection is not None and expects_rejection:
        c["expectation_met"] = klass in (MISSING, UNSUPPORTED)
    return c


def qualify_probe(pol, expected_doc, outputs):
    """outputs: {converter: (verification_doc | None, status_doc | None)}"""
    res = {}
    for conv, (ver, status) in outputs.items():
        res[conv] = [dict(entity=e["id"], **classify_entity(pol, e, ver, status)) for e in expected_doc["entities"]]
    return res


def probe_class(cells):
    """The worst class across a probe's entities (a probe is only as good as its weakest entity)."""
    return max((c["class"] for c in cells), key=lambda k: RANK[k])


def capability_verdicts(pol, results, resolved=()):
    """results: {probe: {converter id: [cell]}}. The ids are whatever the run named, in the order given."""
    convs = list(next(iter(results.values()))) if results else list(CONVERTERS)
    rows = []
    for cap, probes in CAPABILITIES.items():
        # rejection probes are judged by expectation, not by class
        rej = [p for p in probes if p in results and all("expectation_met" in c for conv in convs for c in results[p][conv])]
        per_conv = {}
        for conv in convs:
            classes = [probe_class(results[p][conv]) for p in probes if p in results and p not in rej]
            per_conv[conv] = max(classes, key=lambda k: RANK[k]) if classes else MISSING
        not_run = [p for p in rej if any(c.get("not_run") for conv in convs for c in results[p][conv])]
        rej_fail = [p for p in rej if p not in not_run and not all(c["expectation_met"] for conv in convs for c in results[p][conv])]
        best = min(per_conv.values(), key=lambda k: RANK[k])
        disc = [p for p in probes if p in results and p not in rej
                and len({probe_class(results[p][conv]) in EXACT for conv in convs}) > 1 and p not in resolved]
        cert_struct = best == STRUCTURAL_EXACT and not disc and not rej_fail and not not_run
        cert_geom = best in EXACT and not disc and not rej_fail and not not_run
        reasons = []
        if len(per_conv) > 1 and all(k == BOUNDED for k in per_conv.values()):
            reasons.append("both converters land in BOUNDED_APPROXIMATION: not certified even though they agree")
        elif len(per_conv) == 1 and best == BOUNDED:
            reasons.append("the converter lands in BOUNDED_APPROXIMATION: not certified")
        if not_run:
            reasons.append("probes not run (no source.dwg): %s" % ", ".join(not_run))
        if best not in EXACT and not reasons:
            reasons.append("no converter produced an exact representation (best: %s)" % best)
        if disc:
            reasons.append("unresolved converter discrepancy on: %s" % ", ".join(disc))
        if rej_fail:
            reasons.append("a rejection probe was not honoured: %s" % ", ".join(rej_fail))
        rows.append({"capability": cap, "probes": probes, "converters": convs, "by_converter": per_conv,
                     "certified_structural": cert_struct, "certified_geometric": cert_geom,
                     "status": "CERTIFIED" if cert_geom else "BLOCKED", "reasons": reasons})
    return rows


def load_outputs(root, probe, prefix):
    d = Path(root) / probe if root else None
    ver = stat = None
    if d and (d / (prefix + ".verification.json")).exists():
        ver = verification.load(d / (prefix + ".verification.json"))
        errs = verification.validate_doc(ver)
        if errs:
            raise SystemExit("%s: invalid verification record: %s" % (d, errs[0]))
        if ver["numeric_policy_version"] != numeric.load_policy().version:
            raise SystemExit("%s: verification record carries a different numeric policy version" % d)
    if d and (d / (prefix + ".status.json")).exists():
        stat = json.loads((d / (prefix + ".status.json")).read_text())
    return ver, stat


def is_converter_probe(doc):
    """Layer state has no STEP form, so a probe that records it (layer-state-001) is a DWG reader-mapping
    probe only and is not put through the converters."""
    return not any("layer" in e for e in doc["entities"])


def build_report(pol, probes, outputs_for, resolved=(), no_source=None):
    """no_source: {probe id: why it has no source.dwg}; such a probe was never converted and says so."""
    results = {}
    for pid, doc in probes.items():
        if not is_converter_probe(doc):
            continue
        results[pid] = qualify_probe(pol, doc, outputs_for(pid))
        for cells in results[pid].values():
            for c in cells:
                if pid in (no_source or {}) and c["evidence"].get("reason", "").startswith("no converter output"):
                    c["evidence"]["reason"] = "no source.dwg in the corpus, so the converter was not run: " + no_source[pid]
                    c["not_run"] = True
                    c["expectation_met"] = False   # an expectation nobody exercised has not been met
    ids = list(next(iter(results.values()))) if results else []
    caps = capability_verdicts(pol, results, resolved)
    if len(ids) == 1:
        for r in caps:
            r["reasons"].append("single oracle: no second converter, so no cross-converter discrepancy could be checked")
    return {"schema_version": "pvec-gold/probe-qualification/1", "numeric_policy_version": pol.version,
            "converters": dict(zip(("primary", "secondary"), ids)), "oracle_count": len(ids), "probes": results, "capabilities": caps}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", default="fixtures/known-truth")
    ap.add_argument("--primary", nargs=2, metavar=("ID", "DIR"), required=True)
    ap.add_argument("--secondary", nargs=2, metavar=("ID", "DIR"), help="omit for a single-oracle run (the open route today)")
    ap.add_argument("--oracle-scope", default="OPEN_CONVERTERS", choices=[x for x in ORACLE_SCOPES if x != "NONE"])
    ap.add_argument("--excluded", metavar="QUARANTINE_JSON", help="a corpus quarantine.json: its excluded probes have no source.dwg")
    ap.add_argument("--platform", default="linux/amd64", help="platform the converters ran on, recorded in the report")
    ap.add_argument("--lineage", action="append", default=[], metavar="ID=NAME")
    ap.add_argument("--out", default="reports/phase1/probe-qualification.json")
    ap.add_argument("--resolved")
    a = ap.parse_args(argv)
    (pid_, pdir), (sid_, sdir) = a.primary, a.secondary or (None, None)
    if pid_ == sid_:
        raise SystemExit("--primary and --secondary name the same converter %r: that is one oracle, not two" % pid_)
    ids = [i for i in (pid_, sid_) if i]
    lin = dict(x.split("=", 1) for x in a.lineage)
    bad = lineage_problems([{"id": i, "lineage": lin.get(i, "")} for i in ids])
    if bad:
        raise SystemExit(bad[0])
    if a.oracle_scope == "OPEN_CONVERTERS":
        named = [i for i in ids + [lin[i] for i in ids] if VENDOR_NAME.search(i)]
        if named:
            raise SystemExit("oracle scope OPEN_CONVERTERS never names a vendor, but %r does (ADR 0009)" % named[0])
    pol = numeric.load_policy()
    probes = {}
    for f in sorted(Path(a.probes).rglob("expected.math.json")):
        d = em.load(f)
        probes[d["fixture_id"]] = d
    resolved = json.loads(Path(a.resolved).read_text()) if a.resolved else []
    def outputs_for(pid):
        out = {pid_: load_outputs(pdir, pid, "primary")}
        if sid_:
            out[sid_] = load_outputs(sdir, pid, "secondary")
        return out
    no_source = {}
    if a.excluded:
        no_source = {e["id"]: "%s: %s" % (e["reason"], e["evidence"]) for e in json.loads(Path(a.excluded).read_text())["excluded"]}
    rep = build_report(pol, probes, outputs_for, resolved, no_source)
    rep["lineages"] = {i: lin[i] for i in ids}
    rep["oracle_scope"] = a.oracle_scope
    rep["platform"] = a.platform
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, indent=2) + "\n")
    for r in rep["capabilities"]:
        print("%-18s %-10s %s  %s" % (r["capability"], r["status"], "  ".join("%s=%s" % kv for kv in r["by_converter"].items()), "; ".join(r["reasons"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
