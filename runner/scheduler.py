"""Run one job per fixture with a hard concurrency cap, a state file per fixture and bounded logs.

    scheduler.run(fixtures, job, out=, state=, logs=, parallel=, limit=)

job(fixture, workdir, log) writes its artifacts into workdir and may write lines to log. A job that
returns has succeeded, one that raises Refused is a designed refusal, any other exception is a failure.

  * The cap is enforced here: asking for more than `limit` raises LicenceLimitExceeded before any job
    starts, and the pool is built with `parallel` workers, so the limit is a property of the code and
    not of a document. limit_for() reads docker/converter-limits.json and treats an unlisted or null
    converter as 1.
  * A job works in out/.work/<fixture>-<pid> and the directory is renamed to out/<fixture> only when
    the job succeeded, so a failure leaves no artifacts and cannot touch another fixture's.
  * state/<fixture>.json records the status and the SHA-256 of every artifact. A rerun skips a fixture
    whose state is done or refused and whose artifacts still hash the same, and redoes the rest.
  * logs/<fixture>.log holds only that fixture's lines, each prefixed with [fixture], cut to the last
    max_log_bytes.
  * A KeyboardInterrupt (or any BaseException) stops the pool, calls teardown(fixture) for every
    fixture that was in flight, marks them interrupted, removes their work directories and re-raises.
"""
import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

LIMITS = Path(__file__).resolve().parent.parent / "docker" / "converter-limits.json"
MAX_LOG_BYTES = 1 << 20


class LicenceLimitExceeded(ValueError):
    pass


class Refused(Exception):
    """The job declined this fixture on purpose (the converter's designed refusal), which is not a failure."""


def limit_for(converter):
    v = json.loads(LIMITS.read_text()).get(converter)
    return v if isinstance(v, int) and v >= 1 else 1


class _Log:
    def __init__(self, fixture, path):
        self.fixture, self.path, self.buf = fixture, path, []

    def write(self, text):
        for line in str(text).splitlines():
            self.buf.append("[%s] %s\n" % (self.fixture, line))

    def flush_bounded(self, max_bytes):
        data = "".join(self.buf).encode("utf-8", "replace")
        if len(data) > max_bytes:
            data = data[-max_bytes:]
            data = data[data.index(b"\n") + 1:] if b"\n" in data else data
            data = ("[%s] ... earlier lines dropped, kept the last %d bytes\n" % (self.fixture, max_bytes)).encode() + data
        self.path.write_bytes(data)


def _hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def _put(path, doc):
    tmp = path.with_name(path.name + ".tmp%d" % os.getpid())
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def _finished(state_file, out, fixture):
    if not state_file.exists():
        return False
    st = json.loads(state_file.read_text())
    if st["status"] == "refused":
        return True
    d = out / fixture
    return st["status"] == "done" and d.is_dir() and _hashes(d) == st["artifacts"]


def run(fixtures, job, *, out, state, logs, parallel, limit, teardown=None, max_log_bytes=MAX_LOG_BYTES, _barrier=None):
    if parallel > limit:
        raise LicenceLimitExceeded("asked for %d concurrent converters, the limit is %d" % (parallel, limit))
    out, state, logs = Path(out), Path(state), Path(logs)
    work_root = out / ".work"
    for d in (out, state, logs, work_root):
        d.mkdir(parents=True, exist_ok=True)
    summary = {"done": [], "skipped": [], "failed": {}, "refused": {}, "interrupted": []}
    lock = threading.Lock()
    inflight = set()
    stop = threading.Event()

    def finish(fx, status, info):
        with lock:
            inflight.discard(fx)
        return fx, status, info

    def one(fx):
        if stop.is_set():
            return fx, "cancelled", None
        sf = state / (fx + ".json")
        work = work_root / ("%s-%d" % (fx, os.getpid()))
        log = _Log(fx, logs / (fx + ".log"))
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        with lock:
            inflight.add(fx)
        _put(sf, {"fixture": fx, "status": "running"})
        try:
            job(fx, work, log)
        except Refused as ex:
            _put(sf, {"fixture": fx, "status": "refused", "reason": str(ex), "artifacts": {}})
            log.write("refused: %s" % ex)
            return finish(fx, "refused", str(ex))
        except Exception as ex:
            _put(sf, {"fixture": fx, "status": "failed", "error": "%s: %s" % (type(ex).__name__, ex)})
            log.write("failed: %s: %s" % (type(ex).__name__, ex))
            return finish(fx, "failed", "%s: %s" % (type(ex).__name__, ex))
        except BaseException:
            stop.set()
            raise
        else:
            dest = out / fx
            if dest.exists():
                shutil.rmtree(dest)
            os.replace(work, dest)
            _put(sf, {"fixture": fx, "status": "done", "artifacts": _hashes(dest)})
            log.write("done")
            return finish(fx, "done", None)
        finally:
            shutil.rmtree(work, ignore_errors=True)
            log.flush_bounded(max_log_bytes)

    todo = []
    for fx in fixtures:
        (summary["skipped"] if _finished(state / (fx + ".json"), out, fx) else todo).append(fx)
    pool = cf.ThreadPoolExecutor(max_workers=parallel)
    try:
        futs = [pool.submit(one, fx) for fx in todo]
        if _barrier is not None:
            _barrier.wait()
        for f in cf.as_completed(futs):
            fx, status, info = f.result()
            if status == "done":
                summary["done"].append(fx)
            elif status == "cancelled":
                continue
            elif status == "refused":
                summary["refused"][fx] = info
            else:
                summary["failed"][fx] = info
    except BaseException:
        with lock:
            stopped = sorted(inflight)
        for f in futs:
            f.cancel()
        for fx in stopped:
            if teardown:
                teardown(fx)
        pool.shutdown(wait=True, cancel_futures=True)
        for fx in stopped:
            _put(state / (fx + ".json"), {"fixture": fx, "status": "interrupted"})
            shutil.rmtree(out / fx, ignore_errors=True)
        raise
    pool.shutdown()
    summary["exit_code"] = 1 if summary["failed"] else 0
    return summary
