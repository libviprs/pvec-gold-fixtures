# Dependencies for the python runner and its tests. No converter, nothing proprietary.
FROM python:3.12-slim
COPY requirements.txt /r.txt
RUN pip install -q --no-cache-dir --disable-pip-version-check --root-user-action=ignore -r /r.txt
