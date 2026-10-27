"""The ACadSharp route A converter image (issue 48): DWG in, AP242 Part 21 and a status record out.

Two kinds of test live here.

The static ones need nothing: they read the files under tools/converters/acadsharp and run
publish.sh as a dry run. They run in any lane.

The container ones drive the real converter image and the real step-validator image (OCCT, the one
evaluator) through the docker CLI, so they need a docker daemon. They skip without one, unless
GOLD_DOCKER_TESTS=1, in which case a missing daemon is a failure. Settings, all optional:

    DWG2STEP_IMAGE        converter image to test (default: build tools/converters/acadsharp/Dockerfile)
    STEP_VALIDATOR_IMAGE  evaluator image (default gold-stepval:<arch>, as tools/stepval.sh builds it)
    DOCKER_PLATFORM       linux/amd64 or linux/arm64 (default: this machine's)
    GOLD_VOLUME           name of a docker volume that holds this tree, mounted here at GOLD_VOLUME_AT
                          (default /work). tools/converters/acadsharp/test.sh sets both. Without it the
                          directories this process makes are bind-mounted at the same path.
"""
import json
import math
import os
import platform
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from runner import canon, expected_math as em, numeric, step_normalise, verification

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "converters" / "acadsharp"
CORPUS = ROOT / "corpus" / "r0-open"
CONVERTER_ID = "acadsharp-dwg2step"   # stub: issue 47 makes `converter` a string id in the status schema
IMAGE_NAME = "ghcr.io/libviprs/pvec-gold-dwg2step-acadsharp"
POL = numeric.load_policy()

ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine(), "amd64")
PLATFORM = os.environ.get("DOCKER_PLATFORM", "linux/" + ARCH)
EVAL_IMAGE = os.environ.get("STEP_VALIDATOR_IMAGE", "gold-stepval:" + PLATFORM.split("/")[1])
STRICT = os.environ.get("GOLD_DOCKER_TESTS") == "1"
VOLUME = os.environ.get("GOLD_VOLUME")
VOLUME_AT = Path(os.environ.get("GOLD_VOLUME_AT", "/work"))
SCRATCH = ROOT / ".out-acadsharp"

# The inputs: every source.dwg of corpus revision r0-open, in sorted order.
FIXTURES = sorted(p.parent.name for p in CORPUS.glob("fixtures/*/source.dwg"))
# near-singular-001 is the one probe whose authored outcome is a refusal, not a curve.
REFUSED = {"near-singular-001"}
# closed-periodic-001 is a knot-closed periodic spline; STEP has no such thing (docs/validator/step-evaluator.md).
PERIODIC = {"closed-periodic-001"}


def have_docker():
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def docker(*args, check=True, stdin=None):
    r = subprocess.run(["docker", *args], capture_output=True, text=True, stdin=stdin)
    if check and r.returncode != 0:
        raise AssertionError("docker %s failed (%d): %s" % (" ".join(args[:3]), r.returncode, (r.stderr or r.stdout)[-1500:]))
    return r


_image = {}


def converter_image():
    """The image under test: DWG2STEP_IMAGE, or one built here from the Dockerfile in the tree."""
    if "ref" not in _image:
        ref = os.environ.get("DWG2STEP_IMAGE")
        if not ref:
            dockerfile = TOOL / "Dockerfile"
            assert dockerfile.is_file(), "tools/converters/acadsharp/Dockerfile does not exist"
            ref = "gold-dwg2step-acadsharp:test-" + PLATFORM.split("/")[1]
            docker("build", "--platform", PLATFORM, "-f", str(dockerfile), "-t", ref, str(ROOT))
        _image["ref"] = ref
    return _image["ref"]


def cpath(p):
    """The path a container sees for a path in this process."""
    p = Path(p).resolve()
    return str(p) if not VOLUME else "/v/" + str(p.relative_to(VOLUME_AT))


def mounts(*dirs):
    if VOLUME:
        return ["-v", "%s:/v" % VOLUME]
    out = []
    for d in dict.fromkeys(str(Path(x).resolve()) for x in dirs):
        out += ["-v", "%s:%s" % (d, d)]
    return out


