"""Issue 101: print-profile probes for libviprs's layouts epic (libviprs/libviprs#1557).

A twisted viewport, a viewport freeze, a non-plan view, a hide_plot viewport beside one on a no-plot layer, a no-plot
layer in model and paper space, and two layouts with plot settings (one in millimetres, one in inches). Each has
parameters, an authored record and a DWG in r3-open whose reader dump matches the record field for field.
"""
import json
from decimal import Decimal
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "tools" / "authoring" / "params-r3"
KNOWN = ROOT / "fixtures" / "viewports"
REVISION = ROOT / "corpus" / "r3-open"
IDS = ("viewport-twisted-001", "viewport-frozen-layer-001", "viewport-non-plan-001", "viewport-hide-plot-001",
       "no-plot-layer-001", "layout-plot-settings-mm-001", "layout-plot-settings-inch-001")


def record(fid):
    return json.loads((KNOWN / fid / "expected.math.json").read_text())


def read(fid):
    return json.loads((REVISION / "fixtures" / fid / "read.acadrust.json").read_text())


def f(s):
    return struct.unpack(">d", int(s["f64_hex"], 16).to_bytes(8, "big"))[0]


def hexf(h):
    return struct.unpack(">d", int(h, 16).to_bytes(8, "big"))[0]


class Records(unittest.TestCase):
    def test_each_probe_has_params_and_a_validating_record(self):
        from runner import expected_math
        for fid in IDS:
            p = PARAMS / (fid + ".json")
            self.assertTrue(p.is_file(), "no params for %s" % fid)
            self.assertEqual(json.loads(p.read_text())["kind"], "viewport_print", fid)
            rec = KNOWN / fid / "expected.math.json"
            self.assertTrue(rec.is_file(), "no record for %s" % fid)
            self.assertEqual(expected_math.validate_file(str(rec)), [], fid)

    def test_the_twist_is_thirty_degrees_in_radians(self):
        v = record("viewport-twisted-001")["viewports"][0]
        # pi/6 rounded once to f64; math.pi / 6 rounds twice and lands one ulp low.
        self.assertEqual(f(v["view"]["twist"]), float(Decimal("0.523598775598298873077107230546583814032861566562517636829")))

    def test_the_non_plan_view_looks_along_minus_one_minus_one_one(self):
        v = record("viewport-non-plan-001")["viewports"][0]
        self.assertEqual([f(c) for c in v["view"]["direction"]], [-1.0, -1.0, 1.0])

    def test_doors_is_frozen_in_the_first_viewport_only(self):
        vps = record("viewport-frozen-layer-001")["viewports"]
        self.assertEqual([v.get("frozen_layers", []) for v in vps], [["DOORS"], []])

    def test_one_viewport_is_hidden_and_one_sits_on_a_no_plot_layer(self):
        rec = record("viewport-hide-plot-001")
        vps = rec["viewports"]
        self.assertEqual([v.get("hide_plot", False) for v in vps], [True, False, False])
        self.assertEqual([v.get("entity_layer", "0") for v in vps], ["0", "VPNOPLOT", "0"])
        self.assertIn({"name": "VPNOPLOT", "plottable": False, "on": True, "frozen": False}, rec["layers"])

    def test_the_no_plot_layer_holds_a_line_in_model_and_in_paper_space(self):
        rec = record("no-plot-layer-001")
        on = [(e.get("space", "MODEL"), e["layer"]["name"]) for e in rec["entities"]]
        self.assertIn(("MODEL", "NOPLOT"), on)
        self.assertIn(("PAPER", "NOPLOT"), on)
        self.assertIn({"name": "NOPLOT", "plottable": False, "on": True, "frozen": False}, rec["layers"])

    def test_the_plot_settings_are_recorded(self):
        mm = record("layout-plot-settings-mm-001")["layout_plot"]
        self.assertEqual((f(mm["paper_width"]), f(mm["paper_height"]), mm["paper_units"], mm["rotation"]), (420.0, 297.0, 1, 1))
        self.assertEqual((f(mm["scale_numerator"]), f(mm["scale_denominator"])), (1.0, 50.0))
        self.assertEqual([f(x) for x in mm["margins"]], [5.0, 6.0, 7.0, 8.0])
        self.assertEqual([f(x) for x in mm["origin"]], [10.0, 12.0])
        self.assertEqual((mm["print_lineweights"], mm["plot_style_sheet"]), (False, "monochrome.ctb"))
        inch = record("layout-plot-settings-inch-001")["layout_plot"]
        self.assertEqual((inch["paper_units"], inch["print_lineweights"]), (0, True))
        self.assertEqual(f(inch["scale_denominator"]), 96.0)


class Revision(unittest.TestCase):
    def test_r3_open_carries_every_probe_accepted(self):
        m = json.loads((REVISION / "manifest.json").read_text())
        got = {f["id"]: f["status"] for f in m["fixtures"]}
        for fid in IDS:
            self.assertEqual(got.get(fid), "ACCEPTED", fid)

    def test_the_committed_revision_checks_clean(self):
        from runner import r3_open
        self.assertEqual(r3_open.check(), [])

    def test_the_reader_saw_what_was_authored(self):
        from runner import r3_open
        for fid in IDS:
            self.assertEqual(r3_open.compare(record(fid), read(fid)), [], fid)

    def mutated(self, fid, change):
        from runner import r3_open
        r = read(fid)
        change(r)
        return r3_open.compare(record(fid), r)

    def test_a_changed_twist_is_a_mismatch(self):
        def flip(r):
            r["viewports"][0]["twist"] = "0x%016x" % struct.unpack(">Q", struct.pack(">d", -hexf(r["viewports"][0]["twist"])))[0]
        self.assertTrue(self.mutated("viewport-twisted-001", flip))

    def test_a_changed_direction_is_a_mismatch(self):
        def plan(r):
            r["viewports"][0]["view_direction"] = ["0x0000000000000000", "0x0000000000000000", "0x3ff0000000000000"]
        self.assertTrue(self.mutated("viewport-non-plan-001", plan))

    def test_a_lost_freeze_is_a_mismatch(self):
        def thaw(r):
            r["viewports"][0]["frozen_layers"] = []
        self.assertTrue(self.mutated("viewport-frozen-layer-001", thaw))

    def test_a_lost_hide_plot_or_layer_is_a_mismatch(self):
        def show(r):
            r["viewports"][0]["hide_plot"] = False
        self.assertTrue(self.mutated("viewport-hide-plot-001", show))

        def move(r):
            r["viewports"][1]["layer"] = "0"
        self.assertTrue(self.mutated("viewport-hide-plot-001", move))

    def test_a_layer_that_plots_again_is_a_mismatch(self):
        def plots(r):
            for l in r["layers"]:
                if l["name"] == "NOPLOT":
                    l["plottable"] = True
        self.assertTrue(self.mutated("no-plot-layer-001", plots))

    def test_a_changed_plot_setting_is_a_mismatch(self):
        def layout1(r):
            return next(l for l in r["layouts"] if l["name"] == "Layout1")

        def scale(r):
            layout1(r)["scale_denominator"] = "0x4049000000000001"
        self.assertTrue(self.mutated("layout-plot-settings-mm-001", scale))

        def lineweights(r):
            layout1(r)["print_lineweights"] = True
        self.assertTrue(self.mutated("layout-plot-settings-mm-001", lineweights))


if __name__ == "__main__":
    unittest.main()
