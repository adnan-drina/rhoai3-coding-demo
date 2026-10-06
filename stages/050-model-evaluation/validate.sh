#!/usr/bin/env bash
# Exit 0: selected real job/run verified; 1: failure; 2: service ready, evaluation proof pending.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo '[FAIL] python3 is required'; exit 1; }
python3 - <<'CHECK'
import json,subprocess,sys,re,os
result = subprocess.run(["oc", "--request-timeout=10s", "get", "application", "050-model-evaluation",
                         "-n", "openshift-gitops", "-o", "json"], capture_output=True, text=True)
try:
    app=json.loads(result.stdout)
    status=app.get("status", {})
    ready=(result.returncode == 0 and status.get("sync", {}).get("status") == "Synced"
           and status.get("health", {}).get("status") == "Healthy"
           and app["spec"].get("project")=="rhoai-demo"
           and app["spec"].get("destination")=={"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"}
           and not app["spec"].get("sources") and not app["metadata"].get("ownerReferences") and not app["metadata"].get("deletionTimestamp")
           and (not os.environ.get("RHOAI_STAGE050_EXPECTED_REVISION") or os.environ["RHOAI_STAGE050_EXPECTED_REVISION"]==app["spec"]["source"]["targetRevision"])
           and re.fullmatch(r"[0-9a-f]{40}",app["spec"]["source"]["targetRevision"])
           and app["spec"]["source"].get("repoURL")==os.environ["GIT_REPO_URL"]
           and app["spec"]["source"].get("path")=="gitops/stages/050-model-evaluation/base"
           and status.get("operationState",{}).get("phase")=="Succeeded"
           and status["operationState"].get("syncResult",{}).get("revision")==app["spec"]["source"]["targetRevision"]
           and status["operationState"].get("syncResult",{}).get("source",{}).get("path")==app["spec"]["source"]["path"]
           and status.get("sync",{}).get("revision")==app["spec"]["source"]["targetRevision"])
except ValueError:
    ready=False
print("[PASS] Stage 050 Application Synced/Healthy" if ready else "[FAIL] Stage 050 Application not Synced/Healthy")
sys.exit(0 if ready else 1)
CHECK
"$SCRIPT_DIR/validate-ai-services.sh"
# Read-only authenticated discovery, plus optional previously submitted real job/run evidence.
python3 "$SCRIPT_DIR/service-api.py" "$@"
