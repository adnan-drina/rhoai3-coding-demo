#!/bin/bash
# Runs mini-swe-agent on one SWE-bench instance inside that instance's own image (the Job's pod),
# then uploads the prediction and trajectory to the tenant bucket. Mounted from the swebench-agent
# ConfigMap by stages/050-model-evaluation/swebench-run.sh. Environment from the Job:
#   INSTANCE_ID, SUBSET (verified|lite|full), SPLIT, MODEL_NAME (openai/<maas model id>), RUN_ID,
#   OPENAI_API_BASE, OPENAI_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT, AWS_S3_BUCKET,
#   MINI_SWE_AGENT_VERSION.
set -euo pipefail
export HOME=/root MSWEA_COST_TRACKING=ignore_errors UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin
OUT=/out; mkdir -p "$OUT"
echo "instance=${INSTANCE_ID} subset=${SUBSET} model=${MODEL_NAME} run=${RUN_ID}"
# The instance images ship a conda base below Python 3.10; uv installs a managed interpreter for the agent.
curl -sSfL https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh >/dev/null
uv tool install --python 3.12 "mini-swe-agent==${MINI_SWE_AGENT_VERSION}" --with boto3 >/dev/null
export PATH=/usr/local/bin:$PATH
# Filter is an exact match on the instance id; the runner loads the dataset split from Hugging Face.
mini-extra swebench --subset "${SUBSET}" --split "${SPLIT}" --filter "^$(printf '%s' "${INSTANCE_ID}" | sed 's/[][\\.*^$]/\\&/g')$" \
  --environment-class local -o "$OUT" -c /config/mini-swe-agent-swebench.yaml -m "${MODEL_NAME}" -w 1 2>&1 | tail -40
python3 - <<'PY'
import json, os, pathlib
preds = pathlib.Path("/out/preds.json"); iid = os.environ["INSTANCE_ID"]
data = json.loads(preds.read_text()) if preds.exists() else {}
entry = data.get(iid)
print("prediction present:", bool(entry), "| patch chars:", len((entry or {}).get("model_patch") or ""))
PY
# Upload with the uv-managed interpreter (boto3 was installed next to the agent).
"$(dirname "$(readlink -f "$(command -v mini-extra)")")/python" - <<'PY'
import json, os, pathlib, boto3
s3 = boto3.client("s3", endpoint_url=os.environ["AWS_S3_ENDPOINT"], aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"], region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
bucket, run, iid = os.environ["AWS_S3_BUCKET"], os.environ["RUN_ID"], os.environ["INSTANCE_ID"]
preds = pathlib.Path("/out/preds.json"); data = json.loads(preds.read_text()) if preds.exists() else {}
entry = data.get(iid) or {"instance_id": iid, "model_name_or_path": os.environ["MODEL_NAME"], "model_patch": ""}
s3.put_object(Bucket=bucket, Key=f"swebench/{run}/preds/{iid}.json", Body=json.dumps(entry).encode())
traj = pathlib.Path("/out") / iid / f"{iid}.traj.json"
if traj.exists():
    s3.put_object(Bucket=bucket, Key=f"swebench/{run}/trajectories/{iid}.traj.json", Body=traj.read_bytes())
for log in ("minisweagent.log",):
    p = pathlib.Path("/out") / log
    if p.exists():
        s3.put_object(Bucket=bucket, Key=f"swebench/{run}/logs/{iid}.log", Body=p.read_bytes())
print(f"uploaded s3://{bucket}/swebench/{run}/preds/{iid}.json")
PY
