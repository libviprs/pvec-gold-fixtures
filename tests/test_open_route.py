"""Issues 2 and 6 on the open route: qualify the open converter against the probe corpus, freeze the ADRs."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from runner import numeric, phase1_gate as g, qualify_probes as q

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "phase1" / "probe-qualification.json"
KT = ROOT / "fixtures" / "known-truth"
POL = numeric.load_policy()
OPEN = "acadsharp-dwg2step"
NO_DWG = ("shear-001", "general-affine-001", "singular-001")


class SingleOracle(unittest.TestCase):
    """One open converter is enough to qualify the probes, and the report must say it is one oracle."""

    def run_main(self, *extra):
        with tempfile.TemporaryDirectory() as t:
            out = str(Path(t) / "r.json")
            rc = q.main(["--probes", str(KT), "--out", out, "--primary", OPEN, t, "--lineage", OPEN + "=ACadSharp", *extra])
            return rc, json.loads(Path(out).read_text())

    def test_secondary_is_optional(self):
        rc, rep = self.run_main()
        self.assertEqual(rc, 0)
        self.assertEqual(rep["converters"], {"primary": OPEN})
        self.assertEqual(rep["lineages"], {OPEN: "ACadSharp"})
        self.assertEqual(rep["oracle_count"], 1)
        self.assertEqual(rep["oracle_scope"], "OPEN_CONVERTERS")

    def test_a_single_oracle_verdict_says_so(self):
        _, rep = self.run_main()
        for row in rep["capabilities"]:
            self.assertIn("single oracle", " ".join(row["reasons"]), row["capability"])

    def test_a_second_converter_of_the_same_lineage_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(SystemExit):
                q.main(["--probes", str(KT), "--out", str(Path(t) / "r.json"), "--primary", "first-dwg2step", t,
                        "--secondary", "second-dwg2step", t, "--lineage", "first-dwg2step=ACadSharp",
                        "--lineage", "second-dwg2step=ACadSharp"])

    def test_probes_without_a_dwg_say_why(self):
        with tempfile.TemporaryDirectory() as t:
            out = str(Path(t) / "r.json")
            q.main(["--probes", str(KT), "--out", out, "--primary", OPEN, t, "--lineage", OPEN + "=ACadSharp",
                    "--excluded", str(ROOT / "corpus" / "r0-open" / "quarantine.json")])
            rep = json.loads(Path(out).read_text())
        for pid in NO_DWG:
            for c in rep["probes"][pid][OPEN]:
                self.assertIn("no source.dwg", c["evidence"]["reason"], pid)
                self.assertTrue(c["not_run"], pid)
                self.assertFalse(c["expectation_met"], pid)

    def test_a_probe_that_was_never_run_blocks_its_capability(self):
        _, rep = self.run_main("--excluded", str(ROOT / "corpus" / "r0-open" / "quarantine.json"))
        row = next(r for r in rep["capabilities"] if r["capability"] == "affine_transform")
        self.assertEqual(row["status"], "BLOCKED")
        self.assertIn("not run", " ".join(row["reasons"]))
        for n in NO_DWG:
            self.assertIn(n, " ".join(row["reasons"]))

    def test_one_converter_that_is_bounded_is_not_described_as_two_agreeing(self):
        res = {p: {OPEN: [{"entity": "x", "class": q.BOUNDED, "evidence": {}}]} for p in q.CAPABILITIES["line"]}
        r = q.capability_verdicts(POL, res)[0]
        self.assertEqual(r["status"], "BLOCKED")
        self.assertNotIn("both converters", " ".join(r["reasons"]))
        self.assertIn("not certified", " ".join(r["reasons"]))


class CommittedReport(unittest.TestCase):
    """reports/phase1/probe-qualification.json is the output of a real run on native x86_64."""

    def rep(self):
        self.assertTrue(REPORT.exists(), "reports/phase1/probe-qualification.json has not been produced")
        return json.loads(REPORT.read_text())

    def test_report_is_the_open_converter_on_the_adopted_policy(self):
        r = self.rep()
        self.assertEqual(r["numeric_policy_version"], POL.version)
        self.assertEqual(r["converters"], {"primary": OPEN, "secondary": "libredwg-dwg2step"})
        self.assertEqual(r["oracle_scope"], "OPEN_CONVERTERS")
        self.assertEqual(r["oracle_count"], 2)
        self.assertEqual(r["platform"], "linux/amd64")

    def test_gate_check_one_is_green(self):
        self.assertEqual(g.check_probe_classification(REPORT), [])

    def test_every_cell_cites_evidence_and_every_bound_names_its_parameter(self):
        r = self.rep()
        n = 0
        for pid, per in r["probes"].items():
            for c in per[OPEN]:
                n += 1
                self.assertTrue(c["evidence"], pid)
                if c["class"] == q.BOUNDED:
                    self.assertLessEqual({"bound", "at_unit_parameter"}, set(c["evidence"]), pid)
        self.assertGreaterEqual(n, 28)

    def test_the_rejection_probes_are_judged_by_expectation(self):
        r = self.rep()
        self.assertTrue(all(c["expectation_met"] for c in r["probes"]["near-singular-001"][OPEN]))
        for pid in NO_DWG:
            self.assertTrue(all(c["not_run"] and not c["expectation_met"] for c in r["probes"][pid][OPEN]), pid)

    def test_no_probe_the_converter_ran_on_is_a_bounded_approximation(self):
        r = self.rep()
        bad = [(p, c["entity"]) for p, per in r["probes"].items() for c in per[OPEN] if c["class"] == q.BOUNDED]
        self.assertEqual(bad, [])

    def test_every_capability_has_a_verdict(self):
        r = self.rep()
        self.assertEqual({c["capability"] for c in r["capabilities"]}, set(q.CAPABILITIES))
        for c in r["capabilities"]:
            self.assertIn(c["status"], ("CERTIFIED", "BLOCKED"))


class FrozenDocs(unittest.TestCase):
    def read(self, rel):
        return (ROOT / rel).read_text()

    def test_adrs_1_to_7_are_frozen(self):
        for f in sorted((ROOT / "docs" / "adr").glob("000[1-7]-*.md")):
            status = re.search(r"^Status:.*", f.read_text(), re.M).group(0)
            self.assertIn("frozen", status.lower(), f.name)
            self.assertNotIn("proposed", status.lower(), f.name)

    def test_adr_0004_and_0007_cite_adr_0010(self):
        for n in ("0004-independent-step-validator", "0007-licensing-and-image-policy"):
            self.assertIn("ADR 0010", self.read("docs/adr/%s.md" % n), n)

    def test_adr_0010_is_accepted_and_supersedes_the_vendor_clauses(self):
        t = self.read("docs/adr/0010-open-source-only.md")
        status = re.search(r"^Status:.*", t, re.M).group(0).lower()
        self.assertIn("accepted", status)
        for n in ("0002", "0003", "0004", "0007", "0008", "0009"):
            self.assertIn(n, status)

    def test_no_adr_but_0010_names_a_vendor(self):
        needle = re.compile(r"cadex|cad exchanger|\boda\b|\bvendors?\b|VENDOR_CONVERTERS|licensee|proprietary", re.I)
        for f in sorted((ROOT / "docs" / "adr").glob("*.md")):
            if f.name.startswith("0010-"):
                continue
            self.assertEqual(needle.findall(f.read_text()), [], f.name)

    def test_the_exit_gate_is_recorded_as_three_named_checks_with_its_open_route_result(self):
        t = self.read("docs/phase1-converter-qualification.md")
        for name in ("probe-classification", "evaluator-selftest", "expected-math-roundtrip"):
            self.assertIn(name, t)
        self.assertIn("Probe-by-converter matrix", t)
        self.assertIn("Per-capability verdicts", t)
        self.assertIn("Exit statement", t)
        self.assertNotIn("Status: **not run", t)

    def test_the_exit_gate_run_is_recorded_green(self):
        t = self.read("reports/phase1/exit-gate.txt")
        for name in ("probe-classification", "evaluator-selftest", "expected-math-roundtrip"):
            self.assertIn("GREEN " + name, t)
        self.assertIn("phase 1 exit gate: GREEN", t)

    def test_the_open_route_status_names_the_second_oracle_and_the_discrimination_run(self):
        t = self.read("docs/open-route-status.md")
        self.assertRegex(t, r"(?m)^## .*second oracle")
        for word in ("libredwg", "discrimination", "#65", "#67"):
            self.assertIn(word, t.lower() if word.islower() else t)


if __name__ == "__main__":
    unittest.main()
