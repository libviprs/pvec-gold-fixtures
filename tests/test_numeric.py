import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from runner import canon, check_policy_stamp, check_tolerance_literals as chk, check_vendored_policy as cvp, numeric, policy_bump

ROOT = Path(__file__).resolve().parent.parent
POLICY = sorted((ROOT / "policy").glob("pvec-numeric-policy.*.json"))[0]
F = float  # constants below are parsed from text on purpose: this file holds no numeric tolerance literal


def widened(factor, into):
    d = json.loads(POLICY.read_text())
    for k in ("ABS", "REL", "ULP"):
        d["constants"][k] = d["constants"][k] * factor
    p = Path(into) / "pvec-numeric-policy.widened.json"
    p.write_text(json.dumps(d))
    return p


class Loader(unittest.TestCase):
    def test_vendored_policy_is_v1_with_the_documented_constants(self):
        p = numeric.load_policy()
        self.assertEqual(p.version, "PVec numeric policy v1")
        self.assertEqual((p.ABS, p.REL, p.ULP), (F("1e-12"), F("1e-10"), 8))
        self.assertEqual((p.WEIGHT_FLOOR, p.AXIS_RATIO_MAX, p.MAX_ABS_COORD), (F("1e-8"), F("1e6"), 2 ** 40))

    def test_no_vendored_policy_means_refusal_not_a_default(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(directory=d)

    def test_policy_without_version_id_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(POLICY.read_text())
            del data["policy_version"]
            p = Path(d) / "pvec-numeric-policy.x.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)
            data["policy_version"] = "  "
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)

    def test_missing_constant_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(POLICY.read_text())
            del data["constants"]["REL"]
            p = Path(d) / "pvec-numeric-policy.x.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)

    def test_two_policy_files_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("a", "b"):
                (Path(d) / ("pvec-numeric-policy.%s.json" % n)).write_text(POLICY.read_text())
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(directory=d)

    def test_stamp(self):
        self.assertEqual(numeric.policy_stamp(numeric.load_policy()), {"numeric_policy_version": "PVec numeric policy v1"})


