#!/usr/bin/env python3
"""Author the r0-open probes as LibreDWG JSON, for dwgwrite to turn into R2000 or R2004 DWGs.

    author.py --skeleton skeleton.json --kt DIR --params DIR --out DIR --dwgwrite BIN --as r2000|r2004 --writer ID --version ACnnnn [--only ID]

Run inside the LibreDWG image as its own process, with this repository mounted; the image is GPL and nothing of it is
imported here, the two only exchange files. The skeleton is the JSON that dwgread writes for an empty drawing of the
target version (tables, dictionaries, layouts, header). Every entity comes from the same two places the other writers
use and from nowhere else: the f64_hex fields of the authored expected.math.json records, and for the transform ops the
decimal strings of the parameter files. Python prints a float with the shortest text that parses back to the same
binary64, and LibreDWG parses it with strtod, so the authored bits reach the file without a trip through DXF decimals.
A probe that cannot be stored exactly is reported SKIPPED with the reason and no JSON is written.
"""
import copy
import hashlib
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

TAU = 2 * math.pi


class Skip(Exception):
    def __init__(self, reason, evidence):
        super().__init__(evidence)
        self.reason, self.evidence = reason, evidence


def fx(v):
    return struct.unpack(">d", bytes.fromhex(v["f64_hex"][2:].rjust(16, "0")))[0]


def p3(v):
    return [fx(c) for c in v]


def dec(s):
    return float(s)


