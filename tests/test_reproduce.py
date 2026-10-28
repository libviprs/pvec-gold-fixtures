"""runner/reproduce.py: the divergence list, the frozen manifest and the verdicts (#24). No docker here."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runner import reproduce

STEP = "ISO-10303-21;\nHEADER;\nFILE_NAME('a.step','%s',(''),(''),'','','');\nENDSEC;\nDATA;\n#1=LINE();\nENDSEC;\nEND-ISO-10303-21;\n"


class Divergence(unittest.TestCase):
    def test_step_timestamp_is_the_only_allowed_step_difference(self):
        self.assertEqual(reproduce.step_divergence(STEP % "2026-10-28T01:00:00", STEP % "2026-10-28T02:00:00"), [])
        bad = (STEP % "2026-10-28T02:00:00").replace("#1=LINE()", "#1=LINE(1)")
        self.assertEqual(reproduce.step_divergence(STEP % "2026-10-28T01:00:00", bad), ["step: differs beyond FILE_NAME time stamp"])

    def test_json_difference_on_the_list_passes_and_off_the_list_fails(self):
        a = {"status": "ok", "wall_time_seconds": 1.5, "output": {"sha256": "aa", "path": "/x/a"}, "product": {"version": "1"}}
        b = {"status": "ok", "wall_time_seconds": 2.5, "output": {"sha256": "bb", "path": "/x/b"}, "product": {"version": "1"}}
        self.assertEqual(reproduce.json_divergence("status", a, b), [])
        c = copy.deepcopy(b)
        c["product"]["version"] = "2"
        self.assertEqual(reproduce.json_divergence("status", a, c), ["status.product.version"])
        d = dict(b, extra=1)
        self.assertEqual(reproduce.json_divergence("status", a, d), ["status.extra"])

    def test_signature_and_verification_have_no_allowed_difference(self):
        self.assertEqual(reproduce.json_divergence("signature", {"a": 1}, {"a": 2}), ["signature.a"])
        self.assertEqual(reproduce.json_divergence("verification", {"a": [1, 2]}, {"a": [1, 3]}), ["verification.a[1]"])

    def test_the_list_is_what_the_document_names(self):
        doc = (Path(__file__).resolve().parent.parent / "docs" / "reproducibility.md").read_text()
        for name in reproduce.DIVERGENCE_NAMES:
            self.assertIn("`%s`" % name, doc)


def fx(i, sig="s", step="t"):
    return {"id": i, "source_sha256": "d" * 64, "outcome": "CONVERTED", "step_sha256": step * 64, "signature_sha256": sig * 64}


def parts(**over):
    p = dict(corpus={"revision": "r0-open", "bundle_sha256": "b" * 64, "manifest_sha256": "m" * 64},
             fixtures=[fx("a"), fx("b")],
             images={"dwg2step-acadsharp": {"base": "mcr@sha256:" + "1" * 64, "built_image_id": "sha256:" + "2" * 64}},
             converters={"acadsharp-dwg2step": "ACadSharp 3.7.1+d7dc111, tool 1"},
             evaluator={"step_eval": "1", "occt": "7.6.3"},
             numeric_policy="PVec numeric policy v1", version="r0-open-1")
    p.update(over)
    return p


class Manifest(unittest.TestCase):
    def test_all_eight_items_are_pinned(self):
        m = reproduce.build_manifest(**parts())
        for k in ("corpus", "source_hashes", "signatures", "step_hashes", "images", "converters", "evaluator", "numeric_policy"):
            self.assertIn(k, m["pins"])

    def test_a_missing_value_blocks_instead_of_defaulting(self):
        for key, empty in (("images", {}), ("converters", {}), ("evaluator", {}), ("numeric_policy", ""), ("fixtures", [])):
            with self.subTest(key=key), self.assertRaises(reproduce.FreezeBlocked):
                reproduce.build_manifest(**parts(**{key: empty}))

    def test_a_fixture_without_a_hash_blocks(self):
        bad = fx("c")
        bad["signature_sha256"] = ""
        with self.assertRaises(reproduce.FreezeBlocked):
            reproduce.build_manifest(**parts(fixtures=[fx("a"), bad]))

    def test_manifest_is_canonical_json_without_timestamps(self):
        a = reproduce.dump_manifest(reproduce.build_manifest(**parts()))
        b = reproduce.dump_manifest(reproduce.build_manifest(**parts()))
        self.assertEqual(a, b)
        self.assertNotRegex(a, r"20\d\d-\d\d-\d\dT")


class Against(unittest.TestCase):
    def test_same_hashes_match(self):
        m = reproduce.build_manifest(**parts())
        self.assertEqual(reproduce.against_manifest(m, parts()["fixtures"]), {"a": "MATCH", "b": "MATCH"})

    def test_a_changed_signature_is_named(self):
        m = reproduce.build_manifest(**parts())
        got = reproduce.against_manifest(m, [fx("a", sig="x"), fx("b")])
        self.assertEqual(got["a"], "DIFFERS: signature_sha256")
        self.assertEqual(got["b"], "MATCH")

    def test_a_fixture_missing_from_either_side_is_not_a_match(self):
        m = reproduce.build_manifest(**parts())
        got = reproduce.against_manifest(m, [fx("a"), fx("c")])
        self.assertEqual(got["b"], "MISSING_IN_RUN")
        self.assertEqual(got["c"], "NOT_IN_MANIFEST")


class Checksums(unittest.TestCase):
    def test_sha256sums_verify_and_catch_a_flipped_byte(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "x").mkdir()
            (d / "x" / "f.txt").write_text("hello")
            (d / "m.json").write_text("{}")
            reproduce.write_sha256sums(d)
            self.assertEqual(reproduce.verify_sha256sums(d), [])
            (d / "x" / "f.txt").write_text("hellp")
            self.assertEqual(reproduce.verify_sha256sums(d), ["x/f.txt"])


if __name__ == "__main__":
    unittest.main()
