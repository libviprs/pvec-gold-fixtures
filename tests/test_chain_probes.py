"""#69: shear and general affine as INSERT-chain probes, and profile-only tags for the two rejection records.

A DWG INSERT stores a translation, one rotation, three scales and no shear. A chain of three INSERTs (rotate,
scale, rotate) carries any 2x2 matrix with a positive determinant, the same way nested-blocks-001 carries a
composed non-uniform scale. So shear-chain-001 and general-affine-chain-001 are DWG probes with new ids, and
shear-001 and general-affine-001 stay as rejection records that have no DWG on purpose (profile only).
"""
import json
import unittest
from decimal import Decimal, getcontext
from pathlib import Path

from runner import canon, expected_math as em, qualify_probes as q

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "tools" / "authoring" / "params" / "transforms"
CORPUS_PARAMS = ROOT / "tools" / "authoring" / "corpus-params" / "edge"
EDGE = ROOT / "fixtures" / "edge"
KT = ROOT / "fixtures" / "known-truth" / "transforms"
CHAINS = {"shear-chain-001": "shear-001", "general-affine-chain-001": "general-affine-001"}
# the world-space line each chain must land on, worked out by hand from the base line (0.5,0.25)-(3.75,2.5)
WORLD = {
    "shear-chain-001": [Decimal("0.625"), Decimal("0.25"), Decimal("5"), Decimal("2.5")],
    "general-affine-chain-001": [Decimal("1.675"), Decimal("2.175"), Decimal("6.25"), Decimal("3.875")],
}
getcontext().prec = 80


def load(p):
    return json.loads(Path(p).read_text())


def matrix(op):
    """Row-major 4x4 of one authored op, as Decimals."""
    m = [Decimal(int(i % 5 == 0)) for i in range(16)]
    if op["op"] == "translate":
        m[3], m[7], m[11] = (Decimal(x) for x in op["v"])
    elif op["op"] == "rotate_z":
        c, s = (Decimal(x) for x in op["cos_sin"])
        m[0], m[1], m[4], m[5] = c, -s, s, c
    elif op["op"] == "scale":
        m[0], m[5], m[10] = (Decimal(x) for x in op["s"])
    return m


def mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def chain_product(params):
    prod = matrix(params["ops"][0])
    for op in params["ops"][1:]:
        prod = mul(prod, matrix(op))
    return prod


class ChainParameters(unittest.TestCase):
    def test_each_chain_is_rotate_scale_rotate_with_an_optional_translation_first(self):
        for fid in CHAINS:
            p = load(CORPUS_PARAMS / (fid + ".json"))
            kinds = [o["op"] for o in p["ops"]]
            self.assertIn(kinds, (["rotate_z", "scale", "rotate_z"], ["translate", "rotate_z", "scale", "rotate_z"]), fid)
            self.assertEqual(p["expect"], "line", fid)
            self.assertEqual(p["group"], "edge", fid)
            self.assertEqual(p["chain_of"], CHAINS[fid], fid)

    def test_every_op_fits_one_insert_each(self):
        # one INSERT per op; each scale must be positive, since a negative one would be a reflection
        for fid in CHAINS:
            for op in load(CORPUS_PARAMS / (fid + ".json"))["ops"]:
                if op["op"] == "scale":
                    self.assertTrue(all(Decimal(s) > 0 for s in op["s"]), fid)

    def test_the_chain_product_is_the_matrix_of_the_rejection_record(self):
        for fid, rec in CHAINS.items():
            p = load(CORPUS_PARAMS / (fid + ".json"))
            want = [Decimal(x) for x in load(PARAMS / (rec + ".json"))["ops"][0]["m"]]
            self.assertEqual([Decimal(x) for x in p["chain_matrix"]], want, fid)
            got = chain_product(p)
            for i, (g, w) in enumerate(zip(got, want)):
                self.assertLess(abs(g - w), Decimal("1e-30"), "%s entry %d: %s vs %s" % (fid, i, g, w))

    def test_the_chain_has_no_shear_in_any_single_insert(self):
        # a single INSERT is translate, rotate, scale: its 2x2 part is R * diag, which is never a shear
        for fid in CHAINS:
            for op in load(CORPUS_PARAMS / (fid + ".json"))["ops"]:
                self.assertIn(op["op"], ("translate", "rotate_z", "scale"), fid)
                if op["op"] == "rotate_z":
                    c, s = (Decimal(x) for x in op["cos_sin"])
                    self.assertLess(abs(c * c + s * s - 1), Decimal("1e-38"), fid)


