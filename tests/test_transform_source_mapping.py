"""#46: TRANSFORM_PRESERVED is a source-mapping assertion (pvec ADR 0017), not a container one."""
import copy
import unittest
from pathlib import Path

from runner import expected_math as em

ROOT = Path(__file__).resolve().parent.parent
KT = ROOT / "fixtures" / "known-truth"
SEVEN = ["nested-blocks-001", "nonuniform-scale-circle-001", "nonuniform-scale-rotated-001",
         "reflection-001", "rotation-irrational-001", "translation-001", "uniform-scale-001"]


def load(fid):
    hits = list(KT.rglob("%s/expected.math.json" % fid))
    assert len(hits) == 1, fid
    return em.load(hits[0])


def claims(doc, claim):
    return [a for a in doc["assertions"] if a["claim"] == claim]


class Corpus(unittest.TestCase):
    def test_no_fixture_asserts_transform_preserved_as_structural(self):
        for f in sorted(KT.rglob("expected.math.json")):
            for a in claims(em.load(f), "TRANSFORM_PRESERVED"):
                self.assertEqual(a["kind"], "SOURCE_MAPPING", "%s %s" % (f.parent.name, a["id"]))

    def test_the_seven_instance_fixtures_are_retagged(self):
        for fid in SEVEN:
            d = load(fid)
            tp = claims(d, "TRANSFORM_PRESERVED")
            self.assertEqual(len(tp), 1, fid)
            self.assertEqual(tp[0]["kind"], "SOURCE_MAPPING", fid)
            self.assertIn("source mapping", tp[0]["statement"], fid)
            self.assertNotIn("survive as written", tp[0]["statement"], fid)

    def test_the_seven_are_generated_from_the_world_space_curve(self):
        for fid in SEVEN:
            d = load(fid)
            wr = claims(d, "WORLD_SPACE_RESULT")
            self.assertEqual([a["kind"] for a in wr], ["GEOMETRIC"], fid)
            for e in d["entities"]:
                self.assertIn("world", e, fid)

    def test_every_fixture_still_validates(self):
        for f in sorted(KT.rglob("expected.math.json")):
            self.assertEqual(em.validate_file(f), [], f)


class Validator(unittest.TestCase):
    def doc(self):
        return copy.deepcopy(load("translation-001"))

    def test_structural_transform_preserved_is_refused(self):
        d = self.doc()
        claims(d, "TRANSFORM_PRESERVED")[0]["kind"] = "STRUCTURAL"
        errs = em.validate_doc(d)
        self.assertTrue(any("TRANSFORM_PRESERVED" in e for e in errs), errs)

    def test_source_mapping_kind_only_carries_transform_preserved(self):
        d = self.doc()
        claims(d, "WORLD_SPACE_RESULT")[0]["kind"] = "SOURCE_MAPPING"
        errs = em.validate_doc(d)
        self.assertTrue(any("SOURCE_MAPPING" in e for e in errs), errs)

    def test_an_instance_without_a_world_space_assertion_is_refused(self):
        d = self.doc()
        d["assertions"] = [a for a in d["assertions"] if a["claim"] != "WORLD_SPACE_RESULT"]
        errs = em.validate_doc(d)
        self.assertTrue(any("WORLD_SPACE_RESULT" in e for e in errs), errs)


class Docs(unittest.TestCase):
    def test_the_format_doc_explains_the_split(self):
        text = (ROOT / "docs" / "fixtures" / "expected-math.md").read_text()
        self.assertIn("SOURCE_MAPPING", text)
        self.assertIn("ADR 0017", text)


if __name__ == "__main__":
    unittest.main()
