"""Checks that need the step_eval binary (set STEP_EVAL, as in the step-validator image) skip without it."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from runner import canon, expected_math as em, structural, verification

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "fixtures" / "examples" / "rational-bspline.expected.math.json"
STEP_EVAL = os.environ.get("STEP_EVAL")


def run_eval(step):
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "o.json"
        subprocess.run([STEP_EVAL, "--in", str(step), "--out", str(out), "--policy-version", "TEST-ID"], check=True)
        return verification.load(out)


class Shapes(unittest.TestCase):
    def test_verification_schema_reuses_expected_definitions(self):
        v = json.loads(verification.VERIFICATION_SCHEMA.read_text())
        text = json.dumps(v)
        for d in ("scalar", "point3", "curve_core", "transform", "domain", "closure"):
            self.assertIn("expected.math.schema.json#/$defs/%s" % d, text)

    def test_schema_has_no_tolerance(self):
        text = verification.VERIFICATION_SCHEMA.read_text().lower()
        for w in ("tolerance", "epsilon", "ulp"):
            self.assertNotIn(w, text)

    def test_worked_example_fits_the_verification_entity_shape(self):
        ex = em.load(EXAMPLE)["entities"][0]
        ident = ["1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]
        ent = {k: ex[k] for k in ("id", "class", "geometry", "parameter_domain", "closure")}
        ent.update(structure="CURVE_ONLY", samples=[], transform={
            "convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": [canon.scalar(x) for x in ident],
            "determinant": canon.scalar("1"), "classification": "IDENTITY"})
        doc = {"schema_version": "pvec-gold/verification/1", "tool": {"name": "step_eval", "evaluator_version": "1", "occt_version": "7"},
               "numeric_policy_version": "X", "units": {"name": "METRE", "canonical": "metre", "scale_to_canonical": canon.scalar("1"), "source": "file"},
               "entities": [ent]}
        self.assertEqual(verification.validate_doc(doc), [])


@unittest.skipUnless(STEP_EVAL, "STEP_EVAL not set")
class WithEvaluator(unittest.TestCase):
    def test_worked_example_round_trips_field_for_field(self):
        got = run_eval(ROOT / "fixtures" / "validator-selftest" / "rational-bspline.step")
        self.assertEqual(verification.validate_doc(got), [])
        self.assertEqual(got["numeric_policy_version"], "TEST-ID")
        self.assertTrue(got["tool"]["occt_version"])
        e = got["entities"][0]
        ex = em.load(EXAMPLE)["entities"][0]
        # decimal text may differ in spelling ("1" versus "1.0"); the f64_hex bits may not
        self.assertEqual(structural.structural_diff(ex, e), [])

    def test_every_selftest_output_validates_against_the_schema(self):
        for step in sorted((ROOT / "fixtures" / "validator-selftest").glob("*.step")):
            self.assertEqual(verification.validate_doc(run_eval(step)), [], step.name)

    def test_c0_knot_is_excluded_not_evaluated(self):
        # a clamped quadratic with a full-multiplicity interior knot, written inline
        src = (ROOT / "fixtures" / "validator-selftest" / "rational-bspline.step").read_text()
        src = src.replace("(3,1,3),(0.,0.5,1.)", "(3,2,3),(0.,0.5,1.)").replace("B_SPLINE_CURVE(2,(#101,#102,#103,#104)", "B_SPLINE_CURVE(2,(#101,#102,#103,#104,#104)")
        src = src.replace("RATIONAL_B_SPLINE_CURVE((1.,0.5,2.,1.))", "RATIONAL_B_SPLINE_CURVE((1.,0.5,2.,1.,1.))")
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "c0.step"
            p.write_text(src)
            e = run_eval(p)["entities"][0]
        at_knot = [s for s in e["samples"] if s["parameter"]["decimal"] == "0.5"][0]
        self.assertIsNone(at_knot["tangent"])
        self.assertEqual(at_knot["derivative_exclusion"], "C0_KNOT")
        self.assertEqual([x["parameter"]["decimal"] for x in e["derivative_exclusions"]], ["0.5"])


if __name__ == "__main__":
    unittest.main()
