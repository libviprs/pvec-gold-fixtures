# ADR 0007: licensing and image policy

Status: proposed, frozen by the phase 1 exit gate. Panel finding answered: 9.

## Context

Both converter SDKs are commercial. Their images can't be redistributed, their licences have to reach
them somehow, and both are x86_64 only.

## Decision

- The CAD Exchanger and ODA images are non-redistributable. They are built locally from artifacts the
  licensee supplies, pinned by SHA-256, and are never published to a registry. The build fails loudly
  if a pinned artifact is absent or different, and never fetches or substitutes one.
- Licences and activation material come from documented secret paths at run time, mounted read-only.
  No credential is written to a file, echoed into a log, or copied to the build host. The scan that
  checks image history, layers and logs for licence material is `tools/check_no_licence.sh`.
- Both SDKs are x86_64. They are built and run in containers on the native x86_64 host through
  `tools/nas.sh`, never under Rosetta, and every `docker run` passes an explicit `--platform`. Every
  report says which results are native x64 and which are arm64.
- The step-validator image has no proprietary component, which is what lets the other repositories
  consume its output.
- Ordinary CI in `pvec`, `libviprs` and `maplibre-pvec` runs with no proprietary converter present.
  It reads the frozen artifacts instead.

## Consequences

Regenerating the corpus needs the licensee. Reading the corpus doesn't.
