"""Report what changed when the adopted policy version is bumped.

    python3 -m runner.policy_bump OLD.json NEW.json

Each file is a list of {"fixture": id, "outcome": "ACCEPT" | "QUARANTINE" | ...} produced under one
policy version. The report is the counts of outcomes that changed, by transition, plus the fixtures.
"""
import json
import sys
from collections import Counter


def diff(old, new):
    o = {r["fixture"]: r["outcome"] for r in old}
    n = {r["fixture"]: r["outcome"] for r in new}
    changed = {f: (o.get(f), n.get(f)) for f in sorted(set(o) | set(n)) if o.get(f) != n.get(f)}
    return Counter(changed.values()), changed


if __name__ == "__main__":
    counts, changed = diff(json.loads(open(sys.argv[1]).read()), json.loads(open(sys.argv[2]).read()))
    for (a, b), c in sorted(counts.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        print("%s -> %s: %d" % (a, b, c))
    print("%d outcome(s) changed" % len(changed))
    for f, (a, b) in changed.items():
        print("  %s: %s -> %s" % (f, a, b))
