import json
import tempfile
import unittest
from pathlib import Path

from runner import numeric, check_tolerance_literals as chk

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "policy" / "testdata" / "synthetic-not-p1.2.json"


class Loader(unittest.TestCase):
    def test_no_vendored_policy_means_refusal_not_a_default(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(directory=d)

    def test_policy_without_version_id_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(SYNTH.read_text())
            del data["policy_version"]
            p = Path(d) / "pvec-numeric-policy.x.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)
            data["policy_version"] = "  "
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)

    def test_missing_field_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(SYNTH.read_text())
            del data["tolerance"]
            p = Path(d) / "pvec-numeric-policy.x.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(numeric.PolicyError):
                numeric.load_policy(p)

    def test_version_is_exposed(self):
        self.assertEqual(numeric.load_policy(SYNTH).version, "SYNTHETIC-TEST-ONLY")


class Compare(unittest.TestCase):
    def setUp(self):
        self.p = numeric.load_policy(SYNTH)

    def test_ulp_distance(self):
        import math
        self.assertEqual(numeric.ulp_distance(1.0, 1.0), 0)
        self.assertEqual(numeric.ulp_distance(1.0, math.nextafter(1.0, 2.0)), 1)
        self.assertEqual(numeric.ulp_distance(-0.0, 0.0), 0)
        self.assertEqual(numeric.ulp_distance(-math.ulp(0.0), math.ulp(0.0)), 2)

    def test_close_uses_the_policy_triple(self):
        self.assertTrue(self.p.close(1.0, 1.0 + float("1e-10"), 1.0))      # absolute
        self.assertFalse(self.p.close(1.0, 1.0 + float("1e-6"), 1.0))
        self.assertTrue(self.p.close(float("1e7"), float("1e7") + float("1e-6"), float("1e7")))  # relative to scale
        self.assertFalse(self.p.close(float("1e7"), float("1e7") + float("1e-3"), 1.0))          # same gap, small scale

    def test_units_normalisation_is_exact_then_rounded_once(self):
        self.assertEqual(numeric.to_canonical(float("0.3"), 1), float("0.3"))
        self.assertEqual(numeric.to_canonical(25.4, float("0.001")), float(numeric.Fraction(25.4) * numeric.Fraction(float("0.001"))))

    def test_parameter_alignment_round_trip(self):
        d = (float("2.5"), float("7.5"))
        self.assertEqual(numeric.to_unit_parameter(5.0, d), 0.5)
        self.assertEqual(numeric.from_unit_parameter(0.5, d), 5.0)
        self.assertEqual(numeric.to_unit_parameter(2.5, d), 0.0)

    def test_adaptive_refines_until_stable(self):
        import math
        dev, at, lvl = self.p.adaptive_max_deviation(lambda t: math.sin(t), lambda t: math.sin(t) + 0.5 * t * (1 - t), 0.0, 1.0, lambda a, b: abs(a - b))
        self.assertAlmostEqual(dev, 0.125, places=3)
        self.assertAlmostEqual(at, 0.5, places=2)
        self.assertGreaterEqual(lvl, 2)

    def test_adaptive_gives_up_loudly(self):
        import math
        n = [0]
        def wild(t):
            n[0] += 1
            return math.sin(1.0 / (t + float("1e-9")) * n[0])
        with self.assertRaises(numeric.PolicyError):
            self.p.adaptive_max_deviation(wild, lambda t: 0.0, 0.0, 1.0, lambda a, b: abs(a - b) + n[0])


class Exclusions(unittest.TestCase):
    def test_c0_parameters_from_knots(self):
        k = [(0.0, 3), (0.5, 2), (1.0, 3)]
        self.assertEqual(numeric.c0_parameters(k, 2), [0.5])
        self.assertEqual(numeric.c0_parameters(k, 3), [])

    def test_unlisted_c0_join_fails(self):
        ex = numeric.DerivativeExclusions([])
        with self.assertRaises(numeric.PolicyError):
            ex.require_listed("e1", [0.5])

    def test_listed_exclusion_is_per_entity(self):
        ex = numeric.DerivativeExclusions([{"entity": "e1", "parameter": 0.5, "reason": "C0 knot"}])
        ex.require_listed("e1", [0.5])
        self.assertEqual(ex.filter("e1", [0.25, 0.5]), [0.25])
        self.assertEqual(ex.filter("e2", [0.25, 0.5]), [0.25, 0.5])


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
