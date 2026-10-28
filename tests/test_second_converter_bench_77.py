"""#77: the second converter is measured, the orchestration table covers both converters and compare_geometric is timed.

The record checks read committed files, so they are red until the benchmarks have been run and recorded.
"""
import json
import unittest
from pathlib import Path
from unittest import mock

from runner import containers, regenerate, scheduler

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted(p.parent.name for p in (ROOT / "corpus" / "r0-open").glob("fixtures/*/source.dwg"))
ACCEPTED = [f for f in FIXTURES if f != "near-singular-001"]
CONV = "libredwg-dwg2step"


def load(name):
    return json.loads((ROOT / "reports" / "bench" / name).read_text())


def doc(name):
    return (ROOT / "docs" / "benchmarks" / name).read_text()


class Limit(unittest.TestCase):
    def test_the_limits_file_has_a_measured_entry_for_the_second_converter(self):
        d = json.loads((ROOT / "docker" / "converter-limits.json").read_text())
        self.assertIsInstance(d.get(CONV), int)
        self.assertGreaterEqual(scheduler.limit_for(CONV), 1)
        self.assertIn("acadsharp-dwg2step", d)

    def test_the_limit_is_stated_with_its_basis_in_the_orchestration_record(self):
        o = load("libredwg-orchestration.json")
        self.assertEqual(o["converter"], CONV)
        self.assertEqual(o["cap"], scheduler.limit_for(CONV))
        self.assertTrue(o["cap_basis"])


class Wiring(unittest.TestCase):
    def args(self, **kw):
        a = dict(converter=CONV, converter_image="img", eval_image="ev", mem="512m", cpus="2")
        a.update(kw)
        return mock.Mock(**a)

    def converter_call(self, converter):
        calls = []

        def fake_run(image, args, dirs, **kw):
            calls.append((image, kw))
            return mock.Mock(returncode=1, stderr="stop here")
        with mock.patch.object(containers, "run", fake_run):
            try:
                regenerate.make_job(self.args(converter=converter), "1")("line-001", ROOT / "x", mock.Mock())
            except RuntimeError:
                pass
        return calls[0]

    def test_the_second_converter_runs_through_its_own_binary(self):
        self.assertEqual(self.converter_call(CONV)[1].get("entrypoint"), "dwg2step")

    def test_the_first_converter_keeps_the_image_entrypoint(self):
        self.assertIsNone(self.converter_call("acadsharp-dwg2step")[1].get("entrypoint"))


class Throughput(unittest.TestCase):
    def setUp(self):
        self.r = load("libredwg-throughput.json")

    def test_a_native_x64_run_of_the_second_converter_with_its_image_and_version(self):
        r = self.r
        self.assertEqual(r["converter"], CONV)
        self.assertEqual((r["arch"], r["native"], r["emulated"]), ("x64", True, False))
        self.assertTrue(r["image_id"].startswith("sha256:"))
        self.assertIn("LibreDWG", r["converter_version"])

    def test_every_fixture_has_five_repeats_of_every_metric(self):
        self.assertEqual(sorted(self.r["fixtures"]), FIXTURES)
        for fx, m in self.r["fixtures"].items():
            for k in ("startup_s", "conversion_s", "peak_rss_mib", "cgroup_peak_mib", "step_bytes"):
                self.assertGreaterEqual(m[k]["n"], 5, (fx, k))
            self.assertIn("failure_rate", m)

    def test_every_failure_has_a_fixture_and_a_cause(self):
        for f in self.r["failures"]:
            self.assertTrue(f["fixture"] in FIXTURES and f["cause"])

    def test_the_arm64_gap_is_stated_not_hidden(self):
        self.assertIn("arm64", self.r["not_measured"])


class Orchestration(unittest.TestCase):
    def setUp(self):
        self.o = load("libredwg-orchestration.json")

    def test_the_table_has_the_four_parallelism_values_and_a_chosen_one(self):
        self.assertEqual([x["parallel"] for x in self.o["table"]], [1, 2, 4, 8])
        self.assertIn(self.o["chosen"]["parallel"], [1, 2, 4, 8])
        self.assertGreater(self.o["chosen"]["memory_limit_mib"], self.o["observed_peak_rss_mib"])

    def test_no_oom_and_nothing_left_behind(self):
        self.assertEqual((self.o["oom_killed"], self.o["leftover_containers"], self.o["leftover_volumes"]), (0, 0, 0))

    def test_the_tuning_page_covers_both_converters(self):
        d = doc("orchestration-tuning.md")
        for s in ("acadsharp-dwg2step", CONV, "native x86_64"):
            self.assertIn(s, d)

    def test_the_throughput_page_has_the_second_converter(self):
        d = doc("converter-throughput.md")
        self.assertIn(CONV, d)
        self.assertNotIn("has no throughput numbers yet", d)


class Geometric(unittest.TestCase):
    def setUp(self):
        self.g = load("geometric.json")

    def test_compare_geometric_is_timed_on_both_architectures_over_the_accepted_fixtures(self):
        self.assertEqual(sorted(r["arch"] for r in self.g["runs"]), ["arm64", "x64"])
        for r in self.g["runs"]:
            self.assertTrue(r["native"] and not r["emulated"])
            self.assertEqual(sorted(r["fixtures"]), ACCEPTED)
            for fx, m in r["fixtures"].items():
                self.assertGreaterEqual(m["compare_geometric_s"]["n"], 5, fx)
                self.assertIn(m["class"], ("GEOMETRIC_EXACT_REPARAMETERIZED", "BOUNDED_APPROXIMATION"))
                self.assertIn("quantities", m)

    def test_validation_page_times_the_stage_and_drops_the_stale_line(self):
        d = doc("validation.md")
        self.assertIn("compare_geometric", d)
        self.assertNotIn("no adaptive geometric comparison stage exists", d)
        self.assertNotIn("(O2.5 and O2.6 are not built)", d)

    def test_the_validation_record_no_longer_calls_the_stage_unmeasured(self):
        self.assertNotIn("adaptive_geometric", load("validation.json").get("not_measured", {}))

    def test_the_status_page_no_longer_lists_the_benchmarks_as_open(self):
        t = (ROOT / "docs" / "open-route-status.md").read_text()
        self.assertNotIn("has a limit for it alone", t)


if __name__ == "__main__":
    unittest.main()
