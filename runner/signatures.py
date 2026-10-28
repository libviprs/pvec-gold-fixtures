"""Read the frozen signatures. Standard library only, so a consumer needs no OCCT, no STEP parser, no
converter and no jsonschema.

    signatures/manifest.json            the versions, and the SHA-256 of every signature and retained STEP
    signatures/<fixture-id>/signature.json   pvec-gold/signature/1
    signatures/<fixture-id>/primary.step     the audit source the signature was derived from

A consumer calls load(dir, fixture, expect_schema=..., expect_policy=...). It refuses a signature whose
hash is not the manifest's and a manifest whose schema or policy version is not the one the consumer was
written against. What a consumer may and may not depend on is docs/downstream-contract.md.
"""
import hashlib
import json
from pathlib import Path

MANIFEST_VERSION = "pvec-gold/signatures-manifest/1"


class SignatureError(Exception):
    pass


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(root):
    m = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    if m.get("manifest_version") != MANIFEST_VERSION:
        raise SignatureError("manifest_version %r is not %s" % (m.get("manifest_version"), MANIFEST_VERSION))
    return m


def write_manifest(root, fixtures, versions):
    root = Path(root)
    doc = {"manifest_version": MANIFEST_VERSION, "versions": versions,
           "fixtures": {fx: {"signature_sha256": _sha(root / fx / "signature.json"), "step_sha256": _sha(root / fx / "primary.step")}
                        for fx in sorted(fixtures)}}
    (root / "manifest.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(root, fixture, expect_schema=None, expect_policy=None, expect_evaluator=None):
    root = Path(root)
    m = manifest(root)
    for key, want in (("schema", expect_schema), ("policy", expect_policy), ("evaluator", expect_evaluator)):
        if want is not None and m["versions"][key] != want:
            raise SignatureError("manifest %s version is %s, the consumer expects %s" % (key, m["versions"][key], want))
    if fixture not in m["fixtures"]:
        raise SignatureError("%s is not in the manifest" % fixture)
    path = root / fixture / "signature.json"
    if _sha(path) != m["fixtures"][fixture]["signature_sha256"]:
        raise SignatureError("%s: signature.json does not match the manifest hash" % fixture)
    return json.loads(path.read_text(encoding="utf-8"))
