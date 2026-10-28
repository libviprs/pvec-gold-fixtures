"""#70: a DWG for singular-001, the probe no acadrust or ACadSharp writer would store.

A DWG holds an INSERT scale as a plain double, so a file can say 0.0. The writers refuse it (acadrust's setters rewrite
it to 1e-12, ACadSharp throws), so the file is written by acadrust at the commit that has Insert::set_scale_unchecked
(libviprs/acadrust#52, tools/corpus/singular), and the readers had to be told to report what the file says: acadrust
from the same commit, ACadSharp from tools/converters/acadsharp/patches/0001-insert-keep-zero-scale.patch.

What these tests hold the fixture to: three readers return the 0.0 scale bit for bit, they decode the same record, and
both converters refuse the drawing with exit 15 and write no STEP.
"""
import hashlib
import json
import unittest
from pathlib import Path

from runner import expected_math as em

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "fixtures" / "edge" / "singular-001"
R0 = ROOT / "corpus" / "r0-open" / "fixtures" / "near-singular-001"
PATCH = ROOT / "tools" / "converters" / "acadsharp" / "patches" / "0001-insert-keep-zero-scale.patch"
ONE, ZERO = "0x3ff0000000000000", "0x0000000000000000"


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inserts(rec):
    return [e for b in rec["blocks"] for e in b["entities"] if e["type"] == "INSERT"]


class Drawing(unittest.TestCase):
    def test_the_fixture_has_every_file(self):
        for n in ("source.dwg", "README.md", "params.json", "expected.math.json", "read.acadrust.json", "read.acadsharp.json",
                  "read.libredwg.json", "comparison.json", "writer.json", "acadsharp-dwg2step.status.json",
                  "libredwg-dwg2step.status.json", "open-route.json"):
            self.assertTrue((FX / n).is_file(), n)

    def test_it_is_a_dwg_with_an_instance_chain_and_the_authored_record(self):
        self.assertEqual((FX / "source.dwg").read_bytes()[:6], b"AC1032")
        self.assertEqual(em.validate_file(FX / "expected.math.json"), [])
        ent = em.load(FX / "expected.math.json")["entities"][0]
        self.assertEqual(ent["rejection"], {"classification": "SINGULAR_TRANSFORM", "disposition": "REJECT"})
        self.assertEqual((FX / "params.json").read_bytes(), (ROOT / "tools/authoring/params/transforms/singular-001.json").read_bytes())

    def test_three_readers_return_the_zero_scale_bit_for_bit(self):
        for name in ("acadrust", "acadsharp", "libredwg"):
            rec = load(FX / ("read.%s.json" % name))
            ins = inserts(rec)
            self.assertEqual(len(ins), 1, name)
            self.assertEqual(ins[0]["scale"], [ONE, ZERO, ONE], name)

    def test_the_three_readers_are_three_lineages_and_acadrust_is_the_fork_with_the_fix(self):
        got = {n: load(FX / ("read.%s.json" % n))["reader"] for n in ("acadrust", "acadsharp", "libredwg")}
        self.assertTrue(got["acadrust"].startswith("acadrust@0.5.5+"), got)
        self.assertNotEqual(got["acadrust"], "acadrust@0.5.5+d35691f", "d35691f rewrites a zero scale to 1e-12")
        self.assertTrue(got["acadsharp"].startswith("ACadSharp@3.7.1+d7dc111"), got)
        self.assertIn("insert-keep-zero-scale", got["acadsharp"])
        self.assertTrue(got["libredwg"].startswith("LibreDWG@"), got)

    def test_every_reader_record_is_for_this_dwg(self):
        want = sha(FX / "source.dwg")
        for name in ("acadrust", "acadsharp", "libredwg"):
            self.assertEqual(load(FX / ("read.%s.json" % name))["dwg_sha256"], want, name)

    def test_the_comparison_is_a_three_reader_agreement_with_the_scale_compared_exactly(self):
        c = load(FX / "comparison.json")
        self.assertEqual(c["verdict"], "AGREE")
        self.assertEqual(sorted(c["checks"]), ["acadrust", "acadsharp", "libredwg"])
        for name, items in c["checks"].items():
            self.assertTrue(all(i["ok"] for i in items), name)
            scale = [i for i in items if "scale" in i["field"]]
            self.assertTrue(scale, name)
            self.assertTrue(all(i["mode"] == "EXACT" for i in scale), (name, scale))

    def test_the_verdict_is_what_the_stored_records_give(self):
        from runner import numeric, writer_family as wf
        recs = {n: load(FX / ("read.%s.json" % n)) for n in ("acadrust", "acadsharp", "libredwg")}
        v = wf.verdict(numeric.load_policy(), "singular-001", "LibreDWG", "acadsharp", recs)
        self.assertEqual(v["verdict"], "AGREE", v["evidence"])
        self.assertEqual(load(FX / "comparison.json"), json.loads(json.dumps(wf.comparison_doc(numeric.load_policy(), "singular-001", v))))


