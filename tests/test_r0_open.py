"""Loader and manifest checks for corpus revision r0-open (the open-writer known-truth corpus).

These read the corpus the way a downstream consumer would: json, pathlib and hashlib, no vendor
software and no DWG library. They are red until corpus/r0-open exists, and they stay in the suite as
the honesty gate afterwards: the rules in docs/adr/0008-open-writer-known-truth-corpus.md are each
checked here by name.
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "r0-open"
PARAMS = ROOT / "tools" / "authoring" / "params"
ADR = ROOT / "docs" / "adr" / "0008-open-writer-known-truth-corpus.md"
OPEN_FAMILIES = {"acadrust", "ACadSharp"}
ADR_0006_REASONS = {"UNRESOLVED_DISAGREEMENT", "UNSUPPORTED_ENTITY", "APPROXIMATION", "MALFORMED_FIXTURE",
                    "LICENCE_OR_PROVENANCE"}
FORBIDDEN_PRODUCERS = re.compile(r"cad\s*exchanger|cadex|\boda\b|open design", re.I)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest():
    p = CORPUS / "manifest.json"
    assert p.is_file(), "corpus/r0-open/manifest.json does not exist yet"
    return json.loads(p.read_text())


def quarantine():
    p = CORPUS / "quarantine.json"
    assert p.is_file(), "corpus/r0-open/quarantine.json does not exist yet"
    return json.loads(p.read_text())


def probe_ids():
    return sorted(json.loads(p.read_text())["id"] for p in PARAMS.rglob("*.json"))


def family(name_at_version):
    return name_at_version.split("@", 1)[0]


class ManifestHeader(unittest.TestCase):
    def test_revision_and_scope(self):
        m = manifest()
        self.assertEqual(m["corpus_revision"], "r0-open")
        self.assertEqual(m["oracles"], "none")
        self.assertEqual(m["evidence_scope"], "READER_MAPPING_ONLY")
        self.assertEqual(m["step_oracle"], "none")
        self.assertIn("no STEP oracle", m["evidence_statement"])

    def test_writer_is_named_with_a_version(self):
        m = manifest()
        self.assertRegex(m["writer"], r"^[A-Za-z]+@\S+$")
        self.assertIn(family(m["writer"]), OPEN_FAMILIES)

    def test_numeric_policy_is_stamped(self):
        self.assertEqual(manifest()["numeric_policy_version"], "PVec numeric policy v1")

    def test_adr_exists_and_states_the_rules(self):
        self.assertTrue(ADR.is_file(), "ADR 0008 does not exist yet")
        t = ADR.read_text()
        for needle in ("open-writer known-truth corpus", "oracles: none", "KNOWN_TRUTH_EXACT",
                       "no STEP oracle", "quarantine", "ACadSharp", "acadrust", "DUAL_ORACLE_EQUIVALENT"):
            self.assertIn(needle, t, needle)


class HonestyRules(unittest.TestCase):
    def test_no_vendor_attribution_anywhere_structured(self):
        m = manifest()
        producers = [m["writer"]] + [r["reader"] for r in m.get("cross_readers", [])]
        for f in m["fixtures"]:
            producers += [f["dwg"]["writer"], f["cross_read"]["reader"]]
        for p in producers:
            self.assertIsNone(FORBIDDEN_PRODUCERS.search(p), p)

    def test_no_step_files_and_no_dual_oracle_class(self):
        self.assertEqual(list(CORPUS.rglob("*.step")) + list(CORPUS.rglob("*.stp")), [])
        m = manifest()
        classes = {f["evidence_class"] for f in m["fixtures"]}
        self.assertLessEqual(classes, {"KNOWN_TRUTH_EXACT", "QUARANTINED"})
        self.assertNotIn("DUAL_ORACLE_EQUIVALENT", json.dumps(m["fixtures"]))

    def test_every_fixture_has_one_class_and_the_reader_mapping_scope(self):
        for f in manifest()["fixtures"]:
            self.assertEqual(f["evidence_scope"], "READER_MAPPING_ONLY", f["id"])
            self.assertIn("oracles", f)
            self.assertEqual(f["oracles"], "none", f["id"])


class Coverage(unittest.TestCase):
    def test_every_probe_is_accounted_for_exactly_once(self):
        m, q = manifest(), quarantine()
        in_corpus = [f["id"] for f in m["fixtures"]]
        excluded = [e["id"] for e in q["excluded"]]
        self.assertEqual(len(in_corpus + excluded), len(set(in_corpus + excluded)), "a probe is listed twice")
        self.assertEqual(sorted(in_corpus + excluded), probe_ids())

    def test_excluded_probes_name_a_reason_and_have_no_dwg(self):
        for e in quarantine()["excluded"]:
            self.assertIn(e["reason"], ADR_0006_REASONS, e["id"])
            self.assertTrue(e["evidence"].strip(), e["id"])
            self.assertFalse((CORPUS / "fixtures" / e["id"] / "source.dwg").exists(), e["id"])


class EveryFixture(unittest.TestCase):
    def test_artifacts_exist_and_hash(self):
        for f in manifest()["fixtures"]:
            d = CORPUS / f["dwg"]["path"]
            self.assertTrue(d.is_file(), f["id"])
            self.assertEqual(sha(d), f["dwg"]["sha256"], f["id"])
            e = ROOT / f["expected"]["path"]
            self.assertEqual(sha(e), f["expected"]["sha256"], f["id"])
            self.assertEqual(json.loads(e.read_text())["fixture_id"], f["id"])

    def test_cross_read_is_by_the_other_family(self):
        m = manifest()
        for f in m["fixtures"]:
            cr = f["cross_read"]
            self.assertNotEqual(family(cr["reader"]), family(f["dwg"]["writer"]), f["id"])
            self.assertIn(family(cr["reader"]), OPEN_FAMILIES, f["id"])
            rec = CORPUS / cr["record"]
            self.assertTrue(rec.is_file(), f["id"])
            self.assertEqual(sha(rec), cr["sha256"], f["id"])
            self.assertEqual(json.loads(rec.read_text())["dwg_sha256"], f["dwg"]["sha256"], f["id"])

    def test_accepted_means_the_cross_reader_agreed(self):
        for f in manifest()["fixtures"]:
            if f["evidence_class"] == "KNOWN_TRUTH_EXACT":
                self.assertEqual(f["cross_read"]["verdict"], "AGREE", f["id"])
                self.assertEqual(f["status"], "ACCEPTED", f["id"])
            else:
                self.assertEqual(f["status"], "QUARANTINED", f["id"])
                self.assertIn(f["quarantine"]["reason"], ADR_0006_REASONS, f["id"])

    def test_a_cross_read_disagreement_is_quarantined(self):
        for f in manifest()["fixtures"]:
            if f["cross_read"]["verdict"] != "AGREE":
                self.assertEqual(f["evidence_class"], "QUARANTINED", f["id"])
                want = {"DISAGREE": "UNRESOLVED_DISAGREEMENT", "UNREADABLE": "MALFORMED_FIXTURE"}
                self.assertEqual(f["quarantine"]["reason"], want[f["cross_read"]["verdict"]], f["id"])

    def test_checksums_verify(self):
        sums = CORPUS / "SHA256SUMS"
        self.assertTrue(sums.is_file())
        for line in sums.read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(sha(CORPUS / name), digest, name)


class VerdictsRecompute(unittest.TestCase):
    """The verdicts are not taken on trust: they are recomputed from the stored read records."""

    def test_check_passes_on_the_corpus(self):
        from runner import r0_open
        self.assertEqual(r0_open.check(CORPUS), [])

    def _record(self, fid, which="acadsharp"):
        return json.loads((CORPUS / "fixtures" / fid / ("read.%s.json" % which)).read_text())

    def _verdict(self, fid, own, cross):
        from runner import numeric, r0_open
        return r0_open.verdict(numeric.load_policy(), fid, "acadrust@x", own, cross)

    def test_the_corpus_verdicts_are_agree_on_untouched_records(self):
        v = self._verdict("bspline-d3-001", self._record("bspline-d3-001", "acadrust"), self._record("bspline-d3-001"))
        self.assertEqual(v["verdict"], "AGREE")

    def test_a_changed_control_point_in_the_cross_read_quarantines(self):
        own, cross = self._record("bspline-d3-001", "acadrust"), self._record("bspline-d3-001")
        cross["blocks"][0]["entities"][0]["control_points"][2][0] = "0x4000000000000001"
        v = self._verdict("bspline-d3-001", own, cross)
        self.assertEqual((v["verdict"], v["reason"]), ("DISAGREE", "UNRESOLVED_DISAGREEMENT"))

    def test_a_weight_renormalised_to_one_is_caught(self):
        own, cross = self._record("nonunit-weight-001", "acadrust"), self._record("nonunit-weight-001")
        cross["blocks"][0]["entities"][0]["weights"] = ["0x3ff0000000000000"] * len(cross["blocks"][0]["entities"][0]["weights"])
        self.assertEqual(self._verdict("nonunit-weight-001", own, cross)["verdict"], "DISAGREE")

    def test_a_collapsed_knot_is_caught(self):
        own, cross = self._record("repeated-knot-c0-001", "acadrust"), self._record("repeated-knot-c0-001")
        ks = cross["blocks"][0]["entities"][0]["knots"]
        ks[4] = ks[2] = ks[3] = "0x3fe0000000000001"
        self.assertEqual(self._verdict("repeated-knot-c0-001", own, cross)["verdict"], "DISAGREE")

    def test_both_readers_agreeing_with_each_other_but_not_the_truth_still_quarantines(self):
        own, cross = self._record("circle-001", "acadrust"), self._record("circle-001")
        for r in (own, cross):
            r["blocks"][0]["entities"][0]["radius"] = "0x4000000000000000"
        v = self._verdict("circle-001", own, cross)
        self.assertEqual(v["reader_vs_reader_differences"], [])
        self.assertEqual(v["verdict"], "DISAGREE")

    def test_the_two_readers_disagreeing_quarantines_even_when_each_is_near_the_truth(self):
        own, cross = self._record("arc-seam-001", "acadrust"), self._record("arc-seam-001")
        e = cross["blocks"][0]["entities"][0]
        e["end_angle"] = "0x%016x" % (int(e["end_angle"], 16) + 1)  # one ulp, inside the policy
        v = self._verdict("arc-seam-001", own, cross)
        self.assertEqual(v["verdict"], "DISAGREE")
        self.assertTrue(v["reader_vs_reader_differences"])

    def test_an_unopenable_file_is_malformed_not_accepted(self):
        v = self._verdict("line-001", self._record("line-001", "acadrust"), None)
        self.assertEqual((v["verdict"], v["reason"]), ("UNREADABLE", "MALFORMED_FIXTURE"))

    def test_a_reflection_reversed_is_caught(self):
        own, cross = self._record("reflection-001", "acadrust"), self._record("reflection-001")
        for r in (own, cross):
            ins = r["blocks"][0]["entities"][0]
            ins["scale"][0] = "0x3ff0000000000000"  # the reflection silently dropped
        self.assertEqual(self._verdict("reflection-001", own, cross)["verdict"], "DISAGREE")

    def test_the_nested_chain_order_matters(self):
        own, cross = self._record("nested-blocks-001", "acadrust"), self._record("nested-blocks-001")
        for r in (own, cross):
            names = {b["name"]: b for b in r["blocks"]}
            ms = names["*Model_Space"]["entities"][0]
            inner = [b for b in r["blocks"] if b["name"] != "*Model_Space" and b["entities"][0]["type"] == "INSERT"]
            # swap the insert parameters of the outermost level and the next one
            a, b = ms, inner[0]["entities"][0]
            for k in ("insert_point", "scale", "rotation"):
                a[k], b[k] = b[k], a[k]
        self.assertEqual(self._verdict("nested-blocks-001", own, cross)["verdict"], "DISAGREE")


class ExpectedRecordsAreUntouched(unittest.TestCase):
    def test_the_manifest_pins_every_expected_record_and_parameter_file(self):
        for f in manifest()["fixtures"]:
            self.assertEqual(sha(ROOT / f["parameter_file"]["path"]), f["parameter_file"]["sha256"], f["id"])
            rec = json.loads((ROOT / f["expected"]["path"]).read_text())
            self.assertEqual(rec["provenance"]["parameter_file_sha256"], f["parameter_file"]["sha256"], f["id"])
            self.assertNotIn("source.dwg", json.dumps(rec), f["id"])


if __name__ == "__main__":
    unittest.main()
