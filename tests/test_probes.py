import copy
import json
import sys
import unittest
from pathlib import Path

from runner import canon, expected_math as em, structural

ROOT = Path(__file__).resolve().parent.parent
KT = ROOT / "fixtures" / "known-truth"
sys.path.insert(0, str(ROOT / "tools" / "authoring"))
import author_probes  # noqa: E402


def load(fid):
    hits = list(KT.rglob("%s/expected.math.json" % fid))
    assert len(hits) == 1, fid
    return em.load(hits[0])


def ent(fid, idx=0):
    return load(fid)["entities"][idx]


def S(x):
    return canon.scalar(x)


# ---- mutations a normalising or approximating converter might apply -----------------------

def weights_to_one(e):
    e = copy.deepcopy(e)
    g = e["geometry"]
    g["weights"] = [S("1")] * len(g["weights"])
    g["weights_all_unit"] = True
    return e


def collapse_knot(e):
    e = copy.deepcopy(e)
    ks = e["geometry"]["knots"]
    ks[1]["multiplicity"] += ks[2]["multiplicity"]
    del ks[2]
    return e


def reparameterise(e):
    e = copy.deepcopy(e)
    two, one = canon.check_scalar(S("2")), canon.check_scalar(S("1"))
    f = lambda s: S(canon.check_scalar(s) * two + one)  # noqa: E731
    for k in e["geometry"]["knots"]:
        k["value"] = f(k["value"])
    e["parameter_domain"] = {"start": f(e["parameter_domain"]["start"]), "end": f(e["parameter_domain"]["end"])}
    return e


def reverse(e):
    e = copy.deepcopy(e)
    g = e["geometry"]
    if e["class"] == "line":
        g["start"], g["end"] = g["end"], g["start"]
    elif e["class"] == "circular_arc":
        a0, sw = canon.check_scalar(g["start_angle"]), canon.check_scalar(g["sweep_angle"])
        g["start_angle"], g["sweep_angle"] = S(a0 + sw), S(-sw)
    return e


ROWS = {
    "line": ["line-001"], "polyline": ["polyline-001"], "bulge": ["bulge-arc-001"],
    "circle": ["circle-001"], "arc seam": ["arc-seam-001"], "ellipse": ["ellipse-001"], "elliptical arc": ["elliptical-arc-001"],
    "bezier": ["bezier-d3-001"], "bspline": ["bspline-d3-001", "bspline-d5-001"],
    "rational": ["nurbs-d3-001"], "nurbs": ["nurbs-d2-offconic-001"], "repeated knots": ["repeated-knot-c0-001"],
    "non-unit weights": ["nonunit-weight-001"], "closed": ["closed-by-endpoint-001", "closed-periodic-001"],
    "large coordinates": ["large-coords-001"], "tiny radii": ["tiny-radius-001"],
}
TRANSFORMS = ["translation-001", "rotation-irrational-001", "uniform-scale-001", "nonuniform-scale-circle-001",
              "nonuniform-scale-rotated-001", "reflection-001", "shear-001", "general-affine-001", "nested-blocks-001",
              "near-singular-001", "singular-001"]


class Coverage(unittest.TestCase):
    def test_every_row_and_case_has_a_fixture(self):
        for row, ids in list(ROWS.items()) + [("transform", TRANSFORMS)]:
            for i in ids:
                self.assertEqual(len(list(KT.rglob("%s/expected.math.json" % i))), 1, "%s (%s)" % (i, row))

    def test_every_fixture_validates_and_is_authored_from_parameters(self):
        files = sorted(KT.rglob("expected.math.json"))
        self.assertGreaterEqual(len(files), 28)
        for f in files:
            self.assertEqual(em.validate_file(f), [], f)
            d = em.load(f)
            self.assertEqual(d["provenance"]["derivation"], "AUTHORING_PARAMETERS")
            self.assertEqual(d["provenance"]["authoring_script"], "tools/authoring/author_probes.py")
            self.assertEqual(d["evidence_class"], "KNOWN_TRUTH_EXACT")
            param = ROOT / d["provenance"]["parameter_file"]
            import hashlib
            self.assertEqual(hashlib.sha256(param.read_bytes()).hexdigest(), d["provenance"]["parameter_file_sha256"])
            readme = (f.parent / "README.md").read_text()
            self.assertIn("No expected value comes from `primary.step` or `secondary.step`", readme)
            if "profile_only" in d["provenance"]["parameters"]:   # #69: no drawing on purpose, the chain probe has it
                self.assertIn("profile only", readme)
            else:
                self.assertIn("open writer named in the corpus manifest", readme)
            self.assertNotIn("licensed", readme)

    def test_no_probe_mixes_two_rows(self):
        for f in sorted(KT.rglob("expected.math.json")):
            d = em.load(f)
            classes = {e["class"] for e in d["entities"]}
            if d["fixture_id"] in ("bulge-arc-001", "bulge-arc-neg-001"):
                self.assertEqual(classes, {"polyline", "circular_arc"})
            else:
                self.assertEqual(len(classes), 1, f)

    def test_authoring_is_reproducible(self):
        self.assertEqual(author_probes.main(["--check"]), 0)

    def test_expected_files_are_not_fed_from_step(self):
        for f in sorted(KT.rglob("expected.math.json")):
            text = f.read_text()
            self.assertNotIn("primary.step", text)
            self.assertNotIn("secondary.step", text)