class Provenance(unittest.TestCase):
    def test_the_writer_record_names_the_tool_the_script_and_the_dwg(self):
        w = load(FX / "writer.json")
        self.assertEqual(w["dwg"]["sha256"], sha(FX / "source.dwg"))
        self.assertEqual(w["dwg"]["version"], "AC1032")
        self.assertEqual(w["script"], "tools/corpus/singular/run.sh")
        self.assertTrue((ROOT / w["script"]).is_file())
        self.assertIn("set_scale_unchecked", w["tool"])
        self.assertIn("byte-identical", w["deterministic"])
        self.assertIn("LibreDWG", w["readers"]["libredwg"]["reader"])

    def test_the_acadrust_pin_is_a_full_commit_that_is_not_the_one_that_clamps(self):
        w = load(FX / "writer.json")
        self.assertRegex(w["commit"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(w["commit"], "d35691f483534e4affc3a4065486e168c898ac7d")
        self.assertIn(w["commit"][:7], load(FX / "read.acadrust.json")["reader"])
        self.assertEqual(w["writer"], load(FX / "read.acadrust.json")["reader"])
        self.assertIn(w["commit"], (ROOT / "tools/corpus/singular/tool/Cargo.toml").read_text())

    def test_the_tool_changes_nothing_in_r0_open_main_but_the_ids_and_the_scale_setter(self):
        b = (ROOT / "tools/corpus/singular/tool/build.rs").read_text()
        self.assertIn("set_scale_unchecked", b)
        self.assertIn("insert_for's scale setters moved", b)
        self.assertEqual((ROOT / "tools/r0-open/rust/Cargo.toml").read_text().count("d35691f483534e4affc3a4065486e168c898ac7d"), 1)

    def test_the_acadsharp_patch_removes_only_the_three_zero_guards(self):
        text = PATCH.read_text()
        self.assertEqual(text.count("diff --git"), 1)
        self.assertIn("src/ACadSharp/Entities/Insert.cs", text)
        removed = [l for l in text.splitlines() if l.startswith("-") and not l.startswith("---")]
        self.assertEqual(len(removed), 15)
        self.assertEqual([l for l in text.splitlines() if l.startswith("+") and not l.startswith("+++")], [])
        self.assertTrue(all("none zero" in l or "Equals(0)" in l or l.strip("-\t ") in ("{", "}", "") or "nameof" in l for l in removed))

    def test_the_converter_image_applies_the_patch_after_the_pin_check(self):
        df = (ROOT / "tools/converters/acadsharp/Dockerfile").read_text()
        self.assertIn("patches/0001-insert-keep-zero-scale.patch", df)
        self.assertLess(df.index("rev-parse HEAD"), df.index("git -C /opt/acadsharp apply"))
        self.assertLess(df.index("git -C /opt/acadsharp apply"), df.index("dotnet publish"))


class Converters(unittest.TestCase):
    def test_acadsharp_refuses_it_as_singular_with_exit_15_and_writes_no_step(self):
        s = load(FX / "acadsharp-dwg2step.status.json")
        self.assertEqual(s["exit_code"], 15)
        self.assertEqual(s["error"]["class"], "CONVERSION_FAILED")
        self.assertIn("SINGULAR_TRANSFORM", s["error"]["message"])
        self.assertNotIn("NEAR_SINGULAR", s["error"]["message"])
        self.assertFalse((FX / "acadsharp-dwg2step.step").exists())
        self.assertEqual(s["input"]["sha256"], sha(FX / "source.dwg"))

    def test_libredwg_refuses_it_with_exit_15_and_writes_no_step(self):
        s = load(FX / "libredwg-dwg2step.status.json")
        self.assertEqual(s["exit_code"], 15)
        self.assertEqual(s["error"]["class"], "CONVERSION_FAILED")
        self.assertFalse((FX / "libredwg-dwg2step.step").exists())
        self.assertEqual(s["input"]["sha256"], sha(FX / "source.dwg"))

    def test_the_open_route_record_says_the_rejection_was_honoured(self):
        r = load(FX / "open-route.json")
        self.assertEqual(r["exit_code"], 15)
        self.assertFalse(r["step_emitted"])
        self.assertEqual(r["curves_evaluated"], 0)

    def test_the_flattener_names_an_exactly_zero_determinant_singular(self):
        src = (ROOT / "tools/converters/acadsharp/Flatten.cs").read_text()
        self.assertIn('"SINGULAR_TRANSFORM: ', src)


class Corpus(unittest.TestCase):
    def test_r1_open_lists_it_as_an_accepted_edge_fixture_and_not_as_excluded(self):
        m = load(ROOT / "corpus/r1-open/manifest.json")
        f = [x for x in m["fixtures"] if x["id"] == "singular-001"]
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["group"], f[0]["status"], f[0]["evidence_class"]), ("edge", "ACCEPTED", "KNOWN_TRUTH_EXACT"))
        self.assertEqual(f[0]["dwg_version"], "AC1032")
        self.assertEqual(f[0]["dwg_writer"], load(FX / "writer.json")["writer"])
        q = load(ROOT / "corpus/r1-open/quarantine.json")
        self.assertNotIn("singular-001", [e["id"] for e in q["excluded"]])

    def test_r1_open_no_longer_says_the_chain_was_not_attempted_for_the_other_two(self):
        q = load(ROOT / "corpus/r1-open/quarantine.json")
        for e in q["excluded"]:
            if e["id"] in ("shear-001", "general-affine-001"):
                self.assertEqual(e["reason"], "PROFILE_ONLY", e["id"])
                self.assertNotIn("was not attempted", e["evidence"], e["id"])
                self.assertIn("-chain-001", e["evidence"], e["id"])

    def test_r0_open_is_untouched(self):
        q = load(ROOT / "corpus/r0-open/quarantine.json")
        self.assertIn("singular-001", [e["id"] for e in q["excluded"]])
        self.assertFalse((R0.parent / "singular-001").exists())

    def test_the_corpus_check_runs_the_three_reader_recomputation(self):
        from runner import singular_probe
        self.assertEqual(singular_probe.check(ROOT), [])

    def test_the_capability_matrix_lists_it_under_affine_transform(self):
        mat = load(ROOT / "corpus/capability-matrix.json")
        row = [r for r in mat["rows"] if r["capability"] == "affine_transform"][0]
        self.assertIn("singular-001", [f["id"] for f in row["fixtures"]] + [r["id"] for r in row["refusals"]])


if __name__ == "__main__":
    unittest.main()
