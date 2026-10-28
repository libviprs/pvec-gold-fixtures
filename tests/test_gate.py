import json
import tempfile
import unittest
from pathlib import Path

from runner import expected_math as em, numeric, phase1_gate as g, qualify_probes as q

ROOT = Path(__file__).resolve().parent.parent
POL = numeric.load_policy()
A, B = "acadsharp-dwg2step", "libredwg-dwg2step"


def full_report(mutate=None):
    probes = {}
    for f in sorted((ROOT / "fixtures" / "known-truth").rglob("expected.math.json")):
        d = em.load(f)
        probes[d["fixture_id"]] = {c: [{"entity": e["id"], "class": q.STRUCTURAL_EXACT, "evidence": {"fields_compared": 1}} for e in d["entities"]] for c in q.CONVERTERS}
    rep = {"numeric_policy_version": POL.version, "probes": probes}
    if mutate:
        mutate(rep)
    return rep


class Gate(unittest.TestCase):
    def test_the_default_converter_pair_is_the_two_open_ones(self):
        self.assertEqual(q.CONVERTERS, {A: "primary", B: "secondary"})

    def check(self, rep):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.json"
            p.write_text(json.dumps(rep))
            return g.check_probe_classification(p)

    def test_complete_report_is_green(self):
        self.assertEqual(self.check(full_report()), [])

    def test_missing_report_is_red(self):
        self.assertTrue(g.check_probe_classification("/nonexistent/report.json"))

    def test_blank_or_unknown_cell_is_red(self):
        def blank(r):
            r["probes"]["line-001"][A][0]["evidence"] = {}
        self.assertTrue(any("no class or no evidence" in e for e in self.check(full_report(blank))))

        def unknown(r):
            r["probes"]["line-001"][B][0]["class"] = "UNKNOWN"
        self.assertTrue(self.check(full_report(unknown)))

    def test_missing_probe_or_converter_is_red(self):
        def drop(r):
            del r["probes"]["circle-001"]
        self.assertTrue(any("circle-001" in e for e in self.check(full_report(drop))))

        def drop2(r):
            r["probes"]["line-001"][B] = []
        self.assertTrue(any("no cell" in e for e in self.check(full_report(drop2))))

    def test_bounded_cell_needs_its_bound_and_parameter(self):
        def b(r):
            r["probes"]["line-001"][A][0] = {"entity": "line-001", "class": q.BOUNDED, "evidence": {"bound": 0.1}}
        self.assertTrue(any("bounded approximation" in e for e in self.check(full_report(b))))

    def test_wrong_policy_version_is_red(self):
        def v(r):
            r["numeric_policy_version"] = "something else"
        self.assertTrue(any("policy version" in e for e in self.check(full_report(v))))

    def test_without_the_evaluator_the_gate_is_red(self):
        self.assertTrue(g.check_evaluator_selftest("no-such-step-eval-binary"))
        errs = g.check_roundtrip("no-such-step-eval-binary")
        self.assertTrue(any("not run" in e for e in errs))
        self.assertFalse(any("expected.math.json" in e for e in errs))   # the record validation part passes on its own

    def test_the_gate_as_a_whole_is_red_today(self):
        self.assertEqual(g.main(["--evaluator", "no-such-step-eval-binary", "--report", "/nonexistent/r.json"]), 1)


class Adrs(unittest.TestCase):
    ADR = ROOT / "docs" / "adr"

    def test_seven_adrs_with_the_required_parts(self):
        names = ["0001-evidence-classes", "0002-known-truth-authoring", "0003-dual-oracle-role", "0004-independent-step-validator",
                 "0005-numeric-policy-adoption", "0006-quarantine-policy", "0007-licensing-and-image-policy"]
        for n in names:
            t = (self.ADR / (n + ".md")).read_text()
            for part in ("## Context", "## Decision", "## Consequences", "Status:"):
                self.assertIn(part, t, n)
            self.assertIn("anel finding", t, n)

    def test_evidence_classes_are_defined_exactly_once(self):
        classes = ["KNOWN_TRUTH_EXACT", "DUAL_ORACLE_EQUIVALENT", "REAL_WORLD_DIFFERENTIAL", "QUARANTINED"]
        definers = []
        for p in list(ROOT.rglob("*.md")):
            if ".git" in p.parts or ".upstream" in p.parts:
                continue
            t = p.read_text()
            if all(("- `%s`:" % c) in t or ("| `%s` |" % c) in t for c in classes):
                definers.append(str(p.relative_to(ROOT)))
        self.assertEqual(definers, ["docs/adr/0001-evidence-classes.md"])

    def test_adr_0005_has_no_numeric_tolerance(self):
        import re
        t = (self.ADR / "0005-numeric-policy-adoption.md").read_text()
        self.assertEqual(re.findall(r"\d[eE]-\d|0\.0+\d|\bULP\s*=|\bREL\s*=|\bABS\s*=", t), [])

    def test_nothing_calls_display_fidelity_exact(self):
        import re
        for p in ROOT.rglob("*.md"):
            if ".git" in p.parts or ".upstream" in p.parts:
                continue
            for line in p.read_text().splitlines():
                if re.search(r"display[- ]fidelity", line, re.I) and "mathematically exact" in line:
                    self.assertRegex(line, r"(?i)\b(never|not)\b", (p, line))


if __name__ == "__main__":
    unittest.main()
