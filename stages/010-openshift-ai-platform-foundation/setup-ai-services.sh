#!/usr/bin/env bash
# Provision runtime connection data; Argo CD owns all workloads and native CRs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=../../scripts/shared/lib.sh
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
command -v python3 >/dev/null || { echo "[FAIL] python3 is required"; exit 1; }

python3 - "$@" <<'PY'
import argparse
import base64
import json
import os
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import quote, urlparse

parser = argparse.ArgumentParser(description="Create runtime MLflow/EvalHub connection data.")
parser.add_argument("--timeout", type=int, default=900, help="Seconds per service readiness gate.")
parser.add_argument("--namespace-timeout", type=int, default=300)
args = parser.parse_args()
if args.timeout <= 0 or args.namespace_timeout <= 0:
    parser.error("timeouts must be positive")

managed_by = "stage010-ai-services-setup"
request_timeout = os.environ.get("RHOAI_OC_REQUEST_TIMEOUT", "10s")


def run(command, payload=None):
    # Never echo manifests or credential values, including on command failures.
    if command and command[0] == "oc":
        command = ["oc", "--request-timeout=" + request_timeout] + command[1:]
    return subprocess.run(command, input=json.dumps(payload) if payload else None,
                          capture_output=True, text=True)


def get(kind, name, namespace=None):
    command = ["oc", "get", kind, name]
    if namespace:
        command.extend(["-n", namespace])
    command.extend(["-o", "json", "--ignore-not-found"])
    result = run(command)
    if result.returncode != 0:
        return None
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def wait_for(label, probe, timeout):
    deadline = time.monotonic() + timeout
    print(f"Waiting for {label}...", flush=True)
    while True:
        value = probe()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {label}; inspect operator and Argo status.")
        time.sleep(min(5, max(0, deadline - time.monotonic())))


def metadata(name, namespace):
    return {"name": name, "namespace": namespace, "labels": {
        "app.kubernetes.io/part-of": "rhoai-platform",
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/component": "configuration",
        "app.kubernetes.io/managed-by": managed_by,
    }}


def decode(secret, key):
    try:
        return base64.b64decode(secret["data"][key], validate=True).decode()
    except (KeyError, ValueError, UnicodeDecodeError):
        raise RuntimeError("Database Secret has missing or invalid required keys.") from None


def database_uri(feature, namespace, user, password, database):
    scheme = "postgresql" if feature == "mlflow" else "postgres"
    host = f"{feature}-postgresql.{namespace}.svc.cluster.local"
    # Explicit demo boundary: private same-namespace DB transport is plaintext.
    # URI mode overrides the MLflow chart's PGSSLMODE=verify-full for S3 CA setup.
    return (f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@"
            f"{host}:5432/{quote(database, safe='')}?sslmode=disable")


def validate_database_secret(feature, namespace, secret):
    if not secret:
        raise RuntimeError(f"Cannot read {feature} database Secret; check access.")
    user = decode(secret, "database-user")
    password = decode(secret, "database-password")
    database = decode(secret, "database-name")
    if not password or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", user) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise RuntimeError(f"{feature} database Secret has invalid user, password, or database.")
    uri_key = "backend-store-uri" if feature == "mlflow" else "db-url"
    if decode(secret, uri_key) != database_uri(feature, namespace, user, password, database):
        raise RuntimeError(f"{feature} database URI does not match its credentials and demo endpoint; no values changed.")


def ensure_database_secret(feature, namespace):
    name = feature + "-db-credentials"
    existing = get("secret", name, namespace)
    if existing is None:
        raise RuntimeError(f"Cannot inspect {feature} database Secret; refusing to overwrite.")
    if existing:
        validate_database_secret(feature, namespace, existing)
        print(f"Reusing {feature} database credentials.", flush=True)
        return
    password = secrets.token_hex(24)
    uri_key = "backend-store-uri" if feature == "mlflow" else "db-url"
    values = {
        "database-user": feature,
        "database-password": password,
        "database-name": feature,
        uri_key: database_uri(feature, namespace, feature, password, feature),
    }
    payload = {"apiVersion": "v1", "kind": "Secret", "metadata": metadata(name, namespace),
               "type": "Opaque", "stringData": values}
    result = run(["oc", "create", "-f", "-"], payload)
    if result.returncode != 0:
        # Another guarded run may have created it. Reuse only after full validation.
        validate_database_secret(feature, namespace, get("secret", name, namespace))
    print(f"{feature} database credentials are present.", flush=True)


