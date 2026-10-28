# Converter images and setup

Every converter image is open (ADR 0007, ADR 0010). Nothing in the pipeline needs a licence, a key or an activation file, and the only rule left is that none may ever appear.

## The images

| image | what | licence | where it is built |
|---|---|---|---|
| `dwg2step-acadsharp` | the ACadSharp converter ([acadsharp-dwg2step.md](acadsharp-dwg2step.md)) | MIT | this repository, `tools/converters/acadsharp/` |
| `step-validator` | `step_eval` on Open CASCADE, pinned by package version and base-image digest | open | this repository, `validator/` |
| LibreDWG converter | `dwgread` JSON turned into STEP | GPL-3.0-or-later | `libviprs/pvec-oracle-libredwg`, pulled here by digest |

The LibreDWG image is never a build context of this repository. I pull it by digest and only exchange files with it. Images are consumed by digest, never by tag, and they are multi-arch where the code allows. Run them with an explicit `--platform`, and say in every report which results are native x64 and which are native arm64.

## Setup

Docker is all it takes. The converter services are in `docker-compose.yml`, and [docker-workflow.md](../docker-workflow.md) has the topology and the commands.

## The guard

`tools/vendor_guard.sh` refuses vendor archives, licence files and key-shaped strings in the tree, and `.githooks/pre-commit` runs it. `tools/check_no_licence.sh` scans an image's history, layers and logs for licence material, and prints where a pattern matched, never the text. Neither has anything to find today, which is the point.
