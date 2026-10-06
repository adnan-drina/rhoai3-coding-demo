#!/usr/bin/env python3
"""Private read-only API probe, called only by guarded validate.sh; never submits a job."""
import argparse
from contextlib import contextmanager
import http.client
import json
import re
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlparse, quote


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=10s", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Cannot read the native service contract or current session.")
    return result.stdout


@contextmanager
def api(service, namespace, uri, ca, token, workspace):
    address = urlparse(uri)
    if address.scheme != "https" or not address.hostname or address.username or address.password:
        raise RuntimeError("Native address must be HTTPS without embedded credentials.")
    context = ssl.create_default_context(cadata=ca)
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    process = subprocess.Popen(["oc", "--request-timeout=10s", "port-forward", "-n", namespace,
                                "service/" + service, f"{port}:{address.port or 443}", "--address=127.0.0.1"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class NativeHTTPS(http.client.HTTPSConnection):
        def connect(self):
            connection = socket.create_connection(("127.0.0.1", port), self.timeout)
            self.sock = context.wrap_socket(connection, server_hostname=address.hostname)
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Native service port-forward is unavailable.") from None
                time.sleep(.2)
        def request(path, body=None):
            connection = NativeHTTPS(address.hostname, timeout=30, context=context)
            headers = {"Authorization": "Bearer " + token, "X-Tenant": "demo-sandbox",
                       "X-MLFLOW-WORKSPACE": workspace, "Content-Type": "application/json"}
            try:
                connection.request("POST" if body is not None else "GET",
                                   address.path.rstrip("/") + "/" + path.lstrip("/"),
                                   json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                data = response.read(2 * 1024 * 1024 + 1)
                if len(data) > 2 * 1024 * 1024:
                    raise RuntimeError("Native API response exceeds bounded size.")
                if response.status != 200:
                    raise RuntimeError(f"Authenticated native API returned HTTP {response.status}.")
                return json.loads(data)
            finally:
                connection.close()
        yield request
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def discovery_items(response):
    # Pinned EvalHub OpenAPI ProviderResourceList/CollectionResourceList both use items[].
    items = response.get("items") if isinstance(response, dict) else None
    if not isinstance(items, list) or not items or not all(isinstance(item, dict) and isinstance(item.get("resource"), dict)
                                                                  and bool(item["resource"].get("id")) for item in items):
        raise RuntimeError("Native provider/collection discovery returned no actual resources.")
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", help="Read an existing explicitly submitted evaluation; never starts one")
    parser.add_argument("--mlflow-run-id", help="Exact native MLflow run ID recorded for that evaluation")
    args = parser.parse_args()
    if bool(args.job_id) != bool(args.mlflow_run_id):
        parser.error("provide both --job-id and --mlflow-run-id for functional evidence")
    if args.job_id and not re.fullmatch(r"[A-Za-z0-9_-]+", args.job_id):
        parser.error("invalid job identifier")
    if args.mlflow_run_id and not re.fullmatch(r"[a-fA-F0-9]{32}", args.mlflow_run_id):
        parser.error("invalid MLflow run identifier")
    # Also guard direct invocation, before any API/credential reads.
    from pathlib import Path
    import os
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["bash", "-c", 'set -euo pipefail; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in',
                             "stage050-api", str(root)], env=dict(os.environ, REPO_ROOT=str(root)),
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Repository cluster identity guard failed.")
    discovery = json.loads(oc("get", "configmap", "evalhub-discovery", "-n", "demo-sandbox", "-o", "json"))["data"]
    ca = json.loads(oc("get", "configmap", "evalhub-service-ca", "-n", "demo-sandbox", "-o", "json"))["data"]["service-ca.crt"]
    token = oc("whoami", "--show-token").strip()  # Memory only, never output or process arguments.
    with api("evalhub", "evalhub", discovery["evalhub.url"], ca, token, "demo-sandbox") as request:
        if request("api/v1/health").get("status") != "healthy":
            raise RuntimeError("Native EvalHub health response is not healthy.")
        providers = request("api/v1/evaluations/providers?benchmarks=true")
        collections = request("api/v1/evaluations/collections")
        discovery_items(providers)
        discovery_items(collections)
        print("[PASS] Authenticated EvalHub health, providers and collections with tenant and native CA")
        if not args.job_id:
            print("[PARTIAL] No completed real evaluation supplied; service readiness is not evaluation proof.")
            return 2
        job = request("api/v1/evaluations/jobs/" + quote(args.job_id, safe=""))
    if job.get("resource", {}).get("tenant") != "demo-sandbox" or job.get("resource", {}).get("id") != args.job_id:
        raise RuntimeError("Evaluation identity or tenant differs.")
    state = job.get("status", {}).get("state")
    if state in ["pending", "running"]:
        print("[PARTIAL] Selected evaluation has not completed.")
        return 2
    if state != "completed":
        raise RuntimeError("Selected evaluation did not complete successfully.")
    benchmarks = job.get("results", {}).get("benchmarks", [])
    if len(benchmarks) != 1 or not benchmarks[0].get("metrics") or not job.get("model", {}).get("name"):
        raise RuntimeError("Require one real benchmark with model identity and result metrics.")
    if benchmarks[0].get("mlflow_run_id") != args.mlflow_run_id:
        raise RuntimeError("Native benchmark result does not reference the selected MLflow run.")
    experiment_url = job.get("results", {}).get("mlflow_experiment_url", "")
    match = re.search(r"/experiments/([0-9]+)", experiment_url)
    if not match:
        raise RuntimeError("Completed evaluation did not report a native MLflow experiment.")
    mlflow = json.loads(oc("get", "mlflows.mlflow.opendatahub.io", "mlflow", "-o", "json"))
    # A job and service can track in different workspaces; native job results are tenant-scoped.
    with api("mlflow", "redhat-ods-applications", mlflow["status"]["address"]["url"], ca, token, "demo-sandbox") as request:
        run = request("api/2.0/mlflow/runs/get?run_id=" + args.mlflow_run_id).get("run", {})
    info = run.get("info", {})
    if (info.get("run_id") != args.mlflow_run_id or info.get("experiment_id") != match.group(1)
            or info.get("status") != "FINISHED" or not run.get("data", {}).get("metrics")):
        raise RuntimeError("Exact native MLflow run lacks finished metrics in the evaluation experiment.")
    print(json.dumps({"scope": "authenticated real evaluation and MLflow correlation", "tenant": "demo-sandbox",
                      "job_id": args.job_id, "model": job["model"]["name"], "benchmark": benchmarks[0].get("id"),
                      "provider": benchmarks[0].get("provider_id"), "experiment_id": match.group(1),
                      "run_id": args.mlflow_run_id, "state": state}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print("[FAIL] " + str(error), file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, OSError, http.client.HTTPException):
        # Do not echo response bodies, private endpoints or credentials on errors.
        print("[FAIL] Native API/evaluation evidence check failed; inspect service status and recorded job/run identities.", file=sys.stderr)
        sys.exit(1)
