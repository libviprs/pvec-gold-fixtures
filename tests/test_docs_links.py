"""Every relative markdown link in README.md and docs/ resolves, and the twelve documents are linked from the README (#27)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TWELVE = ["README.md", "docs/docker-workflow.md", "docs/converters/images-and-setup.md", "docs/fixtures/authoring.md",
          "docs/evidence-classes.md", "docs/validator/step-evaluator.md", "docs/numeric-policy.md", "docs/provenance.md",
          "docs/acceptance-and-quarantine.md", "docs/reproducibility.md", "docs/downstream-contract.md", "docs/benchmark-report.md"]


class Links(unittest.TestCase):
    def test_twelve_documents_exist_and_are_linked_from_the_readme(self):
        readme = (ROOT / "README.md").read_text()
        for d in TWELVE:
            self.assertTrue((ROOT / d).is_file(), d)
            if d != "README.md":
                self.assertIn("](" + d, readme, d)

    def test_relative_links_resolve(self):
        bad = []
        files = [ROOT / "README.md", ROOT / "reports" / "final-audit.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "corpus").rglob("*.md"))]
        for f in files:
            for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", f.read_text()):
                t = m.group(1)
                if "://" in t or t.startswith("mailto:"):
                    continue
                if not (f.parent / t).resolve().exists():
                    bad.append("%s -> %s" % (f.relative_to(ROOT), t))
        self.assertEqual(bad, [])

    def test_the_vendor_documents_are_gone_and_the_status_document_replaces_them(self):
        for gone in ("docs/vendor-deferred.md", "docs/converters/cadex-qualification.md", "docs/converters/oda-qualification.md",
                     "docs/converters/archive.md", "docs/converters/licensing-and-setup.md"):
            self.assertFalse((ROOT / gone).exists(), gone)
        self.assertTrue((ROOT / "docs" / "open-route-status.md").is_file())

    def test_no_document_names_a_licensed_converter_outside_the_history(self):
        allowed = {"docs/adr/0010-open-source-only.md", "corpus/r0-open/README.md", "corpus/CHANGELOG.md"}
        needle = re.compile(r"cadex|cad exchanger|\boda\b|VENDOR_CONVERTERS|vendor-deferred|licensee", re.I)
        files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "corpus").glob("*.md")),
                 *sorted((ROOT / "corpus").glob("*/README.md"))]
        bad = [str(f.relative_to(ROOT)) for f in files if str(f.relative_to(ROOT)) not in allowed and needle.search(f.read_text())]
        self.assertEqual(bad, [])

    def test_numeric_policy_cites_p1_2_and_has_no_epsilon(self):
        t = (ROOT / "docs" / "numeric-policy.md").read_text()
        self.assertIn("P1.2", t)
        self.assertEqual(re.findall(r"\bULP\s*=|\bREL\s*=|\bABS\s*=", t), [])


if __name__ == "__main__":
    unittest.main()
