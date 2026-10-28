"""Issue #15: structural-exactness and geometric-equivalence reports, and the converter classification.

Everything here reads signatures (pvec-gold/signature/1) and expected.math.json, never STEP text. A
signature for a fixture is made from its expected record with the normaliser's own helpers, so the
"produced" side is a real signature shape; the mutations below then break one thing at a time.
"""
import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner import canon, expected_math as em, normalize, numeric

ROOT = Path(__file__).resolve().parent.parent
POL = numeric.load_policy()
MICRO, MILLI, TINY = 1.0 / 10 ** 6, 1.0 / 10 ** 3, 1.0 / 10 ** 13   # test moves, not thresholds
KT = ROOT / "fixtures" / "known-truth"
CONVERTERS = [
    {"id": "acadsharp-dwg2step", "version": "1.0.0", "lineage": "acadsharp", "image_digest": "sha256:" + "a" * 64},
    {"id": "libredwg-dwg2step", "version": "1.0.0", "lineage": "libredwg", "image_digest": "sha256:" + "b" * 64},
]


def expected(fid):
    return em.load(next(KT.rglob(fid + "/expected.math.json")))


def identity():
    m = [1.0 if i in (0, 5, 10, 15) else 0.0 for i in range(16)]
    return {"convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": [canon.scalar(x) for x in m],
            "determinant": canon.scalar(1.0), "classification": "IDENTITY"}


def signature(fid):
    """The signature a perfect converter would give for this fixture."""
    doc = expected(fid)
    k = canon.check_scalar(doc["units"]["scale_to_canonical"])
    ents = []
    for e in doc["entities"]:
        rec = {x: copy.deepcopy(e[x]) for x in ("class", "structure", "geometry", "parameter_domain", "closure")}
        t = e.get("transform") or (e.get("transform_chain") or {}).get("composed")
        rec["transform"] = copy.deepcopy(t) if t else identity()
        rec["samples"] = []
        ents.append(normalize._entity(rec, k))
    ents.sort(key=normalize.sort_key)
    return {"schema_version": normalize.SCHEMA_VERSION, "units": {"canonical": "metre"}, "entities": ents,
            "versions": {"evaluator": "1", "occt": "7.6.3", "schema": normalize.SCHEMA_VERSION, "policy": POL.version}}


def scal(x):
    return normalize.stored(x)


def sc(s):
    return canon.hex_to_f64(s["f64_hex"])


def st():
    from runner import compare_structural
    return compare_structural


def ge():
    from runner import compare_geometric
    return compare_geometric


def cv():
    from runner import compare_converters
    return compare_converters


def field(rep, name):
    return [f for e in rep["entities"] for f in e["fields"] if f["field"] == name]


def non_match(rep):
    return [f for e in rep["entities"] for f in e["fields"] if f["verdict"] != "MATCH"]


def renormalise_weights(sig):
    """Divide every weight by the largest one: the same rational curve, written with different weights."""
    out = copy.deepcopy(sig)
    g = out["entities"][0]["geometry"]
    top = max(sc(w) for w in g["weights"])
    g["weights"] = [scal(sc(w) / top) for w in g["weights"]]
    return out


