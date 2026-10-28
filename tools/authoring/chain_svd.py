#!/usr/bin/env python3
"""Factor the 2x2 part of an affine map into a block-INSERT chain: rotate, scale, rotate.

    python3 tools/authoring/chain_svd.py A B C D [TX TY]

A DWG INSERT stores a translation, one rotation about its normal and three scales, never a shear. A chain of
three INSERTs does carry any 2x2 matrix with a positive determinant, because A = R(t1) * diag(s1, s2) * R(t2)
is its singular value decomposition with both rotations proper. This prints the ops array for a parameter file
(an optional leading translate first), with every cosine, sine and scale to 40 significant digits. The numbers
are derived values: what a reader sees is the angle the writer stored, so the corpus compares them under
PVec numeric policy v1 and does not call them exact. Nothing here reads a DWG or a converter.
"""
import json
import sys

from mpmath import matrix, mp, mpf, svd_r, cos, sin, atan2

mp.dps = 80
DIGITS = 40


def dec(x):
    return mp.nstr(x, DIGITS, strip_zeros=True, min_fixed=-60, max_fixed=60)


def factor(a, b, c, d):
    """Returns (cos1, sin1, s1, s2, cos2, sin2) with [[a,b],[c,d]] = R(t1) diag(s1, s2) R(t2)."""
    m = matrix([[mpf(a), mpf(b)], [mpf(c), mpf(d)]])
    det = m[0, 0] * m[1, 1] - m[0, 1] * m[1, 0]
    if det <= 0:
        raise SystemExit("determinant %s is not positive: a reflection or a singular map needs another chain" % det)
    u, s, vt = svd_r(m)
    if u[0, 0] * u[1, 1] - u[0, 1] * u[1, 0] < 0:   # both factors improper: flip the second axis of each
        u[0, 1], u[1, 1] = -u[0, 1], -u[1, 1]
        vt[1, 0], vt[1, 1] = -vt[1, 0], -vt[1, 1]
    return u[0, 0], u[1, 0], s[0], s[1], vt[0, 0], vt[1, 0]


def chain_ops(a, b, c, d, translate=None):
    c1, s1, sx, sy, c2, s2 = factor(a, b, c, d)
    ops = []
    if translate:
        ops.append({"op": "translate", "v": [translate[0], translate[1], "0"], "classification": "TRANSLATION"})
    ops.append({"op": "rotate_z", "cos_sin": [dec(c1), dec(s1)], "classification": "ROTATION"})
    ops.append({"op": "scale", "s": [dec(sx), dec(sy), "1"], "classification": "NON_UNIFORM_SCALE"})
    ops.append({"op": "rotate_z", "cos_sin": [dec(c2), dec(s2)], "classification": "ROTATION"})
    return ops


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (4, 6):
        raise SystemExit(__doc__)
    print(json.dumps(chain_ops(*args[:4], translate=args[4:6] or None), indent=1))
