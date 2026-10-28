"""Issue #54: the gold-fixtures side of generating canonical PVec from the real-world signatures.

runner/generator_input.py turns a fixture's two signatures and its converter classification into the one
document the pvec-testkit generator reads as its second input (signature in, the same Plan out). The
determinism, digest and refusal tests here are the ones the issue asks to repeat over real-world
fixtures; the signatures are real step_eval output of the committed self-test STEP files.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner import normalize, numeric, verification

ROOT = Path(__file__).resolve().parent.parent
POL = numeric.load_policy()
REC = ROOT / "fixtures" / "validator-selftest" / "verification"
NAMES = ["bspline", "circle", "ellipse", "line", "rational-bspline", "trimmed-arc"]
CONVERTERS = [
    {"id": "acadsharp-dwg2step", "version": "1.0.0", "source_commit": "d7dc111", "lineage": "acadsharp", "image_digest": "sha256:" + "a" * 64},
    {"id": "libredwg-dwg2step", "version": "0.13.3", "source_commit": "9f2c1aa", "lineage": "libredwg", "image_digest": "sha256:" + "b" * 64},
]
MANIFEST = {"corpus_revision": "r1-open-step", "oracle_scope": "OPEN_CONVERTERS", "evidence_scope": "STEP_ORACLE",
            "oracles": "open", "step_oracle": "open", "converters": CONVERTERS}


def sig(name, arch="x64"):
    return normalize.normalize(verification.load(REC / arch / ("%s.verification.json" % name)))


def gi():
    from runner import generator_input
    return generator_input


def cv():
    from runner import compare_converters
    return compare_converters


def section(a, b, converters=CONVERTERS, scope="OPEN_CONVERTERS"):
    return cv().classify_fixture(POL, None, a, b, converters, scope)


def build(name, a=None, b=None, manifest=MANIFEST):
    a = a or sig(name)
    b = b or sig(name, "arm64")
    return gi().build(POL, name + "-rw", manifest, section(a, b, manifest["converters"], manifest["oracle_scope"]), a, b)


class GeneratorInput(unittest.TestCase):
    def test_the_document_carries_the_four_provenance_fields_but_the_generator_version(self):
        doc = build("circle")
        p = doc["provenance"]
        self.assertEqual((p["fixture_id"], p["corpus_revision"]), ("circle-rw", "r1-open-step"))
        self.assertRegex(p["oracle_revision"], r"^[0-9a-f]{64}$")
        self.assertNotIn("generator_version", p)   # the generator stamps its own version, pvec-side

    def test_the_oracle_block_says_who_the_oracles_were_and_what_agreement_is(self):
        o = build("circle")["oracle"]
        self.assertEqual(o["oracle_scope"], "OPEN_CONVERTERS")
        self.assertEqual(o["evidence_scope"], "STEP_ORACLE")
        self.assertEqual(o["evidence_class"], "DUAL_ORACLE_EQUIVALENT")
        self.assertIs(o["is_source_truth"], False)
        self.assertEqual([c["id"] for c in o["converters"]], ["acadsharp-dwg2step", "libredwg-dwg2step"])
        self.assertEqual([c["lineage"] for c in o["converters"]], ["acadsharp", "libredwg"])

    def test_the_signature_is_carried_bit_for_bit_and_its_digest_is_recorded(self):
        for n in NAMES:
            doc = build(n)
            self.assertEqual(doc["signature"], sig(n))
            self.assertEqual(doc["signature_sha256"], hashlib.sha256(normalize.dumps(sig(n)).encode("ascii")).hexdigest())

    def test_building_twice_gives_identical_bytes(self):
        for n in NAMES:
            self.assertEqual(gi().dumps(build(n)), gi().dumps(build(n)))

    def test_the_bytes_do_not_depend_on_which_architecture_was_primary(self):
        for n in NAMES:
            a = gi().dumps(build(n, sig(n, "x64"), sig(n, "arm64")))
            b = gi().dumps(build(n, sig(n, "arm64"), sig(n, "x64")))
            self.assertEqual(json.loads(a)["signature"], json.loads(b)["signature"])

    def test_a_changed_signature_changes_the_digest_and_the_bytes(self):
        a = sig("line")
        b = copy.deepcopy(a)
        g = b["entities"][0]["geometry"]
        g["end"][0] = normalize.stored(1234.5)
        doc_a, doc_b = build("line", a, a), build("line", b, b)
        self.assertNotEqual(doc_a["signature_sha256"], doc_b["signature_sha256"])
        self.assertNotEqual(gi().dumps(doc_a), gi().dumps(doc_b))

    def test_the_oracle_revision_changes_with_the_converter_image(self):
        m = copy.deepcopy(MANIFEST)
        m["converters"][1]["image_digest"] = "sha256:" + "c" * 64
        self.assertNotEqual(build("line")["provenance"]["oracle_revision"], build("line", manifest=m)["provenance"]["oracle_revision"])

    def test_the_document_validates_against_its_schema(self):
        schema = json.loads((ROOT / "schema" / "generator-input.schema.json").read_text())
        v = Draft202012Validator(schema)
        for n in NAMES:
            self.assertEqual([e.message for e in v.iter_errors(build(n))], [], n)

    def test_the_schema_refuses_a_reader_derived_source(self):
        schema = json.loads((ROOT / "schema" / "generator-input.schema.json").read_text())
        doc = build("line")
        doc["provenance"]["derivation"] = "DWG_READER"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(doc)))

    def test_a_quarantined_fixture_is_refused(self):
        a = sig("line")
        b = copy.deepcopy(a)
        g = b["entities"][0]["geometry"]
        g["end"][0] = normalize.stored(1234.5)
        s = section(a, b)
        self.assertEqual(s["class"], "MATERIAL_DIFFERENCE")
        with self.assertRaises(gi().GeneratorInputRefused) as cm:
            gi().build(POL, "line-rw", MANIFEST, s, a, b)
        self.assertIn("QUARANTINED", str(cm.exception))

    def test_a_revision_with_no_step_oracle_is_refused(self):
        m = dict(MANIFEST, oracle_scope="NONE", evidence_scope="READER_MAPPING_ONLY")
        with self.assertRaises(gi().GeneratorInputRefused):
            gi().build(POL, "line-rw", m, section(sig("line"), sig("line", "arm64")), sig("line"), sig("line", "arm64"))

    def test_two_converters_of_one_lineage_are_refused(self):
        m = copy.deepcopy(MANIFEST)
        m["converters"][1]["lineage"] = "acadsharp"
        with self.assertRaises(gi().GeneratorInputRefused):
            gi().build(POL, "line-rw", m, section(sig("line"), sig("line", "arm64")), sig("line"), sig("line", "arm64"))

    def test_a_section_that_does_not_belong_to_the_signatures_is_refused(self):
        s = section(sig("line"), sig("line", "arm64"))
        with self.assertRaises(gi().GeneratorInputRefused):
            gi().build(POL, "circle-rw", MANIFEST, s, sig("circle"), sig("circle", "arm64"))

    def test_a_signature_from_another_policy_version_is_refused(self):
        a = sig("line")
        a["versions"]["policy"] = "PVec numeric policy v0"
        with self.assertRaises(gi().GeneratorInputRefused):
            gi().build(POL, "line-rw", MANIFEST, section(a, sig("line", "arm64")), a, sig("line", "arm64"))

    def test_the_command_writes_one_file_per_accepted_fixture_and_an_index(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for n in ("line", "circle"):
                d = root / "fixtures" / (n + "-rw")
                d.mkdir(parents=True)
                (d / "primary.signature.json").write_text(normalize.dumps(sig(n)))
                (d / "secondary.signature.json").write_text(normalize.dumps(sig(n, "arm64")))
            (root / "manifest.json").write_text(json.dumps(MANIFEST))
            out = root / "out"
            self.assertEqual(gi().main(["--manifest", str(root / "manifest.json"), "--fixtures", str(root / "fixtures"), "--out", str(out)]), 0)
            first = {p.name: p.read_bytes() for p in sorted(out.iterdir())}
            self.assertEqual(sorted(first), ["circle-rw.generator-input.json", "index.json", "line-rw.generator-input.json"])
            index = json.loads(first["index.json"])
            for e in index["fixtures"]:
                self.assertEqual(e["sha256"], hashlib.sha256(first[e["file"]]).hexdigest())
            self.assertEqual(gi().main(["--manifest", str(root / "manifest.json"), "--fixtures", str(root / "fixtures"), "--out", str(out)]), 0)
            self.assertEqual(first, {p.name: p.read_bytes() for p in sorted(out.iterdir())})

    def test_the_command_refuses_a_manifest_that_fails_the_scope_rules(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "fixtures").mkdir()
            m = dict(MANIFEST, converters=[CONVERTERS[0]])
            (root / "manifest.json").write_text(json.dumps(m))
            with self.assertRaises(SystemExit):
                gi().main(["--manifest", str(root / "manifest.json"), "--fixtures", str(root / "fixtures"), "--out", str(root / "out")])

    def test_nothing_in_the_module_reads_a_dwg_reader_output(self):
        src = (ROOT / "runner" / "generator_input.py").read_text()
        for bad in ("read.acad", "acadrust", "acadsharp.json", ".dwg"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
