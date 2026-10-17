"""Writes docs/fixtures/examples/rational-bspline.expected.math.json from the parameters below.

The values are chosen by hand, in advance. Nothing here reads converter output.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runner.canon import scalar  # noqa: E402

PARAMS = {
    "degree": 2,
    "control_points": [["0", "0", "0"], ["1", "2", "0"], ["3", "2.5", "0"], ["4", "0", "0"]],
    "weights": ["1", "0.5", "2", "1"],
    "knots": [["0", 3], ["0.5", 1], ["1", 3]],
}


def pt(p):
    return [scalar(c) for c in p]


def build():
    doc = {
        "schema_version": "pvec-gold/expected.math/1",
        "fixture_id": "worked-example-rational-bspline",
        "evidence_class": "KNOWN_TRUTH_EXACT",
        "units": {"name": "metre", "canonical": "metre", "scale_to_canonical": scalar("1")},
        "provenance": {
            "derivation": "AUTHORING_PARAMETERS",
            "authoring_script": "tools/authoring/worked_example.py",
            "parameter_file": "tools/authoring/worked_example.py#PARAMS",
            "parameters": PARAMS,
            "notes": "Hand-chosen illustration for docs/fixtures/expected-math.md. The weights do not describe a conic.",
        },
        "entities": [
            {
                "id": "nurbs-0",
                "class": "nurbs",
                "structure": "CURVE_ONLY",
                "geometry": {
                    "degree": PARAMS["degree"],
                    "control_points": [pt(p) for p in PARAMS["control_points"]],
                    "knots": [{"value": scalar(v), "multiplicity": m} for v, m in PARAMS["knots"]],
                    "weights": [scalar(w) for w in PARAMS["weights"]],
                    "weights_all_unit": False,
                },
                "parameter_domain": {"start": scalar("0"), "end": scalar("1")},
                "closure": {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False},
            }
        ],
        "assertions": [
            {"id": "a1", "kind": "STRUCTURAL", "entity": "nurbs-0", "claim": "WEIGHTS_PRESERVED",
             "statement": "Weights 1, 0.5, 2, 1 survive as stated; a renormalised all-ones form is a different class."},
            {"id": "a2", "kind": "STRUCTURAL", "entity": "nurbs-0", "claim": "KNOTS_PRESERVED",
             "statement": "Knots 0 (x3), 0.5 (x1), 1 (x3) survive with multiplicities."},
            {"id": "a3", "kind": "GEOMETRIC", "entity": "nurbs-0", "claim": "PARAMETERIZATION_PRESERVED",
             "statement": "Domain [0, 1] is kept; a reparameterised equivalent is geometric-only."},
        ],
    }
    return doc


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
