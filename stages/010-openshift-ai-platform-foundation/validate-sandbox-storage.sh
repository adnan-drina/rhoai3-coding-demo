#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY_CHECK'
import base64,json,subprocess,sys

def get(kind,name):
    p=subprocess.run(["oc","--request-timeout=10s","get",kind,name,"-n","demo-sandbox","-o","json"],capture_output=True,text=True)
    if p.returncode: raise RuntimeError("Required sandbox storage resource unavailable")
    return json.loads(p.stdout)
try:
    for claim,display in [("rhoai-models","Models"),("rhoai-workbench","Workbench")]:
        obc=get("obc",claim);cm=get("configmap",claim);source=get("secret",claim);connection=get("secret",claim+"-connection")
        assert obc.get("status",{}).get("phase")=="Bound"
        for obj in [obc,connection]:
            assert obj["metadata"].get("annotations",{}).get("argocd.argoproj.io/tracking-id","").startswith("sandbox-storage:")
        uid=obc["metadata"]["uid"]
        for obj in [cm,source]: assert any(o.get("kind")=="ObjectBucketClaim" and o.get("uid")==uid for o in obj["metadata"].get("ownerReferences",[]))
        data=cm.get("data",{});target=connection.get("data",{})
        assert data.get("BUCKET_NAME")==claim and data.get("BUCKET_PORT")=="443" and data.get("BUCKET_HOST")
        for key in ["AWS_ACCESS_KEY_ID","AWS_SECRET_ACCESS_KEY"]: assert source.get("data",{}).get(key) and target.get(key)==source["data"][key]
        def decoded(key): return base64.b64decode(target[key],validate=True).decode()
        assert decoded("AWS_S3_BUCKET")==claim and decoded("AWS_S3_ENDPOINT")=="https://"+data["BUCKET_HOST"]+":443"
        assert decoded("AWS_DEFAULT_REGION")==(data.get("BUCKET_REGION") or "us-east-1")
        meta=connection["metadata"];assert meta.get("annotations",{}).get("opendatahub.io/connection-type-protocol")=="s3"
        assert meta["annotations"].get("openshift.io/display-name")==display and meta.get("labels",{}).get("opendatahub.io/dashboard")=="true"
        assert "kubectl.kubernetes.io/last-applied-configuration" not in meta.get("annotations",{})
        assert meta.get("labels",{}).get("opendatahub.io/managed")!="true"
        print(display+" connection: native bucket binding, ownership, credential mapping and metadata passed")
    print("Configuration validation only; authenticated S3 operations and workbench consumption remain separate acceptance.")
except (AssertionError,RuntimeError,ValueError,KeyError):
    print("ERROR: Sandbox S3 configuration validation failed (credential values suppressed)",file=sys.stderr);sys.exit(1)
PY_CHECK
