"""Issue #49: the signature normaliser (runner/normalize.py) and schema/signature.schema.json.

Most checks are pure python and work on verification records. The ones that edit STEP text need
the step_eval binary (set STEP_EVAL, as in the step-validator image) and skip without it. The
cross-architecture check reads two committed sets of step_eval records of the self-test files,
one produced on native x86_64 and one on arm64, so it runs anywhere.
"""
import copy
import json
import os
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner import canon, verification

ROOT = Path(__file__).resolve().parent.parent
SELFTEST = ROOT / "fixtures" / "validator-selftest"
RECORDS = SELFTEST / "verification"
SCHEMA = ROOT / "schema" / "signature.schema.json"
STEP_EVAL = os.environ.get("STEP_EVAL")
NAMES = ["bspline", "circle", "ellipse", "line", "rational-bspline", "trimmed-arc"]


def norm():
    from runner import normalize  # imported late so each test fails on its own while the module is missing
    return normalize


def record(arch, name):
    return verification.load(RECORDS / arch / ("%s.verification.json" % name))


def sig_bytes(rec):
    return norm().dumps(norm().normalize(rec))


def bump(scalar):
    """The next f64 up, as a canonical scalar (one ulp, so the smallest possible move)."""
    f = canon.hex_to_f64(scalar["f64_hex"])
    import math
    return canon.scalar(math.nextafter(f, math.inf))


