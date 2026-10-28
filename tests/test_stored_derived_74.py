"""Issue 74: a signature hashes stored bits, and the values OCCT derives are compared under the numeric policy.

A line's ends and an ellipse's major axis are what OCCT computes from the Part 21 attributes, so they move in
the last digits between x86_64 and arm64. Stored values (control points, knots, weights, radii, domains)
never do, and they stay bit for bit.
"""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from runner import normalize, signatures, verify_signatures as v

ROOT = Path(__file__).resolve().parent.parent


def sc(f, derived=False):
    return (normalize.derived if derived else normalize.stored)(f)


def nudge(scalar, ulps):
    """The same scalar moved by that many ulps."""
    f = float(scalar["decimal"])
    for _ in range(ulps):
        f = math.nextafter(f, math.inf)
    return normalize.stored(f)


def line(start, end):
    return {"class": "line", "structure": "line", "closure": {"closed": False},
            "transform": {"convention": "row-major", "matrix": [sc(float(i % 5 == 0)) for i in range(16)],
                          "determinant": sc(1.0), "classification": "identity"},
            "geometry": {"start": [sc(c) for c in start], "end": [sc(c) for c in end]},
            "parameter_domain": {"start": sc(0.0), "end": sc(5.0)},
            "samples": [{"parameter": sc(0.0, True), "point": [sc(c, True) for c in start], "tangent": [sc(1.0, True), sc(0.0, True), sc(0.0, True)],
                         "curvature": sc(0.0, True), "derivative_exclusion": None}]}


def ellipse():
    e = line([0, 0, 0], [1, 0, 0])
    e["class"] = "ellipse"
    e["geometry"] = {"center": [sc(0.0)] * 3, "normal": [sc(0.0), sc(0.0), sc(1.0)], "major_axis": [sc(0.6), sc(0.8), sc(0.0)],
                     "semi_major": sc(5.0), "semi_minor": sc(3.0)}
    return e


def bspline():
    e = line([0, 0, 0], [1, 0, 0])
    e["class"] = "bspline"
    e["geometry"] = {"degree": 1, "control_points": [[sc(0.1), sc(0.2), sc(0.0)], [sc(1.3), sc(2.2), sc(0.0)]],
                     "knots": [{"value": sc(0.0), "multiplicity": 2}, {"value": sc(1.0), "multiplicity": 2}], "weights_all_unit": True}
    return e


def doc(*entities):
    return {"schema_version": normalize.SCHEMA_VERSION, "units": {"canonical": "metre"},
            "versions": {"evaluator": "e1", "occt": "7.6.3", "schema": normalize.SCHEMA_VERSION, "policy": "v1"},
            "entities": list(entities)}


