"""Build and verify the public release set of a corpus revision, with the standard library only.

    python3 -m runner.corpus_release build REPO_ROOT OUT_DIR     assemble the release
    python3 verify_release.py RELEASE_DIR                        verify one (this file is copied in as that name)

Downstream repositories pin the release and read it with no converter, no evaluator and no Docker, so
this file imports nothing outside the standard library and nothing from this repository. Verifying is
five named checks, listed in RELEASE_CHECKS; each failure line starts with the name of the check.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REVISION_DIR = Path("corpus") / "r1-open"
RELEASE_CHECKS = ("SHA256SUMS_VERIFY", "NO_PRIVATE_DWG", "NO_VENDOR_BINARY", "NO_LICENCE_MATERIAL", "SELF_CONTAINED_MANIFEST")
# Native code, by magic number: ELF, PE (MZ), Mach-O (thin and fat), and Java archives by suffix.
MAGIC = (b"\x7fELF", b"MZ", b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
BINARY_SUFFIXES = {".exe", ".dll", ".so", ".dylib", ".a", ".jar", ".o", ".node"}
LICENCE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(licen[cs]e|activation|serial|api|secret)[_ -]?(key|code|token)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{16,}", re.I),
)
PRIVATE = "PRIVATE"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def public_entry(entry):
    """What the release shows of a manifest entry. A PRIVATE fixture is its id and its hashes."""
    if entry.get("licence_verdict") != PRIVATE:
        return entry
    shown = {k: v for k, v in entry.items() if k != "artifacts"}
    shown["artifacts"] = {}
    shown["private_hashes"] = {name: a["sha256"] for name, a in entry["artifacts"].items()}
    return shown


def release_files(out):
    out = Path(out)
    return sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS")


def build_release(root, out):
    root, out = Path(root), Path(out)
    manifest = json.loads((root / REVISION_DIR / "manifest.json").read_text())
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shown = []
    for entry in manifest["fixtures"]:
        shown.append(public_entry(entry))
        for a in public_entry(entry)["artifacts"].values():
            dest = out / a["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / a["path"], dest)
    manifest["fixtures"] = shown
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for src, name in ((REVISION_DIR / "quarantine.json", "quarantine.json"), (Path("corpus") / "CHANGELOG.md", "CHANGELOG.md"),
                      (Path("corpus") / "provenance.json", "provenance.json"), (Path("corpus") / "capability-matrix.json", "capability-matrix.json")):
        if (root / src).is_file():
            shutil.copyfile(root / src, out / name)
    shutil.copyfile(__file__, out / "verify_release.py")
    lines = ["%s  %s" % (sha256(out / n), n) for n in release_files(out)]
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return manifest


def verify_release(out):
    out = Path(out)
    problems = []
    sums = {}
    sf = out / "SHA256SUMS"
    if not sf.is_file():
        return ["SHA256SUMS_VERIFY: no SHA256SUMS file"]
    for line in sf.read_text().splitlines():
        h, _, name = line.partition("  ")
        sums[name] = h
    for name, h in sums.items():
        f = out / name
        if not f.is_file():
            problems.append("SHA256SUMS_VERIFY: %s is listed and missing" % name)
        elif sha256(f) != h:
            problems.append("SHA256SUMS_VERIFY: %s does not match its hash" % name)
    files = release_files(out)
    for name in files:
        if name not in sums:
            problems.append("SHA256SUMS_VERIFY: %s is in the release and not in SHA256SUMS" % name)

    mf = out / "manifest.json"
    manifest = json.loads(mf.read_text()) if mf.is_file() else {"fixtures": []}
    public_paths = {a["path"] for e in manifest["fixtures"] if e.get("licence_verdict") != PRIVATE for a in e["artifacts"].values()}
    for e in manifest["fixtures"]:
        if e.get("licence_verdict") == PRIVATE and e["artifacts"]:
            problems.append("NO_PRIVATE_DWG: %s is PRIVATE and still lists artifacts" % e["id"])
        for name, a in e["artifacts"].items():
            p = Path(a["path"])
            if p.is_absolute() or ".." in p.parts or not (out / p).is_file():
                problems.append("SELF_CONTAINED_MANIFEST: %s.%s points at %s, which is not in the release" % (e["id"], name, a["path"]))
            elif sha256(out / p) != a["sha256"]:
                problems.append("SELF_CONTAINED_MANIFEST: %s.%s does not match its manifest hash" % (e["id"], name))
    for name in files:
        f = out / name
        suffix = f.suffix.lower()
        if suffix == ".dwg":
            if name not in public_paths:
                problems.append("NO_PRIVATE_DWG: %s is not a public artifact of any manifest entry" % name)
            continue
        head = f.read_bytes()[:8]
        if suffix in BINARY_SUFFIXES or any(head.startswith(m) for m in MAGIC):
            problems.append("NO_VENDOR_BINARY: %s looks like native code" % name)
            continue
        text = f.read_bytes().decode("utf-8", "replace")
        for pat in LICENCE_PATTERNS:
            if pat.search(text):
                problems.append("NO_LICENCE_MATERIAL: %s matches a licence or key pattern" % name)
                break
    return problems


def main(argv):
    if argv[:1] == ["build"] and len(argv) == 3:
        build_release(argv[1], argv[2])
        return 0
    if len(argv) == 1:
        problems = verify_release(argv[0])
        for p in problems:
            print(p)
        print("release OK" if not problems else "%d problem(s)" % len(problems))
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
