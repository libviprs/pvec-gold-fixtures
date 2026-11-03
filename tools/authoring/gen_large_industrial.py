#!/usr/bin/env python3
"""Generate the large industrial drawing's entity list (issue 96), so it never has to be committed.

    gen_large_industrial.py --count 1000000 --out large-industrial-001.json [--seed 96]

The output is plain JSON, `{"fixture_id", "seed", "count", "units", "entities": [...]}`, and it is a pure
function of (seed, count): the same arguments give the same bytes. Entities come from an integer linear
congruential generator, so there is no float arithmetic and no platform dependence. Coordinates are whole
millimetres. The mix is what a plant drawing looks like: mostly short pipe-run lines, then circles (valves and
nozzles), arcs (elbows) and short polylines (cable trays), laid out on a 2 km by 1 km site grid. Nothing here
comes from a vendor drawing or from any real plant.

Writing a DWG from this list is the open writer's job (tools/r0-open/rust), at the size the consumer asks for.
"""
import argparse
import json
import sys

M = 2 ** 64
A = 6364136223846793005
C = 1442695040888963407
SITE_X, SITE_Y = 2_000_000, 1_000_000  # millimetres


def lcg(seed):
    x = seed % M
    while True:
        x = (x * A + C) % M
        yield x >> 33  # the high bits are the good ones


def entities(count, seed):
    r = lcg(seed)
    for i in range(count):
        kind = next(r) % 100
        x, y = next(r) % SITE_X, next(r) % SITE_Y
        if kind < 70:
            dx, dy = next(r) % 4001 - 2000, next(r) % 4001 - 2000
            yield {"id": i, "class": "line", "layer": "PIPE", "start": [x, y], "end": [x + dx, y + dy]}
        elif kind < 85:
            yield {"id": i, "class": "circle", "layer": "VALVE", "center": [x, y], "radius": 50 + next(r) % 450}
        elif kind < 95:
            yield {"id": i, "class": "arc", "layer": "ELBOW", "center": [x, y], "radius": 100 + next(r) % 900,
                   "start_deg": next(r) % 360, "sweep_deg": 30 + next(r) % 150}
        else:
            pts = [[x, y]]
            for _ in range(2 + next(r) % 4):
                px, py = pts[-1]
                pts.append([px + next(r) % 3001 - 1500, py + next(r) % 3001 - 1500])
            yield {"id": i, "class": "polyline", "layer": "TRAY", "vertices": pts}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=96)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.count < 1:
        ap.error("--count must be at least 1")
    with open(a.out, "w", encoding="utf-8") as f:
        head = {"fixture_id": "large-industrial-001", "seed": a.seed, "count": a.count, "units": "millimetre"}
        f.write(json.dumps(head, separators=(",", ":"))[:-1] + ',"entities":[')
        for i, e in enumerate(entities(a.count, a.seed)):
            if i:
                f.write(",")
            f.write(json.dumps(e, separators=(",", ":")))
        f.write("]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
