"""Issue 78: the frozen signatures that compare_geometric called BOUNDED_APPROXIMATION.

Two comparator gaps, not converter faults. A tangent is measured by a five-point stencil whose own error is
recorded and was not added to the tolerance (curvature adds it). And a signature writes derived values (ends,
samples) to 12 significant digits, so a drawing at 1e8 metres carries 1e-4 of rounding that the absolute
tolerance never allowed for.
"""
import json
import unittest
from pathlib import Path

from runner import compare_geometric as cg, expected_math as em, numeric

ROOT = Path(__file__).resolve().parent.parent


def report(fid):
    pol = numeric.load_policy()
    truth = next(ROOT.glob("fixtures/**/%s/expected.math.json" % fid))
    sig = json.loads((ROOT / "signatures" / fid / "signature.json").read_text())
    return cg.compare(pol, em.load(truth), sig)


class Gaps(unittest.TestCase):
    def test_tangent_error_of_the_stencil_is_part_of_the_tolerance(self):
        r = report("bspline-d5-001")
        bad = [x for e in r["entities"] for x in e["quantities"] if not x["admitted"]]
        self.assertEqual(bad, [])
        self.assertEqual(r["class"], cg.GEOMETRIC)

    def test_a_signature_at_large_coordinates_is_judged_with_its_12_digit_rounding(self):
        r = report("large-coords-001")
        self.assertEqual([q["quantity"] for q in r["fixture_quantities"] if not q["admitted"]], [])
        self.assertTrue(all("signature_rounding" in q for q in r["fixture_quantities"] if q["quantity"] in ("bounds", "union_curve_deviation")))
        self.assertEqual(r["class"], cg.GEOMETRIC)

    def test_a_polyline_written_as_lines_is_compared_as_a_set(self):
        for fid in ("large-coords-001", "lwpolyline-closed-001"):
            r = report(fid)
            self.assertTrue(r["compared_as_sets"], fid)
            self.assertEqual(r["class"], cg.GEOMETRIC, fid)

    def test_an_expected_companion_entity_with_no_produced_partner_is_compared_as_a_set(self):
        for fid in ("bulge-arc-001", "bulge-arc-neg-001"):
            self.assertEqual(report(fid)["class"], cg.GEOMETRIC, fid)

    def test_a_set_that_is_off_is_still_bounded(self):
        pol = numeric.load_policy()
        truth = next(ROOT.glob("fixtures/**/lwpolyline-closed-001/expected.math.json"))
        sig = json.loads((ROOT / "signatures" / "lwpolyline-closed-001" / "signature.json").read_text())
        g = sig["entities"][2]["geometry"]
        for k in ("start", "end"):
            g[k][0]["decimal"] = "9.0e+1"
            g[k][0]["f64_hex"] = "0x4056800000000000"
        self.assertEqual(cg.compare(pol, em.load(truth), sig)["class"], cg.BOUNDED)

    def test_the_rounding_allowance_is_recorded_next_to_the_tolerance(self):
        r = report("large-coords-001")
        q = r["entities"][0]["quantities"][0]   # endpoint_start
        self.assertIn("signature_rounding", q)
        self.assertGreater(q["signature_rounding"], 0)

    def test_a_real_miss_is_still_a_miss(self):
        # the allowance is relative to the magnitude and small: a 5 metre error at 1e8 stays bounded
        self.assertLess(cg.SIGNATURE_ROUNDING * 1e8 * 2, 1.0)


if __name__ == "__main__":
    unittest.main()
