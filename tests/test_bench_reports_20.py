"""The measurement records of issue 20: shape and honesty checks on reports/bench/*.json and docs/benchmarks/*.md.

They read committed files, so they are red until the benchmarks have been run and recorded.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted(p.parent.name for p in (ROOT / "corpus" / "r0-open").glob("fixtures/*/source.dwg"))
STATS = {"n", "median", "min", "max", "iqr"}


def load(name):
    return json.loads((ROOT / "reports" / "bench" / name).read_text())


def read(name):
    return (ROOT / "docs" / "benchmarks" / name).read_text()


class Throughput(unittest.TestCase):
    def setUp(self):
        self.rep = load("converter-throughput.json")

    def test_a_native_x64_run_and_an_arm64_run_are_both_present_and_labelled(self):
        arch = {r["arch"]: r for r in self.rep["runs"]}
        self.assertEqual(sorted(arch), ["arm64", "x64"])
        self.assertTrue(arch["x64"]["native"] and arch["arm64"]["native"])
        self.assertFalse(any(r.get("emulated") for r in self.rep["runs"]))

    def test_every_fixture_has_median_and_spread_for_all_five_metrics_over_at_least_five_repeats(self):
        for r in self.rep["runs"]:
            self.assertEqual(sorted(r["fixtures"]), FIXTURES)
            for fx, m in r["fixtures"].items():
                for k in ("startup_s", "conversion_s", "peak_rss_mib", "step_bytes"):
                    self.assertTrue(STATS <= set(m[k]), (r["arch"], fx, k))
                    self.assertGreaterEqual(m[k]["n"], 5, (r["arch"], fx, k))
                self.assertIn("failure_rate", m)
                self.assertGreaterEqual(m["repeats"], 5)

    def test_startup_is_isolated_by_a_no_op_run_in_the_same_image(self):
        for r in self.rep["runs"]:
            self.assertGreaterEqual(r["noop"]["n"], 5)
            self.assertIn("median", r["noop"])

    def test_the_run_names_converter_version_and_image_digest_and_concurrency_and_the_limit(self):
        for r in self.rep["runs"]:
            for k in ("image", "image_id", "converter", "converter_version", "concurrency", "licence_limit", "limit_bounded_throughput"):
                self.assertIn(k, r)

    def test_every_failure_is_attributed_to_a_fixture_and_a_cause(self):
        for r in self.rep["runs"]:
            self.assertIn("failure_rate", r)
            for f in r["failures"]:
                self.assertTrue(f["fixture"] in FIXTURES and f["cause"])

    def test_the_document_states_the_platform_facts(self):
        d = read("converter-throughput.md")
        for s in ("native x86_64", "native arm64", "Rosetta", "licence"):
            self.assertIn(s, d)


class Validation(unittest.TestCase):
    STAGES = ("load_s", "normalise_s", "structural_s", "report_s")

    def test_each_architecture_has_per_fixture_medians_over_five_repeats_and_the_versions(self):
        rep = load("validation.json")
        self.assertEqual(sorted(r["arch"] for r in rep["runs"]), ["arm64", "x64"])
        for r in rep["runs"]:
            for k in ("evaluator_version", "occt_version", "policy_version"):
                self.assertTrue(r[k], k)
            self.assertEqual(sorted(r["fixtures"]), sorted(f for f in FIXTURES if f != "near-singular-001"))
            for fx, m in r["fixtures"].items():
                for s in self.STAGES:
                    self.assertGreaterEqual(m[s]["n"], 5, (fx, s))
                    self.assertIn("median", m[s])
            self.assertEqual(len(r["most_expensive"]), 10)
            for e in r["most_expensive"]:
                self.assertTrue(e["reason"])

    def test_the_geometric_stage_is_listed_as_a_timed_stage_not_as_absent(self):
        rep = load("validation.json")
        self.assertNotIn("adaptive_geometric", rep["not_measured"])
        self.assertIn("compare_geometric", read("validation.md"))

    def test_signatures_and_verdicts_are_compared_across_architectures(self):
        x = load("validation.json")["cross_architecture"]
        self.assertIn("identical", x)
        self.assertIn("divergences", x)
        for d in x["divergences"]:
            self.assertTrue(d["fixture"] and d["field"])

    def test_the_signature_path_is_timed_against_the_step_path(self):
        s = load("validation.json")["signature_path"]
        for k in ("subset", "step_path_s", "signature_path_s", "speedup"):
            self.assertIn(k, s)


class Orchestration(unittest.TestCase):
    def test_the_wall_clock_table_has_parallelism_1_2_4_and_8_and_the_chosen_value_and_peak(self):
        rep = load("orchestration.json")
        for r in rep["runs"]:
            self.assertEqual([x["parallel"] for x in r["table"]], [1, 2, 4, 8])
            self.assertIn(r["chosen"]["parallel"], [1, 2, 4, 8])
            self.assertGreater(r["chosen"]["memory_limit_mib"], r["observed_peak_rss_mib"])
            self.assertEqual(r["oom_killed"], 0)
            self.assertEqual(r["leftover_containers"], 0)
            self.assertEqual(r["leftover_volumes"], 0)
        d = read("orchestration-tuning.md")
        self.assertIn("native x86_64", d)

    def test_compose_has_the_open_converter_with_limits(self):
        c = (ROOT / "docker-compose.yml").read_text()
        i = c.index("acadsharp-converter:")
        block = c[i:i + 1500]
        for s in ("mem_limit", "cpus"):
            self.assertIn(s, block)
        self.assertTrue((ROOT / "docker" / "converter-limits.json").is_file())

    def test_the_open_route_status_covers_the_benchmarks(self):
        t = (ROOT / "docs" / "open-route-status.md").read_text()
        self.assertIn("docs/benchmarks", t)
        self.assertIn("libredwg", t.lower())


if __name__ == "__main__":
    unittest.main()
