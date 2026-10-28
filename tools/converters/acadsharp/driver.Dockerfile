# Test driver for tests/test_acadsharp_converter.py: python, the repo's python dependencies and a docker
# client (the host's socket is handed in at run time). It builds and runs nothing else by itself.
FROM python:3.12-slim
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
COPY requirements.txt /r.txt
RUN pip install -q --no-cache-dir --disable-pip-version-check --root-user-action=ignore -r /r.txt \
    && apt-get update -qq && apt-get install -y -qq --no-install-recommends bash tar grep >/dev/null && rm -rf /var/lib/apt/lists/*