class Structural(unittest.TestCase):
    def test_a_perfect_signature_is_structurally_exact(self):
        for fid in ("line-001", "circle-001", "bspline-d3-001", "nonunit-weight-001", "translation-001"):
            rep = st().compare(POL, expected(fid), signature(fid))
            self.assertEqual(rep["class"], "STRUCTURAL_EXACT", fid)
            self.assertEqual(non_match(rep), [], fid)

    def test_flipping_one_knot_multiplicity_turns_it_red(self):
        sig = signature("bspline-d3-001")
        sig["entities"][0]["geometry"]["knots"][1]["multiplicity"] = 2
        rep = st().compare(POL, expected("bspline-d3-001"), sig)
        self.assertEqual(rep["class"], "STRUCTURAL_DIFFERS")
        (f,) = [f for f in non_match(rep) if f["field"] == "geometry.knots[1].multiplicity"]
        self.assertEqual((f["verdict"], f["expected"], f["produced"]), ("DIFFERENT", 1, 2))

    def test_changing_degree_three_to_five_turns_it_red(self):
        sig = signature("bspline-d3-001")
        sig["entities"][0]["geometry"]["degree"] = 5
        rep = st().compare(POL, expected("bspline-d3-001"), sig)
        self.assertEqual(rep["class"], "STRUCTURAL_DIFFERS")
        (f,) = field(rep, "geometry.degree")
        self.assertEqual((f["verdict"], f["expected"], f["produced"]), ("DIFFERENT", 3, 5))

    def test_renormalised_weights_are_never_structurally_exact(self):
        exp, sig = expected("nonunit-weight-001"), renormalise_weights(signature("nonunit-weight-001"))
        geo = ge().compare(POL, exp, sig)
        self.assertEqual(geo["class"], "GEOMETRIC_EXACT_REPARAMETERIZED")   # the geometry does match
        rep = st().compare(POL, exp, sig, geometric=geo)
        self.assertNotEqual(rep["class"], "STRUCTURAL_EXACT")
        self.assertEqual(rep["class"], "STRUCTURAL_DIFFERS")
        weights = [f for f in rep["entities"][0]["fields"] if f["field"].startswith("geometry.weights[") and f["verdict"] != "MATCH"]
        self.assertTrue(weights)
        self.assertEqual({f["verdict"] for f in weights}, {"REPARAMETERIZED"})

    def test_without_the_geometric_report_the_changed_fields_stay_different(self):
        sig = renormalise_weights(signature("nonunit-weight-001"))
        rep = st().compare(POL, expected("nonunit-weight-001"), sig)
        self.assertEqual({f["verdict"] for f in non_match(rep)}, {"DIFFERENT"})

    def test_every_non_match_names_the_field_and_both_values(self):
        sig = signature("bspline-d3-001")
        g = sig["entities"][0]["geometry"]
        g["control_points"][2][1] = scal(sc(g["control_points"][2][1]) + 0.5)
        rep = st().compare(POL, expected("bspline-d3-001"), sig)
        bad = non_match(rep)
        self.assertEqual([f["field"] for f in bad], ["geometry.control_points[2][1]"])
        f = bad[0]
        self.assertEqual(set(f["expected"]), {"decimal", "f64_hex"})
        self.assertEqual(set(f["produced"]), {"decimal", "f64_hex"})
        self.assertNotEqual(f["expected"]["f64_hex"], f["produced"]["f64_hex"])

    def test_one_ulp_is_a_difference(self):
        import math
        sig = signature("line-001")
        g = sig["entities"][0]["geometry"]
        g["end"][0] = scal(math.nextafter(sc(g["end"][0]), math.inf))
        self.assertEqual(st().compare(POL, expected("line-001"), sig)["class"], "STRUCTURAL_DIFFERS")

    def test_integer_fields_are_compared_exactly_and_reals_by_bits(self):
        rep = st().compare(POL, expected("bspline-d3-001"), signature("bspline-d3-001"))
        kinds = {f["field"]: f["kind"] for f in rep["entities"][0]["fields"]}
        self.assertEqual(kinds["geometry.degree"], "INTEGER")
        self.assertEqual(kinds["geometry.knots[0].multiplicity"], "INTEGER")
        self.assertEqual(kinds["geometry.control_points[0][0]"], "REAL")

    def test_the_report_records_both_versions_and_the_architecture(self):
        rep = st().compare(POL, expected("line-001"), signature("line-001"))
        self.assertEqual(rep["numeric_policy_version"], POL.version)
        self.assertEqual(rep["signature_schema_version"], "pvec-gold/signature/1")
        self.assertIn("architecture", rep["stage"])
        self.assertEqual(rep["stage"]["name"], "compare_structural")

    def test_a_report_is_refused_without_expected_math(self):
        with self.assertRaises(st().ReportRefused) as cm:
            st().compare(POL, None, signature("line-001"))
        self.assertIn("expected.math.json", str(cm.exception))

    def test_the_report_validates_against_its_schema(self):
        schema = json.loads((ROOT / "schema" / "structural-report.schema.json").read_text())
        v = Draft202012Validator(schema)
        sig = signature("bspline-d3-001")
        sig["entities"][0]["geometry"]["degree"] = 5
        for s in (signature("bspline-d3-001"), sig):
            rep = st().compare(POL, expected("bspline-d3-001"), s)
            self.assertEqual([e.message for e in v.iter_errors(rep)], [])

    def test_a_differing_result_is_never_called_exact(self):
        sig = signature("bspline-d3-001")
        sig["entities"][0]["geometry"]["degree"] = 5
        text = json.dumps(st().compare(POL, expected("bspline-d3-001"), sig))
        self.assertNotIn("STRUCTURAL_EXACT", text)

    def test_a_missing_entity_is_reported_not_skipped(self):
        sig = signature("bulge-arc-001")
        sig["entities"] = []
        rep = st().compare(POL, expected("bulge-arc-001"), sig)
        self.assertEqual(rep["class"], "STRUCTURAL_DIFFERS")
        self.assertFalse(rep["entities"][0]["matched"])

    def test_a_bare_curve_must_carry_an_identity_transform(self):
        sig = signature("line-001")
        sig["entities"][0]["transform"]["classification"] = "TRANSLATION"
        rep = st().compare(POL, expected("line-001"), sig)
        self.assertEqual(rep["class"], "STRUCTURAL_DIFFERS")

    def test_an_instance_keeps_its_transform_in_the_comparison(self):
        sig = signature("translation-001")
        m = sig["entities"][0]["transform"]["matrix"]
        m[3] = scal(sc(m[3]) + 1.0)
        rep = st().compare(POL, expected("translation-001"), sig)
        self.assertIn("transform.matrix[3]", [f["field"] for f in non_match(rep)])


