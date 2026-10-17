# cadex-converter: CAD Exchanger Batch, DWG -> STEP AP242.
#
# COMMERCIAL AND NOT REDISTRIBUTABLE. The image is built locally from an artifact the licensee
# supplies under vendor/cadex/ (git-ignored) and is never pushed to a registry. No licence or key
# goes into the build: the licence is mounted read-only at run time (docker-compose.yml).
#
#   docker build --platform linux/amd64 -f docker/cadex/Dockerfile \
#       --build-arg CADEX_ARTIFACT=<file> --build-arg CADEX_SHA256=<hash> --build-arg CADEX_VERSION=<build> .
#
# x86_64 only: build and run it on the native x86_64 host (tools/nas.sh), never under Rosetta.
# The base image is pinned by digest. The build stops if the artifact or its pinned hash is wrong.
ARG BASE=debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
FROM ${BASE}
ARG CADEX_ARTIFACT
ARG CADEX_SHA256
ARG CADEX_VERSION
COPY docker/cadex/check-artifact.sh docker/cadex/install.sh /opt/cadex-glue/
RUN --mount=type=bind,source=.,target=/ctx,ro \
    sh /opt/cadex-glue/check-artifact.sh /ctx \
    && sh /opt/cadex-glue/install.sh /ctx/vendor/cadex/${CADEX_ARTIFACT}
COPY tools/convert_cadex.sh /usr/local/bin/convert_cadex.sh
LABEL org.opencontainers.image.title="cadex-converter" \
      org.opencontainers.image.description="CAD Exchanger Batch DWG to STEP AP242. Private, not redistributable." \
      cadex.version="${CADEX_VERSION}"
ENTRYPOINT ["/usr/local/bin/convert_cadex.sh"]
