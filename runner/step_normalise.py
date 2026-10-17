"""Compare two STEP files byte for byte except for the named nondeterministic fields.

    python3 -m runner.step_normalise A.step B.step

The only field normalised by default is the FILE_NAME time stamp (its second argument). Anything
else a converter varies from run to run must be named in the qualification document and passed with
--also-regex, so the list of exceptions stays explicit.
"""
import re
import sys

FILE_NAME = re.compile(r"(FILE_NAME\s*\(\s*'[^']*'\s*,\s*)'[^']*'")


def normalise(text, extra=()):
    text = FILE_NAME.sub(r"\1'<TIMESTAMP>'", text)
    for rx, repl in extra:
        text = re.sub(rx, repl, text)
    return text


def same(a, b, extra=()):
    return normalise(a, extra) == normalise(b, extra)


if __name__ == "__main__":
    a, b = (open(p, encoding="utf-8", errors="replace").read() for p in sys.argv[1:3])
    extra = [(sys.argv[i + 1], "<NAMED>") for i, v in enumerate(sys.argv) if v == "--also-regex"]
    ok = same(a, b, extra)
    print("identical except the named fields" if ok else "differ beyond the named fields")
    sys.exit(0 if ok else 1)
