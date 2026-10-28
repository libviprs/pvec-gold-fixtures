"""The container wiring for the corpus run (issue 53), gold-fixtures side.

The pvec side (Container::start in crates/pvec-hermetic) is not in this repository. What lives here is
what that side reads and relies on: the pinned digest file, the /corpus mount layout, and a check that a
run with the container unavailable is red. Red until runner/container_wiring.py and the pin file exist.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "corpus" / "container.pin.json"
CORPUS = ROOT / "corpus" / "r0-open"


def wiring(*args, env=None, docker=None):
    e = dict(os.environ, PYTHONPATH=str(ROOT))
    for k in ("CI", "PVEC_DEV_RUN", "GITHUB_ACTIONS"):
        e.pop(k, None)
    e.update(env or {})
    if docker:
        e["DOCKER"] = docker
    return subprocess.run([sys.executable, "-m", "runner.container_wiring"] + list(args), cwd=ROOT, env=e, capture_output=True, text=True)


class Pin(unittest.TestCase):
    def test_pin_file_exists_and_names_the_mount(self):
        d = json.loads(PIN.read_text())
        self.assertEqual(d["mount"], {"source": "corpus/r0-open", "target": "/corpus", "read_only": True})
        self.assertEqual(d["credentials"], "none")

    def test_pin_check_accepts_the_committed_file(self):
        r = wiring("check-pin", str(PIN))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pin_check_strict_refuses_an_unpinned_digest(self):
        r = wiring("check-pin", str(PIN), "--strict")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not pinned", r.stdout + r.stderr)

    def test_pin_check_refuses_a_tag_in_place_of_a_digest(self):
        d = json.loads(PIN.read_text())
        d["images"][0]["digest"] = "latest"
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "pin.json"
            p.write_text(json.dumps(d))
            r = wiring("check-pin", str(p))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("digest", r.stdout + r.stderr)

    def test_pin_check_refuses_any_credential_field(self):
        d = json.loads(PIN.read_text())
        d["images"][0]["licence_file"] = "/secret/key"
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "pin.json"
            p.write_text(json.dumps(d))
            r = wiring("check-pin", str(p))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("credential", r.stdout + r.stderr)

    def test_strict_accepts_a_real_digest(self):
        d = json.loads(PIN.read_text())
        for i in d["images"]:
            i["digest"] = "sha256:" + "ab" * 32
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "pin.json"
            p.write_text(json.dumps(d))
            r = wiring("check-pin", str(p), "--strict")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Layout(unittest.TestCase):
    def test_r0_open_has_the_layout_the_container_mounts(self):
        r = wiring("check-layout", str(CORPUS))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_directory_without_a_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "fixtures").mkdir()
            r = wiring("check-layout", t)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("manifest.json", r.stdout + r.stderr)

    def test_a_fixture_directory_without_a_source_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "fixtures" / "x-001").mkdir(parents=True)
            (Path(t) / "manifest.json").write_text("{}")
            r = wiring("check-layout", t)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("x-001", r.stdout + r.stderr)

    def test_compose_mounts_the_corpus_read_only_at_corpus(self):
        text = (ROOT / "docker-compose.yml").read_text()
        self.assertRegex(text, r"(?m)^\s*-\s*\$\{CORPUS_DIR:-[^}]*corpus/r0-open\}:/corpus:ro\s*$")


class Gate(unittest.TestCase):
    def fake(self, ok):
        t = tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False)
        t.write("#!/bin/sh\nexit %d\n" % (0 if ok else 1))
        t.close()
        os.chmod(t.name, 0o755)
        self.addCleanup(os.unlink, t.name)
        return t.name

    def test_container_available_passes(self):
        r = wiring("require-container", docker=self.fake(True))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_container_unavailable_is_red(self):
        r = wiring("require-container", docker=self.fake(False))
        self.assertEqual(r.returncode, 1)
        self.assertIn("container unavailable", r.stdout + r.stderr)

    def test_no_docker_binary_is_red(self):
        r = wiring("require-container", docker="/nonexistent/docker")
        self.assertEqual(r.returncode, 1)

    def test_ci_run_is_red_even_with_the_developer_switch(self):
        r = wiring("require-container", env={"CI": "true", "PVEC_DEV_RUN": "1"}, docker=self.fake(False))
        self.assertEqual(r.returncode, 1)

    def test_developer_run_skips_and_prints_the_reason(self):
        r = wiring("require-container", env={"PVEC_DEV_RUN": "1"}, docker=self.fake(False))
        self.assertEqual(r.returncode, 0)
        self.assertIn("SKIP", r.stdout + r.stderr)
        self.assertIn("PVEC_DEV_RUN", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
