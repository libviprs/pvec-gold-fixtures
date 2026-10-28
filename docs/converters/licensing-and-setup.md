# Converter licensing and setup

Two converters are commercial. CAD Exchanger Batch, and the ODA Drawings SDK with the ODA STEP SDK, are
used under the licensee's own entitlement. Their images are non-redistributable and are never published. The
repository holds the way to build and run them and none of the software, key or licence (see
[archive.md](archive.md) for the full list of what is absent). Both are x86_64 only, so they build and run in
containers on a native x86_64 host with an explicit `--platform linux/amd64`, never under Rosetta.

The open converter (`dwg2step-acadsharp`, [acadsharp-dwg2step.md](acadsharp-dwg2step.md)) needs no licence and
no setup beyond docker. It is what the `OPEN_CONVERTERS` scope of [ADR 0009](../adr/0009-open-converter-oracle-scope.md) runs.

## Secret paths and mount points

This is the whole licence interface. There is no key in any file here, no example key and no placeholder that
looks like one.

| secret | host path comes from | mounted in the container at | mode |
|---|---|---|---|
| CAD Exchanger licence | the environment variable `CADEX_LICENSE_FILE` | `/run/secrets/cadex-license` | read-only bind |
| ODA activation material | the environment variable `ODA_ACTIVATION_FILE` | `/run/secrets/oda-activation` | read-only bind |

The compose file sets `create_host_path: false`, so an unset or wrong path fails at container start instead of
mounting an empty directory. The licence is read at run time by the wrapper (`tools/convert_cadex.sh` for CAD
Exchanger, `oda_dwg2step` for ODA) and is never written, echoed or logged.

## Setup, in order

1. Obtain the vendor artifacts from the vendors and put them in `vendor/cadex/` and `vendor/oda/`. Both
   directories are git-ignored, and `tools/vendor_guard.sh` refuses to commit anything under them.
2. Build each image on the native x86_64 host with its pinned artifact name and SHA-256 as build args (the
   commands are in [archive.md](archive.md)). The build stops if the artifact is missing or is not the one
   pinned.
3. Put the licence somewhere on that host that you control, and export the two variables above.
4. Run `tools/check_no_licence.sh` on each built image and on the run logs. It prints where a pattern
   matched and never the text.

## What I could not settle

If the licence needs a licence server, `network_mode: none` has to change for that one service, and that
decision belongs to the licensee. If the licence has to sit on the build host to be bind-mounted, that
conflicts with the rule that nothing of the kind is copied there, so the licensee puts it there through a path
they control. Neither case came up, because no entitlement exists on this project; both are written down in the
two qualification pages.

## Statement

No credential was written to a file, echoed, or copied to the NAS or MARS during any phase of this epic.
Licences are supplied at run time from the paths above.
