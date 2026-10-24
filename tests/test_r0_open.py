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
            e = CORPUS / f["expected"]["path"]
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

    def test_a_flipped_bulge_sign_is_caught(self):
        own, cross = self._record("bulge-arc-neg-001", "acadrust"), self._record("bulge-arc-neg-001")
        for r in (own, cross):
            v = r["blocks"][0]["entities"][0]["vertices"][0]
            v[2] = "0x3fd3333333333333"  # +0.3
        self.assertEqual(self._verdict("bulge-arc-neg-001", own, cross)["verdict"], "DISAGREE")

    def test_a_dropped_closed_flag_is_caught(self):
        own, cross = self._record("lwpolyline-closed-001", "acadrust"), self._record("lwpolyline-closed-001")
        for r in (own, cross):
            r["blocks"][0]["entities"][0]["closed"] = False
        self.assertEqual(self._verdict("lwpolyline-closed-001", own, cross)["verdict"], "DISAGREE")

    def test_a_layer_that_loses_its_frozen_state_is_caught(self):
        own, cross = self._record("layer-state-001", "acadrust"), self._record("layer-state-001")
        for r in (own, cross):
            for l in r["layers"]:
                l["frozen"] = False
        self.assertEqual(self._verdict("layer-state-001", own, cross)["verdict"], "DISAGREE")

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
            self.assertEqual(sha(ROOT / f["parameter_file"]["canonical_path"]), f["parameter_file"]["sha256"], f["id"])
            rec = json.loads((CORPUS / f["expected"]["path"]).read_text())
            self.assertEqual(rec["provenance"]["parameter_file_sha256"], f["parameter_file"]["sha256"], f["id"])
            self.assertNotIn("source.dwg", json.dumps(rec), f["id"])


PIN = ROOT / "corpus" / "r0-open.pin.json"
KNOWN_CAPABILITIES = {"line", "polyline", "circle", "ellipse", "trimmed_curve", "composite_curve", "bezier", "bspline",
                      "nurbs", "affine_transform"}
NEW_PROBES = ("bulge-arc-neg-001", "lwpolyline-closed-001", "polyline2d-001", "layer-state-001")


