#!/usr/bin/env python3
"""Compare two validator/derive_set.py output directories (issue 75).

    python3 validator/spike_compare.py DIR_A DIR_B [--frozen signatures]

Self-test files: validator/compare_platforms.py on every f64_hex. The 29 signatures: how many are byte identical,
and for the rest the differing fields. With --frozen, each directory is also checked against the frozen signatures
the same way (bytes, then fields).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validator"))
from runner import normalize  # noqa: E402
import compare_platforms  # noqa: E402


def sigs(a, b, label):
    names = sorted(p.name for p in Path(a).glob("*.signature.json"))
    same, rows = 0, []
    for n in names:
        x, y = (Path(a) / n).read_bytes(), (Path(b) / n).read_bytes()
        if x == y:
            same += 1
        else:
            f = normalize.differing_fields(json.loads(x), json.loads(y))
            rows.append("  %s: %d fields, first %s" % (n.replace(".signature.json", ""), len(f), f[0] if f else "<bytes only>"))
    print("%s: %d of %d signatures byte identical" % (label, same, len(names)))
    print("\n".join(rows))


def main(argv):
    a, b = Path(argv[0]), Path(argv[1])
    print("== self-test (f64_hex on every value)")
    rc = compare_platforms.main(a / "selftest", b / "selftest")
    print("== signatures, A against B")
    sigs(a / "signatures", b / "signatures", "A vs B")
    if "--frozen" in argv:
        fz = Path(argv[argv.index("--frozen") + 1])
        for d, name in ((a, "A"), (b, "B")):
            tmp = Path(d) / "frozen"
            tmp.mkdir(exist_ok=True)
            for p in fz.glob("*/signature.json"):
                (tmp / (p.parent.name + ".signature.json")).write_bytes(p.read_bytes())
            sigs(tmp, d / "signatures", "frozen vs " + name)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
