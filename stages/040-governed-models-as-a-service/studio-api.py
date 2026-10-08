#!/usr/bin/env python3
"""Native Studio API transport; secrets stay in memory, receipts contain no payloads.

Contract: deployed odh-dashboard f4a81e89bf8a1fb0bbe3dfdc7b10eaa39b3d7439.
This uses the BFF that owns playground, agent-profile and tracing provisioning;
it never edits its generated deployments, collector configuration or database.
"""
import argparse
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "demo-sandbox"
SOURCE_IMAGE = "registry.redhat.io/rhoai/odh-mod-arch-gen-ai-rhel9@sha256:9fccbc4215f2c3c792eeaa5a4081826fe4e6cbeb69d5f9aa4572ad06c4b2aecc"


def guard(kubeconfig=None):
    environment = dict(os.environ)
    if kubeconfig:
        environment["KUBECONFIG"] = kubeconfig
    script = ('set -euo pipefail; source "$1/scripts/shared/lib.sh"; '
              'REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env; check_oc_logged_in >/dev/null; '
              'python3 -c \'import json,os; print(json.dumps({k:os.environ.get(k) for k in ("KUBECONFIG","PATH")}))\'')
    result = subprocess.run(["bash", "-c", script,
                             "studio-api", str(ROOT)], capture_output=True, text=True, env=environment)
    if result.returncode:
        raise RuntimeError("OpenShift login/expected-server guard failed; renew approved access before continuing.")
    guarded = json.loads(result.stdout)
    # The queries must use precisely the environment whose cluster was guarded.
    # Persona validation never replaces the established bootstrap environment.
    if not kubeconfig:
        for key, value in guarded.items():
            if value is not None:
                os.environ[key] = value


