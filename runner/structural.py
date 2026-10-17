"""Exact structural comparison of two entity records (expected versus a normalised signature).

Structural means bit-for-bit on the stated fields: class, degree, control points, knots with
multiplicities, weights, parameter domain, closure, orientation. No tolerance is involved, so
this module has none. Geometric equivalence under reparameterisation is a different question,
answered with the numeric policy elsewhere.
"""

STRUCTURAL_EXACT = "STRUCTURAL_EXACT"
STRUCTURAL_DIFFERS = "STRUCTURAL_DIFFERS"


def _walk(node, path, out):
    if isinstance(node, dict):
        if set(node) == {"decimal", "f64_hex"}:
            out[path] = node["f64_hex"]
            return
        for k in sorted(node):
            _walk(node[k], path + "." + k if path else k, out)
    elif isinstance(node, list):
        out[path + "#len"] = len(node)
        for i, v in enumerate(node):
            _walk(v, "%s[%d]" % (path, i), out)
    else:
        out[path] = node


def fields(entity):
    keep = {k: entity[k] for k in ("class", "geometry", "parameter_domain", "closure", "orientation") if k in entity}
    out = {}
    _walk(keep, "", out)
    return out


def structural_diff(expected, actual):
    a, b = fields(expected), fields(actual)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def classify(expected, actual):
    return STRUCTURAL_EXACT if not structural_diff(expected, actual) else STRUCTURAL_DIFFERS


def rejection_verdict(expected_entity, actual_curve):
    """For an entity that carries a rejection: emitting any curve is a failure."""
    if "rejection" not in expected_entity:
        raise ValueError("entity has no expected rejection")
    return "FAIL" if actual_curve is not None else "PASS"