class HardenedCheck(unittest.TestCase):
    """`check` is the whole story: each of these tampers with a copy of the corpus and must be reported,
    even when SHA256SUMS is re-synced afterwards."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="r0open-test-"))
        shutil.copytree(ROOT / "corpus", self.tmp / "corpus")
        self.c = self.tmp / "corpus" / "r0-open"
        from runner import r0_open
        self.r = r0_open

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def problems(self):
        self.r.write_sums(self.c)
        return self.r.check(self.c)

    def test_untouched_copy_is_clean(self):
        self.assertEqual(self.problems(), [])

    def test_forged_comparison_json_is_caught(self):
        p = self.c / "fixtures" / "line-001" / "comparison.json"
        d = json.loads(p.read_text())
        d["checks"]["cross"][0]["expected"] = "0x0000000000000001"
        p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        self.assertTrue(any("comparison.json" in x for x in self.problems()))

    def test_swapped_dwg_bytes_are_caught_against_the_manifest(self):
        p = self.c / "fixtures" / "line-001" / "source.dwg"
        p.write_bytes(p.read_bytes() + b"\0")
        self.assertTrue(any("line-001" in x and "dwg" in x.lower() for x in self.problems()))

    def test_step_files_in_any_case_and_extension_are_caught(self):
        for name in ("FOO.STEP", "bar.p21", "baz.StpZ"):
            (self.c / name).write_text("x")
            self.assertTrue(any(name in x for x in self.problems()), name)
            (self.c / name).unlink()

    def test_step_content_under_another_name_is_caught(self):
        (self.c / "innocent.dat").write_text("ISO-10303-21;\nHEADER;\n")
        self.assertTrue(any("innocent.dat" in x for x in self.problems()))

    def test_vendor_attribution_in_a_readme_is_caught(self):
        p = self.c / "fixtures" / "line-001" / "README.md"
        p.write_text(p.read_text() + "\nThis drawing was converted by CAD Exchanger.\n")
        self.assertTrue(any("line-001/README.md" in x for x in self.problems()))

    def test_vendor_attribution_in_the_changelog_is_caught(self):
        p = self.tmp / "corpus" / "CHANGELOG.md"
        p.write_text(p.read_text() + "\nThe ODA writer produced these.\n")
        self.assertTrue(any("CHANGELOG" in x for x in self.problems()))

    def test_a_vendor_mentioned_in_a_negation_is_allowed(self):
        p = self.c / "fixtures" / "line-001" / "README.md"
        p.write_text(p.read_text() + "\nNothing here was converted by CAD Exchanger or ODA.\n")
        self.assertEqual(self.problems(), [])


class PinnedBundle(unittest.TestCase):
    def test_every_fixture_names_p1_1_capabilities_or_says_none(self):
        for f in manifest()["fixtures"]:
            caps = f["capabilities"]
            self.assertIsInstance(caps, list, f["id"])
            self.assertLessEqual(set(caps), KNOWN_CAPABILITIES, f["id"])
            if not caps:
                self.assertTrue(f["capabilities_note"].strip(), f["id"])

    def test_the_corpus_directory_is_self_contained(self):
        for f in manifest()["fixtures"]:
            self.assertTrue(f["expected"]["path"].startswith("fixtures/"), f["id"])
            self.assertEqual(sha(CORPUS / f["expected"]["path"]), f["expected"]["sha256"], f["id"])
            self.assertEqual(sha(CORPUS / f["expected"]["path"]), sha(ROOT / f["expected"]["canonical_path"]), f["id"])
            self.assertEqual(sha(CORPUS / f["parameter_file"]["path"]), sha(ROOT / f["parameter_file"]["canonical_path"]), f["id"])

    def test_the_pin_matches_a_rebuilt_bundle_and_the_manifest(self):
        from runner import r0_open
        pin = json.loads(PIN.read_text())
        self.assertEqual(pin["corpus_revision"], "r0-open")
        self.assertEqual(pin["manifest_sha256"], sha(CORPUS / "manifest.json"))
        self.assertEqual(pin["bundle_sha256"], r0_open.bundle_sha256(CORPUS))
        self.assertTrue(pin["tag"].strip() and pin["how_to_verify"].strip())


class AddedProbes(unittest.TestCase):
    def fixture(self, fid):
        hits = [f for f in manifest()["fixtures"] if f["id"] == fid]
        self.assertEqual(len(hits), 1, fid + " is not in the manifest")
        return hits[0]

    def test_the_new_probes_are_accepted_or_quarantined_for_a_named_reason(self):
        for fid in NEW_PROBES:
            self.assertIn(self.fixture(fid)["status"], ("ACCEPTED", "QUARANTINED"))

    def test_closed_lwpolyline_is_really_checked_as_closed(self):
        c = json.loads((CORPUS / "fixtures" / "lwpolyline-closed-001" / "comparison.json").read_text())
        row = [i for i in c["checks"]["cross"] if i["field"] == "closed"][0]
        self.assertEqual((row["expected"], row["read"], row["ok"]), (True, True, True))

    def test_old_style_polyline_is_a_polyline_not_other(self):
        for which in ("acadrust", "acadsharp"):
            r = json.loads((CORPUS / "fixtures" / "polyline2d-001" / ("read.%s.json" % which)).read_text())
            self.assertEqual([e["type"] for e in r["blocks"][0]["entities"]], ["POLYLINE"])

    def test_negative_bulge_has_a_reversed_ccw_derived_arc_that_is_checked(self):
        exp = json.loads((ROOT / "fixtures" / "known-truth" / "bulge-arc-neg-001" / "expected.math.json").read_text())
        arc = [e for e in exp["entities"] if e["class"] == "circular_arc"][0]
        # arcs run counter-clockwise, so the record holds the CCW arc with its direction reversed against the source
        self.assertEqual(arc["orientation"], {"parameter_direction": "REVERSED_AGAINST_SOURCE", "sense_about_normal": "CW"})
        self.assertTrue(exp["entities"][0]["geometry"]["bulges"][0]["decimal"].startswith("-"))
        c = json.loads((CORPUS / "fixtures" / "bulge-arc-neg-001" / "comparison.json").read_text())
        self.assertTrue(any(i["field"].startswith("derived_arc.") for i in c["checks"]["cross"]))
        pos = json.loads((CORPUS / "fixtures" / "bulge-arc-001" / "comparison.json").read_text())
        self.assertTrue(any(i["field"].startswith("derived_arc.") for i in pos["checks"]["cross"]))

    def test_layer_states_are_read_back_by_both_readers(self):
        c = json.loads((CORPUS / "fixtures" / "layer-state-001" / "comparison.json").read_text())
        fields = {i["field"] for i in c["checks"]["cross"]}
        for need in ("layer[OFF_L].on", "layer[FROZEN_L].frozen", "layer[SHOWN_L].on"):
            self.assertIn(need, fields)


class WordingAndDispositions(unittest.TestCase):
    def test_adr_states_the_common_mode_caveat(self):
        t = ADR.read_text()
        self.assertIn("common-mode", t)
        self.assertIn("same DWG specification", t)
        self.assertIn("round-trip loss", t)
        self.assertIn("shared misreading", t)

    def test_the_readme_repeats_the_caveat(self):
        self.assertIn("shared misreading", (CORPUS / "README.md").read_text())

    def test_shear_and_affine_exclusions_are_worded_honestly(self):
        q = {e["id"]: e for e in quarantine()["excluded"]}
        for fid in ("shear-001", "general-affine-001"):
            ev = q[fid]["evidence"]
            self.assertIn("single INSERT", ev)
            self.assertIn("three-level", ev)
            self.assertIn("not attempted", ev)
            self.assertNotIn("has no DWG INSERT form", ev)
        self.assertNotIn("has no DWG INSERT form", ADR.read_text())

    def test_rejection_probes_carry_the_downstream_disposition(self):
        f = [x for x in manifest()["fixtures"] if x["id"] == "near-singular-001"][0]
        self.assertIn("NEAR_SINGULAR_TRANSFORM", f["downstream_disposition"])
        self.assertIn("QUARANTINE", f["downstream_disposition"])
        t = (CORPUS / "fixtures" / "near-singular-001" / "README.md").read_text()
        self.assertIn("must not emit a curve", t)
        self.assertIn("near-singular-001", (ROOT / "corpus" / "CHANGELOG.md").read_text())
        for g in manifest()["fixtures"]:
            rejects = "rejection" in json.loads((CORPUS / g["expected"]["path"]).read_text())["entities"][0]
            self.assertEqual("downstream_disposition" in g, rejects, g["id"])


if __name__ == "__main__":
    unittest.main()
