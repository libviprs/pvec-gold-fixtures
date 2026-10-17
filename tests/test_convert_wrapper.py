"""tools/convert_cadex.sh against stub vendor commands (no vendor software involved)."""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner import step_normalise

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "convert_cadex.sh"
SCHEMA = json.loads((ROOT / "schema" / "converter-status.schema.json").read_text())

STEP_OK = "ISO-10303-21;\nHEADER;\nFILE_NAME('%s','%s',(''),(''),'','','');\nFILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF { 1 0 10303 442 1 1 4 }'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"


def stub(path, body):
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class Wrapper(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)
        (self.d / "source.dwg").write_bytes(b"AC1032 fake dwg")
        stub(self.d / "version", "echo 'stub-1.2.3'\n")
        self.env = dict(os.environ, CADEX_VENDOR_CMD=str(self.d / "vendor"), CADEX_VERSION_CMD=str(self.d / "version"))

    def tearDown(self):
        self.t.cleanup()

    def run_wrapper(self, *args, env=None):
        a = list(args) or ["--in", str(self.d / "source.dwg"), "--out", str(self.d / "primary.step")]
        r = subprocess.run([str(SCRIPT)] + a, env=env or self.env, capture_output=True, text=True)
        sp = self.d / "primary.status.json"
        rec = json.loads(sp.read_text()) if sp.exists() else None
        if rec is not None:
            self.assertEqual(list(Draft202012Validator(SCHEMA).iter_errors(rec)), [], rec)
        return r, rec

    def test_success_records_hash_version_schema_and_time(self):
        stub(self.d / "vendor", 'printf "%s" "' + (STEP_OK % ("a", "2026-01-01T00:00:00")).replace('"', '\\"').replace("$", "\\$") + '" > "$2"\n')
        r, rec = self.run_wrapper()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(rec["status"], "OK")
        self.assertEqual(rec["product"]["version"], "stub-1.2.3")
        self.assertIn("AP242", rec["declared_schema"])
        self.assertEqual(len(rec["input"]["sha256"]), 64)
        self.assertEqual(len(rec["output"]["sha256"]), 64)
        self.assertTrue((self.d / "primary.step").exists())

    def test_malformed_input_exits_12_with_a_parseable_record_and_no_output(self):
        stub(self.d / "vendor", 'echo "partial" > "$2"; echo "DWG header is corrupt" >&2; exit 12\n')
        (self.d / "primary.step").write_text("stale from an earlier run")
        r, rec = self.run_wrapper()
        self.assertEqual(r.returncode, 12)
        self.assertEqual((rec["status"], rec["error"]["class"], rec["exit_code"]), ("ERROR", "INPUT_MALFORMED", 12))
        self.assertIn("corrupt", rec["error"]["message"])
        self.assertFalse((self.d / "primary.step").exists())
        self.assertEqual([p.name for p in self.d.glob("*.partial*")], [])

    def test_each_documented_code_maps_to_its_class(self):
        for rc, klass in ((13, "DWG_VERSION_UNSUPPORTED"), (14, "LICENCE_UNAVAILABLE"), (15, "CONVERSION_FAILED"), (16, "OUTPUT_NOT_WRITTEN"), (99, "CONVERSION_FAILED")):
            stub(self.d / "vendor", "exit %d\n" % rc)
            r, rec = self.run_wrapper()
            self.assertEqual(rec["error"]["class"], klass)
            self.assertEqual(r.returncode, 15 if rc == 99 else rc)
            self.assertFalse((self.d / "primary.step").exists())

    def test_missing_input_exits_11(self):
        stub(self.d / "vendor", "exit 0\n")
        r, rec = self.run_wrapper("--in", str(self.d / "nope.dwg"), "--out", str(self.d / "primary.step"))
        self.assertEqual((r.returncode, rec["error"]["class"]), (11, "INPUT_UNREADABLE"))

    def test_usage_error_exits_10(self):
        r = subprocess.run([str(SCRIPT), "--bogus"], env=self.env, capture_output=True, text=True, cwd=self.d)
        self.assertEqual(r.returncode, 10)

    def test_success_with_no_output_file_is_an_error(self):
        stub(self.d / "vendor", "exit 0\n")
        r, rec = self.run_wrapper()
        self.assertEqual((r.returncode, rec["error"]["class"]), (16, "OUTPUT_NOT_WRITTEN"))

    def test_non_step_output_is_rejected(self):
        stub(self.d / "vendor", 'echo "not step" > "$2"\n')
        r, _ = self.run_wrapper()
        self.assertEqual(r.returncode, 16)
        self.assertFalse((self.d / "primary.step").exists())

    def test_non_ap242_schema_is_rejected_and_leaves_no_output(self):
        ap214 = (STEP_OK % ("a", "t")).replace("AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF { 1 0 10303 442 1 1 4 }", "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }")
        stub(self.d / "vendor", "cat > \"$2\" <<'EOF'\n" + ap214 + "EOF\n")
        r, rec = self.run_wrapper()
        self.assertEqual((r.returncode, rec["error"]["class"]), (17, "SCHEMA_NOT_AP242"))
        self.assertFalse((self.d / "primary.step").exists())

    def test_repeat_runs_are_identical_except_the_named_fields(self):
        stub(self.d / "vendor", "cat > \"$2\" <<EOF\n" + (STEP_OK % ("a", "$(date +%s%N)")) + "EOF\n")
        outs = []
        for i in range(2):
            self.run_wrapper("--in", str(self.d / "source.dwg"), "--out", str(self.d / ("p%d.step" % i)), "--status", str(self.d / ("s%d.json" % i)))
            outs.append((self.d / ("p%d.step" % i)).read_text())
        self.assertTrue(step_normalise.same(*outs))
        self.assertFalse(step_normalise.same(outs[0], outs[1].replace("ENDSEC;", "ENDSEC; ", 1)))

    def test_status_never_contains_environment_secrets(self):
        stub(self.d / "vendor", "exit 14\n")
        env = dict(self.env, CADEX_LICENSE_KEY="CANARY-0123456789abcdef")
        r, rec = self.run_wrapper(env=env)
        self.assertNotIn("CANARY", json.dumps(rec) + r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