class Compare(unittest.TestCase):
    def test_a_last_digit_move_of_a_line_end_is_not_a_difference(self):
        a = doc(line([0, 0, 0], [3, 4, 0]))
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["end"][0] = nudge(a["entities"][0]["geometry"]["end"][0], 2)
        self.assertNotEqual(a, b)
        self.assertEqual(v.compare(a, b), [])

    def test_a_last_digit_move_of_an_ellipse_major_axis_is_not_a_difference(self):
        a = doc(ellipse())
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["major_axis"][1] = nudge(a["entities"][0]["geometry"]["major_axis"][1], 3)
        self.assertEqual(v.compare(a, b), [])

    def test_a_last_digit_move_of_a_sample_point_is_not_a_difference(self):
        a = doc(bspline())
        a["entities"][0]["samples"][0]["point"][1] = sc(2.2, True)
        b = copy.deepcopy(a)
        b["entities"][0]["samples"][0]["point"][1] = nudge(sc(2.2, True), 3)
        self.assertEqual(v.compare(a, b), [])

    def test_one_unit_of_the_last_rounded_digit_of_a_far_away_sample_is_not_a_difference_but_two_are(self):
        e = line([1e7, 0, 0], [1e7 + 5, 0, 0])
        e["samples"][0]["point"][0] = normalize.derived(1.00000000000e7)
        a = doc(e)
        b = copy.deepcopy(a)
        b["entities"][0]["samples"][0]["point"][0] = normalize.derived(1.00000000001e7)
        self.assertEqual(v.compare(a, b), [])
        b["entities"][0]["samples"][0]["point"][0] = normalize.derived(1.00000000003e7)
        self.assertEqual(v.compare(a, b), ["entities[0].samples[0].point[0]"])

    def test_one_ulp_on_a_stored_control_point_names_the_field(self):
        a = doc(bspline())
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["control_points"][1][1] = normalize.stored(2.2000000000000006)
        self.assertEqual(v.compare(a, b), ["entities[0].geometry.control_points[1][1]"])

    def test_a_stored_radius_and_a_stored_domain_stay_bitwise(self):
        a = doc(ellipse())
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["semi_major"] = normalize.stored(5.000000000000001)
        b["entities"][0]["parameter_domain"]["end"] = normalize.stored(5.000000000000001)
        self.assertEqual(v.compare(a, b), ["entities[0].geometry.semi_major", "entities[0].parameter_domain.end"])

    def test_a_real_move_of_a_derived_value_is_still_named(self):
        a = doc(line([0, 0, 0], [3, 4, 0]))
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["end"][0] = normalize.stored(3.001)
        self.assertEqual(v.compare(a, b), ["entities[0].geometry.end[0]"])

    def test_a_derived_move_does_not_reorder_entities_into_a_false_difference(self):
        e1, e2 = line([0, 0, 0], [3, 4, 0]), line([1, 1, 0], [2, 2, 0])
        a = doc(*sorted([e1, e2], key=normalize.sort_key))
        f = copy.deepcopy(e1)
        f["geometry"]["end"][0] = nudge(e1["geometry"]["end"][0], 2)
        b = doc(*sorted([f, e2], key=normalize.sort_key))
        self.assertEqual(v.compare(a, b), [])

    def test_a_changed_version_or_entity_count_is_named(self):
        a = doc(line([0, 0, 0], [3, 4, 0]))
        b = copy.deepcopy(a)
        b["versions"]["occt"] = "7.7.0"
        self.assertEqual(v.compare(a, b), ["versions.occt"])
        self.assertEqual(v.compare(a, doc()), ["entities"])


class Verify(unittest.TestCase):
    def frozen(self, t, sig):
        for fx in ("one-001",):
            d = Path(t) / fx
            d.mkdir(parents=True)
            (d / "signature.json").write_text(normalize.dumps(sig))
            (d / "primary.step").write_text("ISO-10303-21;\n")
        signatures.write_manifest(t, ["one-001"], sig["versions"])

    def test_verify_passes_a_fresh_derivation_that_differs_only_in_derived_digits(self):
        sig = doc(line([0, 0, 0], [3, 4, 0]))
        fresh = copy.deepcopy(sig)
        fresh["entities"][0]["geometry"]["end"][1] = nudge(sig["entities"][0]["geometry"]["end"][1], 2)
        with tempfile.TemporaryDirectory() as t:
            self.frozen(t, sig)
            self.assertEqual(v.verify(t, lambda step: copy.deepcopy(fresh)), {})

    def test_verify_names_a_stored_difference_and_the_cli_exits_non_zero(self):
        sig = doc(bspline())
        fresh = copy.deepcopy(sig)
        fresh["entities"][0]["geometry"]["knots"][1]["value"] = normalize.stored(1.0000000000000002)
        with tempfile.TemporaryDirectory() as t:
            self.frozen(t, sig)
            bad = v.verify(t, lambda step: copy.deepcopy(fresh))
            self.assertEqual(bad, {"one-001": ["entities[0].geometry.knots[1].value"]})
            self.assertEqual(v.main([t], derive=lambda step: copy.deepcopy(fresh)), 1)


class Docs(unittest.TestCase):
    def test_the_architecture_caveat_is_gone(self):
        contract = (ROOT / "docs" / "downstream-contract.md").read_text()
        repro = (ROOT / "docs" / "reproducibility.md").read_text()
        self.assertNotIn("The signature being the same on every architecture", contract)
        self.assertNotIn("and not across architectures", contract)
        self.assertNotIn("## The architecture caveat", repro)
        self.assertNotIn("is not expected to match the signature hashes", repro)
        self.assertIn("stored", contract)


if __name__ == "__main__":
    unittest.main()
