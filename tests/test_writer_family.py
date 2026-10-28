"""The writer families beyond acadrust: the cross-read rule for three readers, and the ACadSharp-written corpus.

Written before the code. The rule tests need runner.writer_family; the corpus tests need
corpus/writers/acadsharp, which exists only after tools/corpus/writer-acadsharp/run.sh has run.
"""
import copy
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R0 = ROOT / "corpus" / "r0-open"
FAMILY = ROOT / "corpus" / "writers" / "acadsharp"
WRITERS = ROOT / "corpus" / "writers"
PARAMS = ROOT / "tools" / "authoring" / "params"


def load(p):
    return json.loads(Path(p).read_text())


def probe_ids():
    return sorted(load(p)["id"] for p in PARAMS.rglob("*.json"))


class ThreeReaderRule(unittest.TestCase):
    """A fixture is AGREE only if all three readers match the authored truth and decode the same record."""

    @classmethod
    def setUpClass(cls):
        from runner import numeric, writer_family
        cls.wf, cls.pol = writer_family, numeric.load_policy()
        cls.good = load(R0 / "fixtures" / "line-001" / "read.acadsharp.json")
        cls.names = ("ACadSharp", "acadrust", "LibreDWG")

    def records(self):
        return {n: copy.deepcopy(self.good) for n in self.names}

    def test_three_matching_records_agree(self):
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", self.records())
        self.assertEqual(v["verdict"], "AGREE", v)

    def test_one_reader_off_by_one_bit_disagrees_and_is_named(self):
        r = self.records()
        r["LibreDWG"]["blocks"][0]["entities"][0]["end"][0] = "0x3ff0000000000001"
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "DISAGREE")
        self.assertIn("LibreDWG", v["evidence"])
        self.assertNotIn("acadrust differs", v["evidence"])

    def test_readers_that_match_each_other_but_not_the_truth_disagree(self):
        r = self.records()
        for n in r:
            r[n]["blocks"][0]["entities"][0]["end"][0] = "0x3ff0000000000001"
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "DISAGREE")
        self.assertEqual(v["reader_vs_reader_differences"], {})

    def test_a_reader_that_could_not_open_the_file_is_unreadable_and_named(self):
        r = self.records()
        r["acadrust"] = None
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "UNREADABLE")
        self.assertEqual(v["reason"], "MALFORMED_FIXTURE")
        self.assertIn("acadrust", v["evidence"])

    def test_an_unreadable_file_still_says_what_the_other_readers_saw(self):
        r = self.records()
        r["ACadSharp"] = None
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "UNREADABLE")
        self.assertIn("acadrust", v["evidence"])
        self.assertIn("all match the authored truth", v["evidence"])
        r["LibreDWG"]["blocks"][0]["entities"][0]["end"][0] = "0x3ff0000000000001"
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "UNREADABLE")
        self.assertIn("LibreDWG differs from the authored truth", v["evidence"])

    def test_reader_ids_do_not_count_as_a_difference(self):
        r = self.records()
        for n in r:
            r[n]["reader"] = n + "@1"
        v = self.wf.verdict(self.pol, "line-001", "ACadSharp@x", "ACadSharp", r)
        self.assertEqual(v["verdict"], "AGREE", v)


def manifest():
    assert (FAMILY / "manifest.json").is_file(), "corpus/writers/acadsharp/manifest.json does not exist yet"
    return load(FAMILY / "manifest.json")