def ref(code, n):
    return [code, max(1, (n.bit_length() + 7) // 8), n, n]


def own(n):
    return [0, max(1, (n.bit_length() + 7) // 8), n]


NULL_REF = [4, 0, 0, 0]
# the properties every entity of the skeleton's own LINE carries besides its geometry
COMMON = ("_subclass", "layer", "preview_exists", "entmode", "nolinks", "is_xdic_missing", "has_ds_data", "color", "ltype_scale",
          "ltype_flags", "plotstyle_flags", "material_flags", "shadow_flags", "has_full_visualstyle", "has_face_visualstyle",
          "has_edge_visualstyle", "invisible", "linewt")


class Drawing:
    def __init__(self, skeleton):
        self.j = copy.deepcopy(skeleton)
        self.version = self.j["FILEHEADER"]["version"]
        self.old = self.version == "AC1015"
        objs = self.j["OBJECTS"]
        line = [o for o in objs if o.get("entity") == "LINE"][0]
        self.common = {k: line[k] for k in COMMON if k in line}
        self.layer0 = list(line["layer"])
        objs.remove(line)
        self.ms = [o for o in objs if o.get("object") == "BLOCK_HEADER" and o["name"] == "*Model_Space"][0]
        for k in ("entities", "first_entity", "last_entity"):
            self.ms.pop(k, None)
        if not self.old:
            self.ms["entities"] = []
        self.next = max(o["handle"][2] for o in objs) + 1
        self.block_control = [o for o in objs if o.get("object") == "BLOCK_CONTROL"][0]
        self.layer_control = [o for o in objs if o.get("object") == "LAYER_CONTROL"][0]
        self.layer_obj = [o for o in objs if o.get("object") == "LAYER" and o["name"] == "0"][0]
        self.tail = [o for o in objs if o.get("object") == "VX_CONTROL"]
        for t in self.tail:
            objs.remove(t)
        self.blocks = {}  # block header handle -> (header object, [entity objects in order])
        self.model = []

    def handle(self):
        h = self.next
        self.next += 1
        return h

    def entity(self, kind, number, fields, owner_block=None, in_block=False, **extra):
        h = self.handle()
        o = {"entity": kind, "index": 0, "type": number, "handle": own(h), "size": 0, "bitsize": 0}
        o.update(copy.deepcopy(self.common))
        if in_block:
            o["ownerhandle"] = ref(4, owner_block)
            o["entmode"] = 0
        else:
            o["entmode"] = 2
        o.update(fields)
        o.update(extra)
        return o

    def add_layer(self, name, on, frozen):
        h = self.handle()
        lay = copy.deepcopy(self.layer_obj)
        lay["handle"] = own(h)
        lay["name"] = name
        flag = lay["flag0"] & ~3
        if not on:
            flag |= 2
        if frozen:
            flag |= 1
        lay["flag0"] = flag
        lay["index"] = 0
        self.j["OBJECTS"].append(lay)
        self.layer_control["entries"].append(ref(2, h))
        return ref(5, h)

    def place(self, objs, block_handle=None):
        """Put top-level entities (the first of objs is the entity, the rest its children) into model space or a block."""
        if block_handle is None:
            self.model.append(objs)
        else:
            self.blocks[block_handle][1].append(objs)

    def finish(self):
        objs = self.j["OBJECTS"]

        def link(chain, header, in_block):
            tops = [c[0] for c in chain]
            if self.old:
                for i, t in enumerate(tops):
                    t["prev_entity"] = ref(4, tops[i - 1]["handle"][2]) if i else NULL_REF
                    t["next_entity"] = ref(4, tops[i + 1]["handle"][2]) if i + 1 < len(tops) else NULL_REF
                if tops:
                    header["first_entity"] = ref(4, tops[0]["handle"][2])
                    header["last_entity"] = ref(4, tops[-1]["handle"][2])
            else:
                header["entities"] = [ref(3, t["handle"][2]) for t in tops]
            for c in chain:
                objs.extend(c)

        for h, (bh, chain) in self.blocks.items():
            link(chain, bh, True)
        link(self.model, self.ms, False)
        objs.extend(self.tail)
        for i, o in enumerate(objs):
            o["index"] = i
        self.j["HEADER"]["HANDSEED"] = ref(0, self.next)
        return self.j

    def new_block(self, name):
        bh, bk, eb = self.handle(), self.handle(), self.handle()
        hdr = {k: copy.deepcopy(v) for k, v in self.ms.items() if k not in ("handle", "name", "entities", "first_entity", "last_entity", "block_entity", "endblk_entity", "layout", "index", "size", "bitsize")}
        hdr.update({"object": "BLOCK_HEADER", "index": 0, "type": 49, "handle": own(bh), "size": 0, "bitsize": 0, "name": name,
                    "block_entity": ref(3, bk), "endblk_entity": ref(3, eb), "layout": [5, 0, 0, 0], "inserts": []})
        blk = self.entity("BLOCK", 4, {"_subclass": "AcDbBlockBegin", "name": name}, owner_block=bh, in_block=True)
        blk["handle"] = own(bk)
        self.j["OBJECTS"].extend([hdr, blk])
        end = self.entity("ENDBLK", 5, {"_subclass": "AcDbBlockEnd"}, owner_block=bh, in_block=True)
        end["handle"] = own(eb)
        self.j["OBJECTS"].append(end)
        # the handle counter moved on for the entity() calls above; the block objects keep the three handles taken first
        self.block_control.setdefault("entries", []).append(ref(2, bh))
        self.blocks[bh] = (hdr, [])
        return bh


def make_curve(d, e, dwg_entity, block=None, layer=None):
    cls = e["class"]
    g, cl = e["geometry"], e["closure"]
    ib = block is not None
    kw = {"owner_block": block, "in_block": ib}
    extra = {"layer": layer} if layer else {}
    if cls == "line":
        a, b = p3(g["start"]), p3(g["end"])
        return [d.entity("LINE", 19, {"_subclass": "AcDbLine", "z_is_zero": int(a[2] == 0 and b[2] == 0), "start": a, "end": b, "thickness": 0.0, "extrusion": [0.0, 0.0, 1.0]}, **kw, **extra)]
    if cls in ("circle", "circular_arc"):
        n, x = p3(g["normal"]), p3(g["x_axis"])
        if not (n == [0.0, 0.0, 1.0] and x == [1.0, 0.0, 0.0]):
            raise Skip("UNSUPPORTED_ENTITY", "the probe's x_axis is not the DWG arbitrary-axis default, and a DWG circle or arc cannot carry one")
        if cls == "circle":
            return [d.entity("CIRCLE", 18, {"_subclass": "AcDbCircle", "center": p3(g["center"]), "radius": fx(g["radius"]), "thickness": 0.0, "extrusion": n}, **kw, **extra)]
        s = fx(g["start_angle"])
        t = s + fx(g["sweep_angle"])
        if not 0.0 <= s < TAU:
            raise Skip("UNSUPPORTED_ENTITY", "start angle outside [0, 2pi)")
        if t >= TAU:
            t -= TAU
        return [d.entity("ARC", 17, {"_subclass": "AcDbArc", "center": p3(g["center"]), "radius": fx(g["radius"]), "thickness": 0.0, "extrusion": n, "start_angle": s, "end_angle": t}, **kw, **extra)]
    if cls in ("ellipse", "elliptical_arc"):
        m, a, b = p3(g["major_axis"]), fx(g["semi_major"]), fx(g["semi_minor"])
        s, t = 0.0, TAU
        if cls == "elliptical_arc":
            s = fx(g["start_angle"])
            t = s + fx(g["sweep_angle"])
        return [d.entity("ELLIPSE", 35, {"_subclass": "AcDbEllipse", "center": p3(g["center"]), "sm_axis": [c * a for c in m], "extrusion": p3(g["normal"]),
                                         "axis_ratio": b / a, "start_angle": s, "end_angle": t}, **kw, **extra)]
    if cls == "polyline":
        vs, bs = [p3(v) for v in g["vertices"]], [fx(b) for b in g["bulges"]]
        z0 = vs[0][2]
        if any(v[2] != z0 for v in vs):
            raise Skip("UNSUPPORTED_ENTITY", "an LWPOLYLINE has one elevation, the probe's vertices have different z")
        closed = cl["closed_by_endpoint"]
        if dwg_entity == "POLYLINE":
            pl = d.entity("POLYLINE_2D", 15, {"_subclass": "AcDb2dPolyline", "flag": 1 if closed else 0, "curve_type": 0, "start_width": 0.0, "end_width": 0.0, "thickness": 0.0,
                                              "elevation": z0, "extrusion": [0.0, 0.0, 1.0]}, **kw, **extra)
            kids = []
            for v, b in zip(vs, bs):
                kids.append(d.entity("VERTEX_2D", 10, {"_subclass": "AcDb2dVertex", "flag": 0, "point": [v[0], v[1], 0.0], "bulge": b, "tangent_dir": 0.0},
                                     owner_block=pl["handle"][2], in_block=True, **extra))
            sq = d.entity("SEQEND", 6, {"_subclass": "AcDbEntity"}, owner_block=pl["handle"][2], in_block=True, **extra)
            if d.old:
                pl["first_vertex"], pl["last_vertex"] = ref(4, kids[0]["handle"][2]), ref(4, kids[-1]["handle"][2])
                for i, k in enumerate(kids):  # R2000 walks the vertices through their links
                    k["prev_entity"] = ref(4, kids[i - 1]["handle"][2]) if i else NULL_REF
                    k["next_entity"] = ref(4, kids[i + 1]["handle"][2]) if i + 1 < len(kids) else NULL_REF
            else:
                pl["vertex"] = [ref(3, k["handle"][2]) for k in kids]
            pl["seqend"] = ref(3, sq["handle"][2])
            return [pl] + kids + [sq]
        f = {"_subclass": "AcDbPolyline", "flag": (512 if closed else 0) | (16 if any(bs) else 0), "points": [[v[0], v[1]] for v in vs], "bulges": bs if any(bs) else []}
        if z0 != 0.0:
            f["flag"] |= 8
            f["elevation"] = z0
        return [d.entity("LWPOLYLINE", 77, f, **kw, **extra)]
    if cls in ("bezier", "bspline", "nurbs"):
        degree = g["degree"]
        cps = [p3(c) for c in g["control_points"]]
        if cls == "bezier":
            knots = [fx(e["parameter_domain"]["start"])] * (degree + 1) + [fx(e["parameter_domain"]["end"])] * (degree + 1)
        else:
            knots = [fx(k["value"]) for k in g["knots"] for _ in range(k["multiplicity"])]
        nurbs = cls == "nurbs"
        pts = [{"x": c[0], "y": c[1], "z": c[2], **({"w": fx(w)} if nurbs else {})} for c, w in zip(cps, g["weights"] if nurbs else cps)]
        return [d.entity("SPLINE", 36, {"_subclass": "AcDbSpline", "scenario": 1, "degree": degree, "rational": int(nurbs), "closed_b": int(cl["closed_by_knots"]),
                                        "periodic": int(cl["periodic"]), "knot_tol": 1e-07, "ctrl_tol": 1e-07, "weighted": int(nurbs), "knots": knots, "ctrl_pts": pts},
                         **kw, **extra)]
    raise Skip("UNSUPPORTED_ENTITY", "no DWG form written for class " + cls)


def parse_ops(params):
    ops = []
    for o in params["ops"]:
        k = o["op"]
        if k == "translate":
            ops.append((k, [dec(c) for c in o["v"]]))
        elif k == "scale":
            ops.append((k, [dec(c) for c in o["s"]]))
        elif k == "rotate_z":
            if "angle_rad" in o:
                ang = dec(o["angle_rad"])
            else:
                ang = math.atan2(dec(o["cos_sin"][1]), dec(o["cos_sin"][0]))
            ops.append((k, [ang, 0.0, 0.0]))
        else:
            raise Skip("UNSUPPORTED_ENTITY", "op '%s' (a general matrix) has no single INSERT form: one INSERT carries translation, one rotation about the normal and three scales, and no shear. "
                       "A three-level nested INSERT chain could carry its 2x2 part through a singular value decomposition, but those factors would be derived values compared under policy "
                       "and not EXACT, and the probe's own truth is a rejection outcome that no reader-mapping check can exercise, so that was not attempted" % k)
    return ops


def insert_fields(group):
    ins = {"ins_pt": [0.0, 0.0, 0.0], "scale_flag": 3, "scale": [1.0, 1.0, 1.0], "rotation": 0.0, "extrusion": [0.0, 0.0, 1.0], "has_attribs": 0}
    rank = 0
    for kind, v in group:
        r = {"translate": 0, "rotate_z": 1}.get(kind, 2)
        if r < rank:
            raise Skip("UNSUPPORTED_ENTITY", "ops are not in translate, rotate, scale order, which is the only order one INSERT composes")
        rank = r
        if kind == "translate":
            ins["ins_pt"] = v
        elif kind == "rotate_z":
            ins["rotation"] = v[0]
        else:
            if 0.0 in v:
                raise Skip("UNSUPPORTED_ENTITY", "a zero scale is not authored in this family: singular-001 is the job of the zero-scale probe, as in r0-open")
            ins["scale"] = v
            ins["scale_flag"] = 3 if v == [1.0, 1.0, 1.0] else 2 if v[0] == v[1] == v[2] else 0
    return ins


def build(d, pid, expected, params):
    ents = expected["entities"]
    ent = ents[0]
    de = params.get("dwg_entity")
    if "layer" in ent:
        for e in ents:
            l = e["layer"]
            lay = d.add_layer(l["name"], l["on"], l["frozen"])
            d.place(make_curve(d, e, None, layer=lay))
        return
    curve_ent = ent
    if ent["structure"] == "CURVE_ONLY":
        d.place(make_curve(d, curve_ent, de))
        return
    ops = parse_ops(params)
    groups = [[o] for o in ops] if len(ops) > 1 else [ops]
    stem = "PROBE_" + pid.replace("-", "_").upper()
    handles = [d.new_block("%s_L%d" % (stem, i + 1)) for i in range(len(groups))]
    d.place(make_curve(d, curve_ent, de, block=handles[-1]), handles[-1])
    for i, grp in enumerate(groups):
        f = insert_fields(grp)
        f.update({"_subclass": "AcDbBlockReference", "block_header": ref(5, handles[i])})
        owner = handles[i - 1] if i else None
        ins = d.entity("INSERT", 7, f, owner_block=owner, in_block=owner is not None)
        d.blocks[handles[i]][0]["inserts"].append(ref(4, ins["handle"][2]))
        d.place([ins], owner)


def find(root, name):
    return next(p for p in Path(root).rglob(name))


def main(argv):
    a = dict(zip(argv[::2], argv[1::2]))
    skeleton = json.loads(Path(a["--skeleton"]).read_text())
    out = Path(a["--out"])
    out.mkdir(parents=True, exist_ok=True)
    ids = sorted((json.loads(f.read_text())["id"], f) for f in Path(a["--params"]).rglob("*.json"))
    report = []
    for pid, pf in ids:
        if a.get("--only") not in (None, pid):
            continue
        params = json.loads(pf.read_text())
        exp = json.loads(next(p for p in Path(a["--kt"]).rglob("expected.math.json") if p.parent.name == pid).read_text())
        d = Drawing(skeleton)
        try:
            build(d, pid, exp, params)
        except Skip as s:
            report.append({"id": pid, "status": "SKIPPED", "reason": s.reason, "evidence": s.evidence})
            continue
        (out / pid).mkdir(exist_ok=True)
        src, dwg = out / pid / "authored.json", out / pid / "source.dwg"
        src.write_text(json.dumps(d.finish(), indent=1) + "\n")
        # dwgwrite is the LibreDWG tool; it refuses r2007 and writes r2010 and later with failing checks, so only r2000 and r2004 are asked for.
        r = subprocess.run([a["--dwgwrite"], "--as", a["--as"], "-I", "JSON", "-y", "-o", str(dwg), str(src)], capture_output=True, text=True)
        if r.returncode or not dwg.is_file():
            report.append({"id": pid, "status": "SKIPPED", "reason": "MALFORMED_FIXTURE", "evidence": "dwgwrite: " + (r.stderr or r.stdout).strip()[-300:]})
            continue
        data = dwg.read_bytes()
        if data[:6].decode("ascii", "replace") != a["--version"]:
            # dwgwrite exits 0 and writes a different version when it cannot write the one asked for (r2007 comes out as AC1024)
            report.append({"id": pid, "status": "SKIPPED", "reason": "MALFORMED_FIXTURE",
                           "evidence": "dwgwrite wrote %s when %s was asked for" % (data[:6].decode("ascii", "replace"), a["--version"])})
            dwg.unlink()
            continue
        report.append({"id": pid, "status": "WRITTEN", "dwg_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    rep = {"writer": a["--writer"], "dwg_version": a["--version"], "fixtures": report}
    (out / "write-report.json").write_text(json.dumps(rep, indent=2) + "\n")
    print("%d written, %d skipped" % (sum(r["status"] == "WRITTEN" for r in report), sum(r["status"] == "SKIPPED" for r in report)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
