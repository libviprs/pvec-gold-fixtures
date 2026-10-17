"""Validate a *.verification.json against validator/schema/verification.schema.json.

The verification schema points at the definitions in schema/expected.math.schema.json, so both
files are loaded into one registry and the shapes cannot drift apart.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from . import canon, expected_math as em

ROOT = Path(__file__).resolve().parent.parent
VERIFICATION_SCHEMA = ROOT / "validator" / "schema" / "verification.schema.json"


def _validator():
    exp = json.loads(em.SCHEMA_PATH.read_text(encoding="utf-8"))
    ver = json.loads(VERIFICATION_SCHEMA.read_text(encoding="utf-8"))
    reg = Registry().with_resources([(exp["$id"], Resource.from_contents(exp, DRAFT202012)),
                                     (ver["$id"], Resource.from_contents(ver, DRAFT202012))])
    return Draft202012Validator(ver, registry=reg)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, parse_float=em._no_floats, parse_constant=em._no_floats)


def validate_doc(doc):
    errs = ["schema: %s: %s" % ("/".join(str(p) for p in e.absolute_path), e.message) for e in _validator().iter_errors(doc)]
    if errs:
        return errs
    scalars = []
    em._walk_scalars(doc, "$", scalars)
    out = []
    for where, s in scalars:
        try:
            canon.check_scalar(s, where)
        except canon.CanonError as e:
            out.append(str(e))
    return out
