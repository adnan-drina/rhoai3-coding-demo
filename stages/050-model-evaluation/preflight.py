#!/usr/bin/env python3
"""Read-only deployment contract; never adopt the retained foundation resources."""
import json
import subprocess
import sys
import os
from pathlib import Path

APP = "050-model-evaluation"
NAMESPACE = "redhat-ods-applications"


def get(kind, name, namespace=None):
    command = ["oc", "--request-timeout=10s", "get", kind, name, "--ignore-not-found", "-o", "json"]
    if namespace:
        command += ["-n", namespace]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Cannot inspect prerequisite/ownership; no changes made.")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def require_owned_or_absent(kind, name, namespace=None):
    existing = get(kind, name, namespace)
    if not existing:
        return
    metadata = existing.get("metadata", {})
    native_kind = {"namespace": "Namespace", "role": "Role", "rolebinding": "RoleBinding"}[kind]
    group = "" if kind == "namespace" else "rbac.authorization.k8s.io"
    # Installed Argo tracks cluster-scoped objects with the App destination namespace.
    expected = f"{APP}:{group}/{native_kind}:{namespace or 'openshift-gitops'}/{name}"
    require(not metadata.get("ownerReferences") and not metadata.get("deletionTimestamp")
            and metadata.get("annotations", {}).get("argocd.argoproj.io/tracking-id") == expected,
            "Existing curated namespace or dashboard authorization has foreign ownership; no adoption permitted.")


def guard():
    # Standalone invocation is guarded too; capture all output to avoid exposing endpoints.
    root = Path(__file__).resolve().parents[2]
    command = ['bash', '-c', 'set -euo pipefail; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in',
               'stage050-preflight', str(root)]
    env = dict(os.environ, REPO_ROOT=str(root))
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    require(result.returncode == 0, "Repository cluster identity guard failed; no reads or writes performed.")


