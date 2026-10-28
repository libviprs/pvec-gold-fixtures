"""The document the pvec-testkit generator reads as its second input: a real-world fixture's signature.

    python3 -m runner.generator_input --manifest MANIFEST.json --fixtures DIR --out DIR

The record input of the generator takes expected.math.json; this one takes a signature (signature in, the
same Plan out), so the writer path, the provenance fields and the refusal rules stay shared on the pvec
side. This module is the gold-fixtures half: it decides which fixtures may be handed over, binds the
signature to the oracle that produced it, and writes bytes that depend on content only.

The provenance carries the fixture id, the corpus revision and the oracle revision. The generator version
is the fourth field and the generator's own, so it is not here. The oracle revision is the SHA-256 of the
oracle scope and the converters (id, version, lineage, image digest), so a different converter image is a
different revision.

A fixture is handed over only when its converter section says the two converters agree (MATCH, an exact
reparameterisation or equivalent geometry), the revision's manifest passes the ADR 0009 scope rules, the
oracle scope is not NONE, the signatures are the ones the section was computed from, and they carry the
vendored policy version. Anything QUARANTINED is refused. The input is the primary converter's signature;
the secondary's digest is recorded beside it. Nothing here reads a DWG reader's output: the artifacts are
made from STEP signatures, which is what keeps a CAD reader out of the generator's dependency tree.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from . import compare_converters, expected_math as em, normalize, numeric
from .r0_open import scope_problems

SCHEMA_VERSION = "pvec-gold/generator-input/1"
dumps = normalize.dumps


class GeneratorInputRefused(ValueError):
    pass


def _sha(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def build(pol, fixture_id, manifest, section, primary, secondary):
    scope = manifest.get("oracle_scope")
    if scope in (None, "NONE"):
        raise GeneratorInputRefused("%s: oracle_scope is %s, so no STEP oracle ran and there is no signature to hand over" % (fixture_id, scope))
    bad = scope_problems(manifest)
    if bad:
        raise GeneratorInputRefused("%s: manifest fails the scope rules: %s" % (fixture_id, bad[0]))
    if section["quarantine"] is not None or section["class"] == compare_converters.MATERIAL or section["evidence"] is None:
        raise GeneratorInputRefused("%s: QUARANTINED (%s)" % (fixture_id, section["statement"]))
    if section["signatures"] != {"primary_sha256": compare_converters.digest(primary), "secondary_sha256": compare_converters.digest(secondary)}:
        raise GeneratorInputRefused("%s: the converter section was not computed from these signatures" % fixture_id)
    names = [{k: c[k] for k in compare_converters.KEYS} for c in manifest["converters"]]
    if section["converters"] != names:
        raise GeneratorInputRefused("%s: the converter section names other converters than the manifest" % fixture_id)
    for who, s in (("primary", primary), ("secondary", secondary)):
        if s["versions"]["policy"] != pol.version:
            raise GeneratorInputRefused("%s: the %s signature carries policy %r, not %r" % (fixture_id, who, s["versions"]["policy"], pol.version))
    oracle = {"oracle_scope": scope, "converters": names}
    return {
        "schema_version": SCHEMA_VERSION,
        "provenance": {"fixture_id": fixture_id, "corpus_revision": manifest["corpus_revision"],
                       "oracle_revision": _sha(dumps(oracle)), "derivation": "STEP_SIGNATURE"},
        "oracle": dict(oracle, evidence_scope="STEP_ORACLE", evidence_class="DUAL_ORACLE_EQUIVALENT", is_source_truth=False,
                       classification=section["class"]),
        "numeric_policy_version": pol.version,
        "signature_schema_version": primary["schema_version"],
        "signature_sha256": section["signatures"]["primary_sha256"],
        "secondary_signature_sha256": section["signatures"]["secondary_sha256"],
        "signature": primary,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    pol = numeric.load_policy()
    manifest = json.loads(Path(a.manifest).read_text())
    bad = scope_problems(manifest)
    if bad or manifest.get("oracle_scope") in (None, "NONE"):
        raise SystemExit("manifest refused: " + (bad[0] if bad else "oracle_scope %s carries no STEP oracle" % manifest.get("oracle_scope")))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    index, refused = [], 0
    for d in sorted(p for p in Path(a.fixtures).iterdir() if p.is_dir()):
        load = lambda n: json.loads((d / n).read_text())  # noqa: E731
        try:
            pri, sec = load("primary.signature.json"), load("secondary.signature.json")
            exp = em.load(d / "expected.math.json") if (d / "expected.math.json").exists() else None
            section = compare_converters.classify_fixture(pol, exp, pri, sec, manifest["converters"], manifest["oracle_scope"])
            doc = build(pol, d.name, manifest, section, pri, sec)
        except (GeneratorInputRefused, compare_converters.ComparisonRefused, FileNotFoundError) as e:
            print("REFUSED %s: %s" % (d.name, e))
            refused += 1
            continue
        text = dumps(doc)
        name = "%s.generator-input.json" % d.name
        (out / name).write_text(text, encoding="ascii")
        index.append({"fixture_id": d.name, "file": name, "sha256": _sha(text), "classification": section["class"]})
    (out / "index.json").write_text(dumps({"schema_version": SCHEMA_VERSION.replace("input", "index"), "corpus_revision": manifest["corpus_revision"],
                                           "numeric_policy_version": pol.version, "fixtures": index}), encoding="ascii")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