class Rules(unittest.TestCase):
    def setUp(self):
        self.p = numeric.load_policy()

    def test_np04_the_ulp_term_dominates_at_large_magnitude(self):
        mag = float(2 ** 39)
        self.assertEqual(self.p.tol(1.0, mag), self.p.ULP * math.ulp(mag))
        self.assertGreater(self.p.tol(1.0, mag), self.p.REL)     # a few thousandths of a unit, not 1e-10

    def test_np04_the_floor_and_the_relative_term(self):
        self.assertEqual(self.p.tol(0.0, 0.0), self.p.ABS)
        self.assertEqual(self.p.tol(F("1e6"), 1.0), self.p.REL * F("1e6"))

    def test_np05_near(self):
        self.assertTrue(self.p.near(1.0, 1.0, 1.0))
        self.assertTrue(self.p.near(1.0, 1.0 + F("5e-11"), 1.0))
        self.assertFalse(self.p.near(1.0, 1.0 + F("3e-10"), 1.0))
        self.assertTrue(self.p.near(1.0, 1.0 + F("3e-10"), F("10")))           # the same gap is fine at a larger feature size
        self.assertFalse(self.p.near(float("nan"), 1.0, 1.0))
        self.assertFalse(self.p.near(float("inf"), float("inf"), 1.0))

    def test_np06_degenerate_length(self):
        self.assertTrue(self.p.degenerate_length(0.0, 1.0))
        self.assertTrue(self.p.degenerate_length(float("inf"), 1.0))
        self.assertFalse(self.p.degenerate_length(F("1e-9"), 1.0))

    def test_np13_unit_map(self):
        self.assertEqual(self.p.unit_parameter(5.0, 2.5, 7.5), 0.5)
        self.assertEqual(self.p.from_unit_parameter(0.5, 2.5, 7.5), 5.0)
        with self.assertRaises(numeric.PolicyError):
            self.p.unit_parameter(0.0, 0.0, F("1e-13"))

    def test_np16_two_sided_derivatives(self):
        self.assertTrue(self.p.two_sided_derivative_exists(2, 3, 1))
        self.assertFalse(self.p.two_sided_derivative_exists(1, 3, 3))    # full multiplicity: C0 only
        self.assertFalse(self.p.two_sided_derivative_exists(2, 3, 2))

    def test_widening_the_policy_flips_a_decision(self):
        with tempfile.TemporaryDirectory() as d:
            wide = numeric.load_policy(widened(10, d))
        a, b = 1.0, 1.0 + F("3e-10")
        self.assertFalse(self.p.near(a, b, 1.0))
        self.assertTrue(wide.near(a, b, 1.0))

    def test_units_normalisation_is_exact_then_rounded_once(self):
        self.assertEqual(numeric.to_canonical(F("0.3"), 1), F("0.3"))
        self.assertEqual(numeric.to_canonical(F("25.4"), F("0.001")), float(numeric.Fraction(F("25.4")) * numeric.Fraction(F("0.001"))))

    def test_adaptive_refines_until_stable_by_the_policy(self):
        dev, at, lvl = self.p.adaptive_max_deviation(lambda t: math.sin(t), lambda t: math.sin(t) + 0.5 * t * (1 - t), 0.0, 1.0, lambda a, b: abs(a - b), 1.0)
        self.assertAlmostEqual(dev, 0.125, places=9)
        self.assertAlmostEqual(at, 0.5, places=2)
        self.assertGreaterEqual(lvl, 2)

    def test_adaptive_gives_up_loudly(self):
        n = [0]

        def growing(a, b):
            n[0] += 1
            return n[0]
        with self.assertRaises(numeric.PolicyError):
            self.p.adaptive_max_deviation(lambda t: 0.0, lambda t: 0.0, 0.0, 1.0, growing, 1.0)


class Exclusions(unittest.TestCase):
    def test_c0_parameters_from_knots(self):
        k = [(0.0, 3), (0.5, 2), (1.0, 3)]
        self.assertEqual(numeric.c0_parameters(k, 2), [0.5])
        self.assertEqual(numeric.c0_parameters(k, 3), [])

    def test_unlisted_c0_join_fails(self):
        with self.assertRaises(numeric.PolicyError):
            numeric.DerivativeExclusions([]).require_listed("e1", [0.5])

    def test_listed_exclusion_is_per_entity(self):
        ex = numeric.DerivativeExclusions([{"entity": "e1", "parameter": 0.5, "reason": "C0_KNOT"}])
        ex.require_listed("e1", [0.5])
        self.assertEqual(ex.filter("e1", [0.25, 0.5]), [0.25])
        self.assertEqual(ex.filter("e2", [0.25, 0.5]), [0.25, 0.5])


class FeatureScale(unittest.TestCase):
    def test_scales(self):
        S = canon.scalar
        P = lambda *v: [S(c) for c in v]  # noqa: E731
        self.assertEqual(numeric.feature_scale({"class": "line", "geometry": {"start": P(0, 0, 0), "end": P(3, 4, 0)}}), 5.0)
        self.assertEqual(numeric.feature_scale({"class": "circle", "geometry": {"radius": S(2)}}), 2.0)
        self.assertEqual(numeric.feature_scale({"class": "ellipse", "geometry": {"semi_major": S(4), "semi_minor": S(2)}}), 4.0)
        self.assertEqual(numeric.feature_scale({"class": "bezier", "geometry": {"control_points": [P(0, 0, 0), P(3, 4, 0)]}}), 5.0)


