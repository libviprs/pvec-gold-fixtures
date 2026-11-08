"""Issue 102: every viewport probe has its view target at the origin, so the view centre carries the position.

A DXF or DWG reads the view centre relative to the view target. The writer used to put the target on the view
centre, which a reader following that rule places at twice the authored point. The reader dump records the
target, and r3_open.compare refuses a target off the origin.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVISION = ROOT / "corpus" / "r3-open"
KNOWN = ROOT / "fixtures" / "viewports"
IDS = ("viewport-clipped-001", "viewport-clipped-bounded-001", "paper-space-multi-viewport-001")
ZERO = "0x0000000000000000"


def read(fid):
    return json.loads((REVISION / "fixtures" / fid / "read.acadrust.json").read_text())


class TargetAtOrigin(unittest.TestCase):
    def test_every_committed_viewport_records_a_zero_target(self):
        for fid in IDS:
            for v in read(fid)["viewports"]:
                self.assertIn("view_target", v, "%s viewport %s: the dump has no view_target" % (fid, v["id"]))
                self.assertEqual(v["view_target"], [ZERO, ZERO, ZERO], "%s viewport %s" % (fid, v["id"]))

    def test_a_target_on_the_view_centre_is_a_mismatch(self):
        from runner import r3_open
        for fid in IDS:
            exp = json.loads((KNOWN / fid / "expected.math.json").read_text())
            r = read(fid)
            for v in r["viewports"]:
                v["view_target"] = [v["view_center"][0], v["view_center"][1], ZERO]
            self.assertTrue(any("view_target" in e for e in r3_open.compare(exp, r)), fid)

    def test_a_dump_without_a_target_is_a_mismatch(self):
        from runner import r3_open
        exp = json.loads((KNOWN / "viewport-clipped-001" / "expected.math.json").read_text())
        r = read("viewport-clipped-001")
        for v in r["viewports"]:
            v.pop("view_target", None)
        self.assertTrue(any("view_target" in e for e in r3_open.compare(exp, r)))

    def test_the_writer_puts_the_target_at_the_origin(self):
        src = (ROOT / "tools" / "r0-open" / "rust" / "src" / "main.rs").read_text()
        self.assertFalse("vp.view_target = Vector3::new(vc.x, vc.y" in src, "the writer still puts the target on the view centre")
        self.assertTrue("vp.view_target = Vector3::new(0.0, 0.0, 0.0)" in src, "the writer does not set a zero target")


if __name__ == "__main__":
    unittest.main()