def oc(*args):
    result = subprocess.run(["oc", "--request-timeout=15s", *args], capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError("Native resource read failed; no configuration was changed.")
    return result.stdout


def stage_ready(stage, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("Supply the reviewed published 40-character stage revision.")
    name = {"040": "040-governed-models-as-a-service", "050": "050-model-evaluation"}[stage]
    app = json.loads(oc("get", "application", name, "-n", "openshift-gitops", "-o", "json"))
    spec, status = app["spec"], app.get("status", {})
    source = spec.get("source", {})
    sync = status.get("operationState", {}).get("syncResult", {})
    if (app["metadata"].get("ownerReferences") or app["metadata"].get("deletionTimestamp")
            or spec.get("sources") or spec.get("project") != "rhoai-demo"
            or spec.get("destination") != {"server": "https://kubernetes.default.svc", "namespace": "openshift-gitops"}
            or source.get("repoURL") != "https://github.com/adnan-drina/rhoai3-coding-demo.git"
            or source.get("path") != "gitops/stages/" + name + "/base"
            or source.get("targetRevision") != revision
            or status.get("sync", {}).get("revision") != revision
            or status.get("sync", {}).get("status") != "Synced"
            or status.get("health", {}).get("status") != "Healthy"
            or status.get("operationState", {}).get("phase") != "Succeeded"
            or sync.get("revision") != revision or sync.get("source", {}).get("path") != source["path"]):
        raise RuntimeError("Exact native stage Application source/readiness guard failed.")


class NativeError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Native API returned HTTP {status}.")


@contextmanager
def bff(service="odh-dashboard-gen-ai-ui", port=8143, identity_kubeconfig=None):
    namespace = "redhat-ods-applications"
    hostname = service + "." + namespace + ".svc"
    ca = json.loads(oc("get", "configmap", "mlflow-service-ca", "-n", namespace, "-o", "json"))["data"]["service-ca.crt"]
    token = oc(*(["--kubeconfig", identity_kubeconfig] if identity_kubeconfig else []), "whoami", "--show-token").strip()
    context = ssl.create_default_context(cadata=ca)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        local_port = listener.getsockname()[1]
    process = subprocess.Popen(["oc", "port-forward", "-n", namespace, "service/" + service,
                                f"{local_port}:{port}", "--address=127.0.0.1"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class HTTPS(http.client.HTTPSConnection):
        def connect(self):
            raw = socket.create_connection(("127.0.0.1", local_port), self.timeout)
            self.sock = context.wrap_socket(raw, server_hostname=hostname)
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=1):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Native BFF port-forward unavailable.") from None
                time.sleep(.2)
        def request(method, path, payload=None):
            connection = HTTPS(hostname, timeout=70, context=context)
            try:
                connection.request(method, path, json.dumps(payload) if payload is not None else None,
                                   {"x-forwarded-access-token": token, "Content-Type": "application/json"})
                response = connection.getresponse()
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise RuntimeError("Native response exceeded bounded size.")
                # Do not print response error bodies, which can include URLs or credentials.
                if response.status not in (200, 201, 204):
                    raise NativeError(response.status)
                if response.getheader("X-MLflow-BFF-Unavailable") == "true":
                    raise RuntimeError("Native MLflow BFF unavailable; empty-list fallback is not success.")
                return json.loads(raw) if raw else {}
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


def endpoint(path, namespace=NAMESPACE, **query):
    return "/gen-ai/api/v1/" + path + "?" + urlencode({"namespace": namespace, **query})


def qualify_agents(request, model_id):
    # GenAI flattens the inter-BFF MaaS envelope into {object, data:[...]}.
    models = request("GET", endpoint("maas/models"))["data"]
    selected = [m for m in models if m["id"] == model_id and m.get("ready")]
    if len(selected) != 1:
        raise RuntimeError("Selected governed model is not uniquely available to this persona.")
    profiles = request("GET", endpoint("agent-profiles"))["data"]["profiles"]
    receipts = []
    for variant in (False, True):
        name = "Governed code review" + (" variant" if variant else "")
        spec = {"displayName": name, "description": "Reviewed public demo configuration",
                "model": {"id": model_id, "uri": selected[0]["url"], "sourceType": "maas"},
                "prompt": {"name": "governed-code-review", "source": "mlflow",
                           "namespace": NAMESPACE, "version": "2"},
                "maxOutputTokens": 128, "temperature": .1 if variant else 0, "stream": True}
        found = [p for p in profiles if p["displayName"] == name]
        if len(found) > 1:
            raise RuntimeError("Duplicate sample agent names; refusing ambiguous adoption.")
        created = found[0] if found else request("POST", endpoint("agent-profiles"), {"spec": spec})["data"]
        profile_id = created["profileId"]
        loaded = request("GET", endpoint("agent-profiles/" + profile_id))["data"]
        if loaded["spec"] != spec:
            raise RuntimeError("Persisted agent configuration differs; refusing overwrite.")
        receipts.append({"profile_id": profile_id, "variant": variant, "persisted": True})
    # MLflow global read access must not confer foreign project agent access.
    try:
        request("GET", endpoint("agent-profiles", namespace="ai-curated-prompts"))
    except NativeError as error:
        if error.status != 403:
            raise
    else:
        raise RuntimeError("Persona can access foreign agent configuration namespace.")
    print(json.dumps({"scope": "native agent save/load/variant persistence and foreign-namespace denial", "profiles": receipts}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-revision", required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install-model", help="Explicit native MaaS model ID; creates a new retained playground, never replaces one")
    action.add_argument("--qualify-agents", metavar="MODEL_ID", help="Save/load retained public sample agent variants; no inference")
    action.add_argument("--initialize-guardrails", action="store_true", help="Native Studio guardrail initialization; no model calls")
    parser.add_argument("--persona-kubeconfig", help="Existing developer identity; bootstrap context performs Application guards only")
    args = parser.parse_args()
    guard()
    if args.persona_kubeconfig:
        guard(args.persona_kubeconfig)
    stage_ready("040", args.expected_revision)
    deployment = json.loads(oc("get", "deployment", "gen-ai-ui", "-n", "redhat-ods-applications", "-o", "json"))
    if deployment["spec"]["template"]["spec"]["containers"][0]["image"] != SOURCE_IMAGE:
        raise RuntimeError("GenAI BFF image differs from the reviewed API source contract.")
    with bff(identity_kubeconfig=args.persona_kubeconfig) as request:
        if args.install_model:
            existing = json.loads(oc("get", "ogxservers.ogx.io", "-n", NAMESPACE, "-o", "json"))["items"]
            if existing:
                raise RuntimeError("Playground already exists; preserve its state and use read-only validation.")
            request("POST", endpoint("lsd/install"), {"models": [{"model_name": args.install_model,
                    "model_source_type": "maas", "model_type": "llm", "max_tokens": 128}], "enable_tracing": True})
            print("[PASS] Native retained playground creation requested with opt-in tracing; readiness and spans still require qualification.")
        elif args.qualify_agents:
            if not args.persona_kubeconfig:
                raise RuntimeError("Agent qualification requires an explicit developer persona kubeconfig.")
            qualify_agents(request, args.qualify_agents)
        elif args.initialize_guardrails:
            dashboard = json.loads(oc("get", "odhdashboardconfig", "odh-dashboard-config", "-n", "redhat-ods-applications", "-o", "json"))
            if dashboard["spec"]["dashboardConfig"].get("guardrails") is not True:
                raise RuntimeError("Native Studio guardrails flag must be enabled by its stage owner first.")
            existing = json.loads(oc("get", "nemoguardrails.trustyai.opendatahub.io", "-n", NAMESPACE, "-o", "json"))["items"]
            if not existing:
                request("POST", endpoint("nemo-guardrails/init"), {})
            elif len(existing) != 1 or existing[0]["metadata"]["name"] != "nemoguardrails":
                raise RuntimeError("Unexpected guardrail resources; refusing competing provisioning.")
            print("[PASS] Native Studio guardrail initialization retained; model-backed input/output qualification remains separate.")
        else:
            result = request("GET", endpoint("lsd/status"))
            print(json.dumps({"scope": "native Studio status GET", "response_present": bool(result.get("data"))}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, OSError, ValueError, KeyError) as error:
        # Unexpected response parsing/errors must not dump private response contents.
        if isinstance(error, RuntimeError):
            raise SystemExit("[FAIL] " + str(error))
        raise SystemExit("[FAIL] Native Studio contract could not be verified.")
