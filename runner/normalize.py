"""Turn a step_eval verification record into an implementation-neutral signature.

    python3 -m runner.normalize IN.verification.json OUT.signature.json

The signature (schema/signature.schema.json, pvec-gold/signature/1) is what two converters'
outputs are compared on and what pvec's generator reads. It is made from the evaluator's record
only; nothing here reads STEP text, and nothing here has a tolerance.

What goes in, and what is dropped on purpose:

  * entity ids (the evaluator's own labels), STEP entity numbers, file offsets, comments and
    anything naming a converter are not carried;
  * entities are ordered by a key derived from their content (class, then the SHA-256 of their
    canonical JSON), so the order of the DATA section cannot show;
  * lengths are converted to metres with the record's scale_to_canonical, one multiplication per
    value (a scale of exactly 1 changes nothing); directions and angles are left alone;
  * the sign of a zero is not a fact (-0 becomes 0);
  * every scalar is {decimal, f64_hex, precision}. The decimal is scientific, so precision, the
    count of significant digits in its mantissa, is unambiguous. Stored values (control points,
    knots, weights, centres, radii, matrices, domains) keep their f64 bits and are written as the
    shortest text that round-trips. Evaluated values (sample parameters, points, tangents,
    curvatures, and the DERIVED_GEOMETRY fields OCCT computes) are compared under the numeric policy by
    runner.verify_signatures, never bit for bit. Sample values are rounded to DERIVED_DIGITS significant digits and f64_hex is the bits of that
    rounded decimal, so the last-digit differences OCCT shows between architectures do not reach
    the signature;
  * the evaluator, OCCT, schema and numeric policy versions are carried.
"""
import hashlib
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator

from . import canon, verification

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "signature.schema.json"
SCHEMA_VERSION = "pvec-gold/signature/1"

# Significant digits kept for evaluated values. OCCT's rational evaluation differs between
# architectures by up to about 9 ulp (docs/validator/step-evaluator.md), roughly 2e-15 relative,
# so 12 digits leaves room for that and still discards nothing a comparison needs.
DERIVED_DIGITS = 12

# Geometry fields that are not file content: OCCT computes them (a line's ends from LINE(point, VECTOR(dir,
# magnitude)) and the trim, an ellipse's major axis by re-normalising the placement frame). They differ in
# the last digits between x86_64 and arm64, so they are derived values like the samples, however they are
# written. Everything else in geometry, and every parameter domain, is stored.
DERIVED_GEOMETRY = {"line": ("start", "end"), "ellipse": ("major_axis",), "elliptical_arc": ("major_axis",)}

LENGTH_POINTS = ("start", "end", "center")
LENGTH_SCALARS = ("radius", "semi_major", "semi_minor")


def _text(sign, digs, exp10):
    mant = digs[0] + ("." + digs[1:] if len(digs) > 1 else "")
    return "%s%se%+d" % (sign, mant, exp10)


def stored(f):
    """A scalar with the bits of f, as the shortest round-tripping scientific decimal."""
    f = 0.0 if f == 0 else f
    if not math.isfinite(f):
        raise canon.CanonError("non-finite value")
    sign, digits, exp = Decimal(repr(f)).as_tuple()
    digs = "".join(map(str, digits)).rstrip("0") or "0"
    lead = len(digits) + exp - 1
    text = _text("-" if sign else "", digs, lead if f != 0 else 0)
    return {"decimal": text, "f64_hex": canon.f64_to_hex(f), "precision": len(digs)}


def derived(f):
    """A scalar rounded to DERIVED_DIGITS significant digits, bits taken from the rounded text."""
    f = 0.0 if f == 0 else f
    if not math.isfinite(f):
        raise canon.CanonError("non-finite value")
    mant, exp = ("%.*e" % (DERIVED_DIGITS - 1, f)).split("e")
    sign = "-" if mant.startswith("-") else ""
    digs = mant.lstrip("-").replace(".", "")
    text = _text(sign, digs, int(exp))
    r = float(text)
    r = 0.0 if r == 0 else r
    return {"decimal": text, "f64_hex": canon.f64_to_hex(r), "precision": DERIVED_DIGITS}


def _f(s):
    return canon.check_scalar(s)


def _scale_len(s, k):
    f = _f(s)
    return f if k == 1.0 else f * k


def _pt(p, k, fn):
    return [fn(_scale_len(c, k)) for c in p]


def _geometry(cls, g, k):
    out = {}
    for key, v in g.items():
        if cls == "unsupported":
            out[key] = v
        elif key in LENGTH_POINTS:
            out[key] = _pt(v, k, stored)
        elif key in LENGTH_SCALARS:
            out[key] = stored(_scale_len(v, k))
        elif key == "vertices" or key == "control_points":
            out[key] = [_pt(p, k, stored) for p in v]
        elif key == "knots":
            out[key] = [{"value": stored(_f(n["value"])), "multiplicity": n["multiplicity"]} for n in v]
        elif key == "weights" or key == "bulges":
            out[key] = [stored(_f(w)) for w in v]
        elif key in ("normal", "x_axis", "major_axis"):
            out[key] = [stored(_f(c)) for c in v]
        elif key in ("start_angle", "sweep_angle"):
            out[key] = stored(_f(v))
        else:
            out[key] = v  # degree, weights_all_unit
    return out


