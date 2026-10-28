"""Issue 78: r2-open, the first STEP_ORACLE revision, built from a two-converter generate run.

The logic is exercised on small synthetic trees (a manifest, a few files, a fake `generated/` directory per
fixture). The committed revision, release and audit are checked against the rules at the bottom.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runner import r2_open

ROOT = Path(__file__).resolve().parent.parent
TS = "FILE_NAME('x','2026-10-28T10:00:00',(''),(''),'','','');"
STEP = "ISO-10303-21;\nDATA;\n#1=LINE();\n%s\nENDSEC;\n"
A, B = "acadsharp-dwg2step", "libredwg-dwg2step"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def entry(fid, cls="KNOWN_TRUTH_EXACT", scope="READER_MAPPING_ONLY", group="curves", dwg=b"dwg", truth=True, **kw):
    arts = {"source.dwg": {"path": "corpus/r1-open/fixtures/%s/source.dwg" % fid, "sha256": sha(dwg)}}
    if truth:
        arts["expected.math.json"] = {"path": "corpus/r1-open/fixtures/%s/expected.math.json" % fid, "sha256": sha(b"{}")}
    e = {"id": fid, "group": group, "evidence_class": cls, "evidence_scope": scope, "oracle_scope": "NONE",
         "licence_verdict": "PUBLIC_REDISTRIBUTABLE", "provenance": "SYNTHETIC_AUTHORED", "status": "ACCEPTED", "artifacts": arts}
    e.update(kw)
    return e


def tree(root, entries):
    root = Path(root)
    for e in entries:
        for name, a in e["artifacts"].items():
            p = root / a["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"dwg" if name == "source.dwg" else b"{}")
    d = root / "corpus" / "r1-open"
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps({"corpus_revision": "r1-open", "fixtures": entries, "includes": {}}, sort_keys=True))
    (root / "corpus" / "CHANGELOG.md").write_text("# corpus changelog\n\n<!-- r2-open-moves -->\n<!-- /r2-open-moves -->\n")
    return root


def manifest_for(fid, digest_b="sha256:" + "b" * 64):
    return {"fixture_id": fid, "numeric_policy_version": "PVec numeric policy v1", "evaluator_version": "ev1", "occt_version": "7.6.3",
            "converters": [
                {"role": "primary", "service": "acadsharp-converter", "id": A, "version": "3.7.1", "lineage": "acadsharp",
                 "image": "pvec-gold/dwg2step-acadsharp:local", "image_digest": "sha256:" + "a" * 64, "platform": "linux/amd64"},
                {"role": "secondary", "service": "libredwg-converter", "id": B, "version": "0.14", "lineage": "libredwg",
                 "image": "pvec-oracle-libredwg:local", "image_digest": digest_b, "platform": "linux/amd64"}],
            "validator": {"service": "step-validator", "image": "pvec-gold/step-validator:local", "image_digest": "sha256:" + "c" * 64}}


def gen(runs, fid, verdict_class, reason=None, refused=(), stamp="2026-10-28T10:00:00", sig="s", detail="", digest_b=None):
    d = Path(runs) / fid
    d.mkdir(parents=True, exist_ok=True)
    for role in ("primary", "secondary"):
        if role in refused:
            (d / (role + ".status.json")).write_text(json.dumps({"error": {"class": "CONVERSION_FAILED", "code": 15, "message": "no supported curve"}}))
            continue
        (d / (role + ".step")).write_text(STEP % TS.replace("2026-10-28T10:00:00", stamp))
        (d / (role + ".signature.json")).write_text(json.dumps({"sig": sig, "role": role}))
        (d / (role + ".status.json")).write_text(json.dumps({"status": "OK"}))
    (d / "verdict.json").write_text(json.dumps({"fixture_id": fid, "evidence_class": verdict_class, "reason": reason, "detail": detail,
                                                "cells": {}, "signature_differences": [], "oracle_scope": "OPEN_CONVERTERS", "evidence_scope": "STEP_ORACLE"}))
    (d / "manifest.json").write_text(json.dumps(manifest_for(fid, digest_b or "sha256:" + "b" * 64)))


class Stage(unittest.TestCase):
    def test_stage_lays_out_what_generate_reads(self):
        es = [entry("line-001"), entry("dimension-001", cls="QUARANTINED", scope="CLASSIFICATION_EXPECTED", group="negative", truth=False)]
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as o:
            root = tree(t, es)
            ids = r2_open.stage(root, o)
            self.assertEqual(ids, ["dimension-001", "line-001"])
            self.assertEqual((Path(o) / "fixtures" / "line-001" / "source.dwg").read_bytes(), b"dwg")
            self.assertTrue((Path(o) / "truth" / "line-001" / "expected.math.json").is_file())
            self.assertFalse((Path(o) / "truth" / "dimension-001").exists(), "a fixture with no authored record has no truth")

    def test_a_dwg_that_does_not_match_its_manifest_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as o:
            root = tree(t, [entry("line-001")])
            (root / "corpus/r1-open/fixtures/line-001/source.dwg").write_bytes(b"other")
            with self.assertRaises(r2_open.Refused):
                r2_open.stage(root, o)

    def test_non_accepted_entries_are_not_staged(self):
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as o:
            root = tree(t, [entry("line-001"), entry("gone-001", status="REJECTED")])
            self.assertEqual(r2_open.stage(root, o), ["line-001"])


def obs(verdict_class, reason=None, refused=()):
    return {"verdict": {"evidence_class": verdict_class, "reason": reason, "detail": ""},
            "refused": {"primary": "primary" in refused, "secondary": "secondary" in refused},
            "errors": {"primary": "CONVERSION_FAILED" if "primary" in refused else "", "secondary": "CONVERSION_FAILED" if "secondary" in refused else ""}}


class Decide(unittest.TestCase):
    def test_a_probe_both_converters_got_exact_moves_to_step_oracle(self):
        f, move = r2_open.decide(entry("line-001"), obs("KNOWN_TRUTH_EXACT"))
        self.assertEqual((f["evidence_class"], f["evidence_scope"], f["oracle_scope"]), ("KNOWN_TRUTH_EXACT", "STEP_ORACLE", "OPEN_CONVERTERS"))
        self.assertEqual(move["from"], ["KNOWN_TRUTH_EXACT", "READER_MAPPING_ONLY"])
        self.assertEqual(move["to"], ["KNOWN_TRUTH_EXACT", "STEP_ORACLE"])

    def test_an_approximation_does_not_move_and_says_why(self):
        f, move = r2_open.decide(entry("x-001"), obs("QUARANTINED", "APPROXIMATION"))
        self.assertEqual((f["evidence_class"], f["evidence_scope"]), ("KNOWN_TRUTH_EXACT", "READER_MAPPING_ONLY"))
        self.assertEqual(f["oracle_scope"], "OPEN_CONVERTERS", "the converters did run, the scope of the oracle is the revision's")
        self.assertIn("APPROXIMATION", move["why"])
        self.assertEqual(move["from"], move["to"])

    def test_a_rejection_probe_both_converters_refused_is_confirmed(self):
        e = entry("near-singular-001", group="transforms", downstream_disposition={"expected": "REJECT"})
        f, move = r2_open.decide(e, obs("QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary")))
        self.assertEqual(f["evidence_scope"], "STEP_ORACLE")
        self.assertEqual(f["evidence_class"], "KNOWN_TRUTH_EXACT")

    def test_the_authored_record_alone_marks_a_rejection_probe(self):
        e = entry("singular-001", group="edge", expects_rejection=True)
        f, _ = r2_open.decide(e, obs("QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary")))
        self.assertEqual(f["evidence_scope"], "STEP_ORACLE")

    def test_a_rejection_probe_one_converter_emitted_does_not_move(self):
        e = entry("near-singular-001", group="transforms", downstream_disposition={"expected": "REJECT"})
        f, move = r2_open.decide(e, obs("QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary",)))
        self.assertEqual(f["evidence_scope"], "READER_MAPPING_ONLY")
        self.assertIn("secondary", move["why"])

    def test_a_negative_fixture_both_refused_stays_quarantined_and_gains_step_oracle(self):
        e = entry("dimension-001", cls="QUARANTINED", scope="CLASSIFICATION_EXPECTED", group="negative", truth=False)
        f, move = r2_open.decide(e, obs("QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary")))
        self.assertEqual((f["evidence_class"], f["evidence_scope"]), ("QUARANTINED", "STEP_ORACLE"))
        self.assertEqual(f.get("converter_failures"), [])

    def test_a_degenerate_fixture_a_converter_drew_geometry_for_is_a_listed_failure(self):
        e = entry("zero-length-segment-001", cls="QUARANTINED", scope="REJECTION_EXPECTED", group="degenerate", truth=False)
        f, move = r2_open.decide(e, obs("DUAL_ORACLE_EQUIVALENT", refused=("primary",)))
        self.assertEqual(f["evidence_class"], "QUARANTINED", "agreement does not rescue a fixture that should be refused")
        self.assertEqual(f["evidence_scope"], "REJECTION_EXPECTED")
        self.assertEqual(f["converter_failures"], ["secondary"])

    def test_a_real_world_drawing_both_converted_and_agreed_becomes_dual_oracle_equivalent(self):
        e = entry("rw-001", cls="REAL_WORLD_DIFFERENTIAL", scope="READER_CENSUS_ONLY", group="real-world", truth=False)
        f, move = r2_open.decide(e, obs("DUAL_ORACLE_EQUIVALENT"))
        self.assertEqual((f["evidence_class"], f["evidence_scope"]), ("DUAL_ORACLE_EQUIVALENT", "STEP_ORACLE"))

    def test_a_real_world_drawing_that_is_refused_stays_and_names_the_refusal(self):
        e = entry("rw-001", cls="REAL_WORLD_DIFFERENTIAL", scope="READER_CENSUS_ONLY", group="real-world", truth=False)
        f, move = r2_open.decide(e, obs("QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary")))
        self.assertEqual((f["evidence_class"], f["evidence_scope"]), ("REAL_WORLD_DIFFERENTIAL", "READER_CENSUS_ONLY"))
        self.assertIn("CONVERSION_FAILED", move["why"])

    def test_a_real_world_drawing_whose_signatures_disagree_stays(self):
        e = entry("rw-001", cls="REAL_WORLD_DIFFERENTIAL", scope="READER_CENSUS_ONLY", group="real-world", truth=False)
        f, move = r2_open.decide(e, obs("QUARANTINED", "UNRESOLVED_DISAGREEMENT"))
        self.assertEqual(f["evidence_class"], "REAL_WORLD_DIFFERENTIAL")
        self.assertIn("UNRESOLVED_DISAGREEMENT", move["why"])


def build_in(t, es, specs, **kw):
    root = tree(Path(t) / "root", es)
    runs = Path(t) / "runs"
    for fid, args in specs.items():
        gen(runs, fid, **args)
    out = Path(t) / "out"
    m = r2_open.build(root, runs, out, **kw)
    return root, runs, out, m


SPECS = {"line-001": dict(verdict_class="KNOWN_TRUTH_EXACT"),
         "dimension-001": dict(verdict_class="QUARANTINED", reason="UNSUPPORTED_ENTITY", refused=("primary", "secondary"))}
ES = [entry("line-001"), entry("dimension-001", cls="QUARANTINED", scope="CLASSIFICATION_EXPECTED", group="negative", truth=False)]


class Build(unittest.TestCase):
    def test_manifest_names_two_converters_by_distinct_lineage_and_digest(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, out, m = build_in(t, ES, SPECS)
            self.assertEqual(m["corpus_revision"], "r2-open")
            self.assertEqual(m["oracle_scope"], "OPEN_CONVERTERS")
            cs = m["converters"]
            self.assertEqual([c["id"] for c in cs], [A, B])
            self.assertEqual(len({c["lineage"] for c in cs}), 2)
            self.assertTrue(all(c["image_digest"].startswith("sha256:") for c in cs))
            self.assertEqual(json.loads((out / "manifest.json").read_text()), m)

    def test_a_missing_digest_blocks_the_revision(self):
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", ES)
            for fid, args in SPECS.items():
                gen(Path(t) / "runs", fid, **args)
            mf = json.loads((Path(t) / "runs" / "line-001" / "manifest.json").read_text())
            mf["converters"][1]["image_digest"] = None
            (Path(t) / "runs" / "line-001" / "manifest.json").write_text(json.dumps(mf))
            with self.assertRaises(r2_open.Refused):
                r2_open.build(root, Path(t) / "runs", Path(t) / "out")

    def test_two_runs_that_used_different_images_are_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", ES)
            gen(Path(t) / "runs", "line-001", "KNOWN_TRUTH_EXACT")
            gen(Path(t) / "runs", "dimension-001", "QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary"), digest_b="sha256:" + "d" * 64)
            with self.assertRaises(r2_open.Refused):
                r2_open.build(root, Path(t) / "runs", Path(t) / "out")

    def test_the_same_lineage_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", ES)
            for fid, args in SPECS.items():
                gen(Path(t) / "runs", fid, **args)
                p = Path(t) / "runs" / fid / "manifest.json"
                mf = json.loads(p.read_text())
                mf["converters"][1]["lineage"] = "acadsharp"
                p.write_text(json.dumps(mf))
            with self.assertRaises(r2_open.Refused):
                r2_open.build(root, Path(t) / "runs", Path(t) / "out")

    def test_every_fixture_without_a_run_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", ES)
            gen(Path(t) / "runs", "line-001", "KNOWN_TRUTH_EXACT")
            with self.assertRaises(r2_open.Refused):
                r2_open.build(root, Path(t) / "runs", Path(t) / "out")

    def test_step_is_stored_without_its_time_stamp_and_hashes_are_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, out, m = build_in(t, ES, SPECS)
            e = next(f for f in m["fixtures"] if f["id"] == "line-001")
            step = (out / e["generated"]["primary.step"]["path"]).read_text()
            self.assertIn("<TIMESTAMP>", step)
            self.assertNotIn("2026-10-28", step)
            for a in e["generated"].values():
                self.assertEqual(sha((out / a["path"]).read_bytes()), a["sha256"])

    def test_a_refused_fixture_has_no_step_and_says_so(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, out, m = build_in(t, ES, SPECS)
            e = next(f for f in m["fixtures"] if f["id"] == "dimension-001")
            self.assertNotIn("primary.step", e["generated"])
            self.assertEqual(e["step_oracle"]["refused"], {"primary": True, "secondary": True})

    def test_the_moves_are_in_the_manifest_and_the_changelog_block_is_derived_from_them(self):
        with tempfile.TemporaryDirectory() as t:
            root, _, out, m = build_in(t, ES, SPECS)
            ids = [x["id"] for x in m["moves"]]
            self.assertEqual(sorted(ids), ["dimension-001", "line-001"])
            r2_open.write_changelog(root, m)
            text = (root / "corpus" / "CHANGELOG.md").read_text()
            self.assertIn("`line-001`", text)
            self.assertIn("READER_MAPPING_ONLY", text)
            self.assertEqual(r2_open.changelog_block(text), r2_open.render_moves(m))

    def test_the_sums_file_covers_every_file(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, out, _ = build_in(t, ES, SPECS)
            self.assertEqual(r2_open.verify_sums(out), [])
            (out / "fixtures" / "line-001" / "verdict.json").write_text("{}")
            self.assertEqual(r2_open.verify_sums(out), ["fixtures/line-001/verdict.json"])

    def test_build_is_deterministic(self):
        with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as u:
            _, _, out1, _ = build_in(t, ES, SPECS)
            _, _, out2, _ = build_in(u, ES, SPECS)
            self.assertEqual((out1 / "SHA256SUMS").read_text(), (out2 / "SHA256SUMS").read_text())


class RejectionFromTruth(unittest.TestCase):
    def test_build_reads_the_rejection_from_the_expected_record(self):
        es = [entry("near-singular-001", group="transforms")]
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", es)
            (root / es[0]["artifacts"]["expected.math.json"]["path"]).write_text(json.dumps({"entities": [{"rejection": {"disposition": "QUARANTINE"}}]}))
            gen(Path(t) / "runs", "near-singular-001", "QUARANTINED", "UNSUPPORTED_ENTITY", refused=("primary", "secondary"))
            m = r2_open.build(root, Path(t) / "runs", Path(t) / "out")
            self.assertEqual(m["fixtures"][0]["evidence_scope"], "STEP_ORACLE")
            self.assertTrue(m["fixtures"][0]["expects_rejection"])


class Release(unittest.TestCase):
    def make(self, t):
        root, runs, out, m = build_in(t, ES, SPECS)
        rel = Path(t) / "rel"
        r2_open.release(out, rel, "r2-open-1")
        return rel, out

    def test_release_verifies_with_the_standard_library_only(self):
        with tempfile.TemporaryDirectory() as t:
            rel, _ = self.make(t)
            self.assertEqual(r2_open.verify_release(rel), [])
            m = json.loads((rel / "manifest.json").read_text())
            self.assertEqual(m["status"], "FROZEN_CANDIDATE_NOT_TAGGED")
            self.assertEqual(m["release"], "r2-open-1")
            self.assertEqual(sorted(m["pins"]["signatures"]["line-001"]), [A, B])

    def test_a_fixture_with_a_step_and_no_signature_is_released_without_one(self):
        # the evaluator can refuse a STEP a converter wrote (tiny-extent-001), which leaves a step and no signature
        with tempfile.TemporaryDirectory() as t:
            root = tree(Path(t) / "root", ES)
            runs = Path(t) / "runs"
            for fid, args in SPECS.items():
                gen(runs, fid, **args)
            (runs / "line-001" / "secondary.signature.json").unlink()
            out = Path(t) / "out"
            r2_open.build(root, runs, out)
            rel = Path(t) / "rel"
            m = r2_open.release(out, rel, "r2-open-1")
            self.assertEqual(sorted(m["pins"]["signatures"]["line-001"]), [A])
            self.assertEqual(sorted(m["pins"]["step_hashes"]["line-001"]), [A, B])
            self.assertEqual(r2_open.verify_release(rel), [])

    def test_release_holds_no_dwg_and_no_private_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            rel, _ = self.make(t)
            self.assertEqual([p for p in rel.rglob("*.dwg")], [])

    def test_a_changed_step_or_signature_is_found(self):
        with tempfile.TemporaryDirectory() as t:
            rel, _ = self.make(t)
            p = next((rel / "step").glob("line-001.*.step"))
            p.write_text(p.read_text() + "x")
            self.assertTrue(r2_open.verify_release(rel))

    def test_a_pin_that_no_longer_matches_its_file_is_found_even_if_the_sums_are_redone(self):
        with tempfile.TemporaryDirectory() as t:
            rel, _ = self.make(t)
            p = next((rel / "signatures").glob("line-001.*.signature.json"))
            p.write_text("{}")
            r2_open.write_sums(rel)
            self.assertTrue([x for x in r2_open.verify_release(rel) if "pin" in x])


class Divergence(unittest.TestCase):
    def test_only_the_time_stamp_may_differ_between_two_runs(self):
        with tempfile.TemporaryDirectory() as t:
            gen(Path(t) / "a", "line-001", "KNOWN_TRUTH_EXACT", stamp="2026-10-28T10:00:00")
            gen(Path(t) / "b", "line-001", "KNOWN_TRUTH_EXACT", stamp="2026-10-28T11:30:00")
            self.assertEqual(r2_open.divergences(Path(t) / "a", Path(t) / "b"), [])

    def test_a_different_signature_is_listed(self):
        with tempfile.TemporaryDirectory() as t:
            gen(Path(t) / "a", "line-001", "KNOWN_TRUTH_EXACT")
            gen(Path(t) / "b", "line-001", "KNOWN_TRUTH_EXACT", sig="other")
            d = r2_open.divergences(Path(t) / "a", Path(t) / "b")
            self.assertTrue(any("primary.signature.json" in x for x in d), d)

    def test_a_fixture_in_one_run_only_is_listed(self):
        with tempfile.TemporaryDirectory() as t:
            gen(Path(t) / "a", "line-001", "KNOWN_TRUTH_EXACT")
            gen(Path(t) / "b", "line-001", "KNOWN_TRUTH_EXACT")
            gen(Path(t) / "b", "extra-001", "KNOWN_TRUTH_EXACT")
            self.assertTrue(any("extra-001" in x for x in r2_open.divergences(Path(t) / "a", Path(t) / "b")))


class Audit(unittest.TestCase):
    QUAL = {"converters": {"primary": A, "secondary": B},
            "capabilities": [{"capability": "line", "status": "CERTIFIED", "by_converter": {A: "STRUCTURAL_EXACT", B: "STRUCTURAL_EXACT"}, "probes": ["line-001"]}]}

    def test_blocks_count_what_the_manifest_holds(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, _, m = build_in(t, ES, SPECS)
            b = r2_open.audit_blocks(m, self.QUAL)
            self.assertIn("| KNOWN_TRUTH_EXACT | STEP_ORACLE | 1 |", b["register"])
            self.assertIn("Quarantined fixtures: **1**", b["quarantine"])
            self.assertIn("| `dimension-001` | STEP_ORACLE | primary, secondary | none |", b["quarantine"])
            self.assertIn("| line | CERTIFIED |", b["capabilities"])

    def test_sync_replaces_only_the_generated_blocks_and_reports_drift(self):
        with tempfile.TemporaryDirectory() as t:
            _, _, _, m = build_in(t, ES, SPECS)
            b = r2_open.audit_blocks(m, self.QUAL)
            p = Path(t) / "audit.md"
            p.write_text("prose\n" + "".join("<!-- gen:%s -->\nold\n<!-- /gen:%s -->\nmore prose\n" % (n, n) for n in b))
            self.assertFalse(r2_open.sync_audit(p, b))
            self.assertFalse(r2_open.sync_audit(p, b, write=True))
            self.assertTrue(r2_open.sync_audit(p, b))
            self.assertTrue(p.read_text().startswith("prose\n"))
            self.assertIn("more prose", p.read_text())


class CleanHostScript(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "tools" / "clean_host_r2.sh").read_text()

    def test_the_libredwg_image_is_loaded_by_id_and_never_built_here(self):
        self.assertIn("docker save", self.text.replace("$dk save", "docker save"))
        self.assertNotRegex(self.text, r"build[^\n]*libredwg|libredwg[^\n]*docker build")

    def test_nothing_is_pushed_and_no_credential_is_touched(self):
        for bad in ("docker push", "$dk push", "docker login", "$dk login"):
            self.assertNotIn(bad, self.text)

    def test_it_runs_on_a_throw_away_daemon_and_removes_it(self):
        self.assertIn("docker:27-dind", self.text)
        self.assertIn("rm -f -v", self.text)

    def test_it_drives_the_r2_open_runner(self):
        self.assertIn("runner.r2_open", self.text)


if __name__ == "__main__":
    unittest.main()