class Discrimination(unittest.TestCase):
    def check(self, mutate, ids, field):
        for i in ids:
            e = ent(i)
            self.assertEqual(structural.classify(e, e), structural.STRUCTURAL_EXACT)
            m = mutate(e)
            self.assertEqual(structural.classify(e, m), structural.STRUCTURAL_DIFFERS, i)
            self.assertTrue(any(field in p for p in structural.structural_diff(e, m)), (i, structural.structural_diff(e, m)))

    def test_weight_renormalisation_is_caught_on_three_probes(self):
        self.check(weights_to_one, ["nurbs-d3-001", "nurbs-d2-offconic-001", "nonunit-weight-001"], "weights")

    def test_knot_collapse_is_caught_on_three_probes(self):
        self.check(collapse_knot, ["bspline-d3-001", "bspline-d5-001", "nurbs-d3-001", "nurbs-d2-offconic-001"], "knots")

    def test_reparameterisation_is_caught_on_three_probes(self):
        self.check(reparameterise, ["bspline-d3-001", "bspline-d5-001", "nurbs-d3-001", "repeated-knot-c0-001"], "parameter_domain")

    def test_c0_probe_lists_its_excluded_parameter(self):
        d = load("repeated-knot-c0-001")
        self.assertEqual([x["parameter"]["decimal"] for x in d["derivative_exclusions"]], ["0.5"])
        d["derivative_exclusions"] = []
        self.assertTrue(any("derivative_exclusions" in e for e in em.validate_doc(d)))


class Transforms(unittest.TestCase):
    def test_reversing_the_curve_direction_turns_comparison_red(self):
        d = load("reflection-001")
        e = d["entities"][0]
        w = dict(e["world"])
        w["orientation"] = e["orientation"]
        self.assertEqual(structural.classify(w, w), structural.STRUCTURAL_EXACT)
        self.assertEqual(structural.classify(w, reverse(w)), structural.STRUCTURAL_DIFFERS)
        self.assertEqual(e["orientation"], {"parameter_direction": "START_TO_END", "sense_about_normal": "CW"})
        self.assertLess(canon.exact(e["transform"]["determinant"]), 0)

    def test_nonuniform_scale_circle_is_an_ellipse_with_axes(self):
        e = ent("nonuniform-scale-circle-001")
        self.assertEqual(e["class"], "circle")
        w = e["world"]
        self.assertEqual(w["class"], "ellipse")
        self.assertEqual(w["geometry"]["semi_major"]["decimal"], "6.0")
        self.assertEqual(w["geometry"]["semi_minor"]["decimal"], "2.0")
        r = ent("nonuniform-scale-rotated-001")["world"]["geometry"]
        self.assertEqual([c["decimal"] for c in r["major_axis"]], ["0.6", "0.8", "0.0"])

    def test_singular_probes_expect_classification_not_a_curve(self):
        for i, cls in (("singular-001", "SINGULAR_TRANSFORM"), ("near-singular-001", "NEAR_SINGULAR_TRANSFORM")):
            e = ent(i)
            self.assertNotIn("world", e)
            self.assertEqual(e["rejection"]["classification"], cls)
            self.assertEqual(structural.rejection_verdict(e, None), "PASS")
            self.assertEqual(structural.rejection_verdict(e, {"class": "line"}), "FAIL")
        self.assertEqual(ent("singular-001")["transform"]["determinant"]["decimal"], "0.0")
        self.assertEqual(float(ent("near-singular-001")["transform"]["determinant"]["decimal"]), float("1e-12"))

    def test_nested_blocks_are_three_deep_and_order_matters(self):
        e = ent("nested-blocks-001")
        ch = e["transform_chain"]
        self.assertGreaterEqual(len(ch["transforms"]), 3)
        readme = (next(KT.rglob("nested-blocks-001")) / "README.md").read_text()
        self.assertIn("(3.75, 2.0, 0.0)", readme)
        self.assertIn("(-2.5, 4.5, 0.0)", readme)
        self.assertEqual([c["decimal"] for c in e["world"]["geometry"]["start"]], ["3.75", "2.0", "0.0"])

    def test_rotation_matrix_entries_are_rounded_irrationals(self):
        m = ent("rotation-irrational-001")["transform"]["matrix"]
        self.assertEqual(m[0]["f64_hex"], canon.f64_to_hex(0.5403023058681398))   # cos 1
        self.assertEqual(m[4]["f64_hex"], canon.f64_to_hex(0.8414709848078965))   # sin 1


if __name__ == "__main__":
    unittest.main()
