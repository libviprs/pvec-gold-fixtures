#!/usr/bin/env python3
"""A stand-in for the docker CLI, used by tests/test_generate.py. It logs every call to $FAKE_LOG and
answers the few calls runner/generate.py makes. Knobs, all environment variables:

  FAKE_FIXTURES   host dir that /fixtures maps to
  FAKE_VERIF      a verification record the step-validator service copies out (default: validator self-test line)
  FAKE_VERIF_<SERVICE>  per-converter override, keyed by the converter's role, primary or secondary
  FAKE_FAIL       a service name whose run exits 15 and writes an ERROR status
  FAKE_HANG       a service name whose run sleeps until killed
  FAKE_NO_IMAGE   an image name `image inspect` cannot find
  FAKE_CONTAINERS  what `container ls -aq --filter label=...` prints: the project's containers, the runner's own first
  FAKE_PS / FAKE_VOLS  what `ps -a` and `volume ls` print (files), so a leak can be staged
"""
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

args = sys.argv[1:]
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(" ".join(args) + "\n")
ROOT = Path(os.environ["FAKE_ROOT"])
IMAGES = {"acadsharp-converter": "pvec-gold/acadsharp-converter:local", "libredwg-converter": "pvec-gold/libredwg-converter:local",
          "step-validator": "pvec-gold/step-validator:local"}


def host(p):
    return Path(os.environ["FAKE_FIXTURES"]) / p[len("/fixtures/"):]


def opt(name):
    return args[args.index(name) + 1] if name in args else None


a = [x for x in args if x not in ("-f",)]
if args[:1] == ["info"]:
    print("x86_64")
elif args[:2] == ["image", "inspect"]:
    img = args[-1]
    if img == os.environ.get("FAKE_NO_IMAGE"):
        print("Error: No such image: " + img, file=sys.stderr)
        sys.exit(1)
    print("sha256:" + hashlib.sha256(img.encode()).hexdigest())
elif args[:1] == ["ps"]:
    p = os.environ.get("FAKE_PS")
    sys.stdout.write(Path(p).read_text() if p else "")
elif args[:2] == ["container", "ls"]:
    p = os.environ.get("FAKE_CONTAINERS")
    sys.stdout.write(Path(p).read_text() if p else "")
elif args[:2] == ["volume", "ls"]:
    p = os.environ.get("FAKE_VOLS")
    sys.stdout.write(Path(p).read_text() if p else "")
elif "config" in args:
    print(json.dumps({"services": {s: {"image": i, "platform": "linux/amd64"} for s, i in IMAGES.items()}}))
elif "down" in args:
    pass
elif "run" in args:
    i = args.index("run")
    rest = args[i + 1:]
    rest = [x for x in rest if x != "--rm"]
    svc, tail = rest[0], rest[1:]
    if svc == os.environ.get("FAKE_HANG"):
        time.sleep(60)
    sd = ROOT / "fixtures" / "validator-selftest"
    if svc == "step-validator":
        out = host(tail[tail.index("--out") + 1])
        role = Path(tail[tail.index("--out") + 1]).name.split(".")[0].upper()
        v = os.environ.get("FAKE_VERIF_" + role) or os.environ.get("FAKE_VERIF") or str(sd / "verification" / "x64" / "line.verification.json")
        d = json.loads(Path(v).read_text())
        d["numeric_policy_version"] = tail[tail.index("--policy-version") + 1]
        out.write_text(json.dumps(d))
    else:
        src, out = host(opt_in := tail[tail.index("--in") + 1]), host(tail[tail.index("--out") + 1])
        st = host(tail[tail.index("--status") + 1])
        fail = svc == os.environ.get("FAKE_FAIL")
        rec = {"schema_version": "pvec-gold/converter-status/1", "converter": svc.replace("-converter", "") + "-fake",
               "status": "ERROR" if fail else "OK", "exit_code": 15 if fail else 0,
               "input": {"path": opt_in, "sha256": hashlib.sha256(src.read_bytes()).hexdigest()}, "output": None,
               "product": {"name": svc, "version": "9.9"}, "declared_schema": None, "wall_time_seconds": "0.001", "warnings": [],
               "error": {"code": 15, "class": "CONVERSION_FAILED", "message": "fake failure"} if fail else None}
        if not fail:
            shutil.copy(sd / "line.step", out)
            rec["output"] = {"path": tail[tail.index("--out") + 1], "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
        st.write_text(json.dumps(rec))
        sys.exit(15 if fail else 0)
