"""Clean-host reproducibility and the release manifest (#24).

    python3 -m runner.reproduce run --label native-x64 --platform linux/amd64 --out .out-repro/run1 \
        [--against corpus/release/r0-open-1/manifest.json] [--write-release corpus/release/r0-open-1]
    python3 -m runner.reproduce verify corpus/release/r0-open-1

`run` is what tools/clean_host.sh runs inside a driver container that has the docker CLI: it builds the images
from pinned inputs, rewrites the r0-open DWGs, converts each one twice with dwg2step-acadsharp, evaluates and
normalises each STEP file, and compares. Anything that differs between the two runs and is not named in
DIVERGENCE_NAMES (and in docs/reproducibility.md) fails the run. `verify` needs no docker, no converter and no
network: it checks a release directory against its own SHA256SUMS and manifest.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from . import step_normalise

ROOT = Path(__file__).resolve().parent.parent

# Every field that may legitimately differ between two runs from the same pinned inputs. Each name is
# explained in docs/reproducibility.md; a field that differs and is not here fails the run.
DIVERGENCE_NAMES = (
    "step.FILE_NAME.time_stamp",
    "status.wall_time_seconds",
    "status.output.path",
    "status.output.sha256",
    "image.built_image_id",
)
JSON_ALLOWED = {"status": {"status.wall_time_seconds", "status.output.path", "status.output.sha256"}}


class FreezeBlocked(Exception):
    """A pinned value is missing. The release is blocked, nothing defaults."""


def step_divergence(a, b):
    return [] if step_normalise.same(a, b) else ["step: differs beyond FILE_NAME time stamp"]


def _paths(kind_path, a, b, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s.%s" % (kind_path, k))
            else:
                _paths("%s.%s" % (kind_path, k), a[k], b[k], out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _paths("%s[%d]" % (kind_path, i), x, y, out)
    elif a != b:
        out.append(kind_path)


def json_divergence(kind, a, b):
    """Paths where two records differ and the difference is not on the list."""
    out = []
    _paths(kind, a, b, out)
    return [p for p in out if p not in JSON_ALLOWED.get(kind, ())]


# ---- the manifest ----------------------------------------------------------------------------

def build_manifest(corpus, fixtures, images, converters, evaluator, numeric_policy, version):
    for name, v in (("corpus", corpus), ("fixtures", fixtures), ("images", images), ("converters", converters),
                    ("evaluator", evaluator), ("numeric_policy", numeric_policy)):
        if not v:
            raise FreezeBlocked("%s is empty" % name)
    for k in ("revision", "bundle_sha256", "manifest_sha256"):
        if not corpus.get(k):
            raise FreezeBlocked("corpus.%s is empty" % k)
    for f in fixtures:
        need = ["source_sha256"] + (["step_sha256", "signature_sha256"] if f["outcome"] == "CONVERTED" else ["refusal"])
        for k in need:
            if not f.get(k):
                raise FreezeBlocked("%s: %s is empty" % (f["id"], k))
    for n, i in images.items():
        if not i.get("base") or not i.get("built_image_id"):
            raise FreezeBlocked("image %s has no pinned base or no built image id" % n)
    fx = sorted(fixtures, key=lambda f: f["id"])
    return {
        "schema_version": "pvec-gold/release-manifest/1",
        "release": version,
        "status": "FROZEN_CANDIDATE_NOT_TAGGED",
        "pins": {
            "corpus": corpus,
            "source_hashes": {f["id"]: f["source_sha256"] for f in fx},
            "signatures": {f["id"]: f["signature_sha256"] for f in fx if f["outcome"] == "CONVERTED"},
            "step_hashes": {f["id"]: f["step_sha256"] for f in fx if f["outcome"] == "CONVERTED"},
            "images": images,
            "converters": converters,
            "evaluator": evaluator,
            "numeric_policy": numeric_policy,
        },
        "refused": {f["id"]: f["refusal"] for f in fx if f["outcome"] != "CONVERTED"},
        "step_hash_note": "sha256 of the STEP text with the FILE_NAME time stamp replaced by <TIMESTAMP>",
    }


def dump_manifest(m):
    return json.dumps(m, indent=2, sort_keys=True) + "\n"


def against_manifest(m, fixtures):
    pins = m["pins"]
    out = {}
    seen = set()
    for f in fixtures:
        seen.add(f["id"])
        if f["id"] not in pins["source_hashes"]:
            out[f["id"]] = "NOT_IN_MANIFEST"
            continue
        bad = []
        if f["source_sha256"] != pins["source_hashes"][f["id"]]:
            bad.append("source_sha256")
        if f["outcome"] == "CONVERTED":
            if f["step_sha256"] != pins["step_hashes"].get(f["id"]):
                bad.append("step_sha256")
            if f["signature_sha256"] != pins["signatures"].get(f["id"]):
                bad.append("signature_sha256")
        elif f["id"] not in m["refused"]:
            bad.append("outcome")
        out[f["id"]] = "DIFFERS: " + ", ".join(bad) if bad else "MATCH"
    for i in pins["source_hashes"]:
        if i not in seen:
            out[i] = "MISSING_IN_RUN"
    return out


# ---- SHA256SUMS ------------------------------------------------------------------------------

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_sha256sums(d):
    d = Path(d)
    names = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (d / "SHA256SUMS").write_text("".join("%s  %s\n" % (_sha(d / n), n) for n in names))


def verify_sha256sums(d):
    """Names whose hash differs or whose file is missing, plus files that are not listed."""
    d = Path(d)
    bad, listed = [], set()
    for line in (d / "SHA256SUMS").read_text().splitlines():
        h, n = line.split("  ", 1)
        listed.add(n)
        if not (d / n).is_file() or _sha(d / n) != h:
            bad.append(n)
    for p in d.rglob("*"):
        if p.is_file() and p.name != "SHA256SUMS" and str(p.relative_to(d)) not in listed:
            bad.append(str(p.relative_to(d)))
    return sorted(bad)


# ---- the docker half (runs inside the driver container) --------------------------------------

TREE = os.environ.get("GOLD_TREE", str(ROOT))   # this tree, as the docker daemon names the path
EXPECTED_REFUSED_CODE = 15


def docker(*a, check=True, text=True):
    r = subprocess.run(["docker", *a], capture_output=True, text=text)
    if check and r.returncode != 0:
        raise SystemExit("docker %s failed (%d): %s" % (" ".join(a[:3]), r.returncode, (r.stderr or r.stdout)[-2000:]))
    return r


def image_id(ref):
    return docker("image", "inspect", "--format", "{{.Id}}", ref).stdout.strip()


def pinned_inputs():
    pin = json.loads((ROOT / "corpus" / "r0-open.pin.json").read_text())
    out = {}
    for role, s in json.loads((ROOT / "corpus" / "r0-open" / "manifest.json").read_text())["container_images"].items():
        m = re.match(r"(\S+) (sha256:[0-9a-f]{64})", s)
        out[role] = (m.group(1), m.group(2))
    return pin, out


def regenerate_dwgs(platform, workdir):
    """Rewrite the r0-open DWGs in containers pinned by the digests in corpus/r0-open.pin.json."""
    _, imgs = pinned_inputs()
    rust = "%s@%s" % imgs["writer_and_own_reader"]
    dotnet = "%s@%s" % imgs["cross_reader"]
    for ref, cmd in ((rust, "sh /work/tools/r0-open/rust/run-write.sh AC1032"),
                     (dotnet, "sh /work/tools/r0-open/acadsharp-run.sh AC1032")):
        r = docker("run", "--rm", "--platform", platform, "-v", "%s:/work" % TREE, ref, "sh", "-c", cmd)
        print(r.stdout[-400:])
    return {"writer_and_own_reader": rust, "cross_reader": dotnet}


def run_py(*args):
    r = subprocess.run([sys.executable, "-m", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("%s failed: %s" % (" ".join(args[:2]), (r.stdout + r.stderr)[-2000:]))
    return r.stdout


def convert(platform, image, dwg, out, name, env=()):
    out.mkdir(parents=True, exist_ok=True)
    mounts = []
    for d in dict.fromkeys((str(dwg.parent), str(out))):
        mounts += ["-v", "%s:%s" % (d, d)]
    envs = [x for e in env for x in ("-e", e)]
    r = docker("run", "--rm", "--platform", platform, *envs, *mounts, image, "--in", str(dwg),
               "--out", str(out / (name + ".step")), "--status", str(out / (name + ".status.json")), check=False)
    return r.returncode


def evaluate(platform, evalimg, step, policy_version):
    out = step.with_suffix(".verification.json")
    docker("run", "--rm", "--platform", platform, "-v", "%s:%s" % (step.parent, step.parent), evalimg, "step_eval",
           "--in", str(step), "--out", str(out), "--policy-version", policy_version)
    return out


def run(platform, label, out_dir, against=None, write_release=None, skip_regen=False):
    from . import numeric
    arch = platform.split("/")[1]
    pol = numeric.load_policy()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    timings = {}
    stepval = "gold-stepval:" + arch
    conv = "gold-dwg2step-acadsharp:repro-" + arch
    docker("build", "-q", "--platform", platform, "-f", str(ROOT / "docker/step-validator/Dockerfile"), "-t", stepval, str(ROOT))
    docker("build", "-q", "--platform", platform, "-f", str(ROOT / "tools/converters/acadsharp/Dockerfile"), "-t", conv, str(ROOT))
    timings["build_images_seconds"] = round(time.monotonic() - t0, 1)
    t1 = time.monotonic()
    built = {"step-validator": image_id(stepval), "dwg2step-acadsharp": image_id(conv)}
    pin, _ = pinned_inputs()
    corpus_dir = ROOT / "corpus" / "r0-open"
    regen = None
    if not skip_regen:
        regen = regenerate_dwgs(platform, ROOT)
        regen_corpus = out_dir / "corpus-regenerated"
        run_py("runner.r0_open", "assemble", ".out-r0open/AC1032/run1", str(regen_corpus), "--writer-info", "tools/r0-open/writer-info.json")
        # the revision's README.md is hand-written prose, not derived from any DWG, so it is copied in and the
        # checksums are rewritten the way the committed ones were (docs/reproducibility.md)
        (regen_corpus / "README.md").write_bytes((ROOT / "corpus" / "r0-open" / "README.md").read_bytes())
        from . import r0_open
        r0_open.write_sums(regen_corpus)
        run_py("runner.r0_open", "check", str(regen_corpus))
        regen_bundle = run_py("runner.r0_open", "bundle", str(regen_corpus), str(out_dir / "regen.tar")).strip()
        corpus_dir = regen_corpus
    else:
        regen_bundle = None
    timings["regenerate_dwgs_seconds"] = round(time.monotonic() - t1, 1)
    t2 = time.monotonic()
    manifest_sha = hashlib.sha256((corpus_dir / "manifest.json").read_bytes()).hexdigest()
    mf = json.loads((corpus_dir / "manifest.json").read_text())
    fixtures, diverged_total = [], []
    versions, product_seen = {}, {}
    for f in sorted(mf["fixtures"], key=lambda f: f["id"]):
        if f["status"] != "ACCEPTED":
            continue
        fid = f["id"]
        dwg = (corpus_dir / f["dwg"]["path"]).resolve()
        rec = {"id": fid, "source_sha256": hashlib.sha256(dwg.read_bytes()).hexdigest()}
        diffs, runs = [], {}
        for name in ("a", "b"):
            # a is run without SOURCE_DATE_EPOCH on purpose: the time stamp is a named divergence
            d = out_dir / "work" / fid / name
            code = convert(platform, conv, dwg, d, "primary")
            st = json.loads((d / "primary.status.json").read_text())
            runs[name] = {"code": code, "status": st, "dir": d}
        rec["converter_wall_seconds"] = runs["a"]["status"].get("wall_time_seconds")
        diffs += json_divergence("status", runs["a"]["status"], runs["b"]["status"])
        if runs["a"]["code"] != runs["b"]["code"]:
            diffs.append("exit_code")
        if runs["a"]["code"] != 0:
            rec.update(outcome="REFUSED", refusal="exit %d %s" % (runs["a"]["code"], runs["a"]["status"].get("error", {}).get("class", "")), diverged=diffs)
        else:
            texts, sigs, vers = {}, {}, {}
            for name in ("a", "b"):
                d = runs[name]["dir"]
                texts[name] = (d / "primary.step").read_text()
                v = evaluate(platform, stepval, d / "primary.step", pol.version)
                vers[name] = json.loads(v.read_text())
                run_py("runner.normalize", str(v), str(d / "primary.signature.json"))
                sigs[name] = (d / "primary.signature.json").read_bytes()
            diffs += step_divergence(texts["a"], texts["b"])
            diffs += json_divergence("verification", vers["a"], vers["b"])
            if sigs["a"] != sigs["b"]:
                diffs.append("signature")
            norm = step_normalise.normalise(texts["a"])
            sig = json.loads(sigs["a"])
            versions = sig["versions"]
            product_seen = runs["a"]["status"]["product"]
            rec.update(outcome="CONVERTED", step_sha256=hashlib.sha256(norm.encode()).hexdigest(),
                       signature_sha256=hashlib.sha256(sigs["a"]).hexdigest(), step_normalised=norm, signature_bytes=sigs["a"].decode(),
                       diverged=diffs)
        fixtures.append(rec)
        diverged_total += ["%s: %s" % (fid, d) for d in diffs]
    timings["convert_evaluate_normalise_seconds"] = round(time.monotonic() - t2, 1)
    status_ok = not diverged_total
    product = product_seen
    tool_version = re.search(r'ToolVersion = "([^"]+)"', (ROOT / "tools/converters/acadsharp/Program.cs").read_text()).group(1)
    report = {
        "schema_version": "pvec-gold/reproducibility/1",
        "label": label, "platform": platform,
        "images_built": built,
        "pinned_inputs": {"base_images": pinned_inputs()[1], "regenerated_with": regen},
        "regenerated_corpus": None if regen_bundle is None else {"bundle_sha256": regen_bundle, "pinned_bundle_sha256": pin["bundle_sha256"],
                                                                 "matches_pin": regen_bundle == pin["bundle_sha256"],
                                                                 "files_differing_from_committed": differing_files(ROOT / "corpus" / "r0-open", corpus_dir)},
        "fixtures": [{k: v for k, v in f.items() if k not in ("step_normalised", "signature_bytes")} for f in fixtures],
        "unlisted_divergences": diverged_total,
        "divergence_list": list(DIVERGENCE_NAMES),
        "timings": timings,
        "result": "PASS" if status_ok and (regen_bundle is None or regen_bundle == pin["bundle_sha256"]) else "FAIL",
    }
    pieces = dict(
        corpus={"revision": "r0-open", "bundle_sha256": pin["bundle_sha256"], "manifest_sha256": manifest_sha},
        fixtures=[{k: v for k, v in f.items() if k not in ("step_normalised", "signature_bytes")} for f in fixtures],
        images={"dwg2step-acadsharp": {"base": _base_of("tools/converters/acadsharp/Dockerfile"), "built_image_id": built["dwg2step-acadsharp"]},
                "step-validator": {"base": _base_of("docker/step-validator/Dockerfile"), "built_image_id": built["step-validator"]}},
        converters={"acadsharp-dwg2step": "%s %s, tool %s" % (product.get("name", ""), product.get("version", ""), tool_version)},
        evaluator={k: versions.get(k, "") for k in ("evaluator", "occt")},
        numeric_policy=versions.get("policy", ""), version="r0-open-1")
    if against:
        frozen = json.loads(Path(against).read_text())
        report["against"] = {"manifest": str(against), "per_fixture": against_manifest(frozen, pieces["fixtures"]),
                             "base_images_pinned_equal": {n: frozen["pins"]["images"].get(n, {}).get("base") == i["base"] for n, i in pieces["images"].items()},
                             "built_image_id_same_as_frozen": {n: frozen["pins"]["images"].get(n, {}).get("built_image_id") == i["built_image_id"] for n, i in pieces["images"].items()}}
        if not all(report["against"]["base_images_pinned_equal"].values()):
            report["result"] = "FAIL"
        if any(v != "MATCH" for v in report["against"]["per_fixture"].values()):
            report["result"] = "FAIL"
    (out_dir / "reproducibility.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if write_release:
        rel = Path(write_release)
        m = build_manifest(**pieces)
        (rel / "signatures").mkdir(parents=True, exist_ok=True)
        (rel / "step").mkdir(parents=True, exist_ok=True)
        for f in fixtures:
            if f["outcome"] == "CONVERTED":
                (rel / "signatures" / (f["id"] + ".signature.json")).write_text(f["signature_bytes"])
                (rel / "step" / (f["id"] + ".step")).write_text(f["step_normalised"])
        (rel / "manifest.json").write_text(dump_manifest(m))
        write_sha256sums(rel)
    print(json.dumps({"result": report["result"], "unlisted_divergences": diverged_total}, indent=1))
    return 0 if report["result"] == "PASS" else 1


def differing_files(committed, regenerated):
    out = []
    names = {str(p.relative_to(d)) for d in (committed, regenerated) for p in d.rglob("*") if p.is_file()}
    for n in sorted(names):
        a, b = committed / n, regenerated / n
        if not (a.is_file() and b.is_file()) or a.read_bytes() != b.read_bytes():
            out.append(n)
    return out


def _base_of(dockerfile):
    text = (ROOT / dockerfile).read_text()
    refs = re.findall(r"^FROM\s+(\S+@sha256:[0-9a-f]{64})", text, re.M) + re.findall(r"^ARG BASE=(\S+@sha256:[0-9a-f]{64})", text, re.M)
    return ", ".join(dict.fromkeys(refs))


def verify(rel):
    rel = Path(rel)
    bad = verify_sha256sums(rel)
    m = json.loads((rel / "manifest.json").read_text())
    for fid, h in m["pins"]["signatures"].items():
        if _sha(rel / "signatures" / (fid + ".signature.json")) != h:
            bad.append("manifest signature pin: " + fid)
    for fid, h in m["pins"]["step_hashes"].items():
        if _sha(rel / "step" / (fid + ".step")) != h:
            bad.append("manifest step pin: " + fid)
    print("verified" if not bad else "MISMATCH: " + ", ".join(bad))
    return 1 if bad else 0


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="runner.reproduce")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--platform", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--against")
    r.add_argument("--write-release")
    r.add_argument("--skip-regen", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("dir")
    a = p.parse_args(argv)
    if a.cmd == "verify":
        return verify(a.dir)
    return run(a.platform, a.label, a.out, a.against, a.write_release, a.skip_regen)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
