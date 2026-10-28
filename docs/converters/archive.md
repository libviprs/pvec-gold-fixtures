# Archive of the proprietary converter workflow

The licensed converters (CAD Exchanger Batch, ODA Drawings SDK, ODA STEP SDK) are commercial. I keep
everything needed to rebuild their images from a licensee's own entitlement, and nothing that belongs
to the vendor or to the licensee. Routine work in `pvec`, `libviprs` and `maplibre-pvec` after the
freeze needs none of it: they read the frozen artifacts (see [the downstream contract](../downstream-contract.md)).

No credential was written to a file, echoed, or copied to the NAS (or MARS) during any phase of this
epic, and licences are supplied at run time from the documented paths below. That is a statement
about this repository's history and about the build hosts, and `tools/check_no_licence.sh` is the scan
that backs it for images and logs.

## What stays in the repository

| path | what it is |
|---|---|
| `docker/cadex/` | Dockerfile, `check-artifact.sh` (refuses a missing or different artifact), `install.sh` (a placeholder that fails on purpose until a licensee fills in the vendor command line) |
| `docker/oda/` | the same three roles for the two ODA SDKs, and the place the wrapper source `oda_dwg2step.cpp` goes (see below) |
| `docker/step-validator/` | the open STEP evaluator image (Open CASCADE only, no licence) |
| `docker/py/` | the python runner image used by the tests |
| `docker-compose.yml` | the services, their images, platforms and licence mounts |
| `runner/`, `tools/` | the pipeline code, the wrappers (`tools/convert_cadex.sh`) and the checks |
| `docs/converters/*.md` | the qualification procedures and exit-code tables |

`docker/oda/src/oda_dwg2step.cpp` does not exist yet. It has to be written against the SDK's API, which
nobody on this project has seen, and writing it from memory would only look finished. The contract it
has to meet is in [oda-qualification.md](oda-qualification.md).

## What is deliberately absent

| absent item | why | where a licensee supplies it |
|---|---|---|
| CAD Exchanger Batch Linux x86_64 build | vendor binary, not redistributable | `vendor/cadex/<CADEX_ARTIFACT>` (git-ignored) |
| ODA Drawings SDK Linux x86_64 build | ODA membership product | `vendor/oda/<ODA_DRAWINGS_ARTIFACT>` (git-ignored) |
| ODA STEP SDK Linux x86_64 build | ODA membership product | `vendor/oda/<ODA_STEP_ARTIFACT>` (git-ignored) |
| CAD Exchanger licence | secret | host file named by `CADEX_LICENSE_FILE`, mounted read-only at `/run/secrets/cadex-license` |
| ODA activation material | secret | host file named by `ODA_ACTIVATION_FILE`, mounted read-only at `/run/secrets/oda-activation` |
| any built vendor image | non-redistributable | built locally as `pvec-gold/cadex-converter:local` and `pvec-gold/oda-converter:local`, never pushed anywhere |
| the exact vendor versions and SHA-256 pins | nobody here holds an entitlement | the licensee chooses a build and passes `CADEX_VERSION`/`CADEX_SHA256` (and the two ODA pairs) as build args |

I can't state the exact vendor versions because I never held the artifacts: no version was installed,
no hash was pinned, and I would rather say that than invent one. The build args are the pin, and a
licensee's first successful build is when a real version and hash get recorded (in the licensee's
own notes, since the artifact must not enter this repository). Where each product is obtained:

- CAD Exchanger Batch: from CAD Exchanger (the vendor), under a licence that has to cover container
  use and DWG import. Terms unread, see [cadex-qualification.md](cadex-qualification.md).
- ODA Drawings SDK and ODA STEP SDK: from the Open Design Alliance, as a member, Linux x86_64 builds.
  Whether the membership level includes both and the DWG writer is unconfirmed, see
  [oda-qualification.md](oda-qualification.md).

## Rebuilding both images from an entitlement

On a native x86_64 Docker host (MARS, or the NAS), with `--platform linux/amd64` throughout:

```
mkdir -p vendor/cadex vendor/oda          # git-ignored; put the artifacts here
docker build --platform linux/amd64 -f docker/cadex/Dockerfile \
    --build-arg CADEX_ARTIFACT=<file> --build-arg CADEX_SHA256=<hash> --build-arg CADEX_VERSION=<build> \
    -t pvec-gold/cadex-converter:local .
docker build --platform linux/amd64 -f docker/oda/Dockerfile \
    --build-arg ODA_DRAWINGS_ARTIFACT=<file> --build-arg ODA_DRAWINGS_SHA256=<hash> \
    --build-arg ODA_STEP_ARTIFACT=<file>     --build-arg ODA_STEP_SHA256=<hash> \
    -t pvec-gold/oda-converter:local .
```

Then `CADEX_LICENSE_FILE=/path/on/the/host ODA_ACTIVATION_FILE=/path/on/the/host docker compose run ...`.
The licence paths are paths and mount points only. If a licence cannot reach the build host without being
copied there, that is the licensee's decision to make (see the blockers in the two qualification pages).

What is verified today: the Dockerfiles fail loudly, with a message that names the problem, for a missing
build arg, a missing artifact, a wrong pinned hash, and a correct pin on a dummy file that gets as far as the
install placeholder (`tools/check_converter_images.sh`, native x64 on MARS). What is not verified: an end to
end rebuild with real vendor artifacts. No entitlement exists here, so that run is in
[vendor-deferred.md](../vendor-deferred.md) as a licensee task, and I have not recorded a native x64 result for it
because there isn't one.

## The mechanical guard

`tools/vendor_guard.sh` refuses vendor artifact paths, licence file names and key-shaped strings. It runs as
the pre-commit hook (`git config core.hooksPath .githooks`, then `tools/vendor_guard.sh --staged`) and as the
CI check (`tools/vendor_guard.sh --tree`, in `.github/workflows/vendor-guard.yml`; Actions is off at the
moment, so `tools/py.sh` runs the same script through `tests/test_vendor_guard.py` as the local gate). It
prints the file and the rule, never the matched text. `tests/test_vendor_guard.py` plants dummies (a vendor
directory, binaries, licence file names, a key-shaped assignment, a private key block) and checks that the
guard refuses each one and that a commit staging them is refused by the hook. The patterns, which
`tools/vendor-guard.patterns` holds and the test keeps in step with this page, are:

```
path-prefix vendor/
path-glob *.so
path-glob *.so.*
path-glob *.dll
path-glob *.dylib
path-glob *.exe
path-glob *.msi
path-glob *.deb
path-glob *.rpm
path-glob *.run
path-glob ODA*.zip
path-glob ODA*.tar*
path-glob Teigha*
path-glob CadExchanger*
path-glob cadexchanger*
path-glob *.lic
path-glob *.licence
path-glob *.license
path-glob *activation*
path-glob *.pem
path-glob *.key
path-glob *.p12
path-glob *.pfx
content-regex -----BEGIN [A-Z ]*PRIVATE KEY-----
content-regex (licen[cs]e|activation|serial|secret|api|access|auth)[_ -]?(key|code|token)[[:space:]]*[:=][[:space:]]*["']?[A-Za-z0-9+/_.-]{16,}
content-regex gh[pousr]_[A-Za-z0-9]{36,}
content-regex AKIA[0-9A-Z]{16}
```

The root `LICENSE` file is the repository's own MIT licence and does not match any pattern (its name has no
extension). The guard skips the content scan on this page, on the patterns file and on its own test, because
those spell the patterns out.
