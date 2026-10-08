#!/usr/bin/env python3
"""Read-only native MCP ownership/readiness gate; protocol acceptance is separate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
NS = "demo-sandbox"
APP = "agent-tools"
PATH = "gitops/stages/060-agent-runtime-and-agentops/native-mcp"
IMAGE = "registry.redhat.io/openshift-mcp-tech-preview/openshift-mcp-server-rhel9@sha256:855466299c3178f7d9f96a1511005ca6161b8cc6b294df9907c234ce8ecfd0f2"


def need(value, message):
    if not value:
        raise RuntimeError(message)


def guard():
    command = 'set -euo pipefail; set +x; source "$1/scripts/shared/lib.sh"; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env >/dev/null; check_oc_logged_in >/dev/null; python3 -c "$2"'
    code = "import os,json; print(json.dumps({k:os.environ[k] for k in ['KUBECONFIG','PATH','HOME','RHOAI_STAGE060_EXPECTED_REVISION'] if k in os.environ}))"
    result = subprocess.run(["/bin/bash", "-c", command, "guard", str(ROOT), code], capture_output=True, text=True, timeout=45)
    need(result.returncode == 0, "Project cluster guard failed")
    env = dict(os.environ)
    env.update(json.loads(result.stdout))
    return env


def get(env, resource, name=None, namespace=None, optional=False):
    args = ["oc", "--request-timeout=10s", "get", resource]
    if name:
        args.append(name)
    if namespace:
        args += ["-n", namespace]
    if optional and name:
        args.append("--ignore-not-found")
    # Metadata-only credential presence: never load Secret data for this gate.
    output = ["-o", "go-template={{if .metadata.uid}}{\"apiVersion\":\"v1\",\"kind\":\"Secret\",\"metadata\":{\"uid\":\"{{.metadata.uid}}\"}}{{end}}"] if resource == "secret" else ["-o", "json"]
    result = subprocess.run(args + output, env=env, capture_output=True, text=True, timeout=20)
    need(result.returncode == 0, "Native API read failed: " + resource)
    if optional and not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def app_identity(app, revision):
    spec = app["spec"]
    need(not app["metadata"].get("deletionTimestamp") and not app["metadata"].get("ownerReferences"), "Application is terminating or foreign-owned")
    need(not spec.get("sources") and spec.get("project") == "rhoai-demo", "Application project/multisource differs")
    need(spec.get("source", {}).get("path") == PATH and spec["source"].get("repoURL") == "https://github.com/adnan-drina/rhoai3-coding-demo.git", "Application source differs")
    need(spec.get("destination") == {"server": "https://kubernetes.default.svc", "namespace": NS}, "Application destination differs")
    if revision:
        need(spec["source"].get("targetRevision") == revision, "Application desired revision differs")


def tracked(obj):
    need(not obj["metadata"].get("deletionTimestamp") and not obj["metadata"].get("ownerReferences"), "Customer input is terminating or native/foreign-owned")
    group = obj["apiVersion"].split("/")[0] if "/" in obj["apiVersion"] else ""
    expected = f'{APP}:{group}/{obj["kind"]}:{obj["metadata"].get("namespace", "openshift-gitops")}/{obj["metadata"]["name"]}'
    need(obj["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id") == expected, "Customer input is not owned by this Application")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--preflight", action="store_true")
    parsed = args.parse_args()
    env = guard()
    revision = env.get("RHOAI_STAGE060_EXPECTED_REVISION") or subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    dsc = get(env, "datasciencecluster", "default-dsc")
    need(dsc["spec"]["components"].get("mcplifecycleoperator", {}).get("managementState") == "Managed", "Native MCP lifecycle must be explicitly enabled first")
    crd = get(env, "crd", "mcpservers.mcp.x-k8s.io")
    need(any(v["name"] == "v1alpha1" and v["served"] for v in crd["spec"]["versions"]), "Reviewed native MCPServer API is not served")
    need(any(c["type"] == "Established" and c["status"] == "True" for c in crd.get("status", {}).get("conditions", [])), "Native MCPServer API is not established")
    app = get(env, "applications.argoproj.io", APP, "openshift-gitops", optional=True)
    if app:
        app_identity(app, None if parsed.preflight else revision)
        if parsed.preflight:
            need(not app.get("operation") and app.get("status", {}).get("operationState", {}).get("phase") != "Running", "Existing component sync is still active")
    namespace = get(env, "namespace", NS, optional=True)
    need(namespace is not None, "Existing demo project is required; this component never creates a namespace")
    if namespace:
        need(not namespace["metadata"].get("deletionTimestamp"), "Existing demo project is terminating")
        for resource in ["serviceaccount", "configmap", "mcpservers.mcp.x-k8s.io", "route"]:
            obj = get(env, resource, "openshift-mcp-server", NS, optional=True)
            if obj:
                tracked(obj)
    # Never adopt an existing native Service implicitly.
    server = get(env, "mcpservers.mcp.x-k8s.io", "openshift-mcp-server", NS, optional=True) if namespace else None
    if namespace and not server:
        need(not get(env, "service", "openshift-mcp-server", NS, optional=True), "Existing Service cannot be adopted implicitly")
    if parsed.preflight:
        print("[PASS] Guarded native MCP prerequisite and customer ownership checks")
        return
    need(app is not None and server is not None, "Native MCP component is absent")
    route = get(env, "route", "openshift-mcp-server", NS)
    tracked(route)
    need(route["spec"].get("tls") == {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"} and route["spec"]["to"]["name"] == "openshift-mcp-server" and route["spec"].get("port", {}).get("targetPort") == 8080, "HTTPS edge/redirect boundary differs")
    config = tomllib.loads(get(env, "configmap", "openshift-mcp-server", NS)["data"]["config.toml"])
    need(all(config.get(k) is True for k in ["require_oauth", "read_only", "stateless", "skip_jwt_verification", "disable_dynamic_client_registration"]) and config.get("cluster_auth_mode") == "passthrough" and config.get("cluster_provider_strategy") == "in-cluster" and config.get("require_tls") is False and config.get("toolsets") == ["core", "config"] and not config.get("enabled_tools") and not config.get("disabled_tools") and config.get("denied_resources") == [{"group": "", "version": "v1", "kind": "Secret"}], "Effective MCP caller-auth/read-only/tool policy differs")
    need(any(c.get("type") == "Admitted" and c.get("status") == "True" for i in route.get("status", {}).get("ingress", []) for c in i.get("conditions", [])), "HTTPS Route is not admitted")
    status = app["status"]
    operation = status.get("operationState", {})
    source = operation.get("syncResult", {}).get("source", {})
    need(status.get("sync", {}).get("status") == "Synced" and status.get("sync", {}).get("revision") == revision, "Application comparison is stale")
    need(operation.get("phase") == "Succeeded" and operation.get("syncResult", {}).get("revision") == revision and source.get("path") == PATH and source.get("targetRevision") == revision, "Exact native operation has not succeeded")
    need(server["spec"]["source"]["containerImage"]["ref"] == IMAGE, "Native MCP image pin differs")
    need(server["spec"]["config"]["port"] == 8080 and server["spec"]["config"]["path"] == "/mcp", "Approved native HTTP handshake configuration differs")
    ready = [c for c in server.get("status", {}).get("conditions", []) if c["type"] == "Ready"]
    need(len(ready) == 1 and ready[0]["status"] == "True" and ready[0].get("observedGeneration") == server["metadata"]["generation"], "MCPServer readiness is not current")
    for resource in ["deployment", "service", "networkpolicy"]:
        obj = get(env, resource, "openshift-mcp-server", NS)
        need(any(o.get("uid") == server["metadata"]["uid"] and o.get("kind") == "MCPServer" and o.get("controller") is True for o in obj["metadata"].get("ownerReferences", [])), "Native operand controller ownership differs")
        if resource == "deployment":
            need(obj["spec"]["template"]["spec"].get("serviceAccountName") == "openshift-mcp-server", "Native MCP bootstrap service account differs")
            containers = obj["spec"]["template"]["spec"]["containers"]
            need(len(containers) == 1 and containers[0]["image"] == IMAGE, "Native Deployment catalog image differs")
            s = obj.get("status", {})
            n = obj["spec"].get("replicas", 1)
            need(s.get("observedGeneration") == obj["metadata"]["generation"] and all(s.get(k, 0) == n for k in ["replicas", "updatedReplicas", "readyReplicas", "availableReplicas"]), "Native rollout incomplete")
            replicasets = get(env, "replicasets", namespace=NS)["items"]
            rsuids = {r["metadata"]["uid"] for r in replicasets if any(o.get("uid") == obj["metadata"]["uid"] and o.get("controller") is True for o in r["metadata"].get("ownerReferences", []))}
            pods = [p for p in get(env, "pods", namespace=NS)["items"] if not p["metadata"].get("deletionTimestamp") and any(o.get("uid") in rsuids and o.get("controller") is True for o in p["metadata"].get("ownerReferences", []))]
            child = json.loads((ROOT / PATH / "catalog-source.json").read_text())["amd64_image_digest"]
            need(len(pods) == n and all(p["spec"].get("serviceAccountName") == "openshift-mcp-server" and p["status"].get("phase") == "Running" and any(c.get("name") == containers[0]["name"] and c.get("ready") is True and c.get("imageID", "").endswith("@" + child) for c in p["status"].get("containerStatuses", [])) for p in pods), "Ready native Pod runtime image/ownership differs from the reviewed amd64 artifact")
    print("[PASS] Exact source/native MCP ownership and readiness; protocol/caller isolation NOT qualified by this check")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("[FAIL] " + str(error))
        raise SystemExit(1)
