"""Issue 65: LibreDWG is the second oracle on r0-open.

Compose declares the converter by image reference only (the image is GPL and is never a build context here),
the committed probe report carries both columns, and a discrepancy is only ever resolved with its explanation.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from runner import phase1_gate as g, qualify_probes as q

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "phase1" / "probe-qualification.json"
PRIMARY, SECONDARY = "acadsharp-dwg2step", "libredwg-dwg2step"


def service(name):
    text = (ROOT / "docker-compose.yml").read_text()
    m = re.search(r"^  %s:\n((?:    .*\n|\n)+)" % re.escape(name), text, re.M)
    return m.group(1) if m else None


class Compose(unittest.TestCase):
    def test_libredwg_converter_is_declared(self):
        self.assertIsNotNone(service("libredwg-converter"))

    def test_it_is_an_image_reference_never_a_build(self):
        s = service("libredwg-converter") or ""
        self.assertRegex(s, r"image: \$\{LIBREDWG_IMAGE:-[^}]+\}")
        self.assertNotIn("build:", s)
        self.assertNotIn("context:", s)

    def test_it_runs_as_locked_down_as_the_other_open_converter(self):
        s = service("libredwg-converter") or ""
        for want in ("network_mode: none", "read_only: true", "no-new-privileges:true", "cap_drop:", "mem_limit:"):
            self.assertIn(want, s)

    def test_no_dockerfile_in_this_repo_builds_libredwg(self):
        for df in list((ROOT / "docker").rglob("Dockerfile*")) + list((ROOT / "tools").rglob("*ockerfile*")):
            self.assertNotRegex(df.read_text().lower(), r"libredwg", str(df))


class Report(unittest.TestCase):
    def setUp(self):
        self.rep = json.loads(REPORT.read_text())

    def test_two_oracles_with_distinct_lineages(self):
        self.assertEqual(self.rep["oracle_count"], 2)
        self.assertEqual(self.rep["converters"], {"primary": PRIMARY, "secondary": SECONDARY})
        self.assertEqual(self.rep["lineages"], {PRIMARY: "ACadSharp", SECONDARY: "LibreDWG"})
        self.assertEqual(self.rep["oracle_scope"], "OPEN_CONVERTERS")

    def test_every_probe_has_cells_for_both_converters(self):
        for pid, per in self.rep["probes"].items():
            for conv in (PRIMARY, SECONDARY):
                self.assertTrue(per.get(conv), "%s/%s" % (pid, conv))
                for c in per[conv]:
                    self.assertIn(c["class"], q.RANK, pid)

    def test_no_capability_blames_a_single_oracle(self):
        for row in self.rep["capabilities"]:
            self.assertNotIn("single oracle", " ".join(row["reasons"]), row["capability"])

    def test_the_probe_classification_gate_is_green_on_it(self):
        self.assertEqual(g.check_probe_classification(REPORT), [])


class Resolved(unittest.TestCase):
    """A discrepancy is resolved by naming the probe and saying why; a bare name is refused."""

    def run_main(self, resolved):
        with tempfile.TemporaryDirectory() as t:
            rp = Path(t) / "resolved.json"
            rp.write_text(json.dumps(resolved))
            q.main(["--probes", str(ROOT / "fixtures" / "known-truth"), "--out", str(Path(t) / "r.json"),
                    "--primary", "a", t, "--secondary", "b", t, "--lineage", "a=ACadSharp", "--lineage", "b=LibreDWG",
                    "--resolved", str(rp)])

    def test_a_bare_probe_id_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            self.run_main(["line-001"])
        self.assertIn("explanation", str(e.exception))

    def test_an_empty_explanation_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_main([{"probe": "line-001", "explanation": " "}])

    def test_an_unknown_probe_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            self.run_main([{"probe": "nope-001", "explanation": "x"}])
        self.assertIn("nope-001", str(e.exception))

    def test_the_explanation_is_recorded_in_the_report(self):
        with tempfile.TemporaryDirectory() as t:
            rp = Path(t) / "resolved.json"
            rp.write_text(json.dumps([{"probe": "line-001", "explanation": "because"}]))
            out = Path(t) / "r.json"
            q.main(["--probes", str(ROOT / "fixtures" / "known-truth"), "--out", str(out), "--primary", "a", t,
                    "--secondary", "b", t, "--lineage", "a=ACadSharp", "--lineage", "b=LibreDWG", "--resolved", str(rp)])
            self.assertEqual(json.loads(out.read_text())["resolved"], [{"probe": "line-001", "explanation": "because"}])
