#!/usr/bin/env bash
# Read-only native MLflow/EvalHub storage, TLS, token and configured RBAC checks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../scripts/shared/lib.sh
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo "[FAIL] python3 is required"; exit 1; }

python3 - <<'PY'
import json
import os
import subprocess
import sys

failures = 0
request_timeout = os.environ.get("RHOAI_OC_REQUEST_TIMEOUT", "10s")


def check(label, value):
    global failures
    if value:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        failures += 1


def get(kind, name=None, namespace=None):
    args = ["oc", "--request-timeout=" + request_timeout, "get", kind]
    if name:
        args.append(name)
    if namespace:
        args.extend(["-n", namespace])
    args.extend(["-o", "json"])
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def secret_keys(name, namespace):
    # Fetch only key names. Credential payloads are never returned to the validator or printed.
    template = r'{{range $key,$value := .data}}{{$key}}{{"\n"}}{{end}}'
    args = ["oc", "--request-timeout=" + request_timeout, "get", "secret", name, "-n", namespace,
            "-o", "go-template=" + template]
    result = subprocess.run(args, capture_output=True, text=True)
    return set(result.stdout.splitlines()) if result.returncode == 0 else set()


def fresh_workload(obj):
    spec, status = obj.get("spec", {}), obj.get("status", {})
    desired = spec.get("replicas", 1)
    generation = obj.get("metadata", {}).get("generation")
    return (desired > 0 and generation is not None
            and status.get("observedGeneration") == generation
            and status.get("readyReplicas", 0) >= desired
            and status.get("updatedReplicas", 0) == desired
            and status.get("replicas", 0) == desired
            and status.get("availableReplicas", 0) == desired)


def owned_deployment(kind, cr, namespace):
    uid = cr.get("metadata", {}).get("uid")
    if not uid:
        return {}
    matches = [
        item for item in get("deployments", namespace=namespace).get("items", [])
        if any(owner.get("kind") == kind and owner.get("uid") == uid
               and owner.get("controller") is True
               for owner in item.get("metadata", {}).get("ownerReferences", []))
    ]
    check(f"{kind} has one current operator-owned deployment",
          len(matches) == 1 and fresh_workload(matches[0]))
    return matches[0] if len(matches) == 1 else {}


def containers(deployment):
    return deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])


def has_secret_binding(deployment, name, key):
    return any(env.get("valueFrom", {}).get("secretKeyRef", {}).get("name") == name
               and env.get("valueFrom", {}).get("secretKeyRef", {}).get("key") == key
               for container in containers(deployment)
               for env in container.get("env", []))


def env_values(deployment):
    return {env["name"]: env.get("value", "")
            for container in containers(deployment)
            for env in container.get("env", []) if "name" in env}


for feature, namespace in [("mlflow", "redhat-ods-applications")]:
    database = feature + "-postgresql"
    workload = get("statefulset", database, namespace)
    check(f"{feature} PostgreSQL has current ready replicas",
          fresh_workload(workload)
          and bool(workload.get("status", {}).get("currentRevision"))
          and workload.get("status", {}).get("currentRevision")
          == workload.get("status", {}).get("updateRevision"))
    pvc = get("pvc", database, namespace)
    check(f"{feature} durable gp3 PostgreSQL PVC is bound",
          pvc.get("status", {}).get("phase") == "Bound"
          and pvc.get("spec", {}).get("storageClassName") == "gp3-csi")
    required = {"database-user", "database-password", "database-name",
                "backend-store-uri"}
    check(f"{feature} database Secret has required keys",
          required <= secret_keys(feature + "-db-credentials", namespace))

bucket_name = "rhoai-mlflow-artifacts"
bucket = get("objectbucketclaim", bucket_name, "redhat-ods-applications")
check("MLflow artifact ObjectBucketClaim bound to exact bucket",
      bucket.get("status", {}).get("phase") == "Bound"
      and bucket.get("spec", {}).get("bucketName") == bucket_name)
