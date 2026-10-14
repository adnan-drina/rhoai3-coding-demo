#!/usr/bin/env python3
"""Read-only deployment contract; never adopt the retained foundation resources."""
import json
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/shared"))
import stage_apps  # noqa: E402

RETIRED_APP = "050-model-evaluation"  # the single Application replaced by component Applications
NAMESPACE = "redhat-ods-applications"


def owned(suffix):
    """Exact tracking id of the Stage 050 component Application that renders the object."""
    owner = stage_apps.owners("050").get(suffix)
    return owner + ":" + suffix if owner else None


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
    expected = owned(f"{group}/{native_kind}:{namespace or 'openshift-gitops'}/{name}")
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
    foundation = stage_apps.stage_problems("010")
    require(not foundation, "Stage 010 must be reconciled: " + "; ".join(foundation))
    dashboard_fields = stage_apps.delegated("010", "OdhDashboardConfig", "odh-dashboard-config", NAMESPACE, "opendatahub.io")
    require({"/spec/dashboardConfig/disableLMEval", "/spec/dashboardConfig/globalProjectPrompts", "/spec/globalMLflowNamespaces"} <= dashboard_fields,
            "Foundation has not delegated evaluation/global prompt configuration.")
    dashboard = get("odhdashboardconfig", "odh-dashboard-config", NAMESPACE)
    require(dashboard.get("spec", {}).get("globalMLflowNamespaces", []) in [[], ["ai-curated-prompts"]],
            "Foreign global prompt configuration requires reviewed merge before deployment.")
    delegated = stage_apps.delegated("010", "DataScienceCluster", "default-dsc", group="datasciencecluster.opendatahub.io")
    require({"/spec/components/trustyai", "/spec/components/mlflowoperator"} <= delegated,
            "Foundation has not delegated both evaluation components; complete reviewed handoff first.")
    # The EvalHub tenant is Stage 050's own Evaluated Models namespace; no foundation delegation is needed.
    for dependency in ["030-private-model-serving", *stage_apps.names("040")]:
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
    argocd = get("argocd", "openshift-gitops", "openshift-gitops")
    health = argocd.get("spec", {}).get("extraConfig", {}).get("resource.customizations.health.mlflow.opendatahub.io_MLflow", "")
    require(all(word in health for word in ["Available", "MLflowOperatorReady", "Migration", "observedGeneration"]),
            "Install the reviewed native MLflow health gate before Stage 050.")
    require(not get("application", RETIRED_APP, "openshift-gitops"),
            "Retired single Stage050 Application still exists; finish the component move (docs/OPERATIONS.md).")
    for desired in stage_apps.components("050"):
        own = get("application", desired["metadata"]["name"], "openshift-gitops")
        if own:
            require(own["spec"].get("project") == "rhoai-demo" and own["spec"].get("source", {}).get("repoURL") == os.environ["GIT_REPO_URL"]
                    and own["spec"].get("source", {}).get("path") == desired["spec"]["source"]["path"]
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
    for kind, typename, name, namespace in resources:
        obj = get(kind, name, namespace) if not kind.startswith("mlflows") or api_present else {}
        if not obj:
            continue
        meta=obj["metadata"];tracking=meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id", "")
        group=obj["apiVersion"].split("/")[0] if "/" in obj["apiVersion"] else ""
        suffix=group+"/"+typename+":"+(namespace or "openshift-gitops")+"/"+name
        require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp"), "Retained authored resource has a foreign owner or is terminating.")
        require(tracking == owned(suffix), "Existing retained resource has another GitOps owner.")
        if kind=="pvc":require(obj.get("status",{}).get("phase")=="Bound", "Retained MLflow PVC is not Bound.")
        if kind=="objectbucketclaim":require(obj.get("status",{}).get("phase")=="Bound" and obj["spec"].get("bucketName")=="rhoai-mlflow-artifacts", "Retained artifact bucket differs.")
    # EvalHub targets must be absent or exactly owned by this Application.
    for kind,typename,name,namespace in [("namespace","Namespace","evalhub",None),("statefulset","StatefulSet","evalhub-postgresql","evalhub"),("pvc","PersistentVolumeClaim","evalhub-postgresql","evalhub"),("service","Service","evalhub-postgresql","evalhub"),("networkpolicy","NetworkPolicy","evalhub-postgresql","evalhub")]:
        obj=get(kind,name,namespace)
        if obj:
            meta=obj["metadata"];group=obj["apiVersion"].split("/")[0] if "/" in obj["apiVersion"] else ""
            require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp") and meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id")==owned(group+"/"+typename+":"+(namespace or "openshift-gitops")+"/"+name), "EvalHub resource has foreign ownership.")
    if get("crd","evalhubs.trustyai.opendatahub.io"):
        obj=get("evalhubs.trustyai.opendatahub.io","evalhub","evalhub")
        if obj:
            meta=obj["metadata"]
            require(not meta.get("ownerReferences") and not meta.get("deletionTimestamp") and meta.get("annotations",{}).get("argocd.argoproj.io/tracking-id")==owned("trustyai.opendatahub.io/EvalHub:evalhub/evalhub"), "Existing EvalHub has foreign ownership.")
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
