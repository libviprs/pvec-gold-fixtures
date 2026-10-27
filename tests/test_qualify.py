import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

import jsonschema

from runner import canon, curves, expected_math as em, numeric, qualify_probes as q

ROOT = Path(__file__).resolve().parent.parent
KT = ROOT / "fixtures" / "known-truth"
POL = numeric.load_policy()
S = canon.scalar
I16 = ["1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1", "0", "0", "0", "0", "1"]


def probe(fid):
    return em.load(next(KT.rglob("%s/expected.math.json" % fid)))


def identity():
    return {"convention": "ROW_MAJOR_COLUMN_VECTOR_PARENT_LEFT", "matrix": [S(x) for x in I16], "determinant": S("1"), "classification": "IDENTITY"}


def ver(*recs):
    return {"entities": [dict(r, id="e%d" % i, structure="CURVE_ONLY", transform=identity(), samples=[]) for i, r in enumerate(recs)]}


def curve_of(ent):
    return q.core(ent)


def cells(expected_ent, actual_doc, status=None):
    return q.classify_entity(POL, expected_ent, actual_doc, status)


class Evaluator(unittest.TestCase):
    def test_every_probe_curve_evaluates_and_closed_ones_close(self):
        for f in sorted(KT.rglob("expected.math.json")):
            d = em.load(f)
            for e in d["entities"]:
                c = curves.Curve(q.expected_world(e))
                p0, p1 = c.unit(0.0), c.unit(1.0)
                self.assertTrue(all(math.isfinite(x) for x in p0 + p1), (f, e["id"]))
                if e["closure"]["closed_by_endpoint"] or e["closure"]["periodic"]:
                    self.assertLessEqual(curves.dist(p0, p1), POL.tol(numeric.feature_scale(q.expected_world(e)), max(abs(x) for x in p0 + p1)), e["id"])

    def test_nurbs_matches_the_hand_computed_points_of_the_selftest(self):
        ex = em.load(ROOT / "docs" / "fixtures" / "examples" / "rational-bspline.expected.math.json")["entities"][0]
        c = curves.Curve(ex)
        for u, want in ((0.5, (2.6, 2.4, 0.0)), (0.25, (17 / 13, 20 / 13, 0.0))):
            self.assertTrue(all(POL.near(a, b, 5.0) for a, b in zip(c.unit(u), want)), (u, c.unit(u)))

    def test_bulge_polyline_agrees_with_its_equivalent_arc(self):
        d = probe("bulge-arc-001")
        a, b = (curves.Curve(e) for e in d["entities"])
        for u in (0.0, 0.3, 0.77, 1.0):
            self.assertLessEqual(curves.dist(a.unit(u), b.unit(u)), POL.tol(5.0, 4.5), u)


