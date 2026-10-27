#!/usr/bin/env bash
# Publish the dwg2step-acadsharp image to GHCR as a multi-arch (amd64 + arm64) image and print its digest.
#
#   publish.sh --dry-run    print what would run, touch nothing (no docker call, no network)
#   publish.sh --push       build both platforms and push; prints image@sha256:<digest>
#
# Consumers pin the printed name@digest, never the tag. The tag below is only a handle for humans.
# This script never sees a secret: --push relies on a registry session the caller already has, and fails
# with the registry's own message when there is none.
set -euo pipefail
here=$(cd "$(dirname "$0")/../../.." && pwd)
image=ghcr.io/libviprs/pvec-gold-dwg2step-acadsharp
platforms=linux/amd64,linux/arm64
commit=$(sed -n 's/^ARG ACADSHARP_COMMIT=\([0-9a-f]\{40\}\)$/\1/p' "$here/tools/converters/acadsharp/Dockerfile")
tag=acadsharp-${commit:0:7}
mode=${1:-}
case $mode in
  --dry-run)
    echo "dry run: nothing is built or pushed"
    echo "image:     $image"
    echo "tag:       $tag"
    echo "platforms: $platforms"
    echo "would run, from $here:"
    echo "  docker buildx build --platform $platforms -f tools/converters/acadsharp/Dockerfile --provenance=false --push -t $image:$tag --metadata-file <tmp> ."
    echo "and print:  $image@sha256:<digest from the metadata file>"
    ;;
  --push)
    if [ -n "$(git -C "$here" status --porcelain 2>/dev/null)" ]; then echo "refusing to publish from a dirty tree" >&2; exit 3; fi
    meta=$(mktemp)
    trap 'rm -f "$meta"' EXIT
    docker buildx build --platform "$platforms" -f "$here/tools/converters/acadsharp/Dockerfile" --provenance=false --push \
      -t "$image:$tag" --metadata-file "$meta" "$here"
    digest=$(sed -n 's/.*"containerimage.digest": *"\(sha256:[0-9a-f]\{64\}\)".*/\1/p' "$meta" | head -n1)
    [ -n "$digest" ] || { echo "no digest in the build metadata" >&2; exit 4; }
    echo "$image@$digest"
    ;;
  *)
    echo "usage: publish.sh --dry-run | --push   (--push is the only form that publishes)" >&2
    exit 2
    ;;
esac
