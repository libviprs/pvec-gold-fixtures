"""Fail if an artifact does not carry the adopted policy version.

    python3 -m runner.check_policy_stamp FILE...

Every comparison.json, *.verification.json and corpus manifest must have a top-level
numeric_policy_version equal to the version id in the vendored policy file.
"""
import json
from pathlib import Path
import sys

from . import numeric


def check(paths, pol=None):
    pol = pol or numeric.load_policy()
    bad = []
    for p in paths:
        try:
            v = json.loads(Path(p).read_text(encoding="utf-8")).get("numeric_policy_version")
        except (OSError, ValueError, AttributeError) as e:
            bad.append("%s: unreadable (%s)" % (p, e))
            continue
        if v != pol.version:
            bad.append("%s: numeric_policy_version %r, adopted %r" % (p, v, pol.version))
    return bad


if __name__ == "__main__":
    b = check(sys.argv[1:])
    for x in b:
        print("FAIL " + x)
    print("all artifacts carry the adopted policy version" if not b else "%d artifact(s) without it" % len(b))
    sys.exit(1 if b else 0)
