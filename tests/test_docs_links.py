"""Every relative markdown link in README.md and docs/ resolves, and the twelve documents are linked from the README (#27)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TWELVE = ["README.md", "docs/docker-workflow.md", "docs/converters/licensing-and-setup.md", "docs/fixtures/authoring.md",
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

    def test_numeric_policy_cites_p1_2_and_has_no_epsilon(self):
        t = (ROOT / "docs" / "numeric-policy.md").read_text()
        self.assertIn("P1.2", t)
        self.assertEqual(re.findall(r"\bULP\s*=|\bREL\s*=|\bABS\s*=", t), [])


if __name__ == "__main__":
    unittest.main()