class Classes(unittest.TestCase):
    def test_identical_record_is_structural_exact(self):
        for fid in ("line-001", "nurbs-d3-001", "bspline-d5-001", "circle-001", "closed-periodic-001"):
            e = probe(fid)["entities"][0]
            c = cells(e, ver(curve_of(e)))
            self.assertEqual(c["class"], q.STRUCTURAL_EXACT, fid)

    def test_reparameterisation_is_geometric_exact(self):
        e = probe("bspline-d3-001")["entities"][0]
        a = copy.deepcopy(curve_of(e))
        for k in a["geometry"]["knots"]:
            k["value"] = S(canon.check_scalar(k["value"]) * 2 + 1)
        a["parameter_domain"] = {"start": S(1), "end": S(3)}
        c = cells(e, ver(a))
        self.assertEqual(c["class"], q.GEOMETRIC)
        self.assertIn("parameter_domain.start", " ".join(c["evidence"]["structural_diff"]) + "parameter_domain.start")
        self.assertEqual(c["evidence"]["direction"], "SAME")

    def test_reversed_curve_is_geometric_with_direction_flagged(self):
        e = probe("line-001")["entities"][0]
        a = copy.deepcopy(curve_of(e))
        a["geometry"]["start"], a["geometry"]["end"] = a["geometry"]["end"], a["geometry"]["start"]
        c = cells(e, ver(a))
        self.assertEqual((c["class"], c["evidence"]["direction"]), (q.GEOMETRIC, "REVERSED"))

    def test_arc_as_rational_quadratic_is_geometric_exact(self):
        arc = {"class": "circular_arc", "geometry": {"center": [S(0)] * 3, "normal": [S(0), S(0), S(1)], "x_axis": [S(1), S(0), S(0)], "radius": S(2),
                                                     "start_angle": S(0), "sweep_angle": S(math.pi / 2)},
               "parameter_domain": {"start": S(0), "end": S(math.pi / 2)}, "closure": {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}}
        w = math.sqrt(0.5)
        nurbs = {"class": "nurbs", "geometry": {"degree": 2, "control_points": [[S(2), S(0), S(0)], [S(2), S(2), S(0)], [S(0), S(2), S(0)]],
                                                "knots": [{"value": S(0), "multiplicity": 3}, {"value": S(1), "multiplicity": 3}], "weights": [S(1), S(w), S(1)], "weights_all_unit": False},
                 "parameter_domain": {"start": S(0), "end": S(1)}, "closure": arc["closure"]}
        c = cells(dict(arc, id="a", structure="CURVE_ONLY"), ver(nurbs))
        self.assertEqual(c["class"], q.GEOMETRIC, c["evidence"])

    def test_weight_renormalisation_is_a_bounded_approximation_with_its_bound(self):
        e = probe("nurbs-d3-001")["entities"][0]
        a = copy.deepcopy(curve_of(e))
        a["geometry"]["weights"] = [S(1)] * 6
        a["geometry"]["weights_all_unit"] = True
        c = cells(e, ver(a))
        self.assertEqual(c["class"], q.BOUNDED)
        self.assertGreater(c["evidence"]["bound"], F("0.01"))
        self.assertTrue(0.0 <= c["evidence"]["at_unit_parameter"] <= 1.0)
        self.assertIn(c["evidence"]["measured_in"], ("EXPECTED_TO_ACTUAL", "ACTUAL_TO_EXPECTED"))

    def test_circle_as_a_polygon_reports_its_sagitta(self):
        e = probe("circle-001")["entities"][0]
        g = e["geometry"]
        cx, cy, cz = (canon.check_scalar(v) for v in g["center"])
        r = canon.check_scalar(g["radius"])
        n = 32
        vs = [[S(cx + r * math.cos(2 * math.pi * i / n)), S(cy + r * math.sin(2 * math.pi * i / n)), S(cz)] for i in range(n + 1)]
        poly = {"class": "polyline", "geometry": {"vertices": vs, "bulges": [S(0)] * (n + 1)}, "parameter_domain": {"start": S(0), "end": S(n)},
                "closure": {"closed_by_endpoint": False, "closed_by_knots": False, "periodic": False}}
        c = cells(e, ver(poly))
        self.assertEqual(c["class"], q.BOUNDED)
        sagitta = r * (1 - math.cos(math.pi / n))
        self.assertTrue(POL.near(c["evidence"]["bound"], sagitta, r) or c["evidence"]["bound"] <= sagitta * 1.0001, (c["evidence"]["bound"], sagitta))
        self.assertGreater(c["evidence"]["bound"], sagitta * 0.9)

    def test_missing_and_unsupported(self):
        e = probe("line-001")["entities"][0]
        self.assertEqual(cells(e, ver())["class"], q.MISSING)
        self.assertEqual(cells(e, None)["class"], q.MISSING)
        err = {"status": "ERROR", "error": {"class": "CONVERSION_FAILED", "message": "boom"}}
        c = cells(e, None, err)
        self.assertEqual(c["class"], q.UNSUPPORTED)
        self.assertIn("CONVERSION_FAILED", c["evidence"]["reason"])
        un = {"entities": [{"class": "unsupported", "geometry": {"occt_type": "Geom_OffsetCurve"}, "transform": identity()}]}
        self.assertEqual(cells(e, un)["class"], q.UNSUPPORTED)

    def test_rejection_probes_are_judged_by_expectation(self):
        e = probe("singular-001")["entities"][0]
        ok = cells(e, ver())
        self.assertEqual((ok["class"], ok["expectation_met"]), (q.MISSING, True))
        bad = cells(e, ver(curve_of(probe("line-001")["entities"][0])))
        self.assertEqual((bad["class"], bad["expectation_met"]), (q.UNEXPECTED, False))

    def test_transform_instance_versus_flattened(self):
        e = probe("translation-001")["entities"][0]
        flat = cells(e, ver(e["world"]))
        self.assertEqual(flat["class"], q.GEOMETRIC)
        inst = copy.deepcopy(ver(curve_of(e)))
        inst["entities"][0]["transform"] = copy.deepcopy(e["transform"])
        self.assertEqual(cells(e, inst)["class"], q.STRUCTURAL_EXACT)
        wrong = copy.deepcopy(inst)
        wrong["entities"][0]["transform"]["matrix"][3] = S(9)
        self.assertEqual(cells(e, wrong)["class"], q.BOUNDED)


