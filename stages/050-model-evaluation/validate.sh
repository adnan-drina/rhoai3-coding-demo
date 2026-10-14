#!/usr/bin/env bash
# Exit 0: selected real job/run verified; 1: failure; 2: service ready, evaluation proof pending.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required'; exit 1; }
export REPO_ROOT
python3 - <<'CHECK'
import json,os,subprocess,sys
sys.path.insert(0,os.environ["REPO_ROOT"]+"/scripts/shared");import stage_apps
def parked_only(app):
    # A deliberately stopped candidate (serving.kserve.io/stop) reports Suspended; nothing else may be unhealthy.
    if app.get("status",{}).get("health",{}).get("status") != "Suspended":
        return True
    for r in app["status"].get("resources",[]):
        h=(r.get("health") or {}).get("status")
        if h in (None,"Healthy"):
            continue
        if h != "Suspended" or r.get("kind") != "InferenceService":
            return False
        isvc=subprocess.run(["oc","--request-timeout=10s","get","inferenceservice",r["name"],"-n",r["namespace"],"-o","jsonpath={.metadata.annotations.serving\\.kserve\\.io/stop}"],capture_output=True,text=True)
        if isvc.returncode or isvc.stdout.strip()!="true":
            return False
    return True
problems=stage_apps.stage_problems("050",os.environ.get("RHOAI_STAGE050_EXPECTED_REVISION"),os.environ["GIT_REPO_URL"])
qualification=stage_apps.get_application("050-model-qualification")
if qualification and not parked_only(qualification):
    problems.append("050-model-qualification: Suspended by something other than a stopped candidate InferenceService")
if stage_apps.get_application("050-model-evaluation"):
    problems.append("retired single Application 050-model-evaluation still exists")
for problem in problems:
    print("  - "+problem)
print("[PASS] Stage 050 Applications Synced/Healthy" if not problems else "[FAIL] Stage 050 Applications not Synced/Healthy")
sys.exit(0 if not problems else 1)
CHECK
"$SCRIPT_DIR/validate-ai-services.sh"
# Read-only authenticated discovery, plus optional previously submitted real job/run evidence.
python3 "$SCRIPT_DIR/service-api.py" "$@"
