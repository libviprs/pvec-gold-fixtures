"""Issue 96: viewport, paper-space and large-industrial fixtures (needed by libviprs#1055 and #1064).

Red until the fixtures exist. libviprs records these cases as not available while there is nothing here to
run against, so each test names what libviprs would look for: params and an authored expected.math.json for the
clipped viewport (exact and bounded-only), a paper-space layout with 20 viewports, and a generator, with a
manifest entry carrying a size class, for the large industrial drawing (about 10^6 entities, never committed).
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "tools" / "authoring" / "params-r3"
KNOWN = ROOT / "fixtures" / "viewports"
GEN = ROOT / "tools" / "authoring" / "gen_large_industrial.py"
REVISION = ROOT / "corpus" / "r3-open"


def params(fid):
    p = PARAMS / (fid + ".json")
    assert p.is_file(), "issue 96: no params file %s" % p.relative_to(ROOT)
    return json.loads(p.read_text())


class ViewportFixtures(unittest.TestCase):
    def test_clipped_viewport_exact_and_bounded_have_params(self):
        exact = params("viewport-clipped-001")
        bounded = params("viewport-clipped-bounded-001")
        self.assertEqual(exact["kind"], "viewport_clipped")
        self.assertEqual(bounded["kind"], "viewport_clipped_bounded")
        self.assertEqual(exact["clip"]["exactness"], "EXACT")
        self.assertEqual(bounded["clip"]["exactness"], "BOUNDED_ONLY")

    def test_paper_space_layout_has_twenty_viewports(self):
        p = params("paper-space-multi-viewport-001")
        self.assertEqual(p["kind"], "paper_space_layout")
        self.assertEqual(len(p["viewports"]), 20)

    def test_each_has_an_authored_expected_math_record(self):
        for fid in ("viewport-clipped-001", "viewport-clipped-bounded-001", "paper-space-multi-viewport-001"):
            rec = KNOWN / fid / "expected.math.json"
            self.assertTrue(rec.is_file(), "issue 96: %s has no expected.math.json" % fid)
            self.assertIn("assertions", json.loads(rec.read_text()))


class LargeIndustrialGenerator(unittest.TestCase):
    def run_gen(self, out, count):
        self.assertTrue(GEN.is_file(), "issue 96: no generator at %s" % GEN.relative_to(ROOT))
        r = subprocess.run([sys.executable, "-I", str(GEN), "--count", str(count), "--out", str(out)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return Path(out).read_bytes()

    def test_generator_is_deterministic_and_honours_count(self):
        with tempfile.TemporaryDirectory() as d:
            a = self.run_gen(Path(d) / "a.json", 1000)
            b = self.run_gen(Path(d) / "b.json", 1000)
            self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())
            self.assertEqual(len(json.loads(a)["entities"]), 1000)

    def test_manifest_entry_has_a_size_class_and_no_committed_binary(self):
        m = json.loads((REVISION / "manifest.json").read_text())
        e = next(f for f in m["fixtures"] if f["id"] == "large-industrial-001")
        self.assertEqual(e["size_class"], "large")
        self.assertEqual(e["entity_count"], 1000000)
        self.assertEqual(e["generator"], "tools/authoring/gen_large_industrial.py")
        self.assertFalse(list((REVISION).rglob("large-industrial-001*.dwg")), "the large drawing must be generated, not committed")


class Revision(unittest.TestCase):
    def test_the_committed_revision_checks_clean(self):
        from runner import r3_open
        self.assertEqual(r3_open.check(), [])

    def test_a_moved_clip_vertex_is_a_mismatch(self):
        from runner import r3_open
        exp = json.loads((KNOWN / "viewport-clipped-001" / "expected.math.json").read_text())
        read = json.loads((REVISION / "fixtures" / "viewport-clipped-001" / "read.acadrust.json").read_text())
        self.assertEqual(r3_open.compare(exp, read), [])
        read["viewports"][0]["clip_polygon"][0][0] = "0x4051800000000001"
        self.assertTrue(r3_open.compare(exp, read))

    def test_the_records_validate_and_a_clip_without_bounds_does_not(self):
        from runner import expected_math
        for fid in ("viewport-clipped-001", "viewport-clipped-bounded-001", "paper-space-multi-viewport-001"):
            self.assertEqual(expected_math.validate_file(str(KNOWN / fid / "expected.math.json")), [], fid)
        doc = json.loads((KNOWN / "viewport-clipped-bounded-001" / "expected.math.json").read_text())
        del doc["viewports"][0]["clip"]["bounds"]
        self.assertTrue(any("bounds" in e for e in expected_math.validate_doc(doc)))


if __name__ == "__main__":
    unittest.main()
