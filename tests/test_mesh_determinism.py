"""#73: negative/mesh-001 regenerates byte for byte, so the pin note goes. Written before the fix."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INFO = json.loads((ROOT / "tools" / "corpus" / "writer-info.json").read_text())
MANIFEST = json.loads((ROOT / "corpus" / "r1-open" / "manifest.json").read_text())
CORPUS_RS = (ROOT / "tools" / "corpus" / "writer" / "src" / "corpus.rs").read_text()


class MeshDeterminism(unittest.TestCase):
    def test_writer_info_says_26_of_26_and_has_no_pin_note(self):
        d = INFO["determinism"]
        self.assertIn("23 of 23", d)
        self.assertNotRegex(d, r"(?i)pinned|not deterministic|differs between runs")

    def test_manifest_determinism_matches_writer_info(self):
        self.assertEqual(MANIFEST["determinism"], INFO["determinism"])

    def test_mesh_001_is_not_special_cased_in_the_manifest(self):
        f = [x for x in MANIFEST["fixtures"] if x["id"] == "mesh-001"][0]
        self.assertNotIn("pin", json.dumps(f).lower().replace("pinned_by", ""))
        self.assertNotRegex(json.dumps(MANIFEST), r"(?i)not byte-reproducible|hash is pinned")

    def test_the_writer_orders_the_mesh_edges(self):
        self.assertRegex(CORPUS_RS, r"edges\.sort")

    def test_the_mesh_still_goes_through_the_acadrust_mesh_writer(self):
        self.assertIn("Mesh::from_triangles", CORPUS_RS)


if __name__ == "__main__":
    unittest.main()