def _transform(t, k):
    m = [_f(x) for x in t["matrix"]]
    if k != 1.0:
        for i in (3, 7, 11):
            m[i] = m[i] * k
    return {"convention": t["convention"], "matrix": [stored(x) for x in m],
            "determinant": stored(_f(t["determinant"])), "classification": t["classification"]}


def _entity(e, k):
    cls = e["class"]
    param_k = k if cls == "line" else 1.0  # a line is parameterised by length
    out = {
        "class": cls,
        "structure": e["structure"],
        "geometry": _geometry(cls, e["geometry"], k),
        "parameter_domain": {"start": stored(_scale_len(e["parameter_domain"]["start"], param_k)),
                             "end": stored(_scale_len(e["parameter_domain"]["end"], param_k))},
        "closure": dict(e["closure"]),
        "transform": _transform(e["transform"], k),
    }
    samples = []
    for s in e["samples"]:
        samples.append({
            "parameter": derived(_scale_len(s["parameter"], param_k)),
            "point": _pt(s["point"], k, derived),
            "tangent": None if s["tangent"] is None else [derived(_f(c)) for c in s["tangent"]],
            "curvature": None if s["curvature"] is None else derived(_f(s["curvature"]) / k),
            "derivative_exclusion": s["derivative_exclusion"],
        })
    samples.sort(key=lambda s: (canon.hex_to_f64(s["parameter"]["f64_hex"]), dumps(s)))
    out["samples"] = samples
    if e.get("derivative_exclusions"):
        ex = [{"parameter": derived(_scale_len(x["parameter"], param_k)), "reason": x["reason"]} for x in e["derivative_exclusions"]]
        out["derivative_exclusions"] = sorted(ex, key=lambda x: canon.hex_to_f64(x["parameter"]["f64_hex"]))
    return out


def dumps(doc):
    """The one serialisation: sorted keys, two-space indent, trailing newline."""
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def sort_key(entity):
    return (entity["class"], hashlib.sha256(dumps(entity).encode("ascii")).hexdigest())


def normalize(rec):
    k = _f(rec["units"]["scale_to_canonical"])
    if not k > 0:
        raise ValueError("units.scale_to_canonical must be positive, got %s" % rec["units"]["scale_to_canonical"]["decimal"])
    ents = sorted((_entity(e, k) for e in rec["entities"]), key=sort_key)
    return {
        "schema_version": SCHEMA_VERSION,
        "versions": {"evaluator": rec["tool"]["evaluator_version"], "occt": rec["tool"]["occt_version"],
                     "schema": SCHEMA_VERSION, "policy": rec["numeric_policy_version"]},
        "units": {"canonical": "metre"},
        "entities": ents,
    }


def _digits(decimal):
    return len(decimal.split("e")[0].lstrip("-").replace(".", ""))


def validate_doc(doc):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = ["schema: %s: %s" % ("/".join(str(p) for p in e.absolute_path), e.message) for e in Draft202012Validator(schema).iter_errors(doc)]
    if errs:
        return errs

    def walk(node, path):
        if isinstance(node, dict):
            if "f64_hex" in node:
                try:
                    canon.check_scalar({"decimal": node["decimal"], "f64_hex": node["f64_hex"]}, path)
                except canon.CanonError as ex:
                    errs.append(str(ex))
                if node["precision"] != _digits(node["decimal"]):
                    errs.append("%s: precision %d is not the %d significant digits of %s" % (path, node["precision"], _digits(node["decimal"]), node["decimal"]))
                return
            for key, v in node.items():
                walk(v, "%s.%s" % (path, key))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))
    walk(doc, "$")
    return errs


def _flat(node, path, out):
    if isinstance(node, dict) and "f64_hex" in node:
        out[path] = (node["decimal"], node["f64_hex"], node["precision"])
    elif isinstance(node, dict):
        for key, v in node.items():
            _flat(v, "%s.%s" % (path, key) if path else key, out)
    elif isinstance(node, list):
        out[path + "#len"] = len(node)
        for i, v in enumerate(node):
            _flat(v, "%s[%d]" % (path, i), out)
    else:
        out[path] = node


def differing_fields(a, b):
    """Paths at which two signatures differ (a scalar is one field), for naming a divergence."""
    x, y = {}, {}
    _flat(a, "", x)
    _flat(b, "", y)
    bad = sorted(p for p in set(x) | set(y) if x.get(p) != y.get(p))
    return [p[:-4] if p.endswith("#len") else p for p in bad]


def run(src, dst):
    rec = verification.load(src)
    errs = verification.validate_doc(rec)
    if errs:
        return errs
    try:
        sig = normalize(rec)
    except ValueError as ex:
        return [str(ex)]
    errs = validate_doc(sig)
    if errs:
        return errs
    Path(dst).write_text(dumps(sig), encoding="utf-8")
    return []


if __name__ == "__main__":
    e = run(sys.argv[1], sys.argv[2])
    for x in e:
        print("FAIL " + x)
    sys.exit(1 if e else 0)