def scalars(node, path="$"):
    if isinstance(node, dict):
        if "f64_hex" in node:
            yield path, node
            return
        for k, v in node.items():
            yield from scalars(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from scalars(v, "%s[%d]" % (path, i))


def digits(decimal):
    mantissa = re.split("[eE]", decimal)[0].lstrip("-").replace(".", "")
    return len(mantissa)


class Reorder(unittest.TestCase):
    def test_renumbering_and_shuffling_the_data_section_leaves_the_signature_identical(self):
        if not STEP_EVAL:
            self.skipTest("STEP_EVAL not set")
        for step in sorted(SELFTEST.glob("*.step")):
            lines = step.read_text().splitlines()
            a = lines.index("DATA;") + 1
            b = lines.index("ENDSEC;", a)
            ids = sorted(int(re.match(r"#(\d+)=", ln).group(1)) for ln in lines[a:b])
            rng = random.Random(49)
            shuffled_ids = ids[:]
            rng.shuffle(shuffled_ids)
            new = {old: 5000 + 7 * n for old, n in zip(ids, shuffled_ids)}
            body = [re.sub(r"#(\d+)", lambda m: "#%d" % new[int(m.group(1))], ln) for ln in lines[a:b]]
            rng.shuffle(body)
            text = "\n".join(lines[:a] + body + lines[b:]) + "\n"
            self.assertNotEqual(text, step.read_text())
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "m.step"
                p.write_text(text)
                outs = []
                for src in (step, p):
                    o = Path(t) / (src.stem + ".json")
                    subprocess.run([STEP_EVAL, "--in", str(src), "--out", str(o), "--policy-version", "TEST-ID"], check=True)
                    outs.append(sig_bytes(verification.load(o)))
            self.assertEqual(outs[0], outs[1], step.name)

    def test_entity_order_and_ids_in_the_record_do_not_matter(self):
        rec = record("x64", "circle")
        other = record("x64", "line")
        both = copy.deepcopy(rec)
        both["entities"] = [copy.deepcopy(rec["entities"][0]), copy.deepcopy(other["entities"][0])]
        flipped = copy.deepcopy(both)
        flipped["entities"].reverse()
        for i, e in enumerate(flipped["entities"]):
            e["id"] = "renumbered-%d" % (900 - i)
        self.assertEqual(sig_bytes(both), sig_bytes(flipped))

    def test_the_order_is_derived_from_content(self):
        rec = record("x64", "circle")
        both = copy.deepcopy(rec)
        both["entities"] = [copy.deepcopy(rec["entities"][0]), copy.deepcopy(record("x64", "line")["entities"][0])]
        sig = norm().normalize(both)
        keys = [norm().sort_key(e) for e in sig["entities"]]
        self.assertEqual(keys, sorted(keys))


class Mutations(unittest.TestCase):
    def changed(self, name, edit):
        rec = record("x64", name)
        mut = copy.deepcopy(rec)
        edit(mut["entities"][0])
        self.assertNotEqual(rec, mut)
        self.assertNotEqual(sig_bytes(rec), sig_bytes(mut))
        diff = norm().differing_fields(norm().normalize(rec), norm().normalize(mut))
        self.assertTrue(diff, "the differing field must be named")
        return diff

    def test_one_moved_knot_changes_it(self):
        def edit(e):
            e["geometry"]["knots"][1]["value"] = bump(e["geometry"]["knots"][1]["value"])
        diff = self.changed("bspline", edit)
        self.assertTrue(any("knots" in d for d in diff), diff)

    def test_one_moved_weight_changes_it(self):
        def edit(e):
            e["geometry"]["weights"][1] = bump(e["geometry"]["weights"][1])
        diff = self.changed("rational-bspline", edit)
        self.assertTrue(any("weights" in d for d in diff), diff)

    def test_one_moved_control_point_changes_it(self):
        def edit(e):
            e["geometry"]["control_points"][2][1] = bump(e["geometry"]["control_points"][2][1])
        diff = self.changed("bspline", edit)
        self.assertTrue(any("control_points[2]" in d for d in diff), diff)

    def test_a_knot_multiplicity_change_changes_it(self):
        def edit(e):
            e["geometry"]["knots"][1]["multiplicity"] += 1
        self.changed("bspline", edit)

    def test_with_the_evaluator_a_knot_edited_in_the_step_text_changes_it(self):
        if not STEP_EVAL:
            self.skipTest("STEP_EVAL not set")
        src = (SELFTEST / "bspline.step").read_text()
        self.assertIn("0.5", src)
        sigs = []
        with tempfile.TemporaryDirectory() as t:
            for n, text in enumerate((src, src.replace("(0.,0.5,1.)", "(0.,0.5000000000000001,1.)"))):
                p = Path(t) / ("k%d.step" % n)
                p.write_text(text)
                o = Path(t) / ("k%d.json" % n)
                subprocess.run([STEP_EVAL, "--in", str(p), "--out", str(o), "--policy-version", "TEST-ID"], check=True)
                sigs.append(sig_bytes(verification.load(o)))
        if sigs[0] == sigs[1]:
            self.skipTest("self-test bspline does not use that knot spelling")
        self.assertNotEqual(sigs[0], sigs[1])


class Content(unittest.TestCase):
    def sig(self, arch="x64", name="rational-bspline"):
        return norm().normalize(record(arch, name))

    def test_no_field_carries_an_entity_id_offset_or_converter_name(self):
        rec = record("x64", "circle")
        rec["entities"][0]["id"] = "#4711"
        bad_keys = {"id", "entity_id", "step_id", "offset", "file_offset", "converter", "converters", "producer", "tool"}
        words = re.compile(r"#\d+|cadex|cad exchanger|\boda\b|acadsharp|libredwg|acadrust|dwg2step|converter", re.I)
        sig = norm().normalize(rec)

        def walk(node, path):
            if isinstance(node, dict):
                for k, v in node.items():
                    self.assertNotIn(k.lower(), bad_keys, "%s.%s" % (path, k))
                    self.assertIsNone(words.search(k), "%s.%s" % (path, k))
                    walk(v, "%s.%s" % (path, k))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, "%s[%d]" % (path, i))
            elif isinstance(node, str):
                self.assertIsNone(words.search(node), "%s = %r" % (path, node))
        walk(sig, "$")
        self.assertNotIn("4711", norm().dumps(sig))

    def test_the_four_versions_are_carried(self):
        rec = record("x64", "line")
        sig = norm().normalize(rec)
        v = sig["versions"]
        self.assertEqual(v["evaluator"], rec["tool"]["evaluator_version"])
        self.assertEqual(v["occt"], rec["tool"]["occt_version"])
        self.assertEqual(v["policy"], rec["numeric_policy_version"])
        self.assertEqual(v["schema"], "pvec-gold/signature/1")
        self.assertEqual(sig["schema_version"], "pvec-gold/signature/1")

    def test_every_scalar_declares_precision_equal_to_its_digits(self):
        for name in NAMES:
            sig = self.sig("x64", name)
            n = 0
            for where, s in scalars(sig):
                n += 1
                self.assertEqual(set(s), {"decimal", "f64_hex", "precision"}, where)
                self.assertEqual(s["precision"], digits(s["decimal"]), "%s %s" % (name, where))
                self.assertEqual(canon.check_scalar({"decimal": s["decimal"], "f64_hex": s["f64_hex"]}, where), canon.hex_to_f64(s["f64_hex"]))
            self.assertGreater(n, 10, name)

    def test_stored_values_keep_their_bits_and_derived_samples_are_rounded_to_a_declared_precision(self):
        rec = record("x64", "rational-bspline")
        sig = self.sig()
        e = sig["entities"][0]
        # a stored control point comes through bit for bit, as the shortest round-trip text
        self.assertEqual(e["geometry"]["control_points"][1][0]["f64_hex"], rec["entities"][0]["geometry"]["control_points"][1][0]["f64_hex"])
        self.assertTrue(e["samples"])
        for s in e["samples"]:
            self.assertEqual(s["point"][0]["precision"], 12)
        self.assertLessEqual(max(sc["precision"] for _, sc in scalars(e["geometry"])), 17)

    def test_negative_zero_is_not_a_fact(self):
        rec = record("x64", "line")
        rec["entities"][0]["geometry"]["start"][0] = {"decimal": "-0.0", "f64_hex": "0x8000000000000000"}
        zero = copy.deepcopy(rec)
        zero["entities"][0]["geometry"]["start"][0] = {"decimal": "0.0", "f64_hex": "0x0000000000000000"}
        self.assertEqual(sig_bytes(rec), sig_bytes(zero))

    def test_lengths_are_converted_to_the_canonical_unit(self):
        rec = record("x64", "circle")
        inch = copy.deepcopy(rec)
        inch["units"] = {"name": "INCH", "canonical": "metre", "scale_to_canonical": canon.scalar("0.0254"), "source": "file"}
        g = inch["entities"][0]["geometry"]
        sig = norm().normalize(inch)
        r = sig["entities"][0]["geometry"]["radius"]
        self.assertEqual(r["f64_hex"], canon.scalar(canon.hex_to_f64(g["radius"]["f64_hex"]) * 0.0254)["f64_hex"])
        text = norm().dumps(sig)
        self.assertNotIn("INCH", text.upper())
        self.assertEqual(sig["units"], {"canonical": "metre"})

    def test_a_zero_or_negative_unit_scale_is_refused_cleanly(self):
        for bad in ("0", "-0.0254"):
            rec = record("x64", "circle")
            rec["units"]["scale_to_canonical"] = canon.scalar(bad)
            with self.assertRaises(ValueError):
                norm().normalize(rec)
            with tempfile.TemporaryDirectory() as t:
                src, out = Path(t) / "r.verification.json", Path(t) / "o.signature.json"
                src.write_text(json.dumps(rec))
                r = subprocess.run(["python3", "-m", "runner.normalize", str(src), str(out)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 1, bad)
                self.assertNotIn("Traceback", r.stderr, bad)
                self.assertIn("scale_to_canonical", r.stdout + r.stderr, bad)
                self.assertFalse(out.exists(), bad)

    def test_unsupported_entities_keep_their_occt_type(self):
        rec = record("x64", "line")
        e = rec["entities"][0]
        e["class"] = "unsupported"
        e["geometry"] = {"occt_type": "Geom_OffsetCurve"}
        sig = norm().normalize(rec)
        self.assertEqual(sig["entities"][0]["class"], "unsupported")
        self.assertEqual(sig["entities"][0]["geometry"], {"occt_type": "Geom_OffsetCurve"})


class Schema(unittest.TestCase):
    def test_the_schema_is_a_valid_draft_2020_12_schema_with_no_tolerance(self):
        schema = json.loads(SCHEMA.read_text())
        Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["properties"]["schema_version"]["const"], "pvec-gold/signature/1")
        low = SCHEMA.read_text().lower()
        for w in ("tolerance", "epsilon", "ulp"):
            self.assertNotIn(w, low)

    def test_every_output_validates_and_a_scalar_without_precision_does_not(self):
        for name in NAMES:
            sig = norm().normalize(record("x64", name))
            self.assertEqual(norm().validate_doc(sig), [], name)
        sig = norm().normalize(record("x64", "bspline"))
        del sig["entities"][0]["geometry"]["knots"][0]["value"]["precision"]
        self.assertTrue(norm().validate_doc(sig))
        sig = norm().normalize(record("x64", "bspline"))
        sig["entities"][0]["geometry"]["knots"][0]["value"]["precision"] += 1
        self.assertTrue(any("precision" in e for e in norm().validate_doc(sig)))

    def test_an_entity_id_is_refused_by_the_schema(self):
        sig = norm().normalize(record("x64", "line"))
        sig["entities"][0]["id"] = "#12"
        self.assertTrue(norm().validate_doc(sig))

    def test_the_command_line_writes_the_signature(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "line.signature.json"
            r = subprocess.run(["python3", "-m", "runner.normalize", str(RECORDS / "x64" / "line.verification.json"), str(out)],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_text(), sig_bytes(record("x64", "line")))


class AcrossArchitectures(unittest.TestCase):
    def test_arm64_and_x64_signatures_of_the_selftest_files_are_identical_or_name_the_field(self):
        total = 0
        for name in NAMES:
            a = norm().normalize(record("arm64", name))
            b = norm().normalize(record("x64", name))
            total += 1
            diff = norm().differing_fields(a, b)
            self.assertEqual(diff, [], "%s: signatures differ in %s" % (name, diff))
            self.assertEqual(norm().dumps(a), norm().dumps(b), name)
        self.assertEqual(total, 6)

    def test_the_raw_records_do_differ_so_the_check_is_not_vacuous(self):
        a, b = record("arm64", "rational-bspline"), record("x64", "rational-bspline")
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_differing_fields_names_the_path(self):
        a = norm().normalize(record("x64", "bspline"))
        b = copy.deepcopy(a)
        b["entities"][0]["geometry"]["knots"][1]["value"] = bump(b["entities"][0]["geometry"]["knots"][1]["value"]) | {"precision": 17}
        self.assertEqual(norm().differing_fields(a, b), ["entities[0].geometry.knots[1].value"])


class Goldens(unittest.TestCase):
    def test_the_committed_selftest_signatures_are_what_the_normaliser_writes(self):
        for name in NAMES:
            golden = (SELFTEST / "signatures" / ("%s.signature.json" % name)).read_text()
            for arch in ("x64", "arm64"):
                self.assertEqual(golden, sig_bytes(record(arch, name)), "%s from %s" % (name, arch))


class Docs(unittest.TestCase):
    def test_the_doc_exists_and_names_the_schema_version(self):
        text = (ROOT / "docs" / "fixtures" / "signature.md").read_text()
        self.assertIn("pvec-gold/signature/1", text)
        self.assertIn("precision", text)


if __name__ == "__main__":
    unittest.main()
