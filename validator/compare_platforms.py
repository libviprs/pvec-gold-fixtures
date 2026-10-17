#!/usr/bin/env python3
"""Compare two directories of *.verification.json (say arm64 and native x64) on every f64_hex.

    python3 validator/compare_platforms.py DIR_A DIR_B

Prints each divergence with file, entity and field path and exits 1 if there is any. The tool
block (which names no platform) is skipped; everything else must agree bit for bit.
"""
import json
import sys
from pathlib import Path


def flat(node, path, out):
    if isinstance(node, dict):
        if set(node) == {"decimal", "f64_hex"}:
            out[path] = node["f64_hex"]
            return
        for k, v in node.items():
            flat(v, "%s.%s" % (path, k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            flat(v, "%s[%d]" % (path, i), out)
    else:
        out[path] = node


def main(a, b):
    bad = total = 0
    for fa in sorted(Path(a).glob("*.verification.json")):
        fb = Path(b) / fa.name
        if not fb.exists():
            print("missing in B: %s" % fa.name)
            bad += 1
            continue
        x, y = {}, {}
        flat(json.loads(fa.read_text()), "", x)
        flat(json.loads(fb.read_text()), "", y)
        for k in sorted(set(x) | set(y)):
            total += k.endswith("]") or True
            if x.get(k) != y.get(k):
                print("%s %s: %s != %s" % (fa.name, k, x.get(k), y.get(k)))
                bad += 1
    print("%d values compared, %d diverge" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
