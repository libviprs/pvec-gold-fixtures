"""One command from a DWG to the fixture artifacts, with the containers torn down on every exit path.

    docker compose run --rm fixture-runner generate [FIXTURE_ID ...]
    python3 -m runner.generate generate [FIXTURE_ID ...] [options]

Per fixture (FIXTURES/<id>/source.dwg), results land in FIXTURES/<id>/generated/:

    hash the source; load the known truth if fixtures/known-truth/<id>/expected.math.json exists;
    convert with the primary and the secondary converter service; run the independent evaluator on both
    STEP files; normalise both records to signatures; compare; classify the evidence (ADR 0001, 0006);
    accept or quarantine; write verdict.json, manifest.json and checksums.sha256.

The services are the docker-compose.yml ones, driven with `docker compose run --rm`, so the bind mounts
and the no-network, read-only settings are the compose file's. Nothing here knows a vendor command line,
a licence or a key. Any way out of the run ends in `docker compose down --volumes --remove-orphans`:
success, a converter that exits non-zero, an exception, SIGINT or SIGTERM. A converter failure quarantines
that fixture with its reason and the run goes on; the exit status is non-zero if anything was quarantined.

It refuses to start, before any container exists, if the numeric policy version cannot be read, if the
two converters do not have distinct lineages (ADR 0009), or if the image digest of any of the three
services cannot be resolved. The run log says per stage whether it ran native x64 or arm64.

Re-runs with unchanged inputs reproduce checksums.sha256 except for what the converters themselves vary:
the FILE_NAME time stamp in the STEP header and wall_time_seconds in the status record.
"""
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
from pathlib import Path

from . import expected_math as em, normalize, numeric, qualify_probes as qp, verification
from .r0_open import ORACLE_SCOPES, lineage_problems

ROOT = Path(__file__).resolve().parent.parent
DOCKER = os.environ.get("DOCKER", "docker")
LINEAGE = {"cadex-converter": "cadex", "oda-converter": "oda", "acadsharp-converter": "acadsharp",
           "libredwg-converter": "libredwg"}
EXACT = (qp.STRUCTURAL_EXACT, qp.GEOMETRIC)
ARTIFACTS = ("primary.step", "secondary.step", "primary.status.json", "secondary.status.json",
             "primary.verification.json", "secondary.verification.json", "primary.signature.json",
             "secondary.signature.json", "verdict.json", "manifest.json")
CHECKSUMS = "checksums.sha256"


class Refused(Exception):
    pass


