# Docker workflow

Everything that executes in this pipeline executes in a container on a native docker host. The Mac I work
from only runs `ssh`, `git` and `docker` clients. That is a rule, not a preference: an x64 result
under Rosetta is not the experiment a native runner would run. Every `docker run` and `docker build` passes an explicit `--platform`, and every number in these
documents says whether it is native x64 or arm64.

## The services and their images

The topology, so you can rebuild it without reading `docker-compose.yml`. The compose file has the open converter (`acadsharp-converter`), `step-validator` and `fixture-runner`; the LibreDWG converter is pulled by digest from its own repository and joins the compose file when its image is published. Images are tagged `:local` and none
of them is pushed anywhere, except that the two open images may be published by digest (ADR 0007, amendment).

| service / image | what it is | platform | network | licence | defined in |
|---|---|---|---|---|---|
| `step-validator` (`pvec-gold/step-validator:local`, or `gold-stepval:<arch>` when built by the scripts) | the independent STEP evaluator, Open CASCADE only | amd64 and arm64 | none | none | `docker/step-validator/` |
| `dwg2step-acadsharp` (`gold-dwg2step-acadsharp:*`; publishable name `ghcr.io/libviprs/pvec-gold-dwg2step-acadsharp`) | the open converter on ACadSharp, MIT | amd64 and arm64 | none | none | `tools/converters/acadsharp/` |

| `fixture-runner` (`pvec-gold/fixture-runner:local`) | `docker compose run --rm fixture-runner generate [id ...]`: drives two converter services and the validator with the host socket (`runner/generate.py`) | validator platform | none | none | `docker/fixture-runner/` |

The python tests run in the `docker/py` image (python, git and `requirements.txt`, no converter, no converter). `generate` needs two converters with distinct lineages, so a real run of it waits on the second
open converter ([open-route-status.md](open-route-status.md)). The open route's one command is
`python3 -m runner.reproduce run` (below), driven from `tools/clean_host.sh`.

All converter services run with a read-only root, `tmpfs` on `/tmp`, all capabilities dropped and
`no-new-privileges`. No image holds a licence or a key: see [converters/images-and-setup.md](converters/images-and-setup.md).

## The hosts

- MARS (`devshell@192.168.0.100`): native x86_64, the default for anything x64. Scratch lives under
  `/work/nas-work/<name>`.
- The UGREEN NAS (`rom@192.168.0.10`): native x86_64 as well, the fallback.
- mercury: native arm64 (Colima), for the arm64 half.

`tools/nas.sh` (in the workspace root, `libviprs/tools/nas.sh`) is the wrapper: `push` copies a tree to a
named scratch dir, `run` executes a command in an image with that tree at `/work`, `build` adds the docker
socket for a driver that itself drives `docker build`, and `clean` removes the scratch dir. `tools/py.sh`
runs python in the `docker/py` image on MARS and `tools/r0-open/mars.sh` does the same for the corpus tooling.

## The commands

```
tools/py.sh python3 -m unittest discover -s tests -t .        # the python gate (no converter needed)
tools/converters/acadsharp/test.sh mars                        # build and test the open converter, native x64
tools/converters/acadsharp/test.sh mercury                     # the same, native arm64
tools/r0-open/run.sh                                           # rewrite the r0-open DWGs from the authored parameters
tools/clean_host.sh mars --write-release corpus/release/r0-open-1   # a clean-host rebuild and regeneration
tools/check_no_licence.sh IMAGE [LOG...]                       # no licence material in an image's history or layers
tools/vendor_guard.sh --tree                                   # no third-party archive, licence file or key-shaped string
```

## Rules that do not bend

- No credential is written to a file, echoed into a log, or copied to a build host.
- No `docker prune` and no restart of a shared daemon. Cleanliness comes from a throw-away daemon
  (`tools/clean_host.sh`) or from removing exactly the images a script made (`--done`).
- Inputs are pinned: base images by the digest of their multi-arch index, upstream sources by full commit,
  OCCT by exact package version. A build that resolves anything else stops.
