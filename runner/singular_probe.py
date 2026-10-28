"""singular-001: the probe whose DWG holds an INSERT scale of exactly 0.0 (issue 70).

    python3 -m runner.singular_probe assemble RUN_DIR [--libredwg-image ID]   build fixtures/edge/singular-001 from tools/corpus/singular/run.sh
    python3 -m runner.singular_probe check [ROOT]                              recompute the verdict from the stored read records

No writer of the r0-open pipeline can store this file: acadrust's checked setters rewrite the zero to 1e-12. The commit
named in tools/corpus/singular/tool/Cargo.toml has Insert::set_scale_unchecked and a DWG reader that keeps what the file
stores (libviprs/acadrust#52), and the ACadSharp reader runs with tools/converters/acadsharp/patches/0001. LibreDWG's
dwgdump needs nothing. The rule is writer_family's three-reader rule: every reader matches the authored record, every
reader decodes the same record as the first, and the scale is compared EXACT, so a reader that clamps fails it.
"""
import json
import re
import sys
from pathlib import Path

from . import numeric, writer_family as wf
from .r0_open import ROOT, dump_json, expected_path, load_json, params_path, sha256

FID = "singular-001"
READERS = ("acadrust", "acadsharp", "libredwg")
OWN = "acadsharp"   # the reader the other two are compared with, as in the r0-open cross-read
TOOL = Path("tools/corpus/singular")


def fixture(root=ROOT):
    return Path(root) / "fixtures" / "edge" / FID


def read_records(d):
    return {n: load_json(d / ("read.%s.json" % n)) for n in READERS}


def acadrust_pin(root=ROOT):
    m = (Path(root) / TOOL / "tool" / "Cargo.toml").read_text()
    return re.search(r'rev = "([0-9a-f]{40})"', m).group(1)


def readme(v, pin):
    return (
        "# singular-001\n\n"
        "A line under scale (1, 0, 1), determinant exactly 0. The authored outcome is rejection (`SINGULAR_TRANSFORM`, `REJECT`), "
        "and a pipeline that emits geometry for it fails. `expected.math.json` is the record I authored before any DWG "
        "existed (a copy of `fixtures/known-truth/transforms/singular-001`), and this drawing is the first one that holds it.\n\n"
        "A DWG stores an INSERT scale as a plain double, so the file can say 0.0. The writers refuse it: acadrust's setters "
        "rewrite it to 1e-12 and ACadSharp throws, which is why `r0-open` lists this probe as excluded (and still does). "
        "I wrote this file with acadrust at `%s` (`Insert::set_scale_unchecked`, libviprs/acadrust#52) through "
        "`tools/corpus/singular`, from the parameter file's own numbers. Two writes are byte-identical.\n\n"
        "Three readers decode it: acadrust at the same commit (its reader now keeps a stored zero), ACadSharp at `d7dc111` with "
        "`tools/converters/acadsharp/patches/0001-insert-keep-zero-scale.patch` (upstream master dropped the same guard), and "
        "LibreDWG's `dwgdump`. All three return the y scale as the bits `0x0000000000000000`, compared EXACT, and decode the "
        "same record, so the verdict is %s.\n\n"
        "Both converters refuse it with exit 15 and write no STEP: `acadsharp-dwg2step` as `SINGULAR_TRANSFORM` and "
        "`libredwg-dwg2step` as a singular INSERT matrix. The evidence is reader mapping and refusal only (`READER_MAPPING_ONLY`); "
        "a mapper must not emit a curve for this entity.\n" % (pin[:7], v["verdict"]))


def assemble(run, root=ROOT, libredwg_image=None):
    root, run = Path(root), Path(run)
    pol = numeric.load_policy()
    src, d = run / "run1", fixture(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.dwg").write_bytes((src / "source.dwg").read_bytes())
    (d / "expected.math.json").write_bytes(expected_path(FID).read_bytes())
    (d / "params.json").write_bytes(params_path(FID).read_bytes())
    recs = {}
    for n in READERS:
        recs[n] = load_json(src / ("%s.read.json" % n))
        dump_json(recs[n], d / ("read.%s.json" % n))
    v = wf.verdict(numeric.load_policy(), FID, "acadrust", OWN, recs)
    dump_json(wf.comparison_doc(pol, FID, v), d / "comparison.json")
    status = load_json(src / "libredwg-dwg2step.status.json")
    status["input"]["path"] = "source.dwg"
    dump_json(status, d / "libredwg-dwg2step.status.json")
    pin = acadrust_pin(root)
    writer = {
        "writer": recs["acadrust"]["reader"], "commit": pin, "tool": "acadrust DwgWriter, Insert::set_scale_unchecked (libviprs/acadrust#52)",
        "script": str(TOOL / "run.sh"), "dwg": {"sha256": sha256(d / "source.dwg"), "version": recs["acadsharp"]["dwg_version"]},
        "deterministic": "two writes from the parameter file are byte-identical",
        "readers": {"acadrust": {"reader": recs["acadrust"]["reader"], "commit": pin},
                    "acadsharp": {"reader": recs["acadsharp"]["reader"], "patch": "tools/converters/acadsharp/patches/0001-insert-keep-zero-scale.patch"},
                    "libredwg": {"reader": recs["libredwg"]["reader"], "image": libredwg_image or "pvec-oracle-libredwg, by local id, never built from this repository"}},
    }
    dump_json(writer, d / "writer.json")
    (d / "README.md").write_text(readme(v, pin))
    return v


def check(root=ROOT):
    root, d = Path(root), fixture(root)
    if not d.is_dir():
        return []
    pol, out = numeric.load_policy(), []
    recs = read_records(d)
    w = load_json(d / "writer.json")
    if w["dwg"]["sha256"] != sha256(d / "source.dwg"):
        out.append("singular-001: writer.json names a different DWG")
    for n, r in recs.items():
        if r["dwg_sha256"] != w["dwg"]["sha256"]:
            out.append("singular-001: the %s record is for a different DWG" % n)
    if w["commit"] != acadrust_pin(root) or w["commit"][:7] not in recs["acadrust"]["reader"]:
        out.append("singular-001: the acadrust commit in writer.json, Cargo.toml and the read record differ")
    v = wf.verdict(pol, FID, "acadrust", OWN, recs)
    if v["verdict"] != "AGREE":
        out.append("singular-001: the three readers do not agree: %s" % v["evidence"])
    if load_json(d / "comparison.json") != json.loads(json.dumps(wf.comparison_doc(pol, FID, v))):
        out.append("singular-001: comparison.json differs from the comparison recomputed from the read records")
    return out


def main(argv):
    if argv[:1] == ["assemble"] and len(argv) >= 2:
        img = argv[argv.index("--libredwg-image") + 1] if "--libredwg-image" in argv else None
        v = assemble(argv[1], libredwg_image=img)
        print(v["verdict"], v["evidence"] or "")
        return 0 if v["verdict"] == "AGREE" else 1
    if argv[:1] == ["check"]:
        problems = check(argv[1] if len(argv) > 1 else ROOT)
        print("\n".join(problems) or "singular-001 OK")
        return 1 if problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
