"""Check policy/pvec-numeric-policy.*.json against a copy of pvec's docs/NUMERIC_POLICY.md.

    python3 -m runner.check_vendored_policy path/to/NUMERIC_POLICY.md

The document's constants table is the source. The vendored file must hold exactly those numbers and
the document's SHA-256, so a stale or hand-edited policy is caught. Nothing here sets a number.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

from . import numeric

ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*`([^`]+)`")


def parse_value(text):
    m = re.fullmatch(r"2\^(\d+)", text.strip())
    return float(2 ** int(m.group(1))) if m else float(text)


def table(doc_text):
    out = {}
    for line in doc_text.splitlines():
        m = ROW.match(line)
        if m and m.group(1) in numeric.REQUIRED:
            out[m.group(1)] = parse_value(m.group(2))
    return out


def check(doc_path, policy_path=None):
    errs = []
    raw = Path(doc_path).read_bytes()
    pol_path = policy_path or sorted(Path(numeric.POLICY_DIR).glob("pvec-numeric-policy.*.json"))[0]
    data = json.loads(Path(pol_path).read_text())
    if hashlib.sha256(raw).hexdigest() != data["source"]["document_sha256"]:
        errs.append("document_sha256 does not match the supplied NUMERIC_POLICY.md")
    want = table(raw.decode("utf-8"))
    for k in numeric.REQUIRED:
        if k not in want:
            errs.append("constant %s not found in the document table" % k)
        elif float(data["constants"].get(k, float("nan"))) != want[k]:
            errs.append("constant %s: vendored %r, document %r" % (k, data["constants"].get(k), want[k]))
    return errs


if __name__ == "__main__":
    e = check(sys.argv[1])
    for x in e:
        print("FAIL " + x)
    print("vendored policy matches the document" if not e else "%d problem(s)" % len(e))
    sys.exit(1 if e else 0)
