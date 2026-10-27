# dwg2step-acadsharp: DWG in, AP242 Part 21 and a status record out. MIT code all the way down:
# ACadSharp's DwgReader decodes the drawing and Step21.cs writes the STEP text. No geometry kernel and no
# evaluator is in this image; the separate step-validator image is the only thing that reads the output.
#
# Build from the repository root (the policy file is copied from policy/):
#   docker build -f tools/converters/acadsharp/Dockerfile -t dwg2step-acadsharp .
#
# Both base images are pinned by the digest of their multi-arch index, so arm64 and x86_64 resolve the same
# release. The upstream source is pinned by full commit and the build stops if the checkout is anything else.
FROM mcr.microsoft.com/dotnet/sdk:10.0.401-noble@sha256:e70cdb7f80b0348f5cb85f19a8f670fca061f033d57eed12fa003d58b0e06317 AS build
ARG ACADSHARP_COMMIT=d7dc111023477d8a9fffc2153139459c95b4f345
ENV HOME=/tmp/home DOTNET_CLI_HOME=/tmp/dn DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
RUN git clone -q https://github.com/DomCR/ACadSharp /opt/acadsharp \
    && git -C /opt/acadsharp checkout -q "${ACADSHARP_COMMIT}" \
    && test "$(git -C /opt/acadsharp rev-parse HEAD)" = "${ACADSHARP_COMMIT}" \
    && git -C /opt/acadsharp submodule update -q --init --recursive
WORKDIR /src
COPY tools/converters/acadsharp/Dwg2Step.csproj tools/converters/acadsharp/Program.cs tools/converters/acadsharp/Flatten.cs tools/converters/acadsharp/Step21.cs ./
RUN dotnet publish Dwg2Step.csproj -c Release -o /out -p:AcsSrc=/opt/acadsharp/src -p:UseAppHost=false >/tmp/publish.log 2>&1 \
    || { tail -40 /tmp/publish.log; exit 1; }

FROM mcr.microsoft.com/dotnet/runtime:10.0.12-noble@sha256:b89586dc17781f25531909993658aa8161205ae38b8cec8847df4a8221a403d5 AS runtime
COPY --from=build /out /opt/dwg2step
COPY policy/pvec-numeric-policy.v1.json /opt/dwg2step/policy/pvec-numeric-policy.v1.json
RUN printf '#!/bin/sh\nexec dotnet /opt/dwg2step/Dwg2Step.dll "$@"\n' > /usr/local/bin/dwg2step-acadsharp \
    && chmod 0755 /usr/local/bin/dwg2step-acadsharp
ENV DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
WORKDIR /work
ENTRYPOINT ["dwg2step-acadsharp"]
