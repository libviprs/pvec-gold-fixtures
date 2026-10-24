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
        self.assertEqual(manifest()["numeric_policy"]["policy_version"], "PVec numeric policy v1")

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
                self.assertEqual(f["quarantine"]["reason"], "UNRESOLVED_DISAGREEMENT", f["id"])

    def test_checksums_verify(self):
        sums = CORPUS / "SHA256SUMS"
        self.assertTrue(sums.is_file())
        for line in sums.read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(sha(CORPUS / name), digest, name)


if __name__ == "__main__":
    unittest.main()
