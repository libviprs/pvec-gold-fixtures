# Dependencies for the python runner and its tests. No converter, nothing proprietary.
FROM python:3.12-slim
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git >/dev/null && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /r.txt
RUN pip install -q --no-cache-dir --disable-pip-version-check --root-user-action=ignore -r /r.txt