class Vendoring(unittest.TestCase):
    DOC = ("| Name | Value | Used by |\n|---|---|---|\n| `ABS` | `1e-12` (coordinate units) | x |\n| `REL` | `1e-10` | x |\n| `ULP` | `8` | x |\n"
           "| `WEIGHT_FLOOR` | `1e-8` | x |\n| `AXIS_RATIO_MAX` | `1e6` | x |\n| `MAX_ABS_COORD` | `2^40` = 1099511627776 | x |\n")

    def test_table_parse(self):
        t = cvp.table(self.DOC)
        self.assertEqual(t["ULP"], 8.0)
        self.assertEqual(t["MAX_ABS_COORD"], float(2 ** 40))
        self.assertEqual(t["ABS"], F("1e-12"))

    def test_check_detects_a_stale_or_edited_policy(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            doc = Path(d) / "doc.md"
            doc.write_text(self.DOC)
            data = json.loads(POLICY.read_text())
            data["source"]["document_sha256"] = hashlib.sha256(self.DOC.encode()).hexdigest()
            pol = Path(d) / "pvec-numeric-policy.t.json"
            pol.write_text(json.dumps(data))
            self.assertEqual(cvp.check(doc, pol), [])
            data["constants"]["REL"] = F("1e-9")
            pol.write_text(json.dumps(data))
            self.assertTrue(any("REL" in e for e in cvp.check(doc, pol)))
            doc.write_text(self.DOC + "\n")
            self.assertTrue(any("document_sha256" in e for e in cvp.check(doc, pol)))

    @unittest.skipUnless(os.environ.get("UPSTREAM_POLICY_DOC"), "set UPSTREAM_POLICY_DOC to a copy of pvec's docs/NUMERIC_POLICY.md")
    def test_vendored_file_matches_the_upstream_document(self):
        self.assertEqual(cvp.check(os.environ["UPSTREAM_POLICY_DOC"]), [])


class Stamp(unittest.TestCase):
    def test_artifacts_must_carry_the_adopted_version(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad, none = (Path(d) / n for n in ("good.verification.json", "bad.verification.json", "comparison.json"))
            good.write_text(json.dumps(numeric.policy_stamp(numeric.load_policy())))
            bad.write_text(json.dumps({"numeric_policy_version": "something else"}))
            none.write_text("{}")
            self.assertEqual(check_policy_stamp.check([good]), [])
            self.assertEqual(len(check_policy_stamp.check([good, bad, none])), 2)


class Bump(unittest.TestCase):
    def test_report_counts_changed_outcomes(self):
        old = [{"fixture": "a", "outcome": "ACCEPT"}, {"fixture": "b", "outcome": "ACCEPT"}, {"fixture": "c", "outcome": "QUARANTINE"}]
        new = [{"fixture": "a", "outcome": "ACCEPT"}, {"fixture": "b", "outcome": "QUARANTINE"}, {"fixture": "c", "outcome": "QUARANTINE"}]
        counts, changed = policy_bump.diff(old, new)
        self.assertEqual(dict(counts), {("ACCEPT", "QUARANTINE"): 1})
        self.assertEqual(list(changed), ["b"])


class LiteralCheck(unittest.TestCase):
    def test_repository_is_clean(self):
        self.assertEqual(chk.scan(ROOT), [])

    def test_mutation_bare_constant_turns_the_check_red(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "runner").mkdir()
            (root / "runner" / "ok.py").write_text('X = "no numbers here"\n')
            self.assertEqual(chk.scan(root), [])
            lit = "1e" + "-6"
            (root / "runner" / "bad.py").write_text("def close(a, b):\n    return abs(a - b) < %s\n" % lit)
            self.assertEqual(len(chk.scan(root)), 1)
            (root / "runner" / "bad.py").write_text("tolerance = 3\n")
            self.assertEqual(len(chk.scan(root)), 1)
            (root / "runner" / "bad.py").unlink()
            (root / "validator.cpp").write_text("static const double kEps = %s;\n" % lit)
            self.assertTrue(chk.scan(root))

    def test_policy_dir_is_exempt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "policy").mkdir()
            (root / "policy" / "p.py").write_text("tolerance = %s\n" % ("1e" + "-9"))
            self.assertEqual(chk.scan(root), [])


if __name__ == "__main__":
    unittest.main()