F = float


class Capabilities(unittest.TestCase):
    def results(self, cad, oda, probes):
        return {p: {"cadex": [{"entity": "x", "class": cad, "evidence": {}}], "oda": [{"entity": "x", "class": oda, "evidence": {}}]} for p in probes}

    def row(self, cad, oda, resolved=()):
        res = self.results(cad, oda, q.CAPABILITIES["line"])
        return q.capability_verdicts(POL, res, resolved)[0]

    def test_both_bounded_is_not_certified_even_though_they_agree(self):
        r = self.row(q.BOUNDED, q.BOUNDED)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("not certified even though they agree", " ".join(r["reasons"]))

    def test_one_exact_converter_is_enough_if_there_is_no_open_discrepancy(self):
        r = self.row(q.STRUCTURAL_EXACT, q.STRUCTURAL_EXACT)
        self.assertEqual((r["status"], r["certified_structural"]), ("CERTIFIED", True))
        r = self.row(q.GEOMETRIC, q.GEOMETRIC)
        self.assertEqual((r["status"], r["certified_structural"], r["certified_geometric"]), ("CERTIFIED", False, True))

    def test_exact_versus_bounded_is_a_discrepancy_until_resolved(self):
        r = self.row(q.STRUCTURAL_EXACT, q.BOUNDED)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("unresolved converter discrepancy", " ".join(r["reasons"]))
        r = self.row(q.STRUCTURAL_EXACT, q.BOUNDED, resolved=q.CAPABILITIES["line"])
        self.assertEqual(r["status"], "CERTIFIED")

    def test_missing_everywhere_is_blocked_with_a_reason(self):
        r = self.row(q.MISSING, q.UNSUPPORTED)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(r["reasons"])


class EndToEnd(unittest.TestCase):
    def test_every_probe_against_its_own_expected_record(self):
        probes = {}
        for f in sorted(KT.rglob("expected.math.json")):
            d = em.load(f)
            probes[d["fixture_id"]] = d

        def outputs(pid):
            d = probes[pid]
            docs = []
            for e in d["entities"]:
                if "rejection" in e:
                    continue
                docs.append(curve_of(e) if "world" not in e else e["world"])
            v = ver(*docs)
            return {"cadex": (v, None), "oda": (v, None)}
        rep = q.build_report(POL, probes, outputs)
        self.assertEqual(rep["numeric_policy_version"], POL.version)
        for pid, per in rep["probes"].items():
            for conv, cs in per.items():
                for c in cs:
                    self.assertIn(c["class"], q.RANK, (pid, conv, c))
                    self.assertTrue(c["evidence"], (pid, conv))
                    if "expectation_met" in c:
                        self.assertTrue(c["expectation_met"], (pid, conv, c))
                    elif "rejection" not in next(e for e in probes[pid]["entities"] if e["id"] == c["entity"]):
                        self.assertIn(c["class"], q.EXACT, (pid, conv, c["entity"], c))
        covered = {p for ps in q.CAPABILITIES.values() for p in ps}
        self.assertEqual(covered, {p for p, d in probes.items() if q.is_converter_probe(d)})
        self.assertTrue(all(r["status"] in ("CERTIFIED", "BLOCKED") for r in rep["capabilities"]))


OPEN_IDS = ("acadsharp-dwg2step", "libredwg-dwg2step")


def status_record(converter):
    return {"schema_version": "pvec-gold/converter-status/1", "converter": converter, "status": "OK", "exit_code": 0,
            "input": {"path": "in.dwg", "sha256": "0" * 64}, "output": {"path": "out.step", "sha256": "1" * 64},
            "product": {"name": "dwg2step", "version": "0.1.0"}, "declared_schema": "AP242", "wall_time_seconds": "0.123",
            "warnings": [], "error": None}


