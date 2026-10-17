"""Canonical scalar representation for expected.math.json and *.verification.json.

A scalar is {"decimal": "<text>", "f64_hex": "0x<16 hex digits>"}. The hex is the intended
IEEE-754 binary64 and is authoritative. The decimal must parse, under correct
round-to-nearest, to exactly those bits. Python's float() parser is correctly rounded, so it
is the reference here.

This module holds no tolerance. It compares bits, nothing else.
"""
import math
import re
import struct
from decimal import Decimal
from fractions import Fraction

DECIMAL_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$")
HEX_RE = re.compile(r"^0x[0-9a-f]{16}$")


class CanonError(ValueError):
    pass


def f64_to_hex(x: float) -> str:
    return "0x%016x" % struct.unpack(">Q", struct.pack(">d", x))[0]


def hex_to_f64(h: str) -> float:
    if not HEX_RE.match(h):
        raise CanonError("f64_hex is not 0x plus 16 lowercase hex digits: %r" % (h,))
    return struct.unpack(">d", struct.pack(">Q", int(h, 16)))[0]


def scalar(x) -> dict:
    """Build a canonical scalar from a float, int, Fraction or decimal string.

    The decimal text is the shortest string that round-trips (repr), so it is also what a
    reader would print.
    """
    if isinstance(x, float):
        f = x
    elif isinstance(x, (int, Fraction, Decimal)):
        f = float(x)  # correctly rounded for all three
    elif isinstance(x, str):
        if not DECIMAL_RE.match(x):
            raise CanonError("not a decimal string: %r" % (x,))
        f = float(x)
    else:
        raise CanonError("cannot make a scalar from %r" % (type(x),))
    if not math.isfinite(f):
        raise CanonError("non-finite value")
    return {"decimal": repr(f), "f64_hex": f64_to_hex(f)}


def check_scalar(s, where="scalar") -> float:
    """Return the f64 a scalar denotes, or raise CanonError if decimal and hex disagree."""
    if not isinstance(s, dict) or set(s) != {"decimal", "f64_hex"}:
        raise CanonError("%s: a scalar is exactly {decimal, f64_hex}" % where)
    d, h = s["decimal"], s["f64_hex"]
    if not isinstance(d, str) or not DECIMAL_RE.match(d):
        raise CanonError("%s: decimal does not parse: %r" % (where, d))
    f = hex_to_f64(h)
    if not math.isfinite(f):
        raise CanonError("%s: non-finite f64_hex" % where)
    if f64_to_hex(float(d)) != h:
        raise CanonError(
            "%s: decimal %s rounds to %s, not the stated %s" % (where, d, f64_to_hex(float(d)), h)
        )
    return f


def exact(s) -> Fraction:
    """The exact rational value of a scalar's f64 (no rounding)."""
    return Fraction(check_scalar(s))