def shift_x(sig, dx):
    sig = copy.deepcopy(sig)
    g = sig["entities"][0]["geometry"]
    for k in ("start", "end"):
        g[k][0] = scal(sc(g[k][0]) + dx)
    return sig


def quantity(rep, name):
    return [q for e in rep["entities"] for q in e["quantities"] if q["quantity"] == name] + \
           [q for q in rep.get("fixture_quantities", []) if q["quantity"] == name]


class Geometric(unittest.TestCase):
    def test_a_perfect_signature_is_geometrically_equal(self):
        rep = ge().compare(POL, expected("bspline-d3-001"), signature("bspline-d3-001"))
        self.assertEqual(rep["class"], "GEOMETRIC_EXACT_REPARAMETERIZED")

    def test_every_deviation_has_a_number_a_unit_a_parameter_and_a_tolerance(self):
        rep = ge().compare(POL, expected("circle-001"), signature("circle-001"))
        qs = [q for e in rep["entities"] for q in e["quantities"]] + rep["fixture_quantities"]
        self.assertTrue(qs)
        for q in qs:
            for key in ("deviation", "unit", "at_unit_parameter", "tolerance", "admitted"):
                self.assertIn(key, q, q["quantity"])
            self.assertIsInstance(q["deviation"], float)
            self.assertIsInstance(q["tolerance"], float)
        names = {q["quantity"] for q in qs}
        self.assertTrue({"endpoint_start", "endpoint_end", "bounds", "curve_deviation", "arc_length"} <= names, names)

    def test_a_1e6_translation_turns_endpoints_and_bounds_red(self):
        rep = ge().compare(POL, expected("line-001"), shift_x(signature("line-001"), MICRO))
        self.assertEqual(rep["class"], "BOUNDED_APPROXIMATION")
        self.assertGreater(rep["bound"], (0.9 * MICRO))
        self.assertFalse(quantity(rep, "endpoint_start")[0]["admitted"])
        self.assertFalse(quantity(rep, "endpoint_end")[0]["admitted"])
        self.assertFalse(quantity(rep, "bounds")[0]["admitted"])

    def test_the_policy_tolerance_admits_a_sub_tolerance_move(self):
        rep = ge().compare(POL, expected("line-001"), shift_x(signature("line-001"), TINY))
        self.assertEqual(rep["class"], "GEOMETRIC_EXACT_REPARAMETERIZED")

    def test_sampling_converges_and_says_where(self):
        rep = ge().compare(POL, expected("bspline-d3-001"), signature("bspline-d3-001"))
        (q,) = quantity(rep, "curve_deviation")[:1]
        self.assertTrue(q["converged"])
        self.assertGreaterEqual(q["refinement_level"], 2)
        self.assertGreater(q["sample_count"], 8)
        self.assertGreaterEqual(q["at_unit_parameter"], 0.0)
        self.assertLessEqual(q["at_unit_parameter"], 1.0)

    def test_reparameterised_weights_are_geometrically_equal_and_say_so(self):
        rep = ge().compare(POL, expected("nonunit-weight-001"), renormalise_weights(signature("nonunit-weight-001")))
        self.assertEqual(rep["class"], "GEOMETRIC_EXACT_REPARAMETERIZED")
        self.assertNotIn("STRUCTURAL", json.dumps(rep))
        self.assertNotIn("DISPLAY", json.dumps(rep))

    def test_a_full_multiplicity_interior_knot_is_listed_as_excluded(self):
        rep = ge().compare(POL, expected("repeated-knot-c0-001"), signature("repeated-knot-c0-001"))
        ex = rep["entities"][0]["derivative_exclusions"]
        self.assertEqual(len(ex), 1)
        self.assertEqual(ex[0]["parameter"]["decimal"], "5e-1")
        self.assertIn("C0", ex[0]["reason"])
        self.assertEqual(rep["entities"][0]["curvature"]["compared"], False)

    def test_curvature_is_compared_on_a_smooth_curve_and_a_wrong_one_fails(self):
        sig = signature("circle-001")
        r = sc(sig["entities"][0]["geometry"]["radius"])
        sig["entities"][0]["samples"] = [{
            "parameter": normalize.derived(0.5), "point": [normalize.derived(x) for x in (r * 0.8775825618903728 + 0.0, r * 0.479425538604203, 0.0)],
            "tangent": None, "curvature": normalize.derived(1.0 / r), "derivative_exclusion": None}]
        c = sc(sig["entities"][0]["geometry"]["center"][0]) if False else 0.0
        rep = ge().compare(POL, expected("circle-001"), sig)
        cq = [q for q in rep["entities"][0]["quantities"] if q["quantity"] == "curvature"]
        self.assertEqual(len(cq), 1)
        self.assertTrue(cq[0]["admitted"])
        sig["entities"][0]["samples"][0]["curvature"] = normalize.derived(1.5 / r)
        bad = ge().compare(POL, expected("circle-001"), sig)
        self.assertEqual(bad["class"], "BOUNDED_APPROXIMATION")
        self.assertFalse([q for q in bad["entities"][0]["quantities"] if q["quantity"] == "curvature"][0]["admitted"])

    def test_a_sample_flagged_as_excluded_is_not_compared(self):
        sig = signature("circle-001")
        sig["entities"][0]["samples"] = [{
            "parameter": normalize.derived(0.5), "point": [normalize.derived(x) for x in (0.0, 0.0, 0.0)],
            "tangent": None, "curvature": None, "derivative_exclusion": "C0 knot"}]
        rep = ge().compare(POL, expected("circle-001"), sig)
        self.assertEqual([q for q in rep["entities"][0]["quantities"] if q["quantity"] in ("tangent", "curvature")], [])
        self.assertEqual(canon.hex_to_f64(rep["entities"][0]["samples_excluded"][0]["parameter"]["f64_hex"]), 0.5)

    def test_the_policy_version_is_in_the_report_and_it_validates(self):
        schema = json.loads((ROOT / "schema" / "geometric-report.schema.json").read_text())
        v = Draft202012Validator(schema)
        for s in (signature("line-001"), shift_x(signature("line-001"), MICRO)):
            rep = ge().compare(POL, expected("line-001"), s)
            self.assertEqual(rep["numeric_policy_version"], POL.version)
            self.assertEqual([e.message for e in v.iter_errors(rep)], [])

    def test_a_report_is_refused_without_expected_math(self):
        with self.assertRaises(ge().ReportRefused):
            ge().compare(POL, None, signature("line-001"))

    def test_a_bounded_result_carries_its_measured_bound(self):
        rep = ge().compare(POL, expected("line-001"), shift_x(signature("line-001"), MILLI))
        self.assertEqual(rep["class"], "BOUNDED_APPROXIMATION")
        self.assertAlmostEqual(rep["bound"], MILLI, places=9)


