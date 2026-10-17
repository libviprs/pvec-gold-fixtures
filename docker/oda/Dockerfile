# oda-converter: ODA Drawings SDK (DWG read and write) plus ODA STEP SDK (AP242 export), wrapped
# by docker/oda/src/oda_dwg2step.cpp.
#
# COMMERCIAL AND NOT REDISTRIBUTABLE. Both SDKs are ODA membership products. Neither the SDK nor
# the image is committed or published. The artifacts come from vendor/oda/ (git-ignored), which the
# licensee fills; activation material is mounted at run time (docker-compose.yml), never built in.
#
#   docker build --platform linux/amd64 -f docker/oda/Dockerfile \
#       --build-arg ODA_DRAWINGS_ARTIFACT=<file> --build-arg ODA_DRAWINGS_SHA256=<hash> \
#       --build-arg ODA_STEP_ARTIFACT=<file>     --build-arg ODA_STEP_SHA256=<hash> .
#
# x86_64 only: build and run it on the native x86_64 host (tools/nas.sh), never under Rosetta.
ARG BASE=debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
FROM ${BASE}
ARG ODA_DRAWINGS_ARTIFACT
ARG ODA_DRAWINGS_SHA256
ARG ODA_STEP_ARTIFACT
ARG ODA_STEP_SHA256
COPY docker/oda/check-artifacts.sh docker/oda/install.sh /opt/oda-glue/
RUN --mount=type=bind,source=.,target=/ctx,ro \
    sh /opt/oda-glue/check-artifacts.sh /ctx \
    && sh /opt/oda-glue/install.sh /ctx/vendor/oda
ENTRYPOINT ["/usr/local/bin/oda_dwg2step"]