check("MLflow artifact credentials provisioned by OBC",
      {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
      <= secret_keys(bucket_name, "redhat-ods-applications"))
bucket_config = get("configmap", bucket_name, "redhat-ods-applications").get("data", {})
check("MLflow artifact endpoint uses the internal HTTPS service",
      bucket_config.get("BUCKET_NAME") == bucket_name
      and bucket_config.get("BUCKET_PORT") == "443"
      and bucket_config.get("BUCKET_HOST", "").endswith(
          (".openshift-storage.svc", ".openshift-storage.svc.cluster.local")))
ca = get("configmap", "mlflow-service-ca", "redhat-ods-applications")
check("MLflow service CA bundle has been injected",
      bool(ca.get("data", {}).get("service-ca.crt")))

mlflow = get("mlflows.mlflow.opendatahub.io", "mlflow")
conditions = mlflow.get("status", {}).get("conditions", [])
check("MLflow Available for current resource generation",
      mlflow.get("metadata", {}).get("generation") is not None
      and any(condition.get("type") == "Available" and condition.get("status") == "True"
              for condition in conditions)
      and all(any(condition.get("type") == kind and condition.get("status") == "True"
                  and condition.get("observedGeneration")
                  == mlflow.get("metadata", {}).get("generation")
                  for condition in conditions)
              for kind in ["MLflowOperatorReady", "Migration"]))
spec = mlflow.get("spec", {})
check("MLflow uses PostgreSQL Secret and proxied OBC artifacts",
      spec.get("backendStoreUriFrom") == {
          "name": "mlflow-db-credentials", "key": "backend-store-uri"}
      and spec.get("serveArtifacts") is True
      and spec.get("artifactsDestination") == f"s3://{bucket_name}/artifacts"
      and spec.get("defaultArtifactRoot", "mlflow-artifacts:/") == "mlflow-artifacts:/")
mlflow_deployment = owned_deployment("MLflow", mlflow, "redhat-ods-applications")
mlflow_env = env_values(mlflow_deployment)
check("MLflow native workload uses backend Secret and verifies S3 TLS",
      has_secret_binding(mlflow_deployment, "mlflow-db-credentials", "backend-store-uri")
      and bool(mlflow_env.get("AWS_CA_BUNDLE"))
      and mlflow_env.get("MLFLOW_S3_IGNORE_TLS") == "false"
      and any(source.get("secretRef", {}).get("name") == bucket_name
              for container in containers(mlflow_deployment)
              for source in container.get("envFrom", [])))


namespace = "evalhub"
database = get("statefulset", "evalhub-postgresql", namespace)
check("EvalHub PostgreSQL current and ready", fresh_workload(database)
      and bool(database.get("status", {}).get("currentRevision"))
      and database.get("status", {}).get("currentRevision") == database.get("status", {}).get("updateRevision"))
pvc = get("pvc", "evalhub-postgresql", namespace)
check("EvalHub durable gp3 database bound", pvc.get("status", {}).get("phase") == "Bound"
      and pvc.get("spec", {}).get("storageClassName") == "gp3-csi")
check("EvalHub database credential keys present",
      {"database-user", "database-password", "database-name", "db-url"}
      <= secret_keys("evalhub-db-credentials", namespace))
hub = get("evalhubs.trustyai.opendatahub.io", "evalhub", namespace)
check("Native EvalHub multi-tenant PostgreSQL ready", hub.get("status", {}).get("ready") == "True"
      and hub.get("status", {}).get("phase") == "Ready"
      and hub.get("spec", {}).get("tenancy") == "multi"
      and hub.get("spec", {}).get("database") == {"type": "postgresql", "secret": "evalhub-db-credentials"})
deployment = owned_deployment("EvalHub", hub, namespace)
podspec = deployment.get("spec", {}).get("template", {}).get("spec", {})
service_account = podspec.get("serviceAccountName", "")
env = env_values(deployment)
check("Native EvalHub tracks the ready MLflow address",
      get("configmap", "evalhub-mlflow-connection", namespace).get("data", {}).get("tracking-uri")
      == mlflow.get("status", {}).get("address", {}).get("url")
      and bool(mlflow.get("status", {}).get("address", {}).get("url"))
      and any(e.get("name") == "MLFLOW_TRACKING_URI" and e.get("valueFrom", {}).get("configMapKeyRef")
              == {"name": "evalhub-mlflow-connection", "key": "tracking-uri"}
              for c in containers(deployment) for e in c.get("env", [])))
check("Native EvalHub database Secret binding", has_secret_binding(deployment, "evalhub-db-credentials", "db-url"))
volumes = podspec.get("volumes", [])
mounts = [m for c in containers(deployment) for m in c.get("volumeMounts", [])]
check("Native MLflow service CA and projected token mounted",
      env.get("MLFLOW_CA_CERT_PATH") == "/etc/evalhub/ca/service-ca.crt"
      and env.get("MLFLOW_TOKEN_PATH") == "/var/run/secrets/mlflow/token"
      and env.get("MLFLOW_WORKSPACE") == "evalhub"
      and env.get("MLFLOW_INSECURE_SKIP_VERIFY", "false").lower() != "true"
      and any(v.get("name") == "service-ca" and v.get("configMap", {}).get("name") == "evalhub-service-ca" for v in volumes)
      and any(v.get("name") == "mlflow-token" and any(s.get("serviceAccountToken", {}).get("path") == "token"
                  and 0 < s.get("serviceAccountToken", {}).get("expirationSeconds", 0) <= 3600
                  for s in v.get("projected", {}).get("sources", [])) for v in volumes)
      and any(m.get("name") == "service-ca" and m.get("mountPath") == "/etc/evalhub/ca" for m in mounts)
      and any(m.get("name") == "mlflow-token" and m.get("mountPath") == "/var/run/secrets/mlflow" for m in mounts)
      and bool(get("configmap", "evalhub-service-ca", namespace).get("data", {}).get("service-ca.crt")))
label = "evalhub.trustyai.opendatahub.io/tenant"
check("Existing demo namespace is the tenant; server namespace is separate",
      label in get("namespace", "demo-sandbox").get("metadata", {}).get("labels", {})
      and label not in get("namespace", namespace).get("metadata", {}).get("labels", {}))
discovery = get("configmap", "evalhub-discovery", "demo-sandbox").get("data", {})
check("Native tenant discovery and callback service CA reconciled",
      bool(discovery.get("evalhub.url"))
      and bool(get("configmap", "evalhub-service-ca", "demo-sandbox").get("data", {}).get("service-ca.crt")))
job_account = "evalhub-evalhub-job"
check("Native tenant evaluation job service account exists", bool(get("serviceaccount", job_account, "demo-sandbox")))


def allowed(user, groups, group, resource, verb, namespace):
    payload = {"apiVersion": "authorization.k8s.io/v1", "kind": "SubjectAccessReview", "spec": {
        "user": user, "groups": groups, "resourceAttributes": {
            "group": group, "resource": resource, "verb": verb, "namespace": namespace}}}
    result = subprocess.run(["oc", "--request-timeout=" + request_timeout, "create", "-f", "-", "-o", "json"],
                            input=json.dumps(payload), capture_output=True, text=True)
    try:
        return result.returncode == 0 and json.loads(result.stdout).get("status", {}).get("allowed") is True
    except ValueError:
        return False


check("Native EvalHub service authorized for MLflow in its workspace",
      bool(service_account) and all(allowed("system:serviceaccount:evalhub:" + service_account,
            ["system:serviceaccounts", "system:serviceaccounts:evalhub", "system:authenticated"],
            "mlflow.kubeflow.org", "experiments", verb, "evalhub") for verb in ["create", "get", "update"]))
check("Native EvalHub service authorized to create tenant jobs",
      bool(service_account) and allowed("system:serviceaccount:evalhub:" + service_account,
            ["system:serviceaccounts", "system:serviceaccounts:evalhub", "system:authenticated"],
            "batch", "jobs", "create", "demo-sandbox"))
check("Native tenant job authorized for MLflow experiment results",
      all(allowed("system:serviceaccount:demo-sandbox:" + job_account,
            ["system:serviceaccounts", "system:serviceaccounts:demo-sandbox", "system:authenticated"],
            "mlflow.kubeflow.org", "experiments", verb, "demo-sandbox") for verb in ["create", "get", "update"]))
for user, group in [("ai-admin", "rhods-admins"), ("ai-developer", "rhoai-developers")]:
    check("Configured " + user + " group grants evaluation and MLflow access",
          all(allowed(user, [group, "system:authenticated"], "trustyai.opendatahub.io", resource, verb, "demo-sandbox")
              for resource, verb in [("evaluations", "create"), ("evaluations", "get"), ("providers", "get"), ("collections", "get")])
          and all(allowed(user, [group, "system:authenticated"], "mlflow.kubeflow.org", "experiments", verb, "demo-sandbox")
                  for verb in ["create", "get"]))

print("Scope: native service/storage configuration and configured-group authorization."
      " Actual persona sessions, dashboard discovery, artifact persistence and real benchmark evidence are separate.")
sys.exit(1 if failures else 0)

PY
