"""The signature artifacts: packaging, the consumer, re-derivation and drift detection (issue 20).

The frozen artifacts live under signatures/. These tests need no container except the one that proves a
consumer reads them with no OCCT, no STEP parser and no converter: that one runs in python:3.12-slim.
"""
import ast
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from runner import normalize

ROOT = Path(__file__).resolve().parent.parent
SIG = ROOT / "signatures"
CORPUS = ROOT / "corpus" / "r0-open"
FIXTURES = sorted(p.parent.name for p in CORPUS.glob("fixtures/*/source.dwg"))
REFUSED = {"near-singular-001"}
ACCEPTED = [f for f in FIXTURES if f not in REFUSED]


def tiny_set(tmp):
    """A two-fixture signature directory made by hand, for the tests that need no evaluator."""
    from runner import signatures
    sig = {"schema_version": normalize.SCHEMA_VERSION, "units": {"canonical": "metre"}, "entities": [],
           "versions": {"evaluator": "e1", "occt": "7.6.3", "schema": normalize.SCHEMA_VERSION, "policy": "v1"}}
    for fx in ("one-001", "two-001"):
        d = Path(tmp) / fx
        d.mkdir(parents=True)
        (d / "signature.json").write_text(normalize.dumps(sig))
        (d / "primary.step").write_text("ISO-10303-21;\n")
    signatures.write_manifest(tmp, ["one-001", "two-001"], sig["versions"])
    return sig


class Consumer(unittest.TestCase):
    def test_the_consumer_module_imports_only_the_standard_library(self):
        tree = ast.parse((ROOT / "runner" / "signatures.py").read_text())
        stdlib = set(__import__("sys").stdlib_module_names)
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                mods.add(n.module.split(".")[0])
        self.assertEqual(mods - stdlib, set())

    def test_load_checks_the_manifest_versions_and_the_signature_hash(self):
        from runner import signatures
        with tempfile.TemporaryDirectory() as t:
            tiny_set(t)
            self.assertEqual(signatures.load(t, "one-001")["schema_version"], normalize.SCHEMA_VERSION)
            with self.assertRaises(signatures.SignatureError):
                signatures.load(t, "one-001", expect_schema="pvec-gold/signature/2")
            with self.assertRaises(signatures.SignatureError):
                signatures.load(t, "one-001", expect_policy="v2")
            (Path(t) / "one-001" / "signature.json").write_text("{}\n")
            with self.assertRaises(signatures.SignatureError):
                signatures.load(t, "one-001")

    def test_every_accepted_fixture_ships_a_signature_and_its_retained_step_and_the_refused_one_does_not(self):
        for fx in ACCEPTED:
            self.assertTrue((SIG / fx / "signature.json").is_file(), fx)
            self.assertTrue((SIG / fx / "primary.step").is_file(), fx)
        for fx in REFUSED:
            self.assertFalse((SIG / fx / "signature.json").exists(), fx)

    def test_the_manifest_records_schema_evaluator_and_policy_versions(self):
        m = json.loads((SIG / "manifest.json").read_text())
        self.assertEqual(m["versions"]["schema"], normalize.SCHEMA_VERSION)
        for k in ("evaluator", "occt", "policy"):
            self.assertTrue(m["versions"][k], k)
        self.assertEqual(sorted(m["fixtures"]), ACCEPTED)

    def test_a_consumer_reads_every_signature_in_a_container_with_no_occt_no_step_parser_and_no_converter(self):
        if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
            self.skipTest("no docker daemon")
        vol = os.environ.get("GOLD_VOLUME")
        mount = ["-v", "%s:/w:ro" % (vol or ROOT)]
        code = ("import sys; sys.path.insert(0, '/w'); from runner import signatures as s; "
                "m = s.manifest('/w/signatures'); [s.load('/w/signatures', f) for f in m['fixtures']]; "
                "import shutil; assert not any(shutil.which(x) for x in ('step_eval', 'dwg2step-acadsharp')); "
                "print(len(m['fixtures']))")
        r = subprocess.run(["docker", "run", "--rm", "--network", "none", *mount, "python:3.12-slim", "python3", "-I", "-c", code],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(int(r.stdout.strip()), len(ACCEPTED))


class Rederivation(unittest.TestCase):
    def test_equal_signatures_verify_clean(self):
        from runner import verify_signatures as v
        with tempfile.TemporaryDirectory() as t:
            sig = tiny_set(t)
            self.assertEqual(v.verify(t, lambda step: copy.deepcopy(sig)), {})

    def test_a_mutated_frozen_signature_is_detected_and_the_field_is_named(self):
        from runner import verify_signatures as v
        with tempfile.TemporaryDirectory() as t:
            sig = tiny_set(t)
            sig["entities"] = [{"class": "line", "geometry": {"start": normalize.stored(1.0)}}]
            for fx in ("one-001", "two-001"):
                (Path(t) / fx / "signature.json").write_text(normalize.dumps(sig))
            from runner import signatures
            signatures.write_manifest(t, ["one-001", "two-001"], sig["versions"])
            fresh = copy.deepcopy(sig)
            bad = copy.deepcopy(sig)
            bad["entities"][0]["geometry"]["start"] = normalize.stored(1.0000000000000002)
            (Path(t) / "two-001" / "signature.json").write_text(normalize.dumps(bad))
            signatures.write_manifest(t, ["one-001", "two-001"], sig["versions"])
            diffs = v.verify(t, lambda step: copy.deepcopy(fresh))
            self.assertEqual(sorted(diffs), ["two-001"])
            self.assertTrue(any("entities[0].geometry.start" in p for p in diffs["two-001"]), diffs)

    def test_a_byte_difference_with_no_named_field_still_fails(self):
        from runner import verify_signatures as v
        with tempfile.TemporaryDirectory() as t:
            sig = tiny_set(t)
            p = Path(t) / "one-001" / "signature.json"
            p.write_text(p.read_text().replace("\n", "\n\n", 1))
            from runner import signatures
            signatures.write_manifest(t, ["one-001", "two-001"], sig["versions"])
            diffs = v.verify(t, lambda step: copy.deepcopy(sig))
            self.assertIn("one-001", diffs)
            self.assertEqual(diffs["one-001"], ["<bytes differ, no field named>"])

    def test_the_cli_exits_non_zero_on_a_difference(self):
        from runner import verify_signatures as v
        with tempfile.TemporaryDirectory() as t:
            sig = tiny_set(t)
            (Path(t) / "one-001" / "signature.json").write_text("{}\n")
            self.assertEqual(v.main([t], derive=lambda step: copy.deepcopy(sig)), 1)


if __name__ == "__main__":
    unittest.main()
