"""Corpus revision r1-open: edge, mixed-entity, degenerate, negative and real-world fixtures, the
capability matrix, the manifest and the release.

These are written before the code and the fixtures they check (issues #11 and #18), so they start red.
Each acceptance criterion of the two issues is one or more tests here, named for it. The whole-tree tests
read the committed files with json, pathlib and hashlib; the unit tests plant a defect in a temporary
tree and check that it is caught.
"""
import ast
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "fixtures"
NEG = FX / "negative"
KT = FX / "known-truth"
RW = FX / "real-world"
CORPUS = ROOT / "corpus"
REV = CORPUS / "r1-open"
OUTCOMES = {"UNSUPPORTED", "IGNORED", "MISSING"}


def load(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dirs(base):
    return sorted(p for p in Path(base).iterdir() if p.is_dir()) if Path(base).is_dir() else []


def corpus():
    from runner import corpus as c
    return c


def release():
    from runner import corpus_release as r
    return r


# ---- #18: the negative suite ---------------------------------------------------------------------

class NegativeSuite(unittest.TestCase):
    REQUIRED = {"HATCH", "DIMENSION", "TEXT", "MTEXT", "3DSOLID", "MESH", "REGION", "ACAD_PROXY_ENTITY",
                "OLE2FRAME", "XREF", "WIPEOUT", "ACAD_TABLE", "IMAGE"}

    def records(self):
        return {d.name: load(d / "expected.classification.json") for d in dirs(NEG)}

    def test_every_entity_class_has_a_fixture_with_an_outcome_and_a_reason(self):
        recs = self.records()
        seen = {e["dwg_type"] for r in recs.values() for e in r["entities"]}
        self.assertEqual(self.REQUIRED - seen, set())
        for fid, r in recs.items():
            self.assertIn(r["outcome"], OUTCOMES, fid)
            self.assertTrue(r["reason"].strip(), fid)
            for e in r["entities"]:
                self.assertIn(e["outcome"], OUTCOMES, fid)
                self.assertTrue(e["reason"].strip(), fid)

    def test_gradient_and_plain_hatch_are_separate_fixtures(self):
        hatches = [r for r in self.records().values() if any(e["dwg_type"] == "HATCH" for e in r["entities"])]
        self.assertEqual(sorted(bool(e.get("gradient")) for r in hatches for e in r["entities"]), [False, True])

    def test_missing_unsupported_and_ignored_are_each_exercised_and_kept_distinct(self):
        outcomes = {r["outcome"] for r in self.records().values()}
        self.assertEqual(outcomes, OUTCOMES)
        for r in self.records().values():
            self.assertEqual(r["converter_emits_nothing"], r["outcome"] == "MISSING")

    def test_no_negative_fixture_is_known_truth_or_carries_expected_math(self):
        for d in dirs(NEG):
            self.assertFalse((d / "expected.math.json").exists(), d.name)
            r = load(d / "expected.classification.json")
            self.assertNotEqual(r["evidence_class"], "KNOWN_TRUTH_EXACT", d.name)
            self.assertEqual(r["evidence_class"], "QUARANTINED", d.name)

    def test_every_negative_fixture_has_its_full_artifact_set(self):
        for d in dirs(NEG):
            for name in ("source.dwg", "expected.classification.json", "README.md", "census.acadsharp.json", "comparison.json"):
                self.assertTrue((d / name).is_file(), "%s/%s" % (d.name, name))

    def test_the_produced_classification_matches_and_no_geometry_is_accepted(self):
        for d in dirs(NEG):
            cmp_ = load(d / "comparison.json")
            self.assertEqual(cmp_["verdict"], "MATCH", d.name)
            self.assertEqual(cmp_["produced"]["accepted_geometry"], [], d.name)
            self.assertEqual(corpus().negative_problems(d), [], d.name)

    def test_a_negative_fixture_that_yields_accepted_geometry_fails_the_run(self):
        c = corpus()
        expected = {"entities": [{"dwg_type": "HATCH", "count": 1, "outcome": "IGNORED", "reason": "x"}], "converter_emits_nothing": False}
        census = {"summary": {"entity_count": 2}, "blocks": [{"name": "*Model_Space", "entities": [{"type": "Hatch"}, {"type": "Line"}]}]}
        produced = c.produced_classification(census, expected)
        self.assertEqual(produced["accepted_geometry"], ["Line"])
        self.assertTrue(c.classification_problems(expected, produced))

    def test_a_different_classification_fails_the_run(self):
        c = corpus()
        expected = {"entities": [{"dwg_type": "HATCH", "count": 1, "outcome": "UNSUPPORTED", "reason": "x"}], "converter_emits_nothing": False}
        census = {"summary": {"entity_count": 1}, "blocks": [{"name": "*Model_Space", "entities": [{"type": "Hatch"}]}]}
        produced = c.produced_classification(census, expected)
        self.assertEqual(produced["entities"][0]["outcome"], "IGNORED")
        self.assertTrue(c.classification_problems(expected, produced))

    def test_an_entity_the_reader_does_not_return_is_missing_not_unsupported(self):
        c = corpus()
        expected = {"entities": [{"dwg_type": "ACAD_PROXY_ENTITY", "count": 1, "outcome": "MISSING", "reason": "x"}], "converter_emits_nothing": True}
        census = {"summary": {"entity_count": 0}, "blocks": [{"name": "*Model_Space", "entities": []}]}
        produced = c.produced_classification(census, expected)
        self.assertEqual(produced["entities"][0]["outcome"], "MISSING")
        self.assertTrue(produced["converter_emits_nothing"])
        self.assertEqual(c.classification_problems(expected, produced), [])

    def test_a_reader_failure_is_a_failure_not_a_classification(self):
        c = corpus()
        produced = c.produced_classification({"read_error": "boom"}, {"entities": [], "converter_emits_nothing": True})
        self.assertTrue(c.classification_problems({"entities": [], "converter_emits_nothing": True}, produced))

    def test_negative_ids_are_disjoint_from_known_truth_and_real_world(self):
        self.assertEqual(corpus().mutual_exclusion_problems(ROOT), [])

    def test_mutual_exclusion_catches_a_promoted_fixture_left_in_the_negative_suite(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "fixtures/negative/hatch-001").mkdir(parents=True)
            (t / "fixtures/edge/hatch-001").mkdir(parents=True)
            (t / "fixtures/edge/hatch-001/expected.math.json").write_text("{}")
            problems = corpus().mutual_exclusion_problems(t)
            self.assertTrue(any("hatch-001" in p for p in problems), problems)


# ---- #11: degenerate, edge and mixed -----------------------------------------------------------------

class Degenerate(unittest.TestCase):
    EXPECT = {"zero-length-segment-001": "DEGENERATE_ZERO_LENGTH_SEGMENT", "zero-radius-001": "DEGENERATE_ZERO_RADIUS",
              "coincident-control-points-001": "DEGENERATE_COINCIDENT_CONTROL_POINTS"}

    def test_each_degenerate_fixture_carries_an_expected_rejection(self):
        for fid, code in self.EXPECT.items():
            d = FX / "degenerate" / fid
            r = load(d / "expected.rejection.json")
            self.assertEqual(r["expected_rejection"]["classification"], code)
            self.assertEqual(r["expected_rejection"]["disposition"], "REJECT")
            self.assertIs(r["expected_rejection"]["geometry_emitted"], False)
            self.assertFalse((d / "expected.math.json").exists())
            self.assertEqual(r["evidence_class"], "QUARANTINED")

    def test_both_readers_return_the_degenerate_entity_and_the_refusal_matches(self):
        for fid, code in self.EXPECT.items():
            cmp_ = load(FX / "degenerate" / fid / "comparison.json")
            self.assertEqual(cmp_["verdict"], "AGREE", fid)
            self.assertEqual(cmp_["produced_rejection"], {"acadrust": code, "acadsharp": code}, fid)

    def test_the_refusal_rule_fires_on_each_degeneracy_and_not_on_a_valid_entity(self):
        c = corpus()
        h = lambda x: "0x%016x" % __import__("struct").unpack(">Q", __import__("struct").pack(">d", x))[0]
        p0, p1 = [h(1.0), h(2.0), h(0.0)], [h(1.0), h(2.5), h(0.0)]
        self.assertEqual(c.degenerate_reason({"type": "LINE", "start": p0, "end": p0}), "DEGENERATE_ZERO_LENGTH_SEGMENT")
        self.assertIsNone(c.degenerate_reason({"type": "LINE", "start": p0, "end": p1}))
        self.assertEqual(c.degenerate_reason({"type": "CIRCLE", "radius": h(0.0)}), "DEGENERATE_ZERO_RADIUS")
        self.assertIsNone(c.degenerate_reason({"type": "CIRCLE", "radius": h(2.0)}))
        self.assertEqual(c.degenerate_reason({"type": "SPLINE", "control_points": [p0, p0, p0]}), "DEGENERATE_COINCIDENT_CONTROL_POINTS")
        self.assertIsNone(c.degenerate_reason({"type": "SPLINE", "control_points": [p0, p1, p0]}))

    def test_the_refusal_follows_the_numeric_policy_not_exact_zero(self):
        c = corpus()
        import struct
        h = lambda x: "0x%016x" % struct.unpack(">Q", struct.pack(">d", x))[0]
        # a reader that clamps a zero radius up to 1e-12 is still refused (NP-06); a 5e-9 segment is valid
        self.assertEqual(c.degenerate_reason({"type": "CIRCLE", "radius": h(float("1e-12"))}), "DEGENERATE_ZERO_RADIUS")
        tiny = {"type": "LINE", "start": [h(0.0)] * 3, "end": [h(float("3e-9")), h(float("4e-9")), h(0.0)]}
        self.assertIsNone(c.degenerate_reason(tiny))

    def test_a_pipeline_that_produces_geometry_for_a_degenerate_fixture_is_a_failure(self):
        c = corpus()
        want = {"expected_rejection": {"classification": "DEGENERATE_ZERO_RADIUS", "disposition": "REJECT", "geometry_emitted": False}}
        self.assertTrue(c.rejection_problems(want, produced=None))
        self.assertTrue(c.rejection_problems(want, produced="DEGENERATE_ZERO_LENGTH_SEGMENT"))
        self.assertEqual(c.rejection_problems(want, produced="DEGENERATE_ZERO_RADIUS"), [])


class EdgeAndMixed(unittest.TestCase):
    def test_edge_cases_cover_boundary_and_extreme_scale(self):
        ids = {d.name for d in dirs(FX / "edge")}
        self.assertTrue({"bspline-nonunit-domain-001", "arc-tiny-sweep-001", "huge-extent-001", "tiny-extent-001"} <= ids, ids)
        huge = load(FX / "edge/huge-extent-001/expected.math.json")["entities"][0]["geometry"]
        self.assertGreater(float(huge["radius"]["decimal"]), 1e6)
        tiny = load(FX / "edge/tiny-extent-001/expected.math.json")["entities"][0]["geometry"]
        self.assertLess(abs(float(tiny["end"][0]["decimal"])), float("1e-8"))

    def test_mixed_drawing_has_five_classes_transforms_and_nested_blocks(self):
        doc = load(FX / "mixed/mixed-entity-001/expected.math.json")
        classes = {e["class"] for e in doc["entities"]}
        self.assertGreaterEqual(len(classes), 5, classes)
        self.assertTrue(any("transform_chain" in e and len(e["transform_chain"]["transforms"]) >= 3 for e in doc["entities"]))
        self.assertTrue(any("transform" in e for e in doc["entities"]))

    def test_edge_and_mixed_fixtures_are_complete_and_both_readers_agree_with_the_record(self):
        found = dirs(FX / "edge") + dirs(FX / "mixed")
        self.assertGreaterEqual(len(found), 5)
        for d in found:
            for name in ("expected.math.json", "README.md", "params.json", "source.dwg", "read.acadrust.json", "read.acadsharp.json", "comparison.json"):
                self.assertTrue((d / name).is_file(), "%s/%s" % (d.name, name))
            self.assertEqual(load(d / "comparison.json")["verdict"], "AGREE", d.name)

    def test_every_record_regenerates_from_its_parameter_file(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools" / "authoring"))
        import author_corpus as ac
        for rel, files in ac.all_fixtures():
            for name, text in files.items():
                self.assertEqual((FX / rel / name).read_text(), text, "%s/%s" % (rel, name))


# ---- #11: real-world corpus, provenance and licensing ----------------------------------------------------

class RealWorld(unittest.TestCase):
    FIELDS = ("origin", "rights_holder", "licence", "licence_basis", "acquisition_date", "redistribution_verdict")

    def test_every_real_world_fixture_has_a_provenance_record_with_a_licence_and_a_verdict(self):
        prov = load(CORPUS / "provenance.json")["fixtures"]
        ids = {d.name for d in dirs(RW)}
        self.assertGreaterEqual(len(ids), 3)
        self.assertEqual(ids, set(prov))
        for fid, rec in prov.items():
            for f in self.FIELDS:
                self.assertTrue(str(rec.get(f, "")).strip(), "%s.%s" % (fid, f))
            self.assertIn(rec["redistribution_verdict"], ("PUBLIC_REDISTRIBUTABLE", "PRIVATE"), fid)

    def test_metrics_are_recorded_per_fixture(self):
        for d in dirs(RW):
            m = load(d / "metrics.json")
            for f in ("entity_count", "class_histogram", "max_block_depth", "spline_count", "max_abs_coordinate", "dwg_version", "discipline"):
                self.assertIn(f, m, "%s.%s" % (d.name, f))
            self.assertGreater(m["entity_count"], 0, d.name)

    def test_generation_refuses_a_fixture_with_no_redistribution_verdict(self):
        c = corpus()
        with self.assertRaises(c.ProvenanceError):
            c.require_verdict("x-001", {"x-001": {"origin": "o", "rights_holder": "r", "licence": "MIT"}})
        with self.assertRaises(c.ProvenanceError):
            c.require_verdict("missing-001", {})
        with self.assertRaises(c.ProvenanceError):
            c.require_verdict("x-001", {"x-001": {"redistribution_verdict": "MAYBE"}})
        self.assertEqual(c.require_verdict("x-001", {"x-001": {"redistribution_verdict": "PRIVATE"}}), "PRIVATE")

    def test_no_private_dwg_bytes_are_in_the_repository(self):
        c = corpus()
        self.assertEqual(c.private_path_problems(ROOT), [])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "fixtures/real-world/p-001").mkdir(parents=True)
            (t / "fixtures/real-world/p-001/source.dwg").write_bytes(b"AC1032")
            (t / "corpus").mkdir()
            (t / "corpus/provenance.json").write_text(json.dumps({"fixtures": {"p-001": {"redistribution_verdict": "PRIVATE"}}}))
            self.assertTrue(c.private_path_problems(t))

    def test_real_world_is_never_known_truth_and_the_classifier_rejects_it_without_a_record(self):
        c = corpus()
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.assertTrue(c.classify_problems(d, "KNOWN_TRUTH_EXACT"))
            self.assertEqual(c.classify_problems(d, "REAL_WORLD_DIFFERENTIAL"), [])
            self.assertEqual(c.classify_problems(d, "QUARANTINED"), [])
            (d / "expected.math.json").write_text("{}")
            self.assertEqual(c.classify_problems(d, "KNOWN_TRUTH_EXACT"), [])
        for d in dirs(RW):
            self.assertIn(load(d / "comparison.json")["evidence_class"], ("REAL_WORLD_DIFFERENTIAL", "QUARANTINED"), d.name)
            self.assertFalse((d / "expected.math.json").exists(), d.name)

    def test_converter_agreement_is_recorded_as_dual_oracle_and_never_as_source_truth(self):
        rec = corpus().agreement_record("acadsharp-dwg2step", "libredwg-dwg2step")
        self.assertEqual(rec["evidence_class"], "DUAL_ORACLE_EQUIVALENT")
        self.assertIs(rec["is_source_truth"], False)
        self.assertEqual(rec["oracle_scope"], "OPEN_CONVERTERS")


# ---- #11: capability matrix -------------------------------------------------------------------------------

class CapabilityMatrix(unittest.TestCase):
    ROWS = {"point", "direction", "axis_placement_2d", "line", "polyline", "circle", "ellipse", "trimmed_curve", "composite_curve",
            "bezier", "bspline", "nurbs", "affine_transform"}

    def matrix(self):
        return load(CORPUS / "capability-matrix.json")

    def test_one_row_per_profile_capability_with_no_empty_row(self):
        m = self.matrix()
        self.assertEqual({r["capability"] for r in m["rows"]}, self.ROWS)
        for r in m["rows"]:
            self.assertTrue(r["fixtures"] or r.get("blocked"), r["capability"])
            for f in r["fixtures"]:
                self.assertIn(f["evidence_class"], ("KNOWN_TRUTH_EXACT", "QUARANTINED"), r["capability"])

    def test_the_matrix_pins_the_profile_version_and_the_numeric_policy_version(self):
        m = self.matrix()
        self.assertRegex(m["profile"]["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(m["profile"]["document_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(m["numeric_policy_version"], "PVec numeric policy v1")

    def test_known_truth_exact_needs_an_authored_record_and_the_matrix_checks_it(self):
        self.assertEqual(corpus().matrix_problems(self.matrix(), ROOT), [])
        bad = {"rows": [{"capability": "line", "fixtures": [{"id": "negative-hatch-001", "evidence_class": "KNOWN_TRUTH_EXACT"}]}]}
        self.assertTrue(corpus().matrix_problems(bad, ROOT))
        self.assertTrue(corpus().matrix_problems({"rows": [{"capability": "line", "fixtures": []}]}, ROOT))


# ---- #18: the manifest, the quarantine list and the release -----------------------------------------------------

class Manifest(unittest.TestCase):
    def manifest(self):
        return load(REV / "manifest.json")

    def test_every_accepted_fixture_has_hashes_and_exactly_one_class(self):
        m = self.manifest()
        for f in m["fixtures"]:
            self.assertIn(f["evidence_class"], ("KNOWN_TRUTH_EXACT", "DUAL_ORACLE_EQUIVALENT", "REAL_WORLD_DIFFERENTIAL", "QUARANTINED"), f["id"])
            for name, a in f["artifacts"].items():
                self.assertEqual(sha(ROOT / a["path"]), a["sha256"], "%s %s" % (f["id"], name))
            if f["evidence_class"] == "KNOWN_TRUTH_EXACT":
                self.assertIn("expected.math.json", f["artifacts"], f["id"])

    def test_the_manifest_records_versions_digests_and_the_covered_groups(self):
        m = self.manifest()
        for k in ("corpus_revision", "numeric_policy_version", "signature_schema_version", "evaluator", "converters", "container_images",
                  "oracle_scope", "dwg_version", "includes"):
            self.assertIn(k, m)
        self.assertEqual(m["corpus_revision"], "r1-open")
        self.assertEqual(m["oracle_scope"], "NONE")
        self.assertEqual(m["signature_schema_version"], "pvec-gold/signature/1")
        for img in m["container_images"].values():
            self.assertRegex(img, r"sha256:[0-9a-f]{64}")
        groups = {f["group"] for f in m["fixtures"]}
        self.assertTrue({"edge", "mixed", "degenerate", "negative", "real-world", "curves"} <= groups, groups)

    def test_an_incomplete_artifact_set_cannot_be_accepted(self):
        c = corpus()
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            d = t / "fixtures/edge/e-001"
            d.mkdir(parents=True)
            (d / "expected.math.json").write_text("{}")
            problems = c.fixture_artifact_problems(t, "edge", "e-001", "ACCEPTED")
            self.assertTrue(any("source.dwg" in p for p in problems), problems)
            self.assertEqual(c.fixture_artifact_problems(t, "edge", "e-001", "QUARANTINED") != [], True)

    def test_sha256sums_verifies_and_the_quarantine_list_is_complete(self):
        for line in (REV / "SHA256SUMS").read_text().splitlines():
            h, name = line.split("  ", 1)
            self.assertEqual(sha(REV / name), h, name)
        q = load(REV / "quarantine.json")
        listed = {x["id"] for x in q["quarantined"]}
        want = {f["id"] for f in self.manifest()["fixtures"] if f["evidence_class"] == "QUARANTINED" and f["id"].split("-")[0] != ""}
        self.assertEqual(listed, {i for i in want})
        for x in q["quarantined"]:
            self.assertTrue(x["reason"] and x["evidence"], x["id"])

    def test_the_whole_tree_check_is_clean(self):
        self.assertEqual(corpus().check(ROOT), [])


class Release(unittest.TestCase):
    def build(self, t):
        out = Path(t) / "release"
        release().build_release(ROOT, out)
        return out

    def test_the_release_verifies_with_nothing_but_the_standard_library(self):
        src = (ROOT / "runner" / "corpus_release.py").read_text()
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                self.assertEqual(n.level, 0, "no relative imports")
                mods.add((n.module or "").split(".")[0])
        self.assertTrue(mods <= {"hashlib", "json", "re", "sys", "pathlib", "shutil", "os"}, mods)
        with tempfile.TemporaryDirectory() as t:
            out = self.build(t)
            self.assertEqual(release().verify_release(out), [])
            self.assertTrue((out / "SHA256SUMS").is_file())
            self.assertTrue((out / "verify_release.py").is_file())

    def test_the_release_carries_public_files_only_and_the_named_checks_exist(self):
        r = release()
        self.assertEqual(set(r.RELEASE_CHECKS), {"SHA256SUMS_VERIFY", "NO_PRIVATE_DWG", "NO_VENDOR_BINARY", "NO_LICENCE_MATERIAL", "SELF_CONTAINED_MANIFEST"})

    def test_each_named_check_fires_on_a_planted_defect(self):
        r = release()
        with tempfile.TemporaryDirectory() as t:
            out = self.build(t)

            def planted(name, data, expect):
                f = out / name
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(data)
                problems = r.verify_release(out)
                f.unlink()
                self.assertTrue(any(expect in p for p in problems), (expect, problems))

            planted("fixtures/real-world/p-001/source.dwg", b"AC1032private", "NO_PRIVATE_DWG")
            planted("bin/tool", b"\x7fELF\x02\x01\x01", "NO_VENDOR_BINARY")
            planted("notes.txt", b"licence_key = ABCDEF0123456789ABCDEF\n", "NO_LICENCE_MATERIAL")
            planted("extra.txt", b"x", "SHA256SUMS_VERIFY")

    def test_a_private_fixture_appears_as_id_and_hash_only(self):
        r = release()
        entry = {"id": "p-001", "group": "real-world", "evidence_class": "REAL_WORLD_DIFFERENTIAL", "status": "ACCEPTED",
                 "licence_verdict": "PRIVATE", "artifacts": {"source.dwg": {"path": "fixtures/real-world/p-001/source.dwg", "sha256": "0" * 64}}}
        shown = r.public_entry(entry)
        self.assertEqual(shown["artifacts"], {})
        self.assertEqual(shown["private_hashes"], {"source.dwg": "0" * 64})


if __name__ == "__main__":
    unittest.main()