def docker(*args, check=False):
    r = subprocess.run([DOCKER] + list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise Refused("%s %s failed: %s" % (DOCKER, " ".join(args[:2]), r.stderr.strip()))
    return r


def host_arch():
    a = docker("info", "--format", "{{.Architecture}}").stdout.strip()
    return "native x64" if a in ("x86_64", "amd64") else "arm64 host (%s)" % (a or "unknown")


def where_converter(platform_name, arch):
    """A linux/amd64 container on an x86_64 host is native; on any other host it would be emulated."""
    if platform_name == "linux/amd64":
        return "native x64" if arch == "native x64" else "EMULATED amd64 under the %s" % arch
    return "arm64" if platform_name == "linux/arm64" else arch


def stage(name, where, fixture=""):
    print("stage %s %s on %s" % (name, fixture, where), flush=True)


def snapshot():
    ps = docker("ps", "-a", "--format", "{{.ID}}").stdout.split()
    vols = docker("volume", "ls", "-q").stdout.split()
    return {"containers": sorted(ps), "volumes": sorted(vols)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence_class(cells, has_truth, agree):
    """(class, ADR 0006 reason or None). cells: {converter: [cell]} against the known truth, when there is one.
    With truth, only exact cells from both converters give KNOWN_TRUTH_EXACT; without it, agreement of the
    two normalised signatures gives DUAL_ORACLE_EQUIVALENT and anything else is an unresolved disagreement."""
    if has_truth:
        classes = {c["class"] for cs in cells.values() for c in cs}
        if classes & {qp.UNSUPPORTED, qp.MISSING}:
            return "QUARANTINED", "UNSUPPORTED_ENTITY"
        if classes - set(EXACT):
            return "QUARANTINED", "APPROXIMATION"
        return "KNOWN_TRUTH_EXACT", None
    return ("DUAL_ORACLE_EQUIVALENT", None) if agree else ("QUARANTINED", "UNRESOLVED_DISAGREEMENT")


def preflight(a):
    try:
        pol = numeric.load_policy(directory=a.policy_dir)
    except numeric.PolicyError as e:
        raise Refused("numeric policy version cannot be resolved: %s" % e)
    lin = dict(LINEAGE)
    lin.update(x.split("=", 1) for x in a.lineage)
    bad = lineage_problems([{"id": s, "lineage": lin.get(s, "")} for s in (a.primary, a.secondary)])
    if bad:
        raise Refused(bad[0])
    if a.primary == a.secondary:
        raise Refused("the primary and the secondary converter are the same service")
    cfg = docker("compose", "-f", str(a.compose_file), "config", "--format", "json", check=True)
    services = json.loads(cfg.stdout)["services"]
    info = {}
    for s in (a.primary, a.secondary, a.validator):
        if s not in services or not services[s].get("image"):
            raise Refused("service %s has no image in %s" % (s, a.compose_file))
        r = docker("image", "inspect", "--format", "{{.Id}}", services[s]["image"])
        digest = r.stdout.strip()
        if r.returncode != 0 or not digest.startswith("sha256:"):
            raise Refused("image digest of %s (%s) cannot be resolved: %s" % (s, services[s]["image"], r.stderr.strip() or "no digest"))
        info[s] = {"image": services[s]["image"], "image_digest": digest, "platform": services[s].get("platform", "")}
    return pol, lin, info


def compose_run(a, service, *args):
    return docker("compose", "-f", str(a.compose_file), "run", "--rm", service, *args)


def load_json(p):
    return json.loads(Path(p).read_text()) if Path(p).is_file() else None


def run_fixture(a, pol, lin, info, arch, fid):
    d = Path(a.fixtures) / fid
    src = d / "source.dwg"
    if not src.is_file():
        raise Refused("%s has no source.dwg" % d)
    out = d / "generated"
    out.mkdir(exist_ok=True)
    for n in ARTIFACTS + (CHECKSUMS,):
        (out / n).unlink(missing_ok=True)
    cin = "/fixtures/%s/source.dwg" % fid
    cout = "/fixtures/%s/generated/" % fid
    stage("hash", platform.machine(), fid)
    src_sha = sha256(src)
    truth_path = Path(a.truth) / fid / "expected.math.json"
    truth = em.load(truth_path) if truth_path.is_file() else None
    stage("truth", "present" if truth else "absent", fid)
    problems, status, ver = [], {}, {}
    for role, svc in (("primary", a.primary), ("secondary", a.secondary)):
        stage("convert-" + role, where_converter(info[svc]["platform"], arch), fid)
        r = compose_run(a, svc, "--in", cin, "--out", cout + role + ".step", "--status", cout + role + ".status.json")
        status[role] = load_json(out / (role + ".status.json"))
        if r.returncode != 0 or not (out / (role + ".step")).is_file():
            err = (status[role] or {}).get("error") or {}
            problems.append((role, err.get("class", "CONVERSION_FAILED"), err.get("message", "exit %d: %s" % (r.returncode, r.stderr.strip()))))
    if not problems:
        for role in ("primary", "secondary"):
            stage("validate-" + role, where_converter(info[a.validator]["platform"], arch), fid)
            r = compose_run(a, a.validator, "step_eval", "--in", cout + role + ".step", "--out", cout + role + ".verification.json",
                            "--policy-version", pol.version)
            vdoc = load_json(out / (role + ".verification.json"))
            errs = verification.validate_doc(vdoc) if vdoc else ["no verification record"]
            if r.returncode != 0 or errs:
                problems.append((role, "EVALUATOR_FAILED", "step_eval exit %d: %s" % (r.returncode, (errs or [r.stderr.strip()])[0])))
            ver[role] = vdoc
    sigs, differing, cells = {}, [], {}
    if not problems:
        stage("normalise", "native x64" if platform.machine() in ("x86_64", "AMD64") else "arm64", fid)
        for role in ("primary", "secondary"):
            errs = normalize.run(out / (role + ".verification.json"), out / (role + ".signature.json"))
            if errs:
                problems.append((role, "NORMALISE_FAILED", errs[0]))
            else:
                sigs[role] = json.loads((out / (role + ".signature.json")).read_text())
    if not problems:
        stage("compare", platform.machine(), fid)
        differing = normalize.differing_fields(sigs["primary"], sigs["secondary"])
        if truth:
            cells = qp.qualify_probe(pol, truth, {r: (ver[r], status[r]) for r in ("primary", "secondary")})
        cls, reason = evidence_class(cells, truth is not None, not differing)
        detail = "signatures differ in: %s" % ", ".join(differing) if differing and not truth else ""
    else:
        cls, reason = "QUARANTINED", ("MALFORMED_FIXTURE" if problems[0][1] == "INPUT_MALFORMED" else "UNSUPPORTED_ENTITY")
        detail = "; ".join("%s: %s: %s" % p for p in problems)
    verdict = {"schema_version": "pvec-gold/fixture-verdict/1", "fixture_id": fid, "evidence_class": cls, "reason": reason,
               "detail": detail, "known_truth": truth is not None, "cells": cells, "signature_differences": differing,
               "oracle_scope": a.oracle_scope, "evidence_scope": "STEP_ORACLE"}
    manifest = {"schema_version": "pvec-gold/fixture-manifest/1", "fixture_id": fid, "source_sha256": src_sha,
                "numeric_policy_version": pol.version,
                "evaluator_version": ((ver.get("primary") or {}).get("tool") or {}).get("evaluator_version"),
                "occt_version": ((ver.get("primary") or {}).get("tool") or {}).get("occt_version"),
                "oracle_scope": a.oracle_scope, "evidence_scope": "STEP_ORACLE",
                "converters": [{"role": r, "service": s, "id": (status[r] or {}).get("converter"), "version": ((status[r] or {}).get("product") or {}).get("version"),
                                "lineage": lin[s], "image": info[s]["image"], "image_digest": info[s]["image_digest"], "platform": info[s]["platform"]}
                               for r, s in (("primary", a.primary), ("secondary", a.secondary))],
                "validator": {"service": a.validator, "image": info[a.validator]["image"], "image_digest": info[a.validator]["image_digest"]}}
    for n, doc in (("verdict.json", verdict), ("manifest.json", manifest)):
        (out / n).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    names = sorted(n for n in ARTIFACTS if (out / n).is_file())
    (out / CHECKSUMS).write_text("".join("%s  %s\n" % (sha256(out / n), n) for n in names))
    print("%s: %s%s" % (fid, cls, " (%s)" % reason if reason else ""), flush=True)
    return cls == "QUARANTINED"


def generate(a):
    ids = a.ids or sorted(p.parent.name for p in Path(a.fixtures).glob("*/source.dwg"))
    if not ids:
        raise Refused("no fixtures under %s (looked for <id>/source.dwg)" % a.fixtures)
    pol, lin, info = preflight(a)
    arch = host_arch()
    before = snapshot() if a.check_leaks else None
    quarantined = 0
    try:
        for fid in ids:
            quarantined += run_fixture(a, pol, lin, info, arch, fid)
    finally:
        teardown(a)
    if before is not None:
        after = snapshot()
        left = [k + " " + x for k in before for x in after[k] if x not in before[k]]
        if left:
            raise Refused("leaked after teardown: " + ", ".join(left))
        print("leak check: docker ps -a and docker volume ls are as they were", flush=True)
    print("%d of %d fixtures quarantined" % (quarantined, len(ids)), flush=True)
    return 1 if quarantined else 0


def teardown(a):
    docker("compose", "-f", str(a.compose_file), "down", "--volumes", "--remove-orphans")


def main(argv):
    ap = argparse.ArgumentParser(prog="runner.generate")
    ap.add_argument("command", choices=["generate"])
    ap.add_argument("ids", nargs="*", metavar="FIXTURE_ID")
    ap.add_argument("--fixtures", default=os.environ.get("FIXTURE_DIR", str(ROOT / "fixtures")))
    ap.add_argument("--truth", default=str(ROOT / "fixtures" / "known-truth"))
    ap.add_argument("--compose-file", default=str(ROOT / "docker-compose.yml"))
    ap.add_argument("--primary", default="cadex-converter")
    ap.add_argument("--secondary", default="oda-converter")
    ap.add_argument("--validator", default="step-validator")
    ap.add_argument("--oracle-scope", default="VENDOR_CONVERTERS", choices=[s for s in ORACLE_SCOPES if s != "NONE"])
    ap.add_argument("--lineage", action="append", default=[], metavar="SERVICE=NAME")
    ap.add_argument("--policy-dir")
    ap.add_argument("--check-leaks", action="store_true")
    a = ap.parse_args(argv)
    a.compose_file = Path(a.compose_file)

    def on_term(sig, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_term)
    try:
        return generate(a)
    except KeyboardInterrupt:
        print("interrupted: containers torn down", flush=True)
        return 130
    except Refused as e:
        print("refused: %s" % e, flush=True)
        teardown(a)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
