"""Re-derive every frozen signature from its retained STEP file and prove it is the same, byte for byte.

    python3 -m runner.verify_signatures signatures [--evaluator step_eval]

Stored values (control points, knots, weights, radii, domains) are compared bit for bit. Values OCCT derives
(sample parameters, points, tangents and curvatures, a line's ends, an ellipse's major axis) are compared under the
vendored numeric policy (NP-05), so a native arm64 run passes against the x86_64 set. The manifest hash covers the
frozen file's bytes, stored and derived alike, and is checked as before.

This is the job that catches signature drift: an evaluator, normaliser or policy change that moves a value,
or a signature edited by hand. A difference is reported with the dotted path of every field that differs; a
byte difference with no differing field (spelling, order, whitespace) fails as "<bytes differ, no field
named>", so no difference is ever silent. Needs step_eval, so it runs in the step-validator image.
"""
import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from . import canon, normalize, numeric, signatures, verification

UNNAMED = "<bytes differ, no field named>"


def derive_with(evaluator):
    def derive(step):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "v.json"
            r = subprocess.run([evaluator, "--in", str(step), "--out", str(out), "--policy-version", numeric.load_policy().version],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("step_eval exited %d on %s: %s" % (r.returncode, step, r.stderr.strip()))
            return normalize.normalize(verification.load(out))
    return derive


def _derived_leaves(e):
    """(stored part of entity e, {path: scalar} of the values OCCT derives). e is not changed."""
    stored, leaves = copy.deepcopy(e), {}

    def take(node, path):
        if isinstance(node, list):
            for i, x in enumerate(node):
                take(x, "%s[%d]" % (path, i))
        elif node is not None:
            leaves[path] = node
    for key in normalize.DERIVED_GEOMETRY.get(e.get("class"), ()):
        if key in stored.get("geometry", {}):
            take(stored["geometry"].pop(key), "geometry." + key)
    for i, s in enumerate(stored.get("samples", [])):
        for key in ("parameter", "point", "tangent", "curvature"):
            take(s.pop(key, None), "samples[%d].%s" % (i, key))
    for i, x in enumerate(stored.get("derivative_exclusions", [])):
        take(x.pop("parameter", None), "derivative_exclusions[%d].parameter" % i)
    return stored, leaves


def _plain(n):
    if isinstance(n, dict) and "f64_hex" in n:
        return {"decimal": n["decimal"], "f64_hex": n["f64_hex"]}
    if isinstance(n, dict):
        return {k: _plain(v) for k, v in n.items()}
    return [_plain(v) for v in n] if isinstance(n, list) else n


def _scale(e):
    try:
        return numeric.feature_scale(_plain(e))
    except (numeric.PolicyError, KeyError, ValueError, IndexError):
        return 0.0


def compare(frozen, fresh, pol=None):
    """Paths at which two signatures differ: any stored value bitwise, derived values beyond the policy tolerance."""
    pol = pol or numeric.load_policy()
    rest = lambda d: {k: v for k, v in d.items() if k != "entities"}
    diffs = normalize.differing_fields(rest(frozen), rest(fresh))
    fa, fb = frozen.get("entities", []), fresh.get("entities", [])
    if len(fa) != len(fb):
        return diffs + ["entities"]
    pa, pb = [_derived_leaves(e) for e in fa], [_derived_leaves(e) for e in fb]
    key = lambda p: (p[0]["class"], hashlib.sha256(normalize.dumps(p[0]).encode("ascii")).hexdigest())
    # Entities are ordered by a hash that includes their derived digits, so a last-digit move can reorder
    # them. Pair by the stored part when the two sides hold the same set; otherwise pair by position.
    ia, ib = (sorted(range(len(fa)), key=lambda i: key(p[i])) for p in (pa, pb))
    if [key(pa[i]) for i in ia] != [key(pb[i]) for i in ib]:
        ia = ib = list(range(len(fa)))
    for i, j in zip(ia, ib):
        (sa, la), (sb, lb) = pa[i], pb[j]
        pre = "entities[%d]." % i
        diffs += [pre + p for p in normalize.differing_fields(sa, sb)]
        scale = _scale(fa[i])
        for p in sorted(set(la) | set(lb)):
            if p not in la or p not in lb:
                diffs.append(pre + p)
            elif la[p]["f64_hex"] != lb[p]["f64_hex"]:
                x, y = canon.hex_to_f64(la[p]["f64_hex"]), canon.hex_to_f64(lb[p]["f64_hex"])
                # A sample was rounded to DERIVED_DIGITS digits, so an unrounded difference below the policy
                # tolerance can still flip the last kept digit: allow that one unit as well.
                unit = 10.0 ** (math.floor(math.log10(max(abs(x), abs(y)))) - normalize.DERIVED_DIGITS + 1) if p.startswith(("samples", "derivative")) and (x or y) else 0.0
                if abs(x - y) > max(pol.tol(scale, max(abs(x), abs(y))), 0.0) + unit:
                    diffs.append(pre + p)
    return sorted(set(diffs))


def verify(root, derive):
    """{fixture: [differing field, ...]} for every fixture whose re-derived signature is not the frozen one."""
    root = Path(root)
    bad = {}
    for fx, rec in signatures.manifest(root)["fixtures"].items():
        frozen_bytes = (root / fx / "signature.json").read_bytes()
        diffs = []
        if signatures._sha(root / fx / "signature.json") != rec["signature_sha256"]:
            diffs.append("<signature.json does not match the manifest hash>")
        if signatures._sha(root / fx / "primary.step") != rec["step_sha256"]:
            diffs.append("<primary.step does not match the manifest hash>")
        fresh = derive(root / fx / "primary.step")
        if normalize.dumps(fresh).encode("ascii") != frozen_bytes:
            try:
                frozen = json.loads(frozen_bytes)
                diffs += compare(frozen, fresh) if normalize.differing_fields(frozen, fresh) else [UNNAMED]
            except ValueError:
                diffs.append(UNNAMED)
        if diffs:
            bad[fx] = diffs
    return bad


def main(argv, derive=None):
    ev = argv[argv.index("--evaluator") + 1] if "--evaluator" in argv else "step_eval"
    root = argv[0]
    bad = verify(root, derive or derive_with(ev))
    n = len(signatures.manifest(root)["fixtures"])
    for fx, fields in sorted(bad.items()):
        print("DRIFT %s: %s" % (fx, ", ".join(fields[:8]) + (" ..." if len(fields) > 8 else "")))
    print("%d of %d signatures re-derived identically" % (n - len(bad), n))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
