# step-validator: the independent STEP evaluator. Open CASCADE only, no converter SDK, no licence.
# Build from the repository root:  docker build -f docker/step-validator/Dockerfile .
#
# The base image is pinned by digest (the multi-arch index, so arm64 and x86_64 resolve the same
# release) and OCCT is pinned by exact Debian package version. The build stops if apt resolves
# anything else.
ARG BASE=debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
FROM ${BASE} AS build
ARG OCCT_PKG=7.6.3+dfsg1-7
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ make cmake libtbb-dev "libocct-data-exchange-dev=${OCCT_PKG}" \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY validator/CMakeLists.txt validator/CMakeLists.txt
COPY validator/src validator/src
RUN cmake -S validator -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j"$(nproc)"

FROM ${BASE} AS runtime
ARG OCCT_PKG=7.6.3+dfsg1-7
RUN apt-get update && apt-get install -y --no-install-recommends python3 "libocct-data-exchange-7.6=${OCCT_PKG}" \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/step_eval /usr/local/bin/step_eval
WORKDIR /work

# test: the runtime plus the python deps, for the unit tests and for development. Used with
# --target test. It does not need the vendored policy, so it is not the shipped image.
FROM runtime AS test
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt
ENV STEP_EVAL=/usr/local/bin/step_eval

# final (the default target): the self-test runs here, against the vendored P1.2 policy, and the
# build fails if any hand-known primitive is not reproduced, or if a mutated file is not caught.
# With no policy file in policy/ the COPY below has nothing to copy and the build stops, which is
# the intended behaviour until P1.2 is vendored.
FROM runtime AS final
COPY policy/pvec-numeric-policy.*.json /work/policy/
COPY runner /work/runner
COPY validator/selftest.py /work/validator/selftest.py
COPY fixtures/validator-selftest /work/fixtures/validator-selftest
RUN cd /work && python3 validator/selftest.py --evaluator step_eval \
        --policy "$(ls policy/pvec-numeric-policy.*.json)" --mutation-check
