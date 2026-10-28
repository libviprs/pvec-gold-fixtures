#!/usr/bin/env python3
"""Run step_eval over the six self-test files and the 29 retained signature STEP files and keep the raw output.

    python3 validator/derive_set.py OUTDIR [--evaluator step_eval]

Writes OUTDIR/selftest/<name>.verification.json (what validator/compare_platforms.py diffs) and
OUTDIR/signatures/<fixture>.signature.json (what runner.normalize makes of the 29 retained STEP files).
Nothing here compares anything; run it once per image and architecture, then compare the directories.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from runner import normalize, numeric, verification  # noqa: E402


def main(argv):
    out = Path(argv[0])
    ev = argv[argv.index("--evaluator") + 1] if "--evaluator" in argv else "step_eval"
    ver = numeric.load_policy().version
    (out / "selftest").mkdir(parents=True, exist_ok=True)
    (out / "signatures").mkdir(parents=True, exist_ok=True)
    for step in sorted((ROOT / "fixtures" / "validator-selftest").glob("*.step")):
        dst = out / "selftest" / (step.stem + ".verification.json")
        subprocess.run([ev, "--in", str(step), "--out", str(dst), "--policy-version", ver], check=True)
    for step in sorted((ROOT / "signatures").glob("*/primary.step")):
        tmp = out / "signatures" / (step.parent.name + ".verification.json")
        subprocess.run([ev, "--in", str(step), "--out", str(tmp), "--policy-version", ver], check=True)
        (out / "signatures" / (step.parent.name + ".signature.json")).write_text(normalize.dumps(normalize.normalize(verification.load(tmp))), encoding="utf-8")
        tmp.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
