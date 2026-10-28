#!/usr/bin/env python3
"""Derive the edge, mixed-entity, degenerate and negative corpus records from their parameter files.

    python3 tools/authoring/author_corpus.py           write the records
    python3 tools/authoring/author_corpus.py --check   fail if what is on disk differs

Inputs are tools/authoring/corpus-params/<group>/*.json, chosen before any DWG existed. Edge and mixed
fixtures get an expected.math.json through the same derivation as author_probes.py (which this imports and
does not change). Degenerate fixtures get an expected.rejection.json: mathematics cannot state a
zero-length line or a zero-radius circle, so the record states the authored parameters and the refusal a
pipeline owes. Negative fixtures get an expected.classification.json. No value here comes from a DWG, a
reader, a STEP file or a converter.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "authoring"))
import author_probes as ap  # noqa: E402
from runner import canon, expected_math as em  # noqa: E402

CP = ROOT / "tools" / "authoring" / "corpus-params"
KT = ROOT / "fixtures" / "known-truth"
NEG = ROOT / "fixtures" / "negative"
SCRIPT = "tools/authoring/author_corpus.py"

# What a pipeline owes for each degenerate reason: the code it reports, and that it emits no geometry.
REJECTIONS = {
    "ZERO_LENGTH_SEGMENT": "DEGENERATE_ZERO_LENGTH_SEGMENT",
    "ZERO_RADIUS": "DEGENERATE_ZERO_RADIUS",
    "COINCIDENT_CONTROL_POINTS": "DEGENERATE_COINCIDENT_CONTROL_POINTS",
}

# The expected outcome for each negative variant, authored from the PVec v1 boundary and not from what
# any reader returned. UNSUPPORTED: recognised and refused. IGNORED: dropped by policy. MISSING: the
# converter is expected to emit nothing at all. Entity names are DXF names.
NEGATIVE = {
    "hatch": ("HATCH", "IGNORED", "A pattern fill is presentation. It has no stroke of its own and the boundary it fills is not asserted as a curve, so v1 drops it by policy."),
    "hatch-gradient": ("HATCH", "IGNORED", "A gradient fill is presentation with a colour ramp on top of a hatch. v1 drops it by policy and never renders a ramp."),
    "dimension": ("DIMENSION", "UNSUPPORTED", "A dimension is an annotation whose lines and arrowheads live in a generated anonymous block and a style. v1 has no annotation entity and does not explode one."),
    "text": ("TEXT", "IGNORED", "Single-line text is not geometry v1 carries, and no glyph outline is promised. It is dropped by policy."),
    "mtext": ("MTEXT", "IGNORED", "Multiline text is not geometry v1 carries, and no glyph outline is promised. It is dropped by policy."),
    "solid3d": ("3DSOLID", "UNSUPPORTED", "An ACIS solid is three-dimensional boundary-representation data, outside the 2D profile. It is recognised and refused."),
    "mesh": ("MESH", "UNSUPPORTED", "A subdivision mesh is faceted surface geometry, outside the 2D profile. It is recognised and refused."),
    "region": ("REGION", "UNSUPPORTED", "A region is an ACIS face, outside the 2D profile. It is recognised and refused."),
    "proxy": ("ACAD_PROXY_ENTITY", "MISSING", "A proxy or custom entity is opaque application data with no decodable geometry, and a reader that cannot instantiate it returns nothing for it. The converter is expected to emit nothing, which is different from recognising and refusing it."),
    "ole": ("OLE2FRAME", "UNSUPPORTED", "An embedded OLE object is a foreign document, not geometry. It is recognised and refused."),
    "wipeout": ("WIPEOUT", "IGNORED", "A wipeout is a masking boundary, a display effect that draws nothing of its own. v1 drops it by policy."),
    "table": ("ACAD_TABLE", "UNSUPPORTED", "A table is a grid of generated lines and text with a style. v1 has no table entity and does not explode one."),
    "image": ("IMAGE", "IGNORED", "A raster image is an external pixel reference, not vector geometry. v1 drops it by policy."),
    "xref": ("XREF", "UNSUPPORTED", "An external reference points at geometry in another file that the pipeline does not resolve. It is recognised and refused."),
    "empty": (None, "MISSING", "The drawing holds no entity at all, so the converter is expected to emit nothing."),
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def readme(title, body):
    return "# %s\n\n%s\n" % (title, body)


# ---- edge and mixed -----------------------------------------------------------------------------

def edge_fixtures():
    for p in sorted((CP / "edge").glob("*.json")):
        rel, expected, _ = ap.build_fixture(p)
        s = json.loads(p.read_text())
        body = ("%s\n\nI authored this edge case from `%s`, and `expected.math.json` is derived from those parameters alone by "
                "`tools/authoring/author_probes.py`. The DWG is written by the acadrust writer from the record's `f64_hex` numbers "
                "(tools/corpus/writer) and checked against it by two readers, so the evidence is reader mapping only "
                "(`READER_MAPPING_ONLY`). No expected value comes from `primary.step` or `secondary.step`, and no STEP file was produced for it."
                % (s["description"], str(p.relative_to(ROOT))))
        yield str(rel), {"expected.math.json": expected, "README.md": readme(s["id"], body)}


def mixed_fixtures():
    for p in sorted((CP / "mixed").glob("*.json")):
        raw = p.read_bytes()
        s = json.loads(raw)
        ents, asserts_by = [], []
        for sub in s["entities"]:
            eid = "%s.%s" % (s["id"], sub["name"])
            if sub.get("kind") == "transform":
                ent, asserts, _ = ap.build_transform_fixture(dict(sub, id=eid))
                ents.append(ent)
                asserts_by += [(eid, a) for a in asserts]
            else:
                kind = sub["class"]
                rec = ap.build_curve(sub)
                ents.append({"id": eid, **rec, "structure": "CURVE_ONLY"})
                for c in ap.STRUCT_CLAIMS[kind]:
                    asserts_by.append((eid, ("STRUCTURAL", c, ap.CLAIM_TEXT[c] % kind if c == "CLASS_PRESERVED" else ap.CLAIM_TEXT[c])))
                asserts_by.append((eid, ("GEOMETRIC", "PARAMETERIZATION_PRESERVED", "The parameter domain is kept; a reparameterised equivalent counts as geometric only.")))
        rel = str(p.relative_to(ROOT))
        doc = {
            "schema_version": "pvec-gold/expected.math/1",
            "fixture_id": s["id"],
            "evidence_class": "KNOWN_TRUTH_EXACT",
            "units": {"name": "metre", "canonical": "metre", "scale_to_canonical": ap.S("1")},
            "provenance": {"derivation": "AUTHORING_PARAMETERS", "authoring_script": SCRIPT, "parameter_file": rel,
                           "parameter_file_sha256": sha(raw), "parameters": s},
            "entities": ents,
            "assertions": [{"id": "a%d" % (i + 1), "kind": k, "entity": e, "claim": c, "statement": t} for i, (e, (k, c, t)) in enumerate(asserts_by)],
        }
        ex = ap.exclusions_for(ents)
        if ex:
            doc["derivative_exclusions"] = ex
        errs = em.validate_doc(json.loads(json.dumps(doc), parse_float=em._no_floats))
        if errs:
            raise SystemExit("%s does not validate:\n  %s" % (s["id"], "\n  ".join(errs)))
        body = ("%s\n\nI authored this drawing from `%s`; `expected.math.json` is derived from those parameters alone by `%s`. "
                "The curve classes are %s. Two entities sit behind block instances: a line behind three nested levels "
                "(translate, rotate, non-uniform scale) and a circle behind one uniform scale. The DWG is written from the "
                "record's `f64_hex` numbers by tools/corpus/writer and read back by two readers (`READER_MAPPING_ONLY`)."
                % (s["description"], rel, SCRIPT, ", ".join(sorted({e["class"] for e in ents}))))
        yield "mixed/" + s["id"], {"expected.math.json": json.dumps(doc, indent=2) + "\n", "README.md": readme(s["id"], body)}


# ---- degenerate -----------------------------------------------------------------------------------

def authored_geometry(s):
    t = s["dwg_entity"]
    if t == "LINE":
        return {"start": [canon.scalar(c) for c in s["start"]], "end": [canon.scalar(c) for c in s["end"]]}
    if t == "CIRCLE":
        return {"center": [canon.scalar(c) for c in s["center"]], "radius": canon.scalar(s["radius"])}
    return {"degree": s["degree"], "control_points": [[canon.scalar(c) for c in p] for p in s["control_points"]],
            "knots": [canon.scalar(k) for k in s["knots"]]}


def degenerate_fixtures():
    for p in sorted((CP / "degenerate").glob("*.json")):
        raw = p.read_bytes()
        s = json.loads(raw)
        rel = str(p.relative_to(ROOT))
        doc = {
            "schema_version": "pvec-gold/expected.rejection/1",
            "fixture_id": s["id"],
            "evidence_class": "QUARANTINED",
            "quarantine_reason": "MALFORMED_FIXTURE",
            "authored": {"dwg_entity": s["dwg_entity"], "geometry": authored_geometry(s)},
            "expected_rejection": {"classification": REJECTIONS[s["reason"]], "disposition": "REJECT", "geometry_emitted": False},
            "provenance": {"derivation": "AUTHORING_PARAMETERS", "authoring_script": SCRIPT, "parameter_file": rel,
                           "parameter_file_sha256": sha(raw), "parameters": s},
            "assertion": "A pipeline that produces geometry for this fixture has failed. Mathematics cannot state this entity as a curve, "
                         "so there is no expected.math.json, and the fixture is quarantined by design (ADR 0006), never accepted.",
        }
        body = ("%s\n\nI authored this from `%s`. It is the degenerate case: the expected outcome is the refusal `%s`, with no geometry "
                "emitted. It has no `expected.math.json` because the record validator rejects a zero-length line, a zero radius "
                "and a spline with no extent, which is the point. The DWG carries the entity as authored."
                % (s["description"], rel, REJECTIONS[s["reason"]]))
        yield "degenerate/" + s["id"], {"expected.rejection.json": json.dumps(doc, indent=2) + "\n", "README.md": readme(s["id"], body)}


# ---- negative ---------------------------------------------------------------------------------------

def negative_fixtures():
    for p in sorted((CP / "negative").glob("*.json")):
        raw = p.read_bytes()
        s = json.loads(raw)
        dxf, outcome, reason = NEGATIVE[s["variant"]]
        ents = [] if dxf is None else [{"dwg_type": dxf, "count": 1, "outcome": outcome, "reason": reason}]
        if s["variant"] == "hatch-gradient":
            ents[0]["gradient"] = True
        doc = {
            "schema_version": "pvec-gold/expected.classification/1",
            "fixture_id": s["id"],
            "evidence_class": "QUARANTINED",
            "quarantine_reason": "UNSUPPORTED_ENTITY",
            "entities": ents,
            "converter_emits_nothing": outcome == "MISSING",
            "outcome": outcome,
            "reason": reason,
            "accepted_geometry": [],
            "provenance": {"derivation": "AUTHORING_PARAMETERS", "authoring_script": SCRIPT,
                           "parameter_file": str(p.relative_to(ROOT)), "parameter_file_sha256": sha(raw)},
        }
        what = "an empty drawing" if dxf is None else "one %s entity%s" % (dxf, " with a gradient" if s["variant"] == "hatch-gradient" else "")
        body = ("%s: %s.\n\nI authored the expectation before writing the DWG: `%s`. %s The drawing holds %s and nothing else, so any "
                "geometry a pipeline accepts from it is a failure. It is `QUARANTINED` with reason `UNSUPPORTED_ENTITY` (ADR 0006), "
                "never `KNOWN_TRUTH_EXACT`, and it carries no `expected.math.json`."
                % (s["id"], outcome, outcome, reason, what))
        yield "negative/" + s["id"], {"params.json": raw.decode(), "expected.classification.json": json.dumps(doc, indent=2) + "\n", "README.md": readme(s["id"], body)}


def all_fixtures():
    yield from edge_fixtures()
    yield from mixed_fixtures()
    yield from degenerate_fixtures()
    yield from negative_fixtures()


def main(argv):
    check = "--check" in argv
    bad = 0
    for rel, files in all_fixtures():
        d = ROOT / "fixtures" / rel
        for name, text in files.items():
            f = d / name
            if check:
                if not f.exists() or f.read_text() != text:
                    print("stale: %s" % f)
                    bad += 1
            else:
                d.mkdir(parents=True, exist_ok=True)
                f.write_text(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