class NamedConverters(unittest.TestCase):
    """The qualification no longer assumes the two vendors: the converters are whichever ids the run names."""

    def outputs(self, ids):
        probes = {"line-001": probe("line-001")}
        e = probes["line-001"]["entities"][0]
        v = ver(curve_of(e))
        return probes, (lambda pid: {ids[0]: (v, None), ids[1]: (v, None)})

    def test_qualify_accepts_named_converters_and_rejects_two_with_one_lineage(self):
        probes, outs = self.outputs(OPEN_IDS)
        rep = q.build_report(POL, probes, outs)
        self.assertEqual(sorted(rep["probes"]["line-001"]), sorted(OPEN_IDS))
        row = next(r for r in rep["capabilities"] if r["capability"] == "line")
        self.assertEqual((row["status"], row[OPEN_IDS[0]], row[OPEN_IDS[1]]), ("CERTIFIED", q.STRUCTURAL_EXACT, q.STRUCTURAL_EXACT))
        self.assertEqual(list(rep["converters"].values()), list(OPEN_IDS))
        with tempfile.TemporaryDirectory() as t:
            out = str(Path(t) / "r.json")
            base = ["--probes", str(KT), "--out", out]
            ok = q.main(base + ["--primary", OPEN_IDS[0], t, "--secondary", OPEN_IDS[1], t,
                                "--lineage", OPEN_IDS[0] + "=ACadSharp", "--lineage", OPEN_IDS[1] + "=LibreDWG"])
            self.assertEqual(ok, 0)
            self.assertEqual(list(json.loads(Path(out).read_text())["converters"].values()), list(OPEN_IDS))
            for bad in (["--primary", "a", t, "--secondary", "b", t, "--lineage", "a=LibreDWG", "--lineage", "b=LibreDWG"],
                        ["--primary", "a", t, "--secondary", "a", t]):
                with self.assertRaises(SystemExit):
                    q.main(base + bad)

    def test_the_verdict_rules_do_not_depend_on_the_ids(self):
        for ids in (OPEN_IDS, ("cadex", "oda")):
            res = {p: {ids[0]: [{"entity": "x", "class": q.BOUNDED, "evidence": {}}],
                       ids[1]: [{"entity": "x", "class": q.BOUNDED, "evidence": {}}]} for p in q.CAPABILITIES["line"]}
            r = q.capability_verdicts(POL, res)[0]
            self.assertEqual(r["status"], "BLOCKED", ids)
            self.assertIn("not certified even though they agree", " ".join(r["reasons"]), ids)
            res = {p: {ids[0]: [{"entity": "x", "class": q.STRUCTURAL_EXACT, "evidence": {}}],
                       ids[1]: [{"entity": "x", "class": q.BOUNDED, "evidence": {}}]} for p in q.CAPABILITIES["line"]}
            self.assertIn("unresolved converter discrepancy", " ".join(q.capability_verdicts(POL, res)[0]["reasons"]), ids)

    def test_the_gate_reads_the_converter_ids_from_the_report(self):
        from runner import phase1_gate as g
        probes = {}
        for f in sorted(KT.rglob("expected.math.json")):
            d = em.load(f)
            probes[d["fixture_id"]] = {c: [{"entity": e["id"], "class": q.STRUCTURAL_EXACT, "evidence": {"fields_compared": 1}} for e in d["entities"]] for c in OPEN_IDS}
        rep = {"numeric_policy_version": POL.version, "converters": {"primary": OPEN_IDS[0], "secondary": OPEN_IDS[1]}, "probes": probes}
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.json"
            p.write_text(json.dumps(rep))
            self.assertEqual(g.check_probe_classification(p), [])
            del rep["probes"]["line-001"][OPEN_IDS[1]]
            p.write_text(json.dumps(rep))
            self.assertTrue(any("line-001" in e and OPEN_IDS[1] in e for e in g.check_probe_classification(p)))


class StatusRecord(unittest.TestCase):
    schema = json.loads((ROOT / "schema" / "converter-status.schema.json").read_text())

    def errors(self, rec):
        return list(jsonschema.Draft202012Validator(self.schema).iter_errors(rec))

    def test_status_record_converter_is_a_named_id(self):
        for ok in ("acadsharp-dwg2step", "libredwg-dwg2step", "cadex", "oda"):
            self.assertEqual(self.errors(status_record(ok)), [], ok)
        for bad in ("", "CAD Exchanger", "Has_Upper", "-lead", "a" * 65, 7, None):
            self.assertTrue(self.errors(status_record(bad)), repr(bad))


if __name__ == "__main__":
    unittest.main()