def polyline_for_line(sig):
    """The same segment written as a two-vertex polyline."""
    out = copy.deepcopy(sig)
    e = out["entities"][0]
    g = e["geometry"]
    e["class"] = "polyline"
    e["parameter_domain"] = {"start": scal(0.0), "end": scal(1.0)}
    e["geometry"] = {"vertices": [g["start"], g["end"]], "bulges": [scal(0.0)]}
    return out


class Converters(unittest.TestCase):
    def classify(self, exp, a, b, scope="OPEN_CONVERTERS"):
        return cv().classify_fixture(POL, exp, a, b, CONVERTERS, scope)

    def test_two_exact_agreeing_converters_match_and_are_dual_oracle_evidence(self):
        s = self.classify(expected("line-001"), signature("line-001"), signature("line-001"))
        self.assertEqual(s["class"], "MATCH")
        self.assertEqual(s["governing"], "KNOWN_TRUTH")
        self.assertEqual(s["evidence"]["class"], "DUAL_ORACLE_EQUIVALENT")
        self.assertIs(s["evidence"]["is_source_truth"], False)
        self.assertEqual(s["evidence"]["evidence_scope"], "STEP_ORACLE")
        self.assertEqual(s["evidence"]["oracle_scope"], "OPEN_CONVERTERS")
        self.assertIsNone(s["quarantine"])

    def test_both_agree_and_both_contradict_the_truth_is_classified_against_the_truth(self):
        bad = shift_x(signature("line-001"), MILLI)
        s = self.classify(expected("line-001"), bad, copy.deepcopy(bad))
        self.assertEqual(s["class"], "MATERIAL_DIFFERENCE")
        self.assertEqual(s["governing"], "KNOWN_TRUTH")
        self.assertEqual(s["truth"]["primary"], "BOUNDED_APPROXIMATION")
        self.assertEqual(s["truth"]["secondary"], "BOUNDED_APPROXIMATION")
        self.assertIn("both converters", s["statement"])
        self.assertIn("contradict", s["statement"])
        self.assertIsNone(s["evidence"])
        self.assertEqual(s["quarantine"]["state"], "QUARANTINED")

    def test_one_exact_one_reparameterised_is_an_exact_reparameterisation(self):
        exp = expected("nonunit-weight-001")
        s = self.classify(exp, signature("nonunit-weight-001"), renormalise_weights(signature("nonunit-weight-001")))
        self.assertEqual(s["class"], "EXACT_REPARAMETERIZATION")
        self.assertEqual(s["truth"], {"primary": "STRUCTURAL_EXACT", "secondary": "GEOMETRIC_EXACT_REPARAMETERIZED"})
        self.assertEqual(s["evidence"]["class"], "DUAL_ORACLE_EQUIVALENT")

    def test_one_exact_one_wrong_is_material(self):
        s = self.classify(expected("line-001"), signature("line-001"), shift_x(signature("line-001"), MILLI))
        self.assertEqual(s["class"], "MATERIAL_DIFFERENCE")
        self.assertEqual(s["deciding"]["converter"], "secondary")
        self.assertAlmostEqual(s["deciding"]["deviation"], MILLI, places=9)

    def test_without_a_truth_identical_signatures_match(self):
        s = self.classify(None, signature("circle-001"), signature("circle-001"))
        self.assertEqual(s["class"], "MATCH")
        self.assertEqual(s["governing"], "SIGNATURE_COMPARISON")
        self.assertEqual(s["evidence"]["class"], "DUAL_ORACLE_EQUIVALENT")

    def test_without_a_truth_renormalised_weights_are_an_exact_reparameterisation(self):
        s = self.classify(None, signature("nonunit-weight-001"), renormalise_weights(signature("nonunit-weight-001")))
        self.assertEqual(s["class"], "EXACT_REPARAMETERIZATION")
        self.assertTrue(s["deciding"]["field"].startswith("geometry.weights"))

    def test_without_a_truth_a_different_class_with_the_same_geometry_is_equivalent_geometry(self):
        s = self.classify(None, signature("line-001"), polyline_for_line(signature("line-001")))
        self.assertEqual(s["class"], "EQUIVALENT_GEOMETRY")
        self.assertEqual(s["deciding"]["field"], "class")

    def test_without_a_truth_a_move_is_a_material_difference_with_its_deviation(self):
        s = self.classify(None, signature("line-001"), shift_x(signature("line-001"), MILLI))
        self.assertEqual(s["class"], "MATERIAL_DIFFERENCE")
        self.assertIsNone(s["evidence"])
        self.assertAlmostEqual(s["deciding"]["deviation"], MILLI, places=9)
        self.assertIn("at_unit_parameter", s["deciding"])

    def test_every_material_difference_is_quarantined_with_a_named_reason(self):
        s = self.classify(None, signature("line-001"), shift_x(signature("line-001"), MILLI))
        q = s["quarantine"]
        self.assertEqual(q["reason"], "UNRESOLVED_DISAGREEMENT")
        self.assertNotIn("unknown", q["detail"].lower())
        self.assertTrue(q["detail"].strip())
        doc = {"corpus_revision": "x", "quarantined": []}
        cv().quarantine_add(doc, "line-001", s)
        self.assertEqual([e["id"] for e in doc["quarantined"]], ["line-001"])
        self.assertEqual(doc["quarantined"][0]["reason"], "UNRESOLVED_DISAGREEMENT")
        cv().quarantine_add(doc, "line-001", s)
        self.assertEqual(len(doc["quarantined"]), 1)   # idempotent

    def test_a_clean_result_is_not_added_to_the_quarantine(self):
        s = self.classify(expected("line-001"), signature("line-001"), signature("line-001"))
        doc = {"corpus_revision": "x", "quarantined": []}
        cv().quarantine_add(doc, "line-001", s)
        self.assertEqual(doc["quarantined"], [])

    def test_the_section_names_converters_digests_and_the_policy(self):
        s = self.classify(expected("line-001"), signature("line-001"), signature("line-001"))
        self.assertEqual([c["id"] for c in s["converters"]], ["acadsharp-dwg2step", "libredwg-dwg2step"])
        self.assertEqual(s["converters"][0]["image_digest"], "sha256:" + "a" * 64)
        self.assertEqual(s["numeric_policy_version"], POL.version)

    def test_two_converters_of_one_lineage_are_refused(self):
        same = [dict(CONVERTERS[0]), dict(CONVERTERS[1], lineage="acadsharp")]
        with self.assertRaises(cv().ComparisonRefused):
            cv().classify_fixture(POL, None, signature("line-001"), signature("line-001"), same, "OPEN_CONVERTERS")

    def test_a_scope_of_none_is_refused(self):
        with self.assertRaises(cv().ComparisonRefused):
            self.classify(None, signature("line-001"), signature("line-001"), scope="NONE")

    def test_the_agreement_is_never_described_as_truth_or_intent(self):
        s = self.classify(None, signature("line-001"), signature("line-001"))
        self.assertNotIn("source truth", s["statement"].replace("not source truth", ""))
        self.assertIn("not source truth", s["statement"])

    def test_the_differences_report_groups_by_construct(self):
        secs = {
            "a-001": self.classify(None, signature("nonunit-weight-001"), renormalise_weights(signature("nonunit-weight-001"))),
            "b-001": self.classify(None, signature("line-001"), polyline_for_line(signature("line-001"))),
            "c-001": self.classify(None, signature("line-001"), signature("line-001")),
        }
        text = cv().render_differences(secs, POL)
        self.assertIn(POL.version, text)
        self.assertIn("acadsharp-dwg2step", text)
        self.assertRegex(text, r"(?m)^## EXACT_REPARAMETERIZATION")
        self.assertRegex(text, r"(?m)^## EQUIVALENT_GEOMETRY")
        self.assertIn("a-001", text)
        self.assertNotIn(" — ", text)

    def test_a_rejection_fixture_is_honoured_by_emitting_nothing(self):
        exp = expected("shear-001")
        empty = {"schema_version": normalize.SCHEMA_VERSION, "units": {"canonical": "metre"}, "entities": [],
                 "versions": {"evaluator": "1", "occt": "7.6.3", "schema": normalize.SCHEMA_VERSION, "policy": POL.version}}
        self.assertEqual(self.classify(exp, empty, empty)["class"], "MATCH")
        s = self.classify(exp, signature("line-001"), empty)
        self.assertEqual(s["class"], "MATERIAL_DIFFERENCE")
        self.assertEqual(s["deciding"]["converter"], "primary")

    def test_the_section_validates_against_its_schema(self):
        schema = json.loads((ROOT / "schema" / "converter-section.schema.json").read_text())
        v = Draft202012Validator(schema)
        for a, b in ((signature("line-001"), signature("line-001")), (signature("line-001"), shift_x(signature("line-001"), MILLI))):
            s = self.classify(expected("line-001"), a, b)
            self.assertEqual([e.message for e in v.iter_errors(s)], [])

    def test_classification_reads_signatures_only(self):
        for name in ("compare_structural", "compare_geometric", "compare_converters"):
            src = (ROOT / "runner" / (name + ".py")).read_text()
            self.assertIsNone(re.search(r"\.step\b|\.stp\b|ISO-10303|DATA;", src), name)
            self.assertNotIn("step_eval", src.replace("step_eval verification", ""), name)

    def test_real_signatures_from_both_architectures_match(self):
        rec = ROOT / "fixtures" / "validator-selftest" / "verification"
        from runner import verification
        names = sorted(p.name for p in (rec / "x64").glob("*.verification.json"))
        self.assertTrue(names)
        for n in names:
            a, b = (normalize.normalize(verification.load(rec / arch / n)) for arch in ("x64", "arm64"))
            self.assertEqual(self.classify(None, a, b)["class"], "MATCH", n)


if __name__ == "__main__":
    unittest.main()
