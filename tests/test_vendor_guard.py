"""tools/vendor_guard.sh against planted dummies (#27). Nothing here is vendor software or a real key."""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tools" / "vendor_guard.sh"
PATTERNS = ROOT / "tools" / "vendor-guard.patterns"
ARCHIVE = ROOT / "docs" / "converters" / "archive.md"
HOOK = ROOT / ".githooks" / "pre-commit"

# built from pieces so this file never contains a key-shaped string itself
DUMMY_VALUE = "Q" * 8 + "z" * 8 + "7" * 8
DUMMY_ASSIGN = "licence_key" + " = " + DUMMY_VALUE + "\n"
DUMMY_BLOCK = "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIB\n-----END " + "RSA PRIVATE KEY-----\n"


def run(*args, cwd=None):
    return subprocess.run(["bash", str(GUARD), *args], cwd=cwd, capture_output=True, text=True)


class Tree(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)
        (self.d / "ok.md").write_text("A normal file that mentions CADEX_LICENSE_FILE as a path variable.\n")

    def plant(self, rel, data=b"x"):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def test_clean_tree_passes(self):
        r = run("--tree", str(self.d))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_vendor_directory_refused(self):
        self.plant("vendor/cadex/CadExchanger-9.9.tar.gz")
        self.assertEqual(run("--tree", str(self.d)).returncode, 1)

    def test_binary_extensions_refused(self):
        for name in ("a.so", "b.dll", "c.exe", "d.deb", "e.rpm", "f.run", "g.msi", "h.dylib", "ODA-sdk.zip"):
            with self.subTest(name=name):
                self.plant("docker/x/" + name)
                self.assertEqual(run("--tree", str(self.d)).returncode, 1)
                (self.d / "docker/x" / name).unlink()

    def test_licence_file_names_refused(self):
        for name in ("cadex.lic", "oda.licence", "oda.license", "oda-activation.xml", "id.pem", "k.key", "k.p12"):
            with self.subTest(name=name):
                self.plant("secrets/" + name)
                self.assertEqual(run("--tree", str(self.d)).returncode, 1)
                (self.d / "secrets" / name).unlink()

    def test_repo_licence_file_is_not_a_licence_file(self):
        self.plant("LICENSE", "MIT\n")
        self.assertEqual(run("--tree", str(self.d)).returncode, 0)

    def test_key_shaped_assignment_refused_without_echo(self):
        self.plant("docs/x.md", DUMMY_ASSIGN)
        r = run("--tree", str(self.d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("docs/x.md", r.stdout + r.stderr)
        self.assertNotIn(DUMMY_VALUE, r.stdout + r.stderr)

    def test_private_key_block_refused(self):
        self.plant("a/b.txt", DUMMY_BLOCK)
        self.assertEqual(run("--tree", str(self.d)).returncode, 1)

    def test_prose_about_keys_passes(self):
        self.plant("docs/y.md", "The licence key is supplied at run time.\nlicence_key=<set at run time>\n")
        self.assertEqual(run("--tree", str(self.d)).returncode, 0)

    def test_this_repository_is_clean(self):
        r = run("--tree", str(ROOT))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Staged(unittest.TestCase):
    """The pre-commit hook refuses a commit that stages a planted dummy."""

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.d), "-c", "user.email=t@t", "-c", "user.name=t", *a],
                              capture_output=True, text=True)

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)
        self.git("init", "-q")
        (self.d / "tools").mkdir()
        (self.d / "tools" / "vendor_guard.sh").write_text(GUARD.read_text())
        (self.d / "tools" / "vendor-guard.patterns").write_text(PATTERNS.read_text())
        (self.d / ".githooks").mkdir()
        (self.d / ".githooks" / "pre-commit").write_text(HOOK.read_text())
        (self.d / ".githooks" / "pre-commit").chmod(0o755)
        self.git("config", "core.hooksPath", ".githooks")

    def test_commit_with_planted_key_is_refused(self):
        (self.d / "n.md").write_text(DUMMY_ASSIGN)
        self.git("add", "n.md")
        r = self.git("commit", "-qm", "x")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.git("rev-parse", "--verify", "HEAD").returncode != 0, True)

    def test_commit_of_clean_file_goes_through(self):
        (self.d / "n.md").write_text("hello\n")
        self.git("add", "n.md")
        self.assertEqual(self.git("commit", "-qm", "x").returncode, 0)

    def test_commit_with_vendor_path_is_refused(self):
        p = self.d / "vendor" / "oda"
        p.mkdir(parents=True)
        (p / "sdk.bin").write_bytes(b"x")
        self.git("add", "-f", "vendor")
        self.assertNotEqual(self.git("commit", "-qm", "x").returncode, 0)


class Documented(unittest.TestCase):
    def test_every_pattern_is_listed_in_the_archive_document(self):
        doc = ARCHIVE.read_text()
        lines = [l for l in PATTERNS.read_text().splitlines() if l.strip() and not l.startswith("#")]
        self.assertGreaterEqual(len(lines), 5)
        for l in lines:
            kind, pat = l.split(None, 1)
            self.assertIn(pat.strip(), doc, f"pattern not in docs/converters/archive.md: {l}")


if __name__ == "__main__":
    unittest.main()