class AcadsharpCorpus(unittest.TestCase):
    def test_every_probe_is_written_or_excluded_with_a_reason(self):
        m = manifest()
        q = load(FAMILY / "quarantine.json")
        got = [f["id"] for f in m["fixtures"]] + [e["id"] for e in q["excluded"]]
        self.assertEqual(sorted(got), probe_ids())
        for e in q["excluded"]:
            self.assertTrue(e["evidence"].strip(), e["id"])

    def test_the_writer_is_named_per_fixture_and_is_acadsharp(self):
        m = manifest()
        self.assertTrue(m["fixtures"])
        for f in m["fixtures"]:
            self.assertRegex(f["dwg"]["writer"], r"^ACadSharp@\S+$", f["id"])
            self.assertEqual(f["dwg"]["dwg_version"], m["dwg_version"], f["id"])

    def test_three_readers_are_recorded_per_fixture_and_the_verdict_is_theirs(self):
        for f in manifest()["fixtures"]:
            self.assertEqual(sorted(r["name"] for r in f["reads"]), ["ACadSharp", "LibreDWG", "acadrust"], f["id"])
            self.assertIn(f["cross_read"]["verdict"], ("AGREE", "DISAGREE", "UNREADABLE"), f["id"])

    def test_every_fixture_is_agree_or_quarantined_with_the_differing_fields(self):
        m = manifest()
        q = {x["id"]: x for x in load(FAMILY / "quarantine.json")["quarantined"]}
        for f in m["fixtures"]:
            if f["cross_read"]["verdict"] == "AGREE":
                self.assertEqual(f["status"], "ACCEPTED", f["id"])
                self.assertNotIn(f["id"], q)
            else:
                self.assertEqual(f["status"], "QUARANTINED", f["id"])
                self.assertTrue(q[f["id"]]["evidence"].strip(), f["id"])
                self.assertIn(q[f["id"]]["reason"], ("UNRESOLVED_DISAGREEMENT", "MALFORMED_FIXTURE"), f["id"])

    def test_determinism_was_measured_twice_and_the_header_fields_are_named(self):
        d = manifest()["determinism"]
        self.assertEqual(d["raw"]["runs"], 2)
        self.assertEqual(d["raw"]["compared"], d["raw"]["identical"] + d["raw"]["differing"])
        self.assertEqual(d["pinned_header"]["runs"], 2)
        self.assertEqual(d["pinned_header"]["differing"], 0)
        self.assertTrue(d["header_fields_that_differ"])
        for name in d["header_fields_that_differ"]:
            self.assertRegex(name, r"^[A-Za-z.]+$")

    def test_check_recomputes_every_verdict_from_the_stored_records(self):
        from runner import writer_family
        self.assertEqual(writer_family.check(FAMILY), [])


class LibredwgCorpora(unittest.TestCase):
    """The third writer family: LibreDWG's dwgwrite, as R2000 and R2004 (it refuses r2007 and does not write r2010 and later reliably)."""
    VERSIONS = {"libredwg-r2000": "AC1015", "libredwg-r2004": "AC1018"}

    def each(self):
        for name, ver in self.VERSIONS.items():
            p = WRITERS / name / "manifest.json"
            self.assertTrue(p.is_file(), "corpus/writers/%s/manifest.json does not exist yet" % name)
            yield name, ver, load(p), load(WRITERS / name / "quarantine.json")

    def test_every_probe_is_written_or_excluded_with_a_reason(self):
        for name, ver, m, q in self.each():
            got = [f["id"] for f in m["fixtures"]] + [e["id"] for e in q["excluded"]]
            self.assertEqual(sorted(got), probe_ids(), name)
            for e in q["excluded"]:
                self.assertTrue(e["evidence"].strip(), (name, e["id"]))

    def test_dwg_version_and_writer_are_recorded_per_fixture(self):
        for name, ver, m, q in self.each():
            self.assertEqual(m["dwg_version"], ver, name)
            self.assertTrue(m["fixtures"], name)
            for f in m["fixtures"]:
                self.assertEqual(f["dwg"]["dwg_version"], ver, (name, f["id"]))
                self.assertRegex(f["dwg"]["writer"], r"^LibreDWG@\S+$", (name, f["id"]))

    def test_three_readers_per_fixture_and_a_verdict_or_a_quarantine_with_the_fields(self):
        for name, ver, m, q in self.each():
            qd = {x["id"]: x for x in q["quarantined"]}
            for f in m["fixtures"]:
                self.assertEqual(sorted(r["name"] for r in f["reads"]), ["ACadSharp", "LibreDWG", "acadrust"], (name, f["id"]))
                if f["cross_read"]["verdict"] == "AGREE":
                    self.assertEqual(f["status"], "ACCEPTED")
                else:
                    self.assertEqual(f["status"], "QUARANTINED")
                    self.assertTrue(qd[f["id"]]["evidence"].strip(), (name, f["id"]))

    def test_determinism_was_measured_twice(self):
        for name, ver, m, q in self.each():
            d = m["determinism"]
            self.assertEqual(d["runs"], 2, name)
            self.assertEqual(d["compared"], d["identical"] + d["differing"], name)
            self.assertGreater(d["compared"], 0, name)

    def test_check_recomputes_every_verdict(self):
        from runner import writer_family
        for name, ver, m, q in self.each():
            self.assertEqual(writer_family.check(WRITERS / name), [], name)

    def test_the_doc_states_which_versions_the_tool_refuses(self):
        t = (WRITERS / "README.md").read_text()
        self.assertIn("r2007", t)
        self.assertRegex(t, r"r2010")
        self.assertIn("dwgwrite", t)
        self.assertIn("dwg_version", t)


if __name__ == "__main__":
    unittest.main()
