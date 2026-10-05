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
    foundation = get("application", "010-openshift-ai-platform-foundation", "openshift-gitops")
    require(foundation.get("status", {}).get("sync", {}).get("status") == "Synced"
            and foundation.get("status", {}).get("health", {}).get("status") == "Healthy",
            "Foundation must be Synced/Healthy before evaluation deployment.")
    require("RespectIgnoreDifferences=true" in foundation.get("spec", {}).get("syncPolicy", {}).get("syncOptions", []),
            "Foundation must respect delegated shared-field ownership.")
    ignores = foundation.get("spec", {}).get("ignoreDifferences", [])
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
        require(app.get("status", {}).get("sync", {}).get("status") == "Synced"
                and app.get("status", {}).get("health", {}).get("status") == "Healthy",
                "Serving and MaaS must be Synced/Healthy before evaluation deployment.")
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
    resources = [("mlflows.mlflow.opendatahub.io", "mlflow", None),
                 ("statefulset", "mlflow-postgresql", NAMESPACE),
                 ("pvc", "mlflow-postgresql", NAMESPACE),
                 ("objectbucketclaim", "rhoai-mlflow-artifacts", NAMESPACE),
                 ("service", "mlflow-postgresql", NAMESPACE),
                 ("networkpolicy", "mlflow-postgresql", NAMESPACE),
                 ("configmap", "mlflow-service-ca", NAMESPACE),
                 ("namespace", "evalhub", None),
                 ("statefulset", "evalhub-postgresql", "evalhub"),
                 ("pvc", "evalhub-postgresql", "evalhub"),
                 ("service", "evalhub-postgresql", "evalhub"),
                 ("networkpolicy", "evalhub-postgresql", "evalhub")]
    if get("crd", "evalhubs.trustyai.opendatahub.io"):
        resources.append(("evalhubs.trustyai.opendatahub.io", "evalhub", "evalhub"))
    # The API itself may not exist in a clean environment. Inspect MLflow only
    # after its CRD exists, without swallowing real authorization failures.
    mlflow_api = bool(get("crd", "mlflows.mlflow.opendatahub.io"))
    for kind, name, namespace in resources:
        if kind.startswith("mlflows") and not mlflow_api:
            continue
        obj = get(kind, name, namespace)
        if not obj:
            continue
        tracking = obj.get("metadata", {}).get("annotations", {}).get("argocd.argoproj.io/tracking-id", "")
        require(tracking.startswith(APP + ":"),
                "Existing evaluation/MLflow resource belongs to another owner; refusing automatic handoff. Preserve its data and review adoption separately.")
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
