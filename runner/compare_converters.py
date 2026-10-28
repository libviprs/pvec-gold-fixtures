"""Classify the primary converter's signature against the secondary's, and quarantine material disagreement.

    python3 -m runner.compare_converters --fixture DIR --manifest MANIFEST.json [--quarantine FILE] [--differences FILE]

DIR holds primary.signature.json and secondary.signature.json, and expected.math.json when the fixture has
known truth. The result is the converter section of comparison.json (schema/converter-section.schema.json),
plus the two per-converter reports written next to it when there is a known truth.

The oracles are whatever the revision's manifest names (ADR 0009): the primary open converter (ACadSharp
lineage) and a secondary of another lineage (the LibreDWG converter, libviprs/pvec-oracle-libredwg) for the
open route. This module never looks at an id, only at the
lineages, which must differ, and at the oracle scope, which must not be NONE.

Classes: MATCH, EXACT_REPARAMETERIZATION, EQUIVALENT_GEOMETRY, MATERIAL_DIFFERENCE.

Precedence, implemented here and not only documented: where expected.math.json exists the verdict against
the known truth governs. Each converter is classified against the truth first. If either lands outside the
exact classes, the fixture is a MATERIAL_DIFFERENCE, including the case where the two converters agree with
each other: two tools agreeing on a value that contradicts the authored mathematics are both wrong, and the
section says that. Only when both are exact against the truth is the pair classified against each other.
With no known truth the signatures are compared as they stand, structurally first and then geometrically.

Agreement is DUAL_ORACLE_EQUIVALENT evidence (ADR 0001), never source truth, and the section says so in its
own words. Classification reads signatures only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import compare_geometric as geo, compare_structural as st, expected_math as em, normalize, numeric
from .qualify_probes import BOUNDED, GEOMETRIC, STRUCTURAL_EXACT
from .r0_open import ORACLE_SCOPES, lineage_problems

SCHEMA_VERSION = "pvec-gold/converter-section/1"
MATCH, REPARAM, EQUIVALENT, MATERIAL = "MATCH", "EXACT_REPARAMETERIZATION", "EQUIVALENT_GEOMETRY", "MATERIAL_DIFFERENCE"
EXACT = (STRUCTURAL_EXACT, GEOMETRIC)
KEYS = ("id", "version", "lineage", "image_digest")


class ComparisonRefused(ValueError):
    pass


def digest(sig):
    return hashlib.sha256(normalize.dumps(sig).encode("ascii")).hexdigest()


def _check_inputs(converters, scope):
    if scope not in ORACLE_SCOPES or scope == "NONE":
        raise ComparisonRefused("oracle_scope %r cannot carry a converter comparison (ADR 0009)" % (scope,))
    if len(converters) != 2:
        raise ComparisonRefused("a converter comparison needs exactly two named converters, got %d" % len(converters))
    for c in converters:
        miss = [k for k in KEYS if not str(c.get(k, "")).strip()]
        if miss:
            raise ComparisonRefused("converter %r lacks %s" % (c.get("id"), ", ".join(miss)))
    bad = lineage_problems(converters)
    if bad:
        raise ComparisonRefused(bad[0])


def against_truth(pol, expected_doc, sig):
    """(class, structural report, geometric report, deciding) for one converter against the known truth."""
    g = geo.compare(pol, expected_doc, sig)
    s = st.compare(pol, expected_doc, sig, geometric=g)
    if s["class"] == "STRUCTURAL_EXACT":
        return STRUCTURAL_EXACT, s, g, None
    return g["class"], s, g, deciding_geometric(g, s)


def first_difference(s):
    for e in s["entities"]:
        for f in e["fields"]:
            if f["verdict"] != "MATCH":
                return f["field"]
        if not e["matched"]:
            return "entities (no counterpart for %s)" % e["entity"]
    return "entities (unexpected extra: %s)" % s["unmatched_produced"] if s["unmatched_produced"] else None


def deciding_geometric(g, s):
    qs = [x for r in g["entities"] for x in r["quantities"]] + g["fixture_quantities"]
    if g["class"] == GEOMETRIC or not qs:
        return {"field": first_difference(s) or g["class"], "deviation": 0.0, "unit": "metre", "at_unit_parameter": 0.0}
    worst = max(qs, key=lambda x: x["deviation"])
    return {"field": worst["quantity"], "deviation": worst["deviation"], "unit": worst["unit"], "at_unit_parameter": worst["at_unit_parameter"]}


def signature_views(sig):
    return [st.bare(e) for e in sig["entities"]], ["entity-%d" % i for i in range(len(sig["entities"]))]


def between(pol, a, b):
    """Primary against secondary with no known truth: (class, deciding)."""
    views, ids = signature_views(a)
    s = st.compare_views(pol, "pair", ids, views, b)
    if s["class"] == "STRUCTURAL_EXACT":
        return MATCH, None
    g = geo.compare_views(pol, "pair", ids, views, b)
    field = first_difference(s)
    if g["class"] != GEOMETRIC:
        d = deciding_geometric(g, s) if g["class"] == BOUNDED else {"field": field or g["class"], "deviation": 0.0, "unit": "metre", "at_unit_parameter": 0.0}
        return MATERIAL, d
    d = {"field": field, "deviation": max([x["deviation"] for r in g["entities"] for x in r["quantities"]] or [0.0]), "unit": "metre",
         "at_unit_parameter": 0.0}
    same_class = sorted(e["class"] for e in a["entities"]) == sorted(e["class"] for e in b["entities"])
    return (REPARAM if same_class else EQUIVALENT), d


def statement(klass, governing, truth, agree, scope, deciding):
    if klass == MATERIAL and governing == "KNOWN_TRUTH":
        if agree:
            return ("both converters agree with each other and both contradict expected.math.json (%s, deviation %.3g %s): "
                    "the authored mathematics governs, so the agreement is not a match" % (deciding["field"], deciding["deviation"], deciding["unit"]))
        who = [k for k, v in truth.items() if v not in EXACT]
        return "the %s converter contradicts expected.math.json (%s, deviation %.3g %s)" % (" and ".join(who), deciding["field"], deciding["deviation"], deciding["unit"])
    if klass == MATERIAL:
        return "the converters disagree materially (%s, deviation %.3g %s)" % (deciding["field"], deciding["deviation"], deciding["unit"])
    return ("the two %s converters give %s signatures: DUAL_ORACLE_EQUIVALENT evidence, not source truth, and no statement about what "
            "the original DWG meant" % (scope, klass))


def quarantine_for(klass, governing, truth, agree, statement_text):
    if klass != MATERIAL:
        return None
    reason = "UNRESOLVED_DISAGREEMENT"
    if governing == "KNOWN_TRUTH" and agree:
        worst = {v for v in truth.values()}
        reason = "APPROXIMATION" if worst == {BOUNDED} else ("UNSUPPORTED_ENTITY" if worst <= {"UNSUPPORTED", "MISSING"} else reason)
    return {"state": "QUARANTINED", "reason": reason, "detail": statement_text}


def classify_fixture(pol, expected_doc, a, b, converters, scope, reports=None):
    """The converter section for one fixture. reports, if a dict, receives the per-converter reports."""
    _check_inputs(converters, scope)
    truth, deciding, agree, governing = None, None, None, "SIGNATURE_COMPARISON"
    if expected_doc is not None:
        governing = "KNOWN_TRUTH"
        res = {k: against_truth(pol, expected_doc, sig) for k, sig in (("primary", a), ("secondary", b))}
        truth = {k: v[0] for k, v in res.items()}
        if reports is not None:
            for k, v in res.items():
                reports[k] = {"structural": v[1], "geometric": v[2]}
        bad = [k for k, v in res.items() if v[0] not in EXACT]
        if bad:
            klass, deciding = MATERIAL, res[bad[0]][3] | {"converter": bad[0]}
            agree = len(bad) == 2 and between(pol, a, b)[0] != MATERIAL
        elif all(v[0] == STRUCTURAL_EXACT for v in res.values()):
            klass = MATCH
        else:
            klass, deciding = between(pol, a, b)
    else:
        klass, deciding = between(pol, a, b)
    text = statement(klass, governing, truth, agree, scope, deciding)
    return {
        "schema_version": SCHEMA_VERSION,
        "class": klass,
        "governing": governing,
        "truth": truth,
        "deciding": deciding,
        "statement": text,
        "evidence": None if klass == MATERIAL else {"class": "DUAL_ORACLE_EQUIVALENT", "is_source_truth": False,
                                                     "evidence_scope": "STEP_ORACLE", "oracle_scope": scope},
        "quarantine": quarantine_for(klass, governing, truth, agree, text),
        "converters": [{k: c[k] for k in KEYS} for c in converters],
        "signatures": {"primary_sha256": digest(a), "secondary_sha256": digest(b)},
        "numeric_policy_version": pol.version,
        "signature_schema_version": a["schema_version"],
    }


def quarantine_add(doc, fixture_id, section):
    """Add a MATERIAL_DIFFERENCE to the quarantine list, once. A clean section changes nothing."""
    q = section["quarantine"]
    if q is None or any(e["id"] == fixture_id for e in doc["quarantined"]):
        return
    doc["quarantined"].append({"id": fixture_id, "reason": q["reason"], "evidence": q["detail"], "state": q["state"]})


def construct(section):
    """The grouping key of the differences report: the field family that decided (geometry.weights, class, bounds...)."""
    parts = (section["deciding"] or {}).get("field", "").split("[")[0].split(".")
    return ".".join(parts[:2]) if parts[0] in ("geometry", "parameter_domain", "closure", "transform") and len(parts) > 1 else parts[0]


def render_differences(sections, pol):
    """docs-style markdown: differences grouped by class, then by construct, so a pattern shows as a pattern."""
    first = next(iter(sections.values()), None)
    lines = ["# Converter differences", "",
             "Numeric policy: %s. Classification reads signatures only." % pol.version, ""]
    if first:
        lines.append("Converters: " + "; ".join("%s %s (%s, %s)" % (c["id"], c["version"], c["lineage"], c["image_digest"]) for c in first["converters"]) + ".")
        lines.append("")
    counts = {}
    for s in sections.values():
        counts[s["class"]] = counts.get(s["class"], 0) + 1
    lines.append("Fixtures: " + ", ".join("%d %s" % (n, k) for k, n in sorted(counts.items())) + ". Agreement is DUAL_ORACLE_EQUIVALENT evidence, not source truth.")
    lines.append("")
    for klass in (REPARAM, EQUIVALENT, MATERIAL):
        rows = sorted((construct(s), fid, s) for fid, s in sections.items() if s["class"] == klass)
        if not rows:
            continue
        lines += ["## " + klass, "", "| construct | fixture | deciding field | deviation | governed by |", "|---|---|---|---|---|"]
        for c, fid, s in rows:
            d = s["deciding"]
            lines.append("| %s | %s | %s | %.3g %s | %s |" % (c, fid, d["field"], d["deviation"], d["unit"], s["governing"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--quarantine")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    pol = numeric.load_policy()
    d = Path(a.fixture)
    manifest = json.loads(Path(a.manifest).read_text())
    exp = em.load(d / "expected.math.json") if (d / "expected.math.json").exists() else None
    load = lambda n: json.loads((d / n).read_text())  # noqa: E731
    reports = {}
    try:
        sec = classify_fixture(pol, exp, load("primary.signature.json"), load("secondary.signature.json"),
                               manifest.get("converters", []), manifest.get("oracle_scope"), reports)
    except ComparisonRefused as e:
        print("REFUSED " + str(e))
        return 2
    for k, rs in reports.items():
        for kind, rep in rs.items():
            (d / ("%s.%s.json" % (k, kind))).write_text(normalize.dumps(rep))
    Path(a.out or d / "converter-section.json").write_text(normalize.dumps(sec))
    if a.quarantine:
        qp = Path(a.quarantine)
        qd = json.loads(qp.read_text())
        quarantine_add(qd, exp["fixture_id"] if exp else d.name, sec)
        qp.write_text(json.dumps(qd, indent=2, sort_keys=True) + "\n")
    print("%s %s" % (d.name, sec["class"]))
    return 0 if sec["class"] != MATERIAL else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