def bucket_ready():
    namespace, name = "redhat-ods-applications", "rhoai-mlflow-artifacts"
    obc = get("objectbucketclaim", name, namespace) or {}
    if obc.get("status", {}).get("phase") != "Bound":
        return False
    if obc.get("spec", {}).get("bucketName") != name:
        raise RuntimeError("MLflow OBC bound to a different bucket; refusing mismatched artifact storage.")
    data = (get("configmap", name, namespace) or {}).get("data", {})
    if not all(data.get(key) for key in ["BUCKET_NAME", "BUCKET_PORT", "BUCKET_HOST"]):
        return False
    if (data.get("BUCKET_NAME") != name or data.get("BUCKET_PORT") != "443"
            or not data.get("BUCKET_HOST", "").endswith(
                (".openshift-storage.svc", ".openshift-storage.svc.cluster.local"))):
        raise RuntimeError("MLflow OBC must publish the internal HTTPS endpoint trusted by the service CA.")
    ca = (get("configmap", "mlflow-service-ca", namespace) or {}).get("data", {})
    if not ca.get("service-ca.crt"):
        return False
    template = '{{range $key,$value := .data}}{{$key}}{{"\n"}}{{end}}'
    result = run(["oc", "get", "secret", name, "-n", namespace, "-o", "go-template=" + template])
    return result.returncode == 0 and {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"} <= set(result.stdout.splitlines())


def available_mlflow():
    obj = get("mlflows.mlflow.opendatahub.io", "mlflow") or {}
    generation = obj.get("metadata", {}).get("generation")
    ready = any(c.get("type") == "Available" and c.get("status") == "True"
                and c.get("observedGeneration") == generation
                for c in obj.get("status", {}).get("conditions", []))
    if not ready or generation is None:
        return False
    uri = obj.get("status", {}).get("address", {}).get("url", "")
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("Available MLflow did not publish a valid native HTTPS address.")
    return uri


def ensure_tracking_config(uri):
    namespace, name = "evalhub", "evalhub-mlflow-connection"
    existing = get("configmap", name, namespace)
    if existing is None:
        raise RuntimeError("Cannot inspect the EvalHub MLflow connection ConfigMap.")
    if existing:
        meta = existing.get("metadata", {})
        if (meta.get("ownerReferences") or meta.get("annotations", {}).get("argocd.argoproj.io/tracking-id")
                or meta.get("labels", {}).get("app.kubernetes.io/managed-by") != managed_by):
            raise RuntimeError("The EvalHub connection ConfigMap has another owner; refusing takeover.")
        if existing.get("data", {}).get("tracking-uri") == uri:
            print("Reusing discovered EvalHub MLflow connection.", flush=True)
            return
    payload = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": metadata(name, namespace),
               "data": {"tracking-uri": uri}}
    if run(["oc", "apply", "-f", "-"], payload).returncode:
        raise RuntimeError("Could not publish the discovered EvalHub MLflow connection.")
    print("Published the native MLflow HTTPS address for EvalHub.", flush=True)


try:
    for namespace in ["redhat-ods-applications", "evalhub"]:
        wait_for(f"namespace {namespace}",
                 lambda namespace=namespace: (get("namespace", namespace) or {}).get("status", {}).get("phase") == "Active",
                 args.namespace_timeout)
    for feature, namespace in [("mlflow", "redhat-ods-applications"), ("evalhub", "evalhub")]:
        ensure_database_secret(feature, namespace)
    wait_for("bound MLflow artifact bucket and trusted S3 endpoint", bucket_ready, args.timeout)
    uri = wait_for("MLflow Available at its current generation", available_mlflow, args.timeout)
    ensure_tracking_config(uri)
except (RuntimeError, OSError) as error:
    print(f"[FAIL] {error}", file=sys.stderr)
    sys.exit(1)
print("Runtime connections ready. Argo CD and the native operators continue reconciliation.")
PY
