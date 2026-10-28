"""The structural-exactness report: expected.math.json against one converter's signature, field by field.

    python3 -m runner.compare_structural EXPECTED.math.json SIGNATURE.json OUT.json [--geometric GEOMETRIC.json]

Structural exactness is the question "did the converter hand back the same representation?": same
class, degree, control points, knots and multiplicities, weights, parameter domain, closure and
transform, bit for bit. A curve that traces the right path with other parameters is not structurally
exact, and this report says so; whether the path is right is the geometric report's business
(runner/compare_geometric.py) and the two are never merged into one word.

Per entity and per field the verdict is MATCH, REPARAMETERIZED or DIFFERENT. Integer fields (degree,
multiplicity, counts) and real fields (compared on their f64 bits) are both exact here, so this module
has no tolerance. REPARAMETERIZED is only ever set from a geometric report that found the entity's
geometry equal under the numeric policy: it marks a representation field that changed while the curve
did not. It does not make the report structurally exact. The overall class stays STRUCTURAL_DIFFERS
until every field is MATCH.

Nothing here reads STEP text. A report is refused when there is no expected.math.json, so the two
converters are never compared against each other under this name.
"""
import argparse
import json
import platform
import sys
from pathlib import Path

from . import canon, expected_math as em, normalize, numeric
from .structural import STRUCTURAL_DIFFERS, STRUCTURAL_EXACT

SCHEMA_VERSION = "pvec-gold/structural-report/1"
MATCH, REPARAMETERIZED, DIFFERENT = "MATCH", "REPARAMETERIZED", "DIFFERENT"
KEEP = ("class", "geometry", "parameter_domain", "closure")
REPARAM_PREFIXES = ("geometry.", "parameter_domain.")


class ReportRefused(ValueError):
    pass


def bare(node):
    """A signature scalar {decimal, f64_hex, precision} as the {decimal, f64_hex} the evaluator code reads."""
    if isinstance(node, dict):
        if "f64_hex" in node:
            return {"decimal": node["decimal"], "f64_hex": node["f64_hex"]}
        return {k: bare(v) for k, v in node.items()}
    if isinstance(node, list):
        return [bare(v) for v in node]
    return node


def identity_transform():
    m = [1.0 if i in (0, 5, 10, 15) else 0.0 for i in range(16)]
    return {"convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": [canon.scalar(x) for x in m],
            "determinant": canon.scalar(1.0), "classification": "IDENTITY"}


def scale_of(expected_doc):
    return canon.check_scalar(expected_doc["units"]["scale_to_canonical"])


def expected_view(ent, k):
    """The expected entity written the way a signature writes it: metres, stored scalars, a transform."""
    t = ent.get("transform") or (ent.get("transform_chain") or {}).get("composed")
    rec = {x: ent[x] for x in ("class", "structure", "geometry", "parameter_domain", "closure")}
    rec["transform"] = t or identity_transform()
    rec["samples"] = []
    return normalize._entity(rec, k)


def _leaves(node, path, out):
    if isinstance(node, dict) and "f64_hex" in node:
        out[path] = {"decimal": node["decimal"], "f64_hex": node["f64_hex"]}
    elif isinstance(node, dict):
        for key in sorted(node):
            _leaves(node[key], "%s.%s" % (path, key) if path else key, out)
    elif isinstance(node, list):
        out[path + ".length"] = len(node)
        for i, v in enumerate(node):
            _leaves(v, "%s[%d]" % (path, i), out)
    else:
        out[path] = node


def fields(entity):
    """Path to leaf for the structural fields. The transform is part of an instance, and a bare curve must be the identity."""
    keep = {k: entity[k] for k in KEEP if k in entity}
    t = entity.get("transform")
    if t is not None:
        keep["transform"] = {"matrix": t["matrix"]}
    out = {}
    _leaves(keep, "", out)
    if t is not None and entity.get("structure") != "INSTANCE_PLUS_TRANSFORM":
        out["transform.classification"] = t["classification"]
    return out


def kind(v):
    if isinstance(v, dict):
        return "REAL"
    return "INTEGER" if isinstance(v, int) and not isinstance(v, bool) else "CATEGORICAL"


