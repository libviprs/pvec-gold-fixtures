"""Issue 67: the three STEP-text mutations, applied to the real output of both open converters.

The text checks run anywhere. The class checks need the step_eval binary (STEP_EVAL, as in the step-validator
test image) and skip without it. The probe names below are the acceptance criterion: each mutation has to
change the structural class of at least three named probes per converter, so they are spelled out here and
a change in either direction (a probe that stops being caught, or a new one) fails the test.
"""
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

from runner import discrimination as dsc

ROOT = Path(__file__).resolve().parent.parent
STEP_EVAL = os.environ.get("STEP_EVAL")
CONVERTERS = ("acadsharp-dwg2step", "libredwg-dwg2step")

WEIGHTS_TO_ONE = {"nonunit-weight-001", "nurbs-d2-offconic-001", "nurbs-d3-001"}
KNOT_COLLAPSE = {"bspline-d3-001", "bspline-d5-001", "closed-by-endpoint-001", "nurbs-d2-offconic-001", "nurbs-d3-001", "nonunit-weight-001"}
REPARAMETERISE = {"bspline-d3-001", "bspline-d5-001", "closed-by-endpoint-001", "closed-periodic-001", "nonunit-weight-001",
                  "nurbs-d2-offconic-001", "nurbs-d3-001", "repeated-knot-c0-001"}
EXPECTED = {"weights-to-1": WEIGHTS_TO_ONE, "knot-collapse": KNOT_COLLAPSE, "reparameterise": REPARAMETERISE}
# LibreDWG's converter does not write closed-periodic-001 the way the authored record has it (its unmutated
# output is already BOUNDED_APPROXIMATION), so there is no exact class for a mutation to move it out of.
# That is a finding about the converter, not a gap in the harness, and the probe is named here so it stays visible.
NOT_EXACT_TO_BEGIN_WITH = {"libredwg-dwg2step": {"closed-periodic-001"}}


def named(conv, mut):
    return EXPECTED[mut] - NOT_EXACT_TO_BEGIN_WITH.get(conv, set())


def step_text(conv, probe):
    return dsc.step_path(conv, probe).read_text()


class TextMutations(unittest.TestCase):
    def test_every_converter_has_real_output_for_every_named_probe(self):
        named = set().union(*EXPECTED.values())
        for conv in CONVERTERS:
            for p in named:
                self.assertTrue(dsc.step_path(conv, p).is_file(), (conv, p))

    def test_libredwg_fixtures_match_their_provenance_record(self):
        rec = json.loads((ROOT / "fixtures" / "discrimination" / "libredwg-dwg2step.provenance.json").read_text())
        self.assertTrue(rec["files"])
        for name, sha in rec["files"].items():
            data = (ROOT / "fixtures" / "discrimination" / "libredwg-dwg2step" / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), sha, name)

    def test_acadsharp_files_are_the_pinned_signature_inputs(self):
        man = json.loads((ROOT / "signatures" / "manifest.json").read_text())["fixtures"]
        for p in set().union(*EXPECTED.values()):
            data = dsc.step_path("acadsharp-dwg2step", p).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), man[p]["step_sha256"], p)

    def test_weights_to_one_writes_only_ones_and_keeps_the_count(self):
        for conv in CONVERTERS:
            src = step_text(conv, "nurbs-d3-001")
            old = re.search(r"RATIONAL_B_SPLINE_CURVE\(\(([^)]*)\)\)", src).group(1).split(",")
            out = dsc.mutate("weights-to-1", src)
            new = re.search(r"RATIONAL_B_SPLINE_CURVE\(\(([^)]*)\)\)", out).group(1).split(",")
            self.assertEqual(len(new), len(old))
            self.assertTrue(all(float(x) == 1.0 for x in new))
            self.assertNotEqual([float(x) for x in old], [1.0] * len(old))

    def test_knot_collapse_merges_one_interior_knot_and_keeps_the_multiplicity_sum(self):
        for conv in CONVERTERS:
            src = step_text(conv, "bspline-d3-001")
            before = dsc.knot_spec(src)
            after = dsc.knot_spec(dsc.mutate("knot-collapse", src))
            self.assertEqual(len(after[1]), len(before[1]) - 1)
            self.assertEqual(sum(after[0]), sum(before[0]))
            self.assertEqual(after[1][0], before[1][0])
            self.assertEqual(after[1][-1], before[1][-1])

    def test_reparameterise_doubles_every_knot_and_nothing_else(self):
        for conv in CONVERTERS:
            src = step_text(conv, "bspline-d3-001")
            before, after = dsc.knot_spec(src), dsc.knot_spec(dsc.mutate("reparameterise", src))
            self.assertEqual(after[0], before[0])
            self.assertEqual(after[1], [2.0 * k for k in before[1]])

    def test_a_mutation_that_does_not_apply_says_so(self):
        # a Bezier segment has no interior knot to collapse, and a polyline has no weights
        self.assertIsNone(dsc.mutate("knot-collapse", step_text("libredwg-dwg2step", "bezier-d3-001")))
        self.assertIsNone(dsc.mutate("weights-to-1", step_text("libredwg-dwg2step", "bspline-d3-001")))

    def test_mutated_text_differs_from_the_real_output_only_in_the_curve_entity(self):
        for conv in CONVERTERS:
            src = step_text("libredwg-dwg2step" if conv.startswith("libredwg") else conv, "nurbs-d3-001")
            out = dsc.mutate("reparameterise", src)
            a, b = src.splitlines(), out.splitlines()
            self.assertEqual(len(a), len(b))
            self.assertEqual(sum(x != y for x, y in zip(a, b)), 1)


@unittest.skipUnless(STEP_EVAL, "STEP_EVAL not set")
class RealOutputThroughTheEvaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = dsc.run(STEP_EVAL)

    def test_the_unmutated_real_output_is_structurally_exact_for_the_named_probes(self):
        for conv in CONVERTERS:
            for p in set().union(*EXPECTED.values()):
                want = "BOUNDED_APPROXIMATION" if p in NOT_EXACT_TO_BEGIN_WITH.get(conv, ()) else "STRUCTURAL_EXACT"
                self.assertEqual(self.report[conv][p]["baseline"], want, (conv, p))

    def test_each_mutation_changes_the_class_of_the_named_probes_in_both_converters(self):
        for conv in CONVERTERS:
            for mut in EXPECTED:
                changed = {p for p, r in self.report[conv].items() if r["mutations"][mut]["changed"]}
                self.assertGreaterEqual(len(changed), 3, (conv, mut))
                self.assertEqual(changed, named(conv, mut), (conv, mut))

    def test_the_new_class_is_the_one_each_mutation_should_cause(self):
        for conv in CONVERTERS:
            for p, r in self.report[conv].items():
                m = r["mutations"]
                if m["weights-to-1"]["changed"]:
                    self.assertEqual(m["weights-to-1"]["class"], "BOUNDED_APPROXIMATION", (conv, p))
                if m["knot-collapse"]["changed"]:
                    self.assertEqual(m["knot-collapse"]["class"], "BOUNDED_APPROXIMATION", (conv, p))
                if m["reparameterise"]["changed"]:
                    self.assertEqual(m["reparameterise"]["class"], "GEOMETRIC_EXACT_REPARAMETERIZED", (conv, p))


if __name__ == "__main__":
    unittest.main()
