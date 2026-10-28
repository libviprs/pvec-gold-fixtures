"""Issue 75: OCCT built from a pinned source tarball with contraction off, and the write-up of what it did."""
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = (ROOT / "docker" / "step-validator" / "Dockerfile.occt-src").read_text()
DOC = (ROOT / "docs" / "validator" / "occt-from-source.md").read_text()


class Build(unittest.TestCase):
    def test_the_tarball_is_pinned_by_tag_and_checked_by_hash(self):
        self.assertIn("OCCT_TAG=V7_6_3", DOCKERFILE)
        self.assertRegex(DOCKERFILE, r"OCCT_SHA256=[0-9a-f]{64}")
        self.assertIn("sha256sum -c", DOCKERFILE)

    def test_contraction_is_off_for_the_library_and_for_step_eval(self):
        self.assertIn('FLAGS="-O2 -ffp-contract=off"', DOCKERFILE)
        self.assertIn('-DCMAKE_CXX_FLAGS="${FLAGS}"', DOCKERFILE)
        self.assertIn("-ffp-contract=off", (ROOT / "validator" / "CMakeLists.txt").read_text())

    def test_the_base_image_is_the_shipped_validators_digest(self):
        base = re.search(r"ARG BASE=(\S+)", DOCKERFILE).group(1)
        self.assertIn(base, (ROOT / "docker" / "step-validator" / "Dockerfile").read_text())

    def test_the_shipped_dockerfile_is_not_switched_to_the_source_build(self):
        self.assertIn("libocct-data-exchange-dev", (ROOT / "docker" / "step-validator" / "Dockerfile").read_text())


class Spike(unittest.TestCase):
    def test_compare_reports_identical_and_differing_signatures(self):
        import io
        import sys
        from contextlib import redirect_stdout
        sys.path.insert(0, str(ROOT / "validator"))
        import spike_compare
        with tempfile.TemporaryDirectory() as t:
            for d, val in (("a", "1"), ("b", "1"), ("c", "2")):
                (Path(t) / d / "selftest").mkdir(parents=True)
                (Path(t) / d / "signatures").mkdir()
                (Path(t) / d / "signatures" / "x.signature.json").write_text(json.dumps({"entities": [], "v": val}))
            out = io.StringIO()
            with redirect_stdout(out):
                spike_compare.sigs(Path(t) / "a" / "signatures", Path(t) / "b" / "signatures", "same")
                spike_compare.sigs(Path(t) / "a" / "signatures", Path(t) / "c" / "signatures", "diff")
            self.assertIn("same: 1 of 1 signatures byte identical", out.getvalue())
            self.assertIn("diff: 0 of 1 signatures byte identical", out.getvalue())


class WriteUp(unittest.TestCase):
    def test_it_states_both_results_the_numbers_and_the_conclusion(self):
        for needle in ("1219", "11 diverge", "0 diverge", "19 of 29", "29 of 29", "mars", "mercury", "FMA",
                       "fixtures/validator-selftest", "validator/spike_compare.py", "Dockerfile.occt-src"):
            self.assertIn(needle, DOC)

    def test_the_step_evaluator_doc_no_longer_only_guesses(self):
        text = (ROOT / "docs" / "validator" / "step-evaluator.md").read_text()
        self.assertIn("occt-from-source.md", text)
        self.assertNotIn("but I haven't checked\nthat", text)


if __name__ == "__main__":
    unittest.main()