def convert(dwg, out_dir, name="primary", extra=(), image=None, env=()):
    """Run the converter on one DWG and read back its status record."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dwg = Path(dwg)
    envs = [x for e in env for x in ("-e", e)]
    r = docker("run", "--rm", "--platform", PLATFORM, *envs, *mounts(dwg.parent, out_dir), image or converter_image(),
               "--in", cpath(dwg), "--out", cpath(out_dir / ("%s.step" % name)), "--status", cpath(out_dir / ("%s.status.json" % name)), *extra, check=False)
    sp = out_dir / ("%s.status.json" % name)
    return {"code": r.returncode, "stderr": r.stderr, "step": out_dir / ("%s.step" % name), "status": json.loads(sp.read_text()) if sp.exists() else None}


def evaluate(step):
    """step_eval, the only evaluator, on one STEP file. Returns the parsed verification record."""
    step = Path(step)
    out = step.with_suffix(".verification.json")
    docker("run", "--rm", "--platform", PLATFORM, *mounts(step.parent), EVAL_IMAGE, "step_eval", "--in", cpath(step),
           "--out", cpath(out), "--policy-version", POL.version)
    return verification.load(out)


def status_schema():
    s = json.loads((ROOT / "schema" / "converter-status.schema.json").read_text())
    # Until the ADR 0009 change lands, `converter` is an enum of the two vendors. A named id is what that change allows.
    s["properties"]["converter"] = {"type": "string", "minLength": 1}
    return s


_cache = {}


def run_all():
    """Convert every r0-open DWG twice (cached for the whole module) and evaluate the first run."""
    if "runs" not in _cache:
        base = SCRATCH / ("run-%d" % os.getpid())
        shutil.rmtree(base, ignore_errors=True)
        _cache["base"] = base
        runs = {}
        for fx in FIXTURES:
            src = CORPUS / "fixtures" / fx / "source.dwg"
            a = convert(src, base / fx / "a")
            b = convert(src, base / fx / "b")
            ev = evaluate(a["step"]) if a["code"] == 0 else None
            runs[fx] = {"a": a, "b": b, "eval": ev}
        _cache["runs"] = runs
    return _cache["runs"]


def tearDownModule():
    base = _cache.get("base")
    if base and base.exists():
        # inside this tree's own .out-* scratch directory (gitignored), made by this process
        docker("run", "--rm", "--platform", PLATFORM, *mounts(base.parent), "alpine:3.20", "rm", "-rf", cpath(base), check=False)


needs_docker = unittest.skipUnless(have_docker() or STRICT, "no docker daemon (set GOLD_DOCKER_TESTS=1 to make this a failure)")


# ---- helpers for comparing against the authored mathematics ----------------------------------

EXACT_FOR = {
    "bezier": ("control_points", "knots", "weights"),
    "bspline": ("control_points", "knots", "weights"),
    "nurbs": ("control_points", "knots", "weights"),
    "circle": ("center", "radius"),
    "circular_arc": ("center", "radius", "start_angle"),
}


def is_scalar(x):
    return isinstance(x, dict) and set(x) == {"decimal", "f64_hex"}


def scalar_fails(path, exp, got, scale, exact, out):
    if not is_scalar(got):
        out.append("%s: missing" % path)
    elif exact:
        if exp["f64_hex"] != got["f64_hex"]:
            out.append("%s: stored value changed, authored %s got %s" % (path, exp["f64_hex"], got["f64_hex"]))
    elif not POL.near(canon.check_scalar(exp), canon.check_scalar(got), scale):
        out.append("%s: authored %s got %s (outside the policy)" % (path, exp["decimal"], got["decimal"]))


def tree_fails(path, exp, got, scale, exact_keys, out, exact=False):
    if is_scalar(exp):
        scalar_fails(path, exp, got, scale, exact, out)
    elif isinstance(exp, dict):
        if not isinstance(got, dict):
            out.append("%s: missing" % path)
            return
        for k, v in exp.items():
            if k not in got:
                out.append("%s.%s: missing" % (path, k))
            else:
                tree_fails("%s.%s" % (path, k), v, got[k], scale, exact_keys, out, exact or k in exact_keys)
    elif isinstance(exp, list):
        if not isinstance(got, list) or len(got) != len(exp):
            out.append("%s: authored %d items, got %s" % (path, len(exp), len(got) if isinstance(got, list) else "none"))
            return
        for i, v in enumerate(exp):
            tree_fails("%s[%d]" % (path, i), v, got[i], scale, exact_keys, out, exact)
    elif exp != got:
        out.append("%s: authored %r got %r" % (path, exp, got))


def authored(fx):
    """(entity record to compare, expected.math entity) per authored entity, polyline containers and their
    derived arcs left to the segment check."""
    doc = em.load(CORPUS / "fixtures" / fx / "expected.math.json")
    out = []
    for e in doc["entities"]:
        if e["id"].endswith("-equivalent-arc"):
            continue
        out.append(e.get("world") or e)
    return out, doc["entities"]


def entity_fails(want, got):
    out = []
    # The reader hands a Bezier back as a B-spline (the evaluator has no way to say otherwise), and a STEP line
    # is parameterised over its length, so neither the Bezier class nor a line's domain is a converter output.
    same_class = want["class"] == got["class"] or (want["class"], got["class"]) == ("bezier", "bspline")
    if not same_class:
        return ["class: authored %s got %s" % (want["class"], got["class"])]
    scale = numeric.feature_scale(want)
    tree_fails("entity", {k: want[k] for k in ("geometry", "parameter_domain", "closure") if k in want and not (k == "parameter_domain" and want["class"] == "line")},
               {k: got[k] for k in ("geometry", "parameter_domain", "closure")}, scale,
               EXACT_FOR.get(want["class"], ()) if "transform" not in want else (), out)
    return out


def sample_point(ent, i):
    return [canon.check_scalar(c) for c in ent["samples"][i]["point"]]


# ---- the static checks -----------------------------------------------------------------------

class Files(unittest.TestCase):
    def test_the_converter_sources_exist(self):
        for name in ("Program.cs", "Step21.cs", "Flatten.cs", "Dockerfile", "publish.sh"):
            self.assertTrue((TOOL / name).is_file(), "tools/converters/acadsharp/%s is missing" % name)
        self.assertTrue((ROOT / "docs" / "converters" / "acadsharp-dwg2step.md").is_file())

    def test_every_base_image_is_pinned_by_digest_and_nothing_names_a_vendor_word(self):
        self.assertTrue((TOOL / "Dockerfile").is_file(), "Dockerfile is missing")
        text = (TOOL / "Dockerfile").read_text()
        froms = re.findall(r"^FROM\s+(\S+)", text, re.M)
        self.assertTrue(froms)
        for f in froms:
            if f in ("build", "runtime") or f.startswith("$"):
                continue
            self.assertRegex(f, r"@sha256:[0-9a-f]{64}$", "unpinned base image %s" % f)
        # pvec's licence scan flags any FROM or image line containing the substring 'oda'
        for line in text.splitlines():
            if line.startswith("FROM"):
                self.assertNotIn("oda", line.lower())
        self.assertNotRegex(text.lower(), r"occt|opencascade|libtk")

    def test_the_acadsharp_commit_is_pinned_in_full(self):
        self.assertTrue((TOOL / "Dockerfile").is_file(), "Dockerfile is missing")
        text = (TOOL / "Dockerfile").read_text()
        self.assertRegex(text, r"ACADSHARP_COMMIT=[0-9a-f]{40}")

    def test_publish_dry_run_names_the_image_and_both_platforms_and_touches_no_credential(self):
        sh = TOOL / "publish.sh"
        self.assertTrue(sh.is_file(), "publish.sh is missing")
        env = {"PATH": os.environ["PATH"], "HOME": tempfile.gettempdir(), "GITHUB_TOKEN": "x" * 40, "GHCR_TOKEN": "y" * 40}
        r = subprocess.run(["bash", str(sh), "--dry-run"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout + r.stderr
        self.assertIn(IMAGE_NAME, out)
        self.assertIn("linux/amd64", out)
        self.assertIn("linux/arm64", out)
        self.assertIn("dry run", out.lower())
        self.assertNotIn("x" * 40, out)
        self.assertNotIn("y" * 40, out)
        script = sh.read_text()
        self.assertNotRegex(script, r"--password|docker login|GITHUB_TOKEN|GHCR_TOKEN", "publish.sh must not handle a credential")

    def test_publish_refuses_to_push_without_an_explicit_flag(self):
        self.assertTrue((TOOL / "publish.sh").is_file(), "publish.sh is missing")
        r = subprocess.run(["bash", str(TOOL / "publish.sh")], capture_output=True, text=True, env={"PATH": os.environ["PATH"]})
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--push", r.stderr + r.stdout)

    def test_no_tolerance_literal_in_the_converter_sources(self):
        self.assertTrue(list(TOOL.glob("*.cs")), "no C# sources yet")
        # the converter reads its one threshold (NP-19) from the vendored policy, it does not carry a number
        for p in TOOL.glob("*.cs"):
            for n, line in enumerate(p.read_text().splitlines(), 1):
                code = re.sub(r'"(\\.|[^"\\])*"', '""', line.split("//")[0])
                self.assertNotRegex(code, r"(?<![\w.])\d+(\.\d+)?[eE]-\d+", "%s:%d" % (p.name, n))


# ---- the container checks --------------------------------------------------------------------

@needs_docker
class Converter(unittest.TestCase):
    def test_converter_output_is_read_by_step_eval_for_every_r0_dwg(self):
        self.assertEqual(len(FIXTURES), 30, "expected the r0-open DWGs")
        runs = run_all()
        for fx in FIXTURES:
            a = runs[fx]["a"]
            if fx in REFUSED:
                continue
            with self.subTest(fixture=fx):
                self.assertEqual(a["code"], 0, a["stderr"])
                self.assertEqual(a["status"]["status"], "OK")
                self.assertEqual(a["status"]["converter"], CONVERTER_ID)
                self.assertEqual(list(Draft202012Validator(status_schema()).iter_errors(a["status"])), [])
                self.assertIn("AP242", a["status"]["declared_schema"])
                self.assertEqual(verification.validate_doc(runs[fx]["eval"]), [])
                self.assertGreater(len(runs[fx]["eval"]["entities"]), 0)
                unsupported = [e["id"] for e in runs[fx]["eval"]["entities"] if e["class"] == "unsupported"]
                self.assertEqual(unsupported, [])

    def test_numbers_are_written_at_17_significant_digits(self):
        runs = run_all()
        text = runs["circle-001"]["a"]["step"].read_text()
        reals = re.findall(r"[-+]?\d\.\d+E[-+]\d+", text)
        self.assertTrue(reals)
        self.assertTrue(all(len(r.split("E")[0].replace("-", "").replace("+", "").replace(".", "")) == 17 for r in reals), reals[:5])

    def test_stored_values_match_authored_bits_on_curve_probes(self):
        runs = run_all()
        curve_probes = [f for f in FIXTURES if f not in REFUSED and not re.search(r"scale|reflection|rotation|translation|nested|polyline|layer|bulge|large-coords", f)]
        self.assertGreaterEqual(len(curve_probes), 15)
        for fx in curve_probes:
            ents, _ = authored(fx)
            got = runs[fx]["eval"]["entities"]
            with self.subTest(fixture=fx):
                self.assertEqual(len(got), len(ents), "edges")
                for want, g in zip(ents, got):
                    if fx in PERIODIC:
                        self.assertEqual(g["class"], "bspline")
                        self.assertEqual(g["geometry"]["degree"], want["geometry"]["degree"])
                        d = g["parameter_domain"]
                        self.assertEqual((d["start"]["f64_hex"], d["end"]["f64_hex"]), (want["parameter_domain"]["start"]["f64_hex"], want["parameter_domain"]["end"]["f64_hex"]))
                        continue
                    self.assertEqual(entity_fails(want, g), [])

    def test_a_periodic_spline_keeps_its_curve_when_it_goes_through_step(self):
        runs = run_all()
        want = authored("closed-periodic-001")[0][0]
        g = runs["closed-periodic-001"]["eval"]["entities"][0]
        # the periodic span [0, 1] starts and ends at the same point
        first, last = sample_point(g, 0), sample_point(g, len(g["samples"]) - 1)
        scale = numeric.feature_scale(want)
        for a, b in zip(first, last):
            self.assertTrue(POL.near(a, b, scale), (first, last))
        # every authored pole is stored verbatim among the poles that were written
        wrote = [[c["f64_hex"] for c in p] for p in g["geometry"]["control_points"]]
        for p in want["geometry"]["control_points"]:
            self.assertIn([c["f64_hex"] for c in p], wrote)

    def test_polyline_segments_are_the_authored_vertices_and_bulge_arcs(self):
        runs = run_all()
        for fx in [f for f in FIXTURES if "polyline" in f or "bulge" in f or "large-coords" in f]:
            ents, _ = authored(fx)
            poly = ents[0]
            vs = [[canon.check_scalar(c) for c in v] for v in poly["geometry"]["vertices"]]
            bulges = [canon.check_scalar(b) for b in poly["geometry"]["bulges"]]
            closed = poly["closure"]["closed_by_endpoint"]
            n = len(vs) if closed else len(vs) - 1
            got = runs[fx]["eval"]["entities"]
            with self.subTest(fixture=fx):
                self.assertEqual(len(got), n)
                for i in range(n):
                    a, b = vs[i], vs[(i + 1) % len(vs)]
                    self.assertEqual(got[i]["class"], "line" if bulges[i] == 0 else "circular_arc")
                    scale = max(abs(x - y) for x, y in zip(a, b))
                    ends = {tuple(sample_point(got[i], 0)), tuple(sample_point(got[i], len(got[i]["samples"]) - 1))}
                    for want in (a, b):
                        self.assertTrue(any(all(POL.near(p, q, scale) for p, q in zip(e, want)) for e in ends), (i, want, ends))

    def test_instances_flatten_to_the_authored_world_curves(self):
        runs = run_all()
        for fx in [f for f in FIXTURES if re.search(r"scale|reflection|rotation|translation|nested", f) and f not in REFUSED]:
            ents, _ = authored(fx)
            with self.subTest(fixture=fx):
                got = runs[fx]["eval"]["entities"]
                self.assertEqual(len(got), len(ents))
                for want, g in zip(ents, got):
                    self.assertEqual(entity_fails(want, g), [])

    def test_nonuniform_scaled_circle_becomes_the_authored_ellipse(self):
        runs = run_all()
        for fx in ("nonuniform-scale-circle-001", "nonuniform-scale-rotated-001"):
            got = runs[fx]["eval"]["entities"]
            with self.subTest(fixture=fx):
                self.assertEqual([g["class"] for g in got], ["ellipse"], "a circle here is wrong, not merely different")
                want = authored(fx)[0][0]
                self.assertEqual(want["class"], "ellipse")
                g = got[0]["geometry"]
                self.assertTrue(POL.near(canon.check_scalar(g["semi_major"]), canon.check_scalar(want["geometry"]["semi_major"]), 6))
                self.assertTrue(POL.near(canon.check_scalar(g["semi_minor"]), canon.check_scalar(want["geometry"]["semi_minor"]), 6))
        want = authored("nonuniform-scale-circle-001")[0][0]["geometry"]
        self.assertEqual(canon.check_scalar(want["semi_major"]), 6.0)
        self.assertEqual(canon.check_scalar(want["semi_minor"]), 2.0)

    def test_reflection_reverses_orientation(self):
        runs = run_all()
        g = runs["reflection-001"]["eval"]["entities"][0]
        self.assertEqual(g["class"], "circular_arc")
        geo = g["geometry"]
        self.assertEqual([canon.check_scalar(c) for c in geo["normal"]], [0.0, 0.0, -1.0], "the placement frame must flip with the mirror")
        self.assertEqual([canon.check_scalar(c) for c in geo["x_axis"]], [-1.0, 0.0, 0.0])
        # the parameter direction is kept (start maps to start): the arc starts at the mirror image of the source start
        cx, cy, r, a0, sw = 2.0, 1.0, 1.5, canon.check_scalar(geo["start_angle"]), canon.check_scalar(geo["sweep_angle"])
        self.assertTrue(POL.near(a0, 0.4, 1))
        self.assertTrue(POL.near(sw, 2.1, 1))
        src_start = (cx + r * math.cos(0.4), cy + r * math.sin(0.4))
        src_end = (cx + r * math.cos(2.5), cy + r * math.sin(2.5))
        s = sample_point(g, 0)
        e = sample_point(g, len(g["samples"]) - 1)
        self.assertTrue(POL.near(s[0], -src_start[0], r) and POL.near(s[1], src_start[1], r), s)
        self.assertTrue(POL.near(e[0], -src_end[0], r) and POL.near(e[1], src_end[1], r), e)

    def test_stored_values_survive_on_a_circle_under_a_proper_rotation(self):
        runs = run_all()
        want = authored("uniform-scale-001")[0][0]
        g = runs["uniform-scale-001"]["eval"]["entities"][0]
        self.assertEqual(g["class"], "circle", "a uniform scale keeps a circle a circle")
        self.assertTrue(POL.near(canon.check_scalar(g["geometry"]["radius"]), canon.check_scalar(want["geometry"]["radius"]), 1))

    def test_two_runs_are_identical_except_the_named_fields(self):
        runs = run_all()
        for fx in FIXTURES:
            if fx in REFUSED:
                continue
            a, b = runs[fx]["a"], runs[fx]["b"]
            with self.subTest(fixture=fx):
                ta, tb = a["step"].read_text(), b["step"].read_text()
                self.assertTrue(step_normalise.same(ta, tb), "STEP differs beyond the FILE_NAME time stamp")
                sa, sb = dict(a["status"]), dict(b["status"])
                for s, t in ((sa, ta), (sb, tb)):
                    s.pop("wall_time_seconds")
                    s["input"] = {"sha256": s["input"]["sha256"]}
                    s["output"] = {"sha256": hashlib_text(step_normalise.normalise(t))}
                self.assertEqual(sa, sb)

    def test_the_time_stamp_follows_source_date_epoch_so_a_run_can_be_byte_identical(self):
        src = CORPUS / "fixtures" / "line-001" / "source.dwg"
        with tempfile.TemporaryDirectory(dir=_scratch()) as t:
            outs = []
            for i in (1, 2):
                r = convert(src, Path(t) / ("run%d" % i), env=["SOURCE_DATE_EPOCH=1700000000"])
                self.assertEqual(r["code"], 0, r["stderr"])
                outs.append(r["step"].read_bytes())
            self.assertEqual(outs[0], outs[1])
            self.assertIn(b"2023-11-14T22:13:20", outs[0])

    def test_malformed_dwg_exits_12_and_leaves_no_step(self):
        good = (CORPUS / "fixtures" / "line-001" / "source.dwg").read_bytes()
        cases = {"truncated": good[:200], "garbage_after_header": good[:6] + bytes(range(256)) * 8, "not_a_dwg": b"this is not a drawing at all\n" * 20}
        for name, blob in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory(dir=_scratch()) as t:
                d = Path(t)
                (d / "in").mkdir()
                (d / "in" / "bad.dwg").write_bytes(blob)
                (d / "out").mkdir()
                (d / "out" / "primary.step").write_text("stale output from an earlier run")
                r = convert(d / "in" / "bad.dwg", d / "out")
                self.assertEqual(r["code"], 12, r["stderr"])
                self.assertFalse(r["step"].exists(), "a failed run must leave no STEP file, not even a stale one")
                self.assertEqual(list((d / "out").glob("*.partial*")), [])
                st = r["status"]
                self.assertEqual(list(Draft202012Validator(status_schema()).iter_errors(st)), [])
                self.assertEqual((st["status"], st["exit_code"], st["error"]["class"]), ("ERROR", 12, "INPUT_MALFORMED"))
                self.assertIsNone(st["output"])

    def test_the_other_exit_codes(self):
        with tempfile.TemporaryDirectory(dir=_scratch()) as t:
            d = Path(t)
            # 10: bad arguments
            r = docker("run", "--rm", "--platform", PLATFORM, *mounts(d), converter_image(), "--out", cpath(d / "x.step"), "--status", cpath(d / "x.status.json"), check=False)
            self.assertEqual(r.returncode, 10)
            self.assertEqual(json.loads((d / "x.status.json").read_text())["error"]["class"], "BAD_ARGUMENTS")
            # 11: input missing
            r = convert(d / "nope.dwg", d / "o11")
            self.assertEqual(r["code"], 11)
            self.assertEqual(r["status"]["error"]["class"], "INPUT_UNREADABLE")
            # 13: a DWG version ACadSharp does not read
            (d / "old.dwg").write_bytes(b"AC1009" + bytes(1000))
            r = convert(d / "old.dwg", d / "o13")
            self.assertEqual(r["code"], 13, r["stderr"])
            self.assertEqual(r["status"]["error"]["class"], "DWG_VERSION_UNSUPPORTED")
            self.assertEqual(list(Draft202012Validator(status_schema()).iter_errors(json.loads((d / "x.status.json").read_text()))), [])
            # 15: a transform the policy refuses (NP-19), named in the message, and no STEP file
            near = CORPUS / "fixtures" / "near-singular-001" / "source.dwg"
            r = convert(near, d / "o15")
            self.assertEqual(r["code"], 15, r["stderr"])
            self.assertFalse(r["step"].exists())
            self.assertEqual(r["status"]["error"]["class"], "CONVERSION_FAILED")
            self.assertIn("NEAR_SINGULAR_TRANSFORM", r["status"]["error"]["message"])

    def test_the_status_record_carries_input_hash_product_and_schema(self):
        a = run_all()["circle-001"]["a"]["status"]
        raw = (CORPUS / "fixtures" / "circle-001" / "source.dwg").read_bytes()
        import hashlib
        self.assertEqual(a["input"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(a["output"]["sha256"], hashlib.sha256(run_all()["circle-001"]["a"]["step"].read_bytes()).hexdigest())
        self.assertEqual(a["product"]["name"], "ACadSharp")
        self.assertRegex(a["product"]["version"], r"[0-9a-f]{7,40}")
        self.assertEqual(a["converter"], CONVERTER_ID)

    def test_the_image_has_no_opencascade_in_it(self):
        r = docker("run", "--rm", "--platform", PLATFORM, "--entrypoint", "sh", converter_image(), "-c",
                   "ls /usr/lib/*/ 2>/dev/null | grep -i -E 'libTK|occt' ; find / -xdev \\( -iname 'libTK*' -o -iname '*occt*' -o -name step_eval \\) 2>/dev/null | head", check=False)
        self.assertEqual(r.stdout.strip(), "", "OCCT must stay out of the converter")


def hashlib_text(s):
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()


def _scratch():
    SCRATCH.mkdir(exist_ok=True)
    return str(SCRATCH)


@needs_docker
class ImageHistory(unittest.TestCase):
    def test_image_history_has_no_licence_material(self):
        img = converter_image()
        hist = Path(_scratch()) / ("history-%d.txt" % os.getpid())
        hist.write_text(docker("history", "--no-trunc", "--format", "{{.CreatedBy}}", img).stdout)
        try:
            save = subprocess.Popen(["docker", "save", img], stdout=subprocess.PIPE)
            scan = subprocess.run(["bash", str(ROOT / "tools" / "scan_layers.sh"), str(hist)], stdin=save.stdout, capture_output=True, text=True)
            save.stdout.close()
            save.wait()
            self.assertEqual(scan.returncode, 0, scan.stdout[-800:])
            # the scan has to be able to fire: a pattern the image certainly contains
            save = subprocess.Popen(["docker", "save", img], stdout=subprocess.PIPE)
            canary = subprocess.run(["bash", str(ROOT / "tools" / "scan_layers.sh"), str(hist)], stdin=save.stdout, capture_output=True, text=True,
                                    env=dict(os.environ, CANARY_PATTERN="dwg2step"))
            save.stdout.close()
            save.wait()
            self.assertEqual(canary.returncode, 1, "the scan did not fire on a known pattern")
        finally:
            hist.unlink()


if __name__ == "__main__":
    unittest.main()