class ChainRecords(unittest.TestCase):
    def test_the_expected_record_exists_validates_and_carries_the_chain(self):
        for fid in CHAINS:
            f = EDGE / fid / "expected.math.json"
            self.assertTrue(f.is_file(), f)
            self.assertEqual(em.validate_file(f), [], fid)
            doc = em.load(f)
            ent = doc["entities"][0]
            self.assertEqual(ent["structure"], "INSTANCE_PLUS_TRANSFORM", fid)
            n = len(load(CORPUS_PARAMS / (fid + ".json"))["ops"])
            self.assertEqual(len(ent["transform_chain"]["transforms"]), n, fid)
            self.assertNotIn("rejection", ent, fid)

    def test_the_world_line_is_the_sheared_base_line(self):
        for fid, want in WORLD.items():
            ent = em.load(EDGE / fid / "expected.math.json")["entities"][0]
            g = ent["world"]["geometry"]
            got = [canon.exact(g["start"][0]), canon.exact(g["start"][1]), canon.exact(g["end"][0]), canon.exact(g["end"][1])]
            for a, b in zip(got, want):
                self.assertLess(abs(Decimal(a.numerator) / Decimal(a.denominator) - b), Decimal("1e-15"), fid)

    def test_the_composed_matrix_in_the_record_is_the_target_matrix(self):
        for fid, rec in CHAINS.items():
            want = [Decimal(x) for x in load(PARAMS / (rec + ".json"))["ops"][0]["m"]]
            comp = em.load(EDGE / fid / "expected.math.json")["entities"][0]["transform_chain"]["composed"]
            for i, (s, w) in enumerate(zip(comp["matrix"], want)):
                f = canon.exact(s)
                self.assertLess(abs(Decimal(f.numerator) / Decimal(f.denominator) - w), Decimal("1e-15"), "%s entry %d" % (fid, i))

    def test_the_drawing_is_there_and_two_readers_agree_with_the_record(self):
        for fid in CHAINS:
            d = EDGE / fid
            self.assertTrue((d / "source.dwg").is_file(), fid)
            self.assertTrue((d / "read.acadrust.json").is_file(), fid)
            self.assertTrue((d / "read.acadsharp.json").is_file(), fid)
            cmp_ = load(d / "comparison.json")
            self.assertEqual(cmp_["verdict"], "AGREE", fid)

    def test_the_converter_result_is_recorded_and_is_not_a_rejection(self):
        for fid in CHAINS:
            r = load(EDGE / fid / "open-route.json")
            self.assertEqual(r["exit_code"], 0, fid)
            self.assertIn(r["worst_class"], ("STRUCTURAL_EXACT", "GEOMETRIC_EXACT_REPARAMETERIZED"), fid)

    def test_the_chain_is_in_the_r1_manifest_under_affine_transform(self):
        m = load(ROOT / "corpus" / "r1-open" / "manifest.json")
        ids = {f["id"]: f for f in m["fixtures"]}
        for fid in CHAINS:
            self.assertIn(fid, ids)
        mat = load(ROOT / "corpus" / "capability-matrix.json")
        row = [r for r in mat["rows"] if r["capability"] == "affine_transform"][0]
        self.assertTrue(set(CHAINS) <= {f["id"] for f in row["fixtures"]})


class ProfileOnly(unittest.TestCase):
    def test_the_two_rejection_records_carry_a_profile_only_tag_with_a_reason(self):
        for rec in CHAINS.values():
            p = load(PARAMS / (rec + ".json"))
            self.assertIn("profile_only", p, rec)
            self.assertIn("single INSERT", p["profile_only"]["reason"], rec)
            self.assertIn("chain", p["profile_only"]["reason"], rec)
            self.assertEqual(p["expect"], "reject", rec)

    def test_they_keep_their_rejection_outcome(self):
        want = {"shear-001": "UNREPRESENTABLE_TRANSFORM", "general-affine-001": "UNREPRESENTABLE_TRANSFORM"}
        for rec, code in want.items():
            ent = em.load(KT / rec / "expected.math.json")["entities"][0]
            self.assertEqual(ent["rejection"], {"classification": code, "disposition": "QUARANTINE"}, rec)
            self.assertEqual(em.validate_file(KT / rec / "expected.math.json"), [], rec)

    def test_the_tag_reaches_the_record_and_the_readme_says_why_there_is_no_drawing(self):
        for rec, chain in {v: k for k, v in CHAINS.items()}.items():
            doc = em.load(KT / rec / "expected.math.json")
            self.assertIn("profile_only", doc["provenance"]["parameters"], rec)
            text = (KT / rec / "README.md").read_text()
            self.assertIn("profile only", text, rec)
            self.assertIn(chain, text, rec)
            self.assertNotIn("isn't here yet", text, rec)
            self.assertNotIn("ODA", text, rec)
            self.assertFalse((KT / rec / "source.dwg").exists(), rec)

    def test_the_capability_table_lists_the_chains_and_not_the_profile_only_records(self):
        probes = q.CAPABILITIES["affine_transform"]
        for chain, rec in CHAINS.items():
            self.assertIn(chain, probes)
            self.assertNotIn(rec, probes)
        self.assertEqual(sorted(q.PROFILE_ONLY), sorted(CHAINS.values()))
        for rec, why in q.PROFILE_ONLY.items():
            self.assertNotIn(rec, [p for ps in q.CAPABILITIES.values() for p in ps])
            self.assertTrue(why)

    def test_a_missing_drawing_for_a_profile_only_record_blocks_nothing(self):
        # build the affine row with every listed probe present and exact: no probe is named as not run
        pol = __import__("runner.numeric", fromlist=["x"]).load_policy()
        exact = [{"entity": "e", "class": q.STRUCTURAL_EXACT, "evidence": {}}]
        results = {p: {"c": exact} for p in q.CAPABILITIES["affine_transform"] if p != "singular-001"}
        rej = [{"entity": "e", "class": q.UNSUPPORTED, "evidence": {}, "expectation_met": True}]
        results["near-singular-001"] = {"c": rej}
        row = [r for r in q.capability_verdicts(pol, results) if r["capability"] == "affine_transform"][0]
        self.assertNotIn("shear-001", " ".join(row["reasons"]))
        self.assertNotIn("general-affine-001", " ".join(row["reasons"]))


if __name__ == "__main__":
    unittest.main()
