"""The licence-aware scheduler and its resumable state (issue 20, the orchestration part).

Everything here is stdlib and in-process: the jobs are plain functions that write files, so these run
in any lane. The container side (the real converter under the scheduler) is exercised by
bench/run-bench.sh and recorded in docs/benchmarks/orchestration-tuning.md.
"""
import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from runner import scheduler


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}


class Env:
    def __init__(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = Path(self._t.name)
        self.out, self.state, self.logs = (self.root / n for n in ("out", "state", "logs"))

    def run(self, fixtures, job, parallel=1, limit=8, **kw):
        return scheduler.run(fixtures, job, out=self.out, state=self.state, logs=self.logs, parallel=parallel, limit=limit, **kw)

    def close(self):
        self._t.cleanup()


def writes(name="a.step"):
    def job(fx, work, log):
        (work / name).write_text("data of %s\n" % fx)
        log.write("converted %s\n" % fx)
    return job


class Limit(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.addCleanup(self.e.close)

    def test_asking_for_more_than_the_licence_limit_is_refused_before_any_job_runs(self):
        called = []
        with self.assertRaises(scheduler.LicenceLimitExceeded):
            self.e.run(["a", "b"], lambda fx, w, l: called.append(fx), parallel=3, limit=2)
        self.assertEqual(called, [])

    def test_the_number_of_jobs_in_flight_never_exceeds_the_limit_and_reaches_it(self):
        lock, now, peak = threading.Lock(), [0], [0]

        def job(fx, work, log):
            with lock:
                now[0] += 1
                peak[0] = max(peak[0], now[0])
            time.sleep(0.05)
            with lock:
                now[0] -= 1
            (work / "a.step").write_text(fx)
        self.e.run(["f%02d" % i for i in range(12)], job, parallel=3, limit=3)
        self.assertEqual(peak[0], 3)

    def test_the_limit_for_a_converter_comes_from_the_limits_file_and_an_unknown_vendor_is_one(self):
        self.assertGreaterEqual(scheduler.limit_for("acadsharp-dwg2step"), 1)
        self.assertEqual(scheduler.limit_for("cadex"), 1)
        self.assertEqual(scheduler.limit_for("oda"), 1)
        self.assertEqual(scheduler.limit_for("a-converter-nobody-listed"), 1)


class Resume(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.addCleanup(self.e.close)

    def test_an_interrupted_run_resumes_and_regenerates_only_the_unfinished_fixtures(self):
        names = ["a", "b", "c", "d", "e"]

        def dies_on_c(fx, work, log):
            if fx == "c":
                raise KeyboardInterrupt
            writes()(fx, work, log)
        with self.assertRaises(KeyboardInterrupt):
            self.e.run(names, dies_on_c)
        done_before = {fx: tree_hashes(self.e.out / fx) for fx in ("a", "b")}
        self.assertEqual(sorted(p.name for p in self.e.out.iterdir() if not p.name.startswith(".")), ["a", "b"])
        ran = []

        def job(fx, work, log):
            ran.append(fx)
            writes()(fx, work, log)
        summary = self.e.run(names, job)
        self.assertEqual(sorted(ran), ["c", "d", "e"])
        self.assertEqual(sorted(summary["skipped"]), ["a", "b"])
        self.assertEqual({fx: tree_hashes(self.e.out / fx) for fx in ("a", "b")}, done_before)
        self.assertEqual(summary["exit_code"], 0)

    def test_a_fixture_whose_artifact_changed_since_it_was_recorded_is_regenerated(self):
        self.e.run(["a", "b"], writes())
        (self.e.out / "a" / "a.step").write_text("tampered\n")
        ran = []
        self.e.run(["a", "b"], lambda fx, w, l: (ran.append(fx), writes()(fx, w, l)))
        self.assertEqual(ran, ["a"])

    def test_nothing_is_left_in_a_running_state_after_an_interrupt(self):
        def job(fx, work, log):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.e.run(["a"], job)
        st = json.loads((self.e.state / "a.json").read_text())
        self.assertEqual(st["status"], "interrupted")
        self.assertEqual([p for p in self.e.out.rglob("*") if p.is_file()], [])


class Isolation(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.addCleanup(self.e.close)

    def test_one_failure_does_not_abort_the_run_or_touch_another_fixture_and_the_exit_is_non_zero(self):
        self.e.run(["a", "c"], writes())
        before = {fx: tree_hashes(self.e.out / fx) for fx in ("a", "c")}

        def job(fx, work, log):
            (work / "partial.step").write_text("half")
            if fx == "b":
                raise RuntimeError("converter exited 12")
            writes()(fx, work, log)
        s = self.e.run(["a", "b", "c", "d"], job)
        self.assertEqual(sorted(s["failed"]), ["b"])
        self.assertIn("converter exited 12", s["failed"]["b"])
        self.assertEqual(s["exit_code"], 1)
        self.assertEqual(sorted(s["done"]), ["d"])
        self.assertFalse((self.e.out / "b").exists(), "a failed fixture leaves no artifacts behind")
        self.assertEqual({fx: tree_hashes(self.e.out / fx) for fx in ("a", "c")}, before)

    def test_a_refusal_is_recorded_as_refused_and_does_not_fail_the_run(self):
        def job(fx, work, log):
            raise scheduler.Refused("NEAR_SINGULAR_TRANSFORM")
        s = self.e.run(["a"], job)
        self.assertEqual(s["refused"], {"a": "NEAR_SINGULAR_TRANSFORM"})
        self.assertEqual(s["exit_code"], 0)

    def test_teardown_runs_for_the_fixtures_in_flight_when_the_run_is_aborted(self):
        torn = []
        started = threading.Barrier(3, timeout=5)

        def job(fx, work, log):
            started.wait()
            if fx == "a":
                raise KeyboardInterrupt
            time.sleep(0.2)
        with self.assertRaises(KeyboardInterrupt):
            self.e.run(["a", "b"], job, parallel=2, limit=2, teardown=torn.append, _barrier=started)
        self.assertEqual(sorted(torn), ["a", "b"])


class Logs(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.addCleanup(self.e.close)

    def test_every_log_line_names_its_fixture_and_a_failure_is_locatable(self):
        def job(fx, work, log):
            log.write("starting\nsecond line\n")
            if fx == "b":
                raise RuntimeError("boom")
        self.e.run(["a", "b"], job)
        for fx in ("a", "b"):
            lines = (self.e.logs / (fx + ".log")).read_text().splitlines()
            self.assertTrue(lines and all(l.startswith("[%s] " % fx) for l in lines), lines)
        self.assertIn("boom", (self.e.logs / "b.log").read_text())

    def test_a_log_is_bounded_and_keeps_its_tail(self):
        def job(fx, work, log):
            for i in range(2000):
                log.write("line %d\n" % i)
        self.e.run(["a"], job, max_log_bytes=4096)
        text = (self.e.logs / "a.log").read_text()
        self.assertLessEqual(len(text.encode()), 4096 + 200)
        self.assertIn("line 1999", text)
        self.assertNotIn("line 0\n", text)


if __name__ == "__main__":
    unittest.main()
