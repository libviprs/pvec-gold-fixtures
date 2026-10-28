"""Re-derive every frozen signature from its retained STEP file and prove it is the same, byte for byte.

    python3 -m runner.verify_signatures signatures [--evaluator step_eval]

This is the job that catches signature drift: an evaluator, normaliser or policy change that moves a value,
or a signature edited by hand. A difference is reported with the dotted path of every field that differs; a
byte difference with no differing field (spelling, order, whitespace) fails as "<bytes differ, no field
named>", so no difference is ever silent. Needs step_eval, so it runs in the step-validator image.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import normalize, numeric, signatures, verification

UNNAMED = "<bytes differ, no field named>"


def derive_with(evaluator):
    def derive(step):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "v.json"
            r = subprocess.run([evaluator, "--in", str(step), "--out", str(out), "--policy-version", numeric.load_policy().version],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("step_eval exited %d on %s: %s" % (r.returncode, step, r.stderr.strip()))
            return normalize.normalize(verification.load(out))
    return derive


def verify(root, derive):
    """{fixture: [differing field, ...]} for every fixture whose re-derived signature is not the frozen one."""
    root = Path(root)
    bad = {}
    for fx, rec in signatures.manifest(root)["fixtures"].items():
        frozen_bytes = (root / fx / "signature.json").read_bytes()
        diffs = []
        if signatures._sha(root / fx / "signature.json") != rec["signature_sha256"]:
            diffs.append("<signature.json does not match the manifest hash>")
        if signatures._sha(root / fx / "primary.step") != rec["step_sha256"]:
            diffs.append("<primary.step does not match the manifest hash>")
        fresh = derive(root / fx / "primary.step")
        if normalize.dumps(fresh).encode("ascii") != frozen_bytes:
            try:
                diffs += normalize.differing_fields(json.loads(frozen_bytes), fresh) or [UNNAMED]
            except ValueError:
                diffs.append(UNNAMED)
        if diffs:
            bad[fx] = diffs
    return bad


def main(argv, derive=None):
    ev = argv[argv.index("--evaluator") + 1] if "--evaluator" in argv else "step_eval"
    root = argv[0]
    bad = verify(root, derive or derive_with(ev))
    n = len(signatures.manifest(root)["fixtures"])
    for fx, fields in sorted(bad.items()):
        print("DRIFT %s: %s" % (fx, ", ".join(fields[:8]) + (" ..." if len(fields) > 8 else "")))
    print("%d of %d signatures re-derived identically" % (n - len(bad), n))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
