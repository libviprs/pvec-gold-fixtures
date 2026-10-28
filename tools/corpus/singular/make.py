#!/usr/bin/env python3
"""Write singular-001's DWG: scale (1, 0, 1), which no acadrust or ACadSharp writer will store.

    make.py --base near-singular-001/source.dwg --params singular-001.json --out source.dwg [--as r2004]

Runs inside the pvec-oracle-libredwg image (used by id or digest, never built from this repository). A DWG holds an
INSERT scale as a plain double, so the file can say 0.0. The only way I found to get that into a file is LibreDWG's
JSON round trip: dwgread turns the acadrust-written near-singular-001 drawing into JSON, I set the INSERT's scale to
the one the parameter file authors, and dwgwrite writes it back. Everything else in the drawing (the block, the line, the
layer) is near-singular-001's. dwgwrite writes R2004 or older, and R2004 is the version whose block headers list their
entities, which dwgdump and the converter read (an R2000 file lists them by first and last handle instead).
"""
import json
import os
import subprocess
import sys
import tempfile


def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("%s failed (%d): %s" % (cmd[0], r.returncode, r.stderr[-600:]))


def main(argv):
    args = dict(zip(argv[::2], argv[1::2]))
    base, params, out = args["--base"], args["--params"], args["--out"]
    version = args.get("--as", "r2004")
    want = [float(x) for x in json.load(open(params))["ops"][0]["s"]]
    with tempfile.TemporaryDirectory() as t:
        src, edited = os.path.join(t, "in.json"), os.path.join(t, "edited.json")
        sh("dwgread-exact", "-O", "JSON", "-o", src, base)
        tree = json.load(open(src))
        inserts = [o for o in tree["OBJECTS"] if o.get("entity") == "INSERT"]
        if len(inserts) != 1:
            sys.exit("expected one INSERT in %s, found %d" % (base, len(inserts)))
        inserts[0]["scale"] = want
        with open(edited, "w") as f:
            json.dump(tree, f)
        if os.path.lexists(out):
            os.remove(out)
        sh("dwgwrite-exact", "--as", version, "-o", out, edited)
    print("wrote %s: INSERT scale %r" % (out, want))


if __name__ == "__main__":
    main(sys.argv[1:])
