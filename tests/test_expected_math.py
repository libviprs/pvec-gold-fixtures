import copy
import json
import unittest
from pathlib import Path

from runner import canon, expected_math as em

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "fixtures" / "examples" / "rational-bspline.expected.math.json"


def S(x):
    return canon.scalar(x)


def base():
    return em.load(EXAMPLE)


def ident(extra=None):
    m = ["1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
    if extra:
        m = extra
    return m


def transform(m, det, cls):
    return {"convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": [S(x) for x in m],
            "determinant": S(det), "classification": cls}


def line_entity(**kw):
    e = {"id": "l0", "class": "line", "structure": "CURVE_ONLY",
         "geometry": {"start": [S("0")] * 3, "end": [S("1"), S("0"), S("0")]},
         "parameter_domain": {"start": S("0"), "end": S("1")},
         "closure": {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}}
    e.update(kw)
    return e


class Canon(unittest.TestCase):
    def test_sqrt_half_pair(self):
        # sqrt(1/2) is 0.70710678118654752440..., whose nearest f64 is ...3bcd.
        s = {"decimal": "0.70710678118654757", "f64_hex": "0x3fe6a09e667f3bcd"}
        self.assertEqual(canon.check_scalar(s), 0.7071067811865476)

    def test_epic_example_pair_is_off_by_one_ulp(self):
        # The pair quoted in epic #1 and issue #5 pairs this decimal with ...3bcc, which is the
        # f64 below the one that decimal rounds to. The check exists to catch exactly this.
        s = {"decimal": "0.70710678118654757", "f64_hex": "0x3fe6a09e667f3bcc"}
        with self.assertRaises(canon.CanonError):
            canon.check_scalar(s)

    def test_truncated_15_digit_decimal_is_rejected(self):
        s = {"decimal": "0.707106781186548", "f64_hex": "0x3fe6a09e667f3bcd"}
        with self.assertRaises(canon.CanonError):
            canon.check_scalar(s)

    def test_long_decimal_is_accepted_when_it_rounds_to_the_bits(self):
        s = {"decimal": "0.707106781186547524400844362104849", "f64_hex": "0x3fe6a09e667f3bcd"}
        self.assertEqual(canon.f64_to_hex(float(s["decimal"])), "0x3fe6a09e667f3bcd")
        canon.check_scalar(s)

    def test_round_trip_many(self):
        for x in [float(t) for t in ("0.1", "10000000.0001", "0.00001", "5e-324", "1.7976931348623157e308", "-2.5")]:
            canon.check_scalar(canon.scalar(x))

    def test_non_finite_rejected(self):
        with self.assertRaises(canon.CanonError):
            canon.scalar(float("inf"))


class Schema(unittest.TestCase):
    def test_worked_example_is_valid(self):
        self.assertEqual(em.validate_file(EXAMPLE), [])

    def test_schema_has_no_tolerance_or_epsilon(self):
        text = (ROOT / "schema" / "expected.math.schema.json").read_text().lower()
        for word in ("tolerance", "epsilon", "\"eps\"", "ulp"):
            self.assertNotIn(word, text)

    def test_bare_float_rejected(self):
        p = ROOT / "tests" / "_bare.json"
        try:
            p.write_text('{"x": 0.5}')
            self.assertTrue(em.validate_file(p))
        finally:
            p.unlink()

    def test_truncated_decimal_in_a_fixture_is_rejected(self):
        d = base()
        d["entities"][0]["geometry"]["weights"][1] = {"decimal": "0.4999999999999", "f64_hex": canon.f64_to_hex(0.5)}
        errs = em.validate_doc(d)
        self.assertTrue(any("rounds to" in e for e in errs), errs)

    def test_non_periodic_knot_relation(self):
        d = base()
        d["entities"][0]["geometry"]["knots"][1]["multiplicity"] = 2
        errs = em.validate_doc(d)
        self.assertTrue(any("control_points + degree + 1" in e for e in errs), errs)

    def test_periodic_knot_relation(self):
        d = base()
        e = d["entities"][0]
        e["closure"] = {"closed_by_endpoint": False, "closed_by_knots": True, "periodic": True}
        # 4 control points need sum == 5 for the periodic relation; the example sums to 7
        errs = em.validate_doc(d)
        self.assertTrue(any("periodic relation" in x for x in errs), errs)
        g = e["geometry"]
        g["degree"] = 2
        g["knots"] = [{"value": S(v), "multiplicity": 1} for v in ("0", "0.25", "0.5", "0.75", "1")]
        self.assertEqual([x for x in em.validate_doc(d) if "periodic relation" in x], [])

    def test_weights_iff_rational(self):
        d = base()
        d["entities"][0]["class"] = "bspline"  # still carries weights
        self.assertTrue(em.validate_doc(d))
        d = base()
        del d["entities"][0]["geometry"]["weights"]
        self.assertTrue(em.validate_doc(d))

    def test_rational_with_unit_weights_must_say_so(self):
        d = base()
        g = d["entities"][0]["geometry"]
        g["weights"] = [S("1")] * 4
        errs = em.validate_doc(d)
        self.assertTrue(any("weights_all_unit" in e for e in errs), errs)
        g["weights_all_unit"] = True
        self.assertEqual(em.validate_doc(d), [])

    def test_unknown_key_rejected(self):
        d = base()
        d["entities"][0]["tolerance"] = S("0.001")
        self.assertTrue(em.validate_doc(d))


class Transforms(unittest.TestCase):
    def doc(self, ent):
        d = base()
        d["entities"] = [ent]
        d["assertions"] = [{"id": "a", "kind": "SOURCE_MAPPING", "entity": ent["id"], "claim": "TRANSFORM_PRESERVED", "statement": "x"}]
        if "world" in ent:
            d["assertions"].append({"id": "b", "kind": "GEOMETRIC", "entity": ent["id"], "claim": "WORLD_SPACE_RESULT", "statement": "x"})
        return d

    def world_line(self):
        return {"class": "line", "geometry": line_entity()["geometry"],
                "parameter_domain": {"start": S("0"), "end": S("1")},
                "closure": {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}}

    def test_good_translation(self):
        m = ["1", "0", "0", "2", "0", "1", "0", "3", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "1", "TRANSLATION"), world=self.world_line())
        self.assertEqual(em.validate_doc(self.doc(e)), [])

    def test_wrong_determinant_rejected(self):
        m = ["2", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "1", "UNIFORM_SCALE"), world=self.world_line())
        self.assertTrue(any("determinant" in x for x in em.validate_doc(self.doc(e))))

    def test_singular_transform_with_curve_rejected(self):
        m = ["1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "0", "SINGULAR"), world=self.world_line())
        errs = em.validate_doc(self.doc(e))
        self.assertTrue(any("rejection" in x for x in errs), errs)

    def test_singular_transform_with_classification_is_valid(self):
        m = ["1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "0", "SINGULAR"),
                        rejection={"classification": "SINGULAR_TRANSFORM", "disposition": "REJECT"})
        self.assertEqual(em.validate_doc(self.doc(e)), [])

    def test_singular_matrix_labelled_regular_rejected(self):
        m = ["1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "0", "GENERAL_AFFINE"), world=self.world_line())
        self.assertTrue(any("SINGULAR" in x for x in em.validate_doc(self.doc(e))))

    def test_reflection_needs_orientation(self):
        m = ["-1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        e = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform=transform(m, "-1", "REFLECTION"), world=self.world_line())
        self.assertTrue(any("orientation" in x for x in em.validate_doc(self.doc(e))))
        e["orientation"] = {"parameter_direction": "START_TO_END", "sense_about_normal": "NOT_APPLICABLE"}
        self.assertEqual(em.validate_doc(self.doc(e)), [])

    def test_chain_composition_order_is_checked(self):
        t = ["1", "0", "0", "1", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        s = ["2", "0", "0", "0", "0", "2", "0", "0", "0", "0", "2", "0", "0", "0", "0", "1"]
        # parent-left: T*S puts the translation outside the scale -> translation stays 1
        ts = ["2", "0", "0", "1", "0", "2", "0", "0", "0", "0", "2", "0", "0", "0", "0", "1"]
        st = ["2", "0", "0", "2", "0", "2", "0", "0", "0", "0", "2", "0", "0", "0", "0", "1"]
        def chain(comp):
            return {"order": "OUTERMOST_FIRST",
                    "transforms": [transform(t, "1", "TRANSLATION"), transform(s, "8", "UNIFORM_SCALE")],
                    "composed": transform(comp, "8", "UNIFORM_SCALE")}
        ok = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform_chain=chain(ts), world=self.world_line())
        self.assertEqual(em.validate_doc(self.doc(ok)), [])
        bad = line_entity(structure="INSTANCE_PLUS_TRANSFORM", transform_chain=chain(st), world=self.world_line())
        self.assertTrue(any("composed" in x for x in em.validate_doc(self.doc(bad))))

    def test_circle_non_uniform_scale_must_be_ellipse(self):
        c = {"id": "c0", "class": "circle", "structure": "FLATTENED",
             "geometry": {"center": [S("0")] * 3, "normal": [S("0"), S("0"), S("1")], "x_axis": [S("1"), S("0"), S("0")], "radius": S("1")},
             "parameter_domain": {"start": S("0"), "end": S("6.283185307179586")},
             "closure": {"closed_by_endpoint": True, "closed_by_knots": False, "periodic": True}}
        m = ["2", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        c["transform"] = transform(m, "2", "NON_UNIFORM_SCALE")
        c["world"] = copy.deepcopy({k: c[k] for k in ("class", "geometry", "parameter_domain", "closure")})
        self.assertTrue(any("ellipse" in x for x in em.validate_doc(self.doc(c))))


if __name__ == "__main__":
    unittest.main()