def _same(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a["f64_hex"] == b["f64_hex"]
    return type(a) is type(b) and a == b


def diff_fields(want, got):
    """Ordered list of (path, expected, produced) for every path present on either side."""
    paths = list(want) + [p for p in got if p not in want]
    return [(p, want.get(p), got.get(p)) for p in paths]


def pair(views, produced):
    """Greedy pairing of expected entities to signature entities: same class first, then fewest differing fields."""
    used, out = set(), []
    for v in views:
        fv = fields(v)
        best = None
        for j, s in enumerate(produced):
            if j in used:
                continue
            fs = fields(dict(s, structure=v.get("structure")))
            n = sum(1 for _, a, b in diff_fields(fv, fs) if not _same(a, b))
            key = (s["class"] != v["class"], n, j)
            if best is None or key < best[0]:
                best = (key, j)
        if best is None:
            out.append(None)
        else:
            used.add(best[1])
            out.append(best[1])
    return out


def _entity_report(ent_id, view, produced, j, promote):
    if j is None:
        return {"entity": ent_id, "matched": False, "signature_index": None, "class": STRUCTURAL_DIFFERS, "fields": []}
    want, got = fields(view), fields(dict(produced, structure=view.get("structure")))
    rows = []
    for path, a, b in diff_fields(want, got):
        if _same(a, b):
            verdict = MATCH
        else:
            verdict = REPARAMETERIZED if promote and path.startswith(REPARAM_PREFIXES) else DIFFERENT
        rows.append({"field": path, "kind": kind(a if a is not None else b), "verdict": verdict, "expected": a, "produced": b})
    exact = all(r["verdict"] == MATCH for r in rows)
    return {"entity": ent_id, "matched": True, "signature_index": j,
            "class": STRUCTURAL_EXACT if exact else STRUCTURAL_DIFFERS, "fields": rows}


def compare(pol, expected_doc, sig, geometric=None):
    if expected_doc is None:
        raise ReportRefused("no expected.math.json for this fixture: a structural report compares a signature to known truth, "
                            "and I will not compare two converters to each other under that name")
    k = scale_of(expected_doc)
    ents = [e for e in expected_doc["entities"] if "rejection" not in e]
    rejected = [e for e in expected_doc["entities"] if "rejection" in e]
    return compare_views(pol, expected_doc["fixture_id"], [e["id"] for e in ents], [expected_view(e, k) for e in ents],
                         sig, geometric, [e["id"] for e in rejected])


def compare_views(pol, fixture_id, ids, views, sig, geometric=None, rejected=()):
    """The comparison proper: views are entities written the way a signature writes them. The expected record
    and, for two converters with no known truth, the primary signature both reach it this way."""
    produced = [bare(e) for e in sig["entities"]]
    idx = pair(views, produced)
    equal = {}
    if geometric is not None:
        equal = {r["entity"]: r["equivalent"] for r in geometric["entities"]}
    rows = [_entity_report(i, v, produced[j] if j is not None else None, j, equal.get(i, False))
            for i, v, j in zip(ids, views, idx)]
    left = [j for j in range(len(produced)) if j not in idx]
    for rid in rejected:   # an entity with an expected rejection is honoured when nothing is left over
        rows.append({"entity": rid, "matched": False, "signature_index": None, "rejection_expected": True,
                     "class": STRUCTURAL_EXACT if not produced else STRUCTURAL_DIFFERS, "fields": []})
    ok = all(r["class"] == STRUCTURAL_EXACT for r in rows) and not left
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "numeric_policy_version": pol.version,
        "signature_schema_version": sig["schema_version"],
        "stage": {"name": "compare_structural", "architecture": platform.machine()},
        "class": STRUCTURAL_EXACT if ok else STRUCTURAL_DIFFERS,
        "unmatched_produced": left,
        "entities": rows,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("expected")
    ap.add_argument("signature")
    ap.add_argument("out")
    ap.add_argument("--geometric")
    a = ap.parse_args(argv)
    pol = numeric.load_policy()
    exp = em.load(a.expected) if Path(a.expected).exists() else None
    sig = json.loads(Path(a.signature).read_text())
    geo = json.loads(Path(a.geometric).read_text()) if a.geometric else None
    try:
        rep = compare(pol, exp, sig, geo)
    except ReportRefused as e:
        print("REFUSED " + str(e))
        return 2
    Path(a.out).write_text(normalize.dumps(rep))
    print("%s %s" % (rep["fixture_id"], rep["class"]))
    return 0 if rep["class"] == STRUCTURAL_EXACT else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
