# Preserve the Stage 130 fork; add only its missing native HTTP dependency closure.
FROM quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:5aab5558481fcbb69483122543b7bcb96b9c34daf44466eea6d375fd37c92029
USER 0
COPY requirements.lock dependency-source.json verify-packaging.py /opt/rhoai3/hermes-api/
COPY wheels/ /tmp/hermes-api-wheels/
RUN /opt/hermes-venv/bin/python /opt/rhoai3/hermes-api/verify-packaging.py before \
 && /opt/hermes-venv/bin/python -m pip install --no-index --find-links=/tmp/hermes-api-wheels --no-deps --require-hashes -r /opt/rhoai3/hermes-api/requirements.lock \
 && /opt/hermes-venv/bin/python /opt/rhoai3/hermes-api/verify-packaging.py after \
 && rm -rf /tmp/hermes-api-wheels /tmp/hermes-api-before.json
# The OpenShell namespace still supplies an arbitrary UID under restricted-v2.
USER 10001
