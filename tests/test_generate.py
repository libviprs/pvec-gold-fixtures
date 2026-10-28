"""runner/generate.py (issue 13): the one-command pipeline, driven against a fake docker CLI.

Everything here is red until runner/generate.py exists. The fake (tests/fake_docker.py) logs every docker
call, so the teardown rules, the refusals and the quarantine behaviour are checked on the real code path,
including a real SIGINT sent to a real process.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAKE = ROOT / "tests" / "fake_docker.py"
SELFTEST = ROOT / "fixtures" / "validator-selftest"
DOWN = "down --volumes --remove-orphans"
ARTIFACTS = ["primary.step", "secondary.step", "primary.status.json", "secondary.status.json", "primary.verification.json",
             "secondary.verification.json", "primary.signature.json", "secondary.signature.json", "verdict.json", "manifest.json",
             "checksums.sha256"]


class Gen(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)
        self.fx = self.d / "fx"
        self.truth = self.d / "truth"
        self.truth.mkdir()
        for n in ("alpha-001", "beta-001"):
            (self.fx / n).mkdir(parents=True)
            (self.fx / n / "source.dwg").write_bytes(b"AC1032 " + n.encode())
        self.log = self.d / "docker.log"
        self.log.write_text("")
        self.env = dict(os.environ, DOCKER=str(FAKE), FAKE_LOG=str(self.log), FAKE_ROOT=str(ROOT), FAKE_FIXTURES=str(self.fx),
                        PYTHONPATH=str(ROOT))
        self.env.pop("FAKE_FAIL", None)

    def tearDown(self):
        self.t.cleanup()

    def start(self, *extra, env=None):
        cmd = [sys.executable, "-m", "runner.generate", "generate", "--fixtures", str(self.fx), "--truth", str(self.truth),
               "--lineage", "acadsharp-converter=acadsharp", "--lineage", "libredwg-converter=libredwg"] + list(extra)
        return subprocess.Popen(cmd, cwd=ROOT, env=env or self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def run_gen(self, *extra, env=None):
        p = self.start(*extra, env=env)
        out, _ = p.communicate(timeout=120)
        return p.returncode, out

    def calls(self):
        return self.log.read_text().splitlines()

    def test_one_command_writes_every_artifact(self):
        rc, out = self.run_gen("alpha-001")
        self.assertEqual(rc, 0, out)
        for a in ARTIFACTS:
            self.assertTrue((self.fx / "alpha-001" / "generated" / a).is_file(), a)
        self.assertFalse((self.fx / "beta-001" / "generated").exists(), "only the named fixture is generated")

    def test_checksums_cover_every_artifact_but_themselves(self):
        self.run_gen("alpha-001")
        lines = (self.fx / "alpha-001" / "generated" / "checksums.sha256").read_text().splitlines()
        self.assertEqual(sorted(l.split("  ")[1] for l in lines), sorted(a for a in ARTIFACTS if a != "checksums.sha256"))

    def test_rerun_with_unchanged_inputs_gives_identical_checksums(self):
        self.run_gen("alpha-001")
        first = (self.fx / "alpha-001" / "generated" / "checksums.sha256").read_text()
        self.run_gen("alpha-001")
        self.assertEqual(first, (self.fx / "alpha-001" / "generated" / "checksums.sha256").read_text())

    def test_manifest_records_digests_versions_policy_and_scope(self):
        self.run_gen("alpha-001")
        m = json.loads((self.fx / "alpha-001" / "generated" / "manifest.json").read_text())
        self.assertEqual(m["numeric_policy_version"], "PVec numeric policy v1")
        self.assertEqual(m["evaluator_version"], "1")
        self.assertEqual(m["oracle_scope"], "OPEN_CONVERTERS")
        self.assertEqual(len(m["source_sha256"]), 64)
        self.assertEqual(len(m["converters"]), 2)
        for c in m["converters"]:
            self.assertRegex(c["image_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(c["version"], "9.9")
            self.assertEqual(c["platform"], "linux/amd64")

    def test_both_converters_agreeing_without_truth_is_dual_oracle(self):
        self.run_gen("alpha-001")
        v = json.loads((self.fx / "alpha-001" / "generated" / "verdict.json").read_text())
        self.assertEqual(v["evidence_class"], "DUAL_ORACLE_EQUIVALENT")

    def test_disagreeing_outputs_quarantine(self):
        env = dict(self.env, FAKE_VERIF_SECONDARY=str(SELFTEST / "verification" / "x64" / "circle.verification.json"))
        rc, out = self.run_gen("alpha-001", env=env)
        v = json.loads((self.fx / "alpha-001" / "generated" / "verdict.json").read_text())
        self.assertEqual(v["evidence_class"], "QUARANTINED")
        self.assertEqual(v["reason"], "UNRESOLVED_DISAGREEMENT")
        self.assertNotEqual(rc, 0)

    def test_converter_failure_quarantines_continues_and_exits_nonzero_with_a_count(self):
        env = dict(self.env, FAKE_FAIL="acadsharp-converter")
        rc, out = self.run_gen("alpha-001", "beta-001", env=env)
        self.assertNotEqual(rc, 0)
        for n in ("alpha-001", "beta-001"):
            v = json.loads((self.fx / n / "generated" / "verdict.json").read_text())
            self.assertEqual(v["evidence_class"], "QUARANTINED", n)
            self.assertIn("CONVERSION_FAILED", v["detail"])
        self.assertIn("2 of 2 fixtures quarantined", out)

    def test_teardown_runs_after_success(self):
        self.run_gen("alpha-001")
        self.assertIn(DOWN, self.calls()[-1])

    def test_teardown_runs_after_a_converter_failure(self):
        self.run_gen("alpha-001", env=dict(self.env, FAKE_FAIL="libredwg-converter"))
        self.assertIn(DOWN, self.calls()[-1])

    def test_teardown_runs_after_an_exception(self):
        (self.fx / "alpha-001" / "source.dwg").unlink()
        rc, out = self.run_gen("alpha-001")
        self.assertNotEqual(rc, 0)
        self.assertIn(DOWN, self.calls()[-1])

    def test_sigint_mid_conversion_tears_down(self):
        p = self.start("alpha-001", env=dict(self.env, FAKE_HANG="libredwg-converter"))
        for _ in range(100):
            if any(" run " in c and "libredwg-converter" in c for c in self.calls()):
                break
            time.sleep(0.1)
        else:
            p.kill()
            self.fail("the run never reached the second converter")
        p.send_signal(signal.SIGINT)
        out, _ = p.communicate(timeout=60)
        self.assertEqual(p.returncode, 130, out)
        self.assertIn(DOWN, self.calls()[-1])

    def test_refuses_to_start_when_an_image_digest_cannot_be_resolved(self):
        rc, out = self.run_gen("alpha-001", env=dict(self.env, FAKE_NO_IMAGE="pvec-gold/libredwg-converter:local"))
        self.assertNotEqual(rc, 0)
        self.assertIn("image digest", out)
        self.assertFalse(any(" run " in c for c in self.calls()), "no container may start")
        self.assertFalse((self.fx / "alpha-001" / "generated").exists())

    def test_refuses_to_start_without_a_policy_version(self):
        pol = self.d / "policy"
        pol.mkdir()
        rc, out = self.run_gen("alpha-001", "--policy-dir", str(pol))
        self.assertNotEqual(rc, 0)
        self.assertIn("policy", out)
        self.assertFalse(any(" run " in c for c in self.calls()))

    def test_run_log_says_where_each_stage_ran(self):
        rc, out = self.run_gen("alpha-001")
        self.assertRegex(out, r"stage convert-primary .*native x64")
        self.assertRegex(out, r"stage normalise .*(native x64|arm64)")

    def test_leak_check_passes_when_nothing_is_left(self):
        rc, out = self.run_gen("alpha-001", "--check-leaks")
        self.assertEqual(rc, 0, out)

    def test_leak_check_fails_when_a_container_is_left(self):
        ps = self.d / "ps"
        ps.write_text("abc\n")
        # the fake lists a container only after the first run call
        env = dict(self.env, FAKE_PS=str(ps))
        rc, out = self.run_gen("alpha-001", "--check-leaks", env=env)
        self.assertEqual(rc, 0, "the same container before and after is not a leak")
        script = self.d / "grow.sh"
        script.write_text("#!/bin/sh\nif [ -f %s ]; then echo abc; echo leaked; else echo abc; touch %s; fi\n" % (self.d / "m", self.d / "m"))
        script.chmod(0o755)
        # a docker that reports one more container on the second ps call
        wrapper = self.d / "docker2"
        wrapper.write_text('#!/bin/sh\nif [ "$1" = ps ]; then exec %s; fi\nexec %s "$@"\n' % (script, FAKE))
        wrapper.chmod(0o755)
        rc, out = self.run_gen("alpha-001", "--check-leaks", env=dict(self.env, DOCKER=str(wrapper)))
        self.assertNotEqual(rc, 0)
        self.assertIn("leaked", out)


class Evidence(unittest.TestCase):
    def test_exact_cells_from_both_converters_with_truth_are_known_truth(self):
        from runner import generate as g
        exact = [{"class": "STRUCTURAL_EXACT"}]
        self.assertEqual(g.evidence_class({"a": exact, "b": exact}, True, True)[0], "KNOWN_TRUTH_EXACT")

    def test_a_bounded_cell_with_truth_quarantines(self):
        from runner import generate as g
        cls, reason = g.evidence_class({"a": [{"class": "STRUCTURAL_EXACT"}], "b": [{"class": "BOUNDED_APPROXIMATION"}]}, True, True)
        self.assertEqual((cls, reason), ("QUARANTINED", "APPROXIMATION"))

    def test_unsupported_cell_quarantines_as_unsupported_entity(self):
        from runner import generate as g
        self.assertEqual(g.evidence_class({"a": [{"class": "UNSUPPORTED"}], "b": [{"class": "STRUCTURAL_EXACT"}]}, True, True),
                         ("QUARANTINED", "UNSUPPORTED_ENTITY"))


if __name__ == "__main__":
    unittest.main()
