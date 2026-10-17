"""Fail when a floating-point tolerance literal appears outside policy/.

    python3 -m runner.check_tolerance_literals [root]

Python files are read with the ast module, so strings and comments are not matched: a float
constant smaller than one hundredth, or any numeric constant assigned to a name that says
eps/epsilon/tol/tolerance/ulp, is a finding. Other source files (C++, shell, YAML, Docker) are
matched with a regex after double-quoted strings are blanked. policy/ is the one place allowed to
hold a threshold, and .git is skipped.
"""
import ast
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "policy", "__pycache__", "node_modules"}
TEXT_EXT = {".cpp", ".cc", ".h", ".hpp", ".sh", ".yml", ".yaml", ".c"}
NAME_RE = re.compile(r"(^|_)(eps|epsilon|tol|tolerance|ulp)(_|$)", re.I)
EXP_RE = re.compile(r"(?<![\w.])\d+(\.\d+)?[eE]-\d+")
SMALL_DEC_RE = re.compile(r"(?<![\w.])0\.0\d+")
ASSIGN_RE = re.compile(r"\b\w*(eps|epsilon|tol|tolerance)\w*\s*[:=]\s*[-+]?[0-9.]", re.I)
SMALL = 1e-2  # a literal under this magnitude in code is treated as a candidate threshold


def _check_py(path, text):
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [(path, e.lineno or 0, "cannot parse")]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            v = abs(node.value)
            if v != 0.0 and v < SMALL:
                out.append((path, node.lineno, "small float literal %r" % node.value))
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.keyword)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign)
                       else [ast.Name(id=node.arg or "")])
            val = node.value
            if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)) and not isinstance(val.value, bool):
                for t in targets:
                    nm = t.id if isinstance(t, ast.Name) else getattr(t, "attr", "")
                    if nm and NAME_RE.search(nm) and val.value != 0:
                        out.append((path, node.lineno if hasattr(node, "lineno") else val.lineno, "numeric constant bound to %r" % nm))
    return out


def _check_text(path, text):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        code = re.sub(r'"(\\.|[^"\\])*"', '""', line)
        if EXP_RE.search(code) or SMALL_DEC_RE.search(code) or ASSIGN_RE.search(code):
            out.append((path, n, "tolerance-like literal"))
    return out


def scan(root):
    root = Path(root)
    findings = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        suffix = p.suffix.lower()
        if suffix == ".py":
            findings += _check_py(p, p.read_text(encoding="utf-8"))
        elif suffix in TEXT_EXT or p.name == "Dockerfile":
            findings += _check_text(p, p.read_text(encoding="utf-8", errors="replace"))
    return findings


def main(argv):
    root = argv[0] if argv else Path(__file__).resolve().parent.parent
    findings = scan(root)
    for p, n, why in findings:
        print("%s:%d: %s" % (p, n, why))
    if findings:
        print("%d tolerance literal(s) outside policy/" % len(findings))
        return 1
    print("no tolerance literals outside policy/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
