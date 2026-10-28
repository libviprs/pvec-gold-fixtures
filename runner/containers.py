"""Run a throw-away container from a process that has the docker CLI and the host's socket.

The docker daemon resolves a -v source on the host, not in the process that asks. So a tree that lives in a
docker volume is mounted by volume name, and a process-local path is turned into the path the container sees
with cpath(). GOLD_VOLUME names the volume and GOLD_VOLUME_AT is where this process has it mounted; without
GOLD_VOLUME the directories are bind-mounted at the same path.
"""
import os
import platform
import subprocess
from pathlib import Path

ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine(), "amd64")
PLATFORM = os.environ.get("DOCKER_PLATFORM", "linux/" + ARCH)
VOLUME = os.environ.get("GOLD_VOLUME")
VOLUME_AT = Path(os.environ.get("GOLD_VOLUME_AT", "/work"))


def cpath(p):
    p = Path(p).resolve()
    return str(p) if not VOLUME else "/v/" + str(p.relative_to(VOLUME_AT))


def mounts(*dirs):
    if VOLUME:
        return ["-v", "%s:/v" % VOLUME]
    out = []
    for d in dict.fromkeys(str(Path(x).resolve()) for x in dirs):
        out += ["-v", "%s:%s" % (d, d)]
    return out


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def run(image, args, dirs, name=None, label=None, mem=None, cpus=None, entrypoint=None, extra=()):
    """docker run --rm on the platform, no network, read-only root, nothing added to the container."""
    cmd = ["run", "--rm", "--platform", PLATFORM, "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges:true", *mounts(*dirs)]
    if name:
        cmd += ["--name", name]
    if label:
        cmd += ["--label", label]
    if mem:
        cmd += ["--memory", mem, "--memory-swap", mem]
    if cpus:
        cmd += ["--cpus", str(cpus)]
    if entrypoint:
        cmd += ["--entrypoint", entrypoint]
    return docker(*cmd, *extra, image, *args)


def remove_labelled(label):
    """Remove every container carrying the label (running or not). Returns how many were removed."""
    ids = docker("ps", "-aq", "--filter", "label=" + label).stdout.split()
    if ids:
        docker("rm", "-f", *ids)
    return len(ids)
