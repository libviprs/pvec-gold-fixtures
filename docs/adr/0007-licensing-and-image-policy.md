# ADR 0007: licensing and image policy

Status: frozen at the phase 1 exit gate (open route, 2026-10-28). ADR 0010 removes the licensed images, so the open image policy below is the whole policy. Panel finding answered: 9.

## Context

The converters and the evaluator run in containers, and other repositories consume what they produce. Images have to be reproducible, safe to publish, and free of anything that must stay on one machine.

## Decision

- Every image is one of the open images. An open image holds only open-licensed components, is rebuilt from pinned inputs, is multi-arch where the code allows, is published to GHCR and is consumed by digest, never by tag. The ACadSharp converter image and the step-validator image are built here. The MIT `LICENSE` file at the root of this repository is what allows publishing them.
- The LibreDWG converter is GPL, so its image is built and published from `libviprs/pvec-oracle-libredwg` and is never a build context of this repository. I pull it by digest and only exchange files with it.
- No credential, licence file or activation material is written to a file, echoed into a log, or copied to a build host. The scan that checks image history, layers and logs is `tools/check_no_licence.sh`, and `tools/vendor_guard.sh` refuses such material in the tree.
- Every `docker run` passes an explicit `--platform`, and every report says which results are native x64 and which are arm64.
- The step-validator image has no closed-source component, which is what lets the other repositories consume its output.
- Ordinary CI in `pvec`, `libviprs` and `maplibre-pvec` runs with no converter present. It reads the frozen artifacts instead.

## Consequences

Anyone with Docker can regenerate the corpus, and reading it needs nothing at all.

## Amendment (ADR 0009)

The open image class (open components, pinned inputs, multi-arch, consumed by digest) and the LibreDWG rule were added here. ADR 0010 folds them into the body above.

## Amendment (ADR 0010)

This ADR was rewritten as the open image policy. The earlier clauses about non-redistributable images, licence secret paths and x86_64-only converter builds are withdrawn, because only open software takes part in the pipeline.
