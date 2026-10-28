# fixture-runner: python plus a docker client and the compose plugin. It orchestrates the other
# services through the host's socket and executes no converter and no evaluator itself.
# Build from the repository root:  docker compose build fixture-runner
FROM python:3.12-slim
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
COPY requirements.txt /tmp/requirements.txt
RUN pip install -q --no-cache-dir --disable-pip-version-check --root-user-action=ignore -r /tmp/requirements.txt
WORKDIR /repo
COPY runner runner
COPY schema schema
COPY policy policy
COPY fixtures/known-truth fixtures/known-truth
COPY docker-compose.yml docker-compose.yml