def main():
    guard()
    require_owned_or_absent("namespace", "ai-curated-prompts")
    for kind in ["role", "rolebinding"]:
        require_owned_or_absent(kind, "enable-model-evaluation-dashboard", NAMESPACE)
    foundation = get("application", "010-openshift-ai-platform-foundation", "openshift-gitops")
    require(foundation.get("status", {}).get("sync", {}).get("status") in ["Synced", "OutOfSync"]
            and foundation.get("status", {}).get("health", {}).get("status") == "Healthy",
            "Foundation must have completed the reviewed handoff before evaluation deployment.")
    require("RespectIgnoreDifferences=true" in foundation.get("spec", {}).get("syncPolicy", {}).get("syncOptions", []),
            "Foundation must respect delegated shared-field ownership.")
    ignores = foundation.get("spec", {}).get("ignoreDifferences", [])
    dashboard_fields = {path for entry in ignores
                        if entry.get("group") == "opendatahub.io" and entry.get("kind") == "OdhDashboardConfig"
                        and entry.get("name") == "odh-dashboard-config" and entry.get("namespace") == NAMESPACE
                        for path in entry.get("jsonPointers", [])}
    require({"/spec/dashboardConfig/disableLMEval", "/spec/dashboardConfig/globalProjectPrompts", "/spec/globalMLflowNamespaces"} <= dashboard_fields,
            "Foundation has not delegated evaluation/global prompt configuration.")
    dashboard = get("odhdashboardconfig", "odh-dashboard-config", NAMESPACE)
    require(dashboard.get("spec", {}).get("globalMLflowNamespaces", []) in [[], ["ai-curated-prompts"]],
            "Foreign global prompt configuration requires reviewed merge before deployment.")
    delegated = {path for entry in ignores
                 if entry.get("group") == "datasciencecluster.opendatahub.io"
                 and entry.get("kind") == "DataScienceCluster" and entry.get("name") == "default-dsc"
                 for path in entry.get("jsonPointers", [])}
    require({"/spec/components/trustyai", "/spec/components/mlflowoperator"} <= delegated,
            "Foundation has not delegated both evaluation components; complete reviewed handoff first.")
    tenant_ignored = any(entry.get("group", "") == "" and entry.get("kind") == "Namespace" and entry.get("name") == "demo-sandbox"
                        and "/metadata/labels/evalhub.trustyai.opendatahub.io~1tenant" in entry.get("jsonPointers", [])
                        for entry in ignores)
    require(tenant_ignored, "Foundation has not delegated the EvalHub tenant namespace label.")
    for dependency in ["030-private-model-serving", "040-governed-models-as-a-service"]:
        app = get("application", dependency, "openshift-gitops")
        require(app.get("status", {}).get("sync", {}).get("status") == "Synced", "Serving/MaaS source must remain reconciled; stopped model compute is allowed.")
    dsc = get("datasciencecluster", "default-dsc")
    require(dsc.get("spec", {}).get("components", {}).get("kserve", {}).get("managementState") == "Managed",
            "Stage 030 KServe must be installed first.")
    require(any(c.get("type") == "KserveReady" and c.get("status") == "True"
                for c in dsc.get("status", {}).get("conditions", [])),
            "Native DSC KserveReady must be True before evaluation deployment.")
    require(bool(get("crd", "inferenceservices.serving.kserve.io")), "KServe InferenceServices API is absent.")
    config = get("configmap", "inferenceservice-config", NAMESPACE)
    try:
        mode = json.loads(config.get("data", {}).get("deploy", "{}"))["defaultDeploymentMode"]
    except (ValueError, KeyError):
        mode = None
    require(mode == "RawDeployment", "Native KServe defaultDeploymentMode must be RawDeployment.")
    require(get("namespace", "demo-sandbox").get("status", {}).get("phase") == "Active",
            "The existing demo tenant namespace is not Active.")
    argocd = get("argocd", "openshift-gitops", "openshift-gitops")
    health = argocd.get("spec", {}).get("extraConfig", {}).get("resource.customizations.health.mlflow.opendatahub.io_MLflow", "")
    require(all(word in health for word in ["Available", "MLflowOperatorReady", "Migration", "observedGeneration"]),
            "Install the reviewed native MLflow health gate before Stage 050.")
    source = foundation.get("spec", {}).get("source", {})
    status = foundation.get("status", {})
    result = status.get("operationState", {}).get("syncResult", {})
    bridge = source.get("path") == "gitops/stages/050-model-evaluation/migration/foundation-omit"
    require(status.get("operationState", {}).get("phase") == "Succeeded"
            and result.get("revision") == source.get("targetRevision")
            and result.get("source", {}).get("path") == source.get("path")
            and status.get("sync", {}).get("revision") == source.get("targetRevision"), "Foundation source/operation is stale.")
    require(source.get("repoURL") == os.environ["GIT_REPO_URL"]
            and foundation["spec"].get("project") == "rhoai-demo"
            and foundation["spec"].get("destination") == {"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"}
            and not foundation["spec"].get("sources") and not foundation["metadata"].get("deletionTimestamp"), "Foundation identity differs.")
    own = get("application", APP, "openshift-gitops")
    if own:
        require(own["spec"].get("project") == "rhoai-demo" and own["spec"].get("source", {}).get("repoURL") == os.environ["GIT_REPO_URL"]
                and own["spec"].get("source", {}).get("path") == "gitops/stages/050-model-evaluation/base"
                and own["spec"].get("destination") == {"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"}
                and not own["spec"].get("sources") and not own["metadata"].get("ownerReferences") and not own["metadata"].get("deletionTimestamp"), "Existing Stage050 Application identity differs.")
    resources = [("mlflows.mlflow.opendatahub.io", "MLflow", "mlflow", None),
                 ("statefulset", "StatefulSet", "mlflow-postgresql", NAMESPACE),
                 ("pvc", "PersistentVolumeClaim", "mlflow-postgresql", NAMESPACE),
                 ("objectbucketclaim", "ObjectBucketClaim", "rhoai-mlflow-artifacts", NAMESPACE),
                 ("service", "Service", "mlflow-postgresql", NAMESPACE),
                 ("networkpolicy", "NetworkPolicy", "mlflow-postgresql", NAMESPACE),
                 ("configmap", "ConfigMap", "mlflow-service-ca", NAMESPACE)]
    api_present = bool(get("crd", "mlflows.mlflow.opendatahub.io"))
    evidence = os.environ.get("RHOAI_STAGE050_HANDOFF_EVIDENCE")
    baseline = json.loads((Path(evidence)/"baseline.json").read_text()) if bridge and evidence else None
    if bridge:
        require(baseline is not None, "Protected adoption requires the original private handoff baseline.")
        proof=Path(evidence)/"omit-after.json"
        require(proof.is_file() and json.loads(proof.read_text()) == baseline, "Successful omission preservation proof is missing or differs.")
        for name in ["mlflow-db-credentials","rhoai-mlflow-artifacts"]:
            result=subprocess.run(["oc","--request-timeout=10s","get","secret",name,"-n",NAMESPACE,"-o","jsonpath={.metadata}"],capture_output=True,text=True,timeout=15)
            require(result.returncode==0 and bool(result.stdout.strip()), "Retained credential metadata unavailable.")
            meta=json.loads(result.stdout);saved=baseline["resources"]["secret/"+name]
            require(meta.get("uid")==saved["uid"] and meta.get("ownerReferences",[])==saved["owners"] and not meta.get("deletionTimestamp"), "Retained credential UID/native owner changed before adoption.")
    for kind, typename, name, namespace in resources:
        obj = get(kind, name, namespace) if not kind.startswith("mlflows") or api_present else {}
        if not obj:
            require(not bridge, "A retained MLflow resource is missing; refusing replacement.")
            continue
        meta=obj["metadata"];tracking=meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id", "")
        group=obj["apiVersion"].split("/")[0] if "/" in obj["apiVersion"] else ""
        suffix=group+"/"+typename+":"+(namespace or "openshift-gitops")+"/"+name
        require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp"), "Retained authored resource has a foreign owner or is terminating.")
        require(tracking == APP+":"+suffix or (bridge and tracking == "010-openshift-ai-platform-foundation:"+suffix), "Existing retained resource has another GitOps owner.")
        if bridge:
            saved=baseline["resources"][kind+"/"+name]
            require(meta["uid"]==saved["uid"] and obj.get("spec")==saved["spec"], "Retained resource identity/spec changed after protection.")
            require({"Prune=false","Delete=false"} <= set(meta.get("annotations",{}).get("argocd.argoproj.io/sync-options","").split(",")), "Retained resource protection missing.")
        if kind=="pvc":require(obj.get("status",{}).get("phase")=="Bound", "Retained MLflow PVC is not Bound.")
        if kind=="objectbucketclaim":require(obj.get("status",{}).get("phase")=="Bound" and obj["spec"].get("bucketName")=="rhoai-mlflow-artifacts", "Retained artifact bucket differs.")
    expected_drift={(t,n,ns or "") for _,t,n,ns in resources}
    drift=[r for r in status.get("resources",[]) if r.get("status")!="Synced"]
    require(not drift or (bridge and all((r.get("kind"),r.get("name"),r.get("namespace", "")) in expected_drift and r.get("requiresPruning") for r in drift)), "Unexpected foundation drift.")
    # EvalHub targets must be absent or exactly owned by this Application.
    for kind,typename,name,namespace in [("namespace","Namespace","evalhub",None),("statefulset","StatefulSet","evalhub-postgresql","evalhub"),("pvc","PersistentVolumeClaim","evalhub-postgresql","evalhub"),("service","Service","evalhub-postgresql","evalhub"),("networkpolicy","NetworkPolicy","evalhub-postgresql","evalhub")]:
        obj=get(kind,name,namespace)
        if obj:
            meta=obj["metadata"];group=obj["apiVersion"].split("/")[0] if "/" in obj["apiVersion"] else ""
            require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp") and meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id")==APP+":"+group+"/"+typename+":"+(namespace or "openshift-gitops")+"/"+name, "EvalHub resource has foreign ownership.")
    if get("crd","evalhubs.trustyai.opendatahub.io"):
        obj=get("evalhubs.trustyai.opendatahub.io","evalhub","evalhub")
        if obj:
            meta=obj["metadata"]
            require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp") and meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id")==APP+":trustyai.opendatahub.io/EvalHub:evalhub/evalhub", "Existing EvalHub has foreign ownership.")
    cm=get("configmap","evalhub-mlflow-connection","evalhub")
    if cm:
        meta=cm["metadata"]
        require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp") and not meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id") and meta.get("labels",{}).get("app.kubernetes.io/managed-by")=="stage050-ai-services-setup", "Runtime MLflow connection has foreign ownership.")
    fresh = []
    for feature, namespace in [("mlflow", NAMESPACE), ("evalhub", "evalhub")]:
        storage = get("pvc", feature + "-postgresql", namespace)
        database = get("statefulset", feature + "-postgresql", namespace)
        # Metadata-only credential presence; never request Secret data here.
        result = subprocess.run(["oc", "--request-timeout=10s", "get", "secret", feature + "-db-credentials",
                                 "-n", namespace, "--ignore-not-found", "-o", "name"], capture_output=True, text=True)
        require(result.returncode == 0, "Cannot inspect database credential presence.")
        require(bool(result.stdout.strip()) or not (storage or database),
                "Existing PostgreSQL storage/workload lacks credentials; refusing password regeneration.")
        if not storage and not database:
            fresh.append(feature)
    # Only deploy.sh consumes this clean-before-first-write allowance.
    print(",".join(fresh))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        print("[FAIL] " + str(error), file=sys.stderr)
        sys.exit(1)
