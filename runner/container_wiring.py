"""What the pvec corpus tests rely on to start the corpus container (libviprs/pvec-gold-fixtures#53).

    python3 -m runner.container_wiring check-pin corpus/container.pin.json [--strict]
    python3 -m runner.container_wiring check-layout corpus/r0-open
    python3 -m runner.container_wiring require-container

The pvec side starts the container (Container::start in crates/pvec-hermetic) and lives in that repository.
This side holds what it reads: the pin file naming each image by digest and the mount, the layout the
container finds under /corpus, and the check that a run without a usable container is red.

require-container exits 0 when `docker info` answers. When it does not, the exit is 1 (red) with the
reason, except for a developer run: PVEC_DEV_RUN=1 turns it into a printed SKIP and exit 0. The switch is
ignored when CI is set, so a CI run without Docker can never skip its way to green.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
CREDENTIAL = re.compile(r"licen[cs]e|key|token|secret|password|activation|credential", re.I)
ALLOWED = {"id", "image", "digest", "role"}


def pin_problems(doc, strict=False):
    out = []
    if doc.get("credentials") != "none":
        out.append('credentials must be "none": no credential is part of the pin')
    m = doc.get("mount") or {}
    if m.get("target") != "/corpus" or m.get("read_only") is not True:
        out.append("mount must target /corpus and be read_only")
    images = doc.get("images")
    if not isinstance(images, list) or not images:
        return out + ["images must list at least one image"]
    for i in images:
        n = i.get("id", "?")
        for k in i:
            if CREDENTIAL.search(k):
                out.append("image %s: field %r looks like a credential and has no place in a pin" % (n, k))
            elif k not in ALLOWED:
                out.append("image %s: unknown field %r" % (n, k))
        d = i.get("digest")
        if d is None:
            if strict:
                out.append("image %s: digest not pinned yet" % n)
        elif not DIGEST.fullmatch(str(d)):
            out.append("image %s: digest must be sha256:<64 hex>, not a tag (%r)" % (n, d))
    return out


def layout_problems(root):
    root = Path(root)
    out = []
    if not (root / "manifest.json").is_file():
        out.append("%s has no manifest.json" % root)
    fx = root / "fixtures"
    if not fx.is_dir():
        return out + ["%s has no fixtures/ directory" % root]
    for d in sorted(p for p in fx.iterdir() if p.is_dir()):
        if not (d / "source.dwg").is_file():
            out.append("fixtures/%s has no source.dwg" % d.name)
    return out


def container_state(docker, env):
    """(ok, message) for the require-container check."""
    try:
        r = subprocess.run([docker, "info"], capture_output=True, text=True, timeout=60)
        ok, why = r.returncode == 0, (r.stderr.strip().splitlines() or ["docker info failed"])[-1]
    except (OSError, subprocess.TimeoutExpired) as e:
        ok, why = False, str(e)
    if ok:
        return True, "container runtime available"
    if env.get("PVEC_DEV_RUN") == "1" and not env.get("CI"):
        return True, "SKIP: container unavailable (%s); skipped because PVEC_DEV_RUN=1, a developer run" % why
    return False, "container unavailable (%s): the corpus tests cannot run without it, so this run fails" % why


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "check-pin" and len(argv) >= 2:
        errs = pin_problems(json.loads(Path(argv[1]).read_text()), "--strict" in argv)
    elif cmd == "check-layout" and len(argv) == 2:
        errs = layout_problems(argv[1])
    elif cmd == "require-container":
        ok, msg = container_state(os.environ.get("DOCKER", "docker"), os.environ)
        print(msg)
        return 0 if ok else 1
    else:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    for e in errs:
        print("FAIL " + e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
