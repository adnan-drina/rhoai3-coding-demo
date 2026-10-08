#!/usr/bin/env python3
"""Read-only native checks. Entry point repeats the repository cluster guard.

No HTTP/provider calls, model downloads, workload creation or operand writes.
Resource payloads and command stderr never enter diagnostic output.
"""
import base64
import io
from urllib.parse import urlparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

APP = "040-governed-models-as-a-service"
SOURCE = "gitops/stages/" + APP + "/base"
ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = os.environ.get("RHOAI_OC_REQUEST_TIMEOUT", "10s")


def need(value, message):
    if not value:
        raise RuntimeError(message)


def command(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Bounded native read did not complete") from None
    need(r.returncode == 0, "Native read failed; inspect authorized operator diagnostics")
    return r.stdout


def get(kind, name=None, ns=None):
    args = ["oc", "--request-timeout=" + TIMEOUT, "get", kind]
    if name:
        args.append(name)
    if ns:
        args += ["-n", ns]
    return json.loads(command(args + ["-o", "json"]))


def conditions(obj):
    return {c["type"]: c for c in obj.get("status", {}).get("conditions", [])}


def current(obj):
    need(not obj["metadata"].get("deletionTimestamp"), "Resource is being deleted")
    generation = obj["metadata"].get("generation")
    need(isinstance(generation, int), "Resource generation is absent")
    need(obj.get("status", {}).get("observedGeneration") == generation,
         "Native observed generation is stale or absent")


def condition(obj, kind, fresh=False):
    c = conditions(obj).get(kind, {})
    need(c.get("status") == "True", "Native " + kind + " condition is not True")
    if fresh or "observedGeneration" in c:
        need(c.get("observedGeneration") == obj["metadata"].get("generation"),
             "Native condition generation is stale or absent")


def workload(obj):
    current(obj)
    s, spec = obj.get("status", {}), obj["spec"]
    replicas = spec.get("replicas", 1)
    need(replicas > 0 and s.get("readyReplicas", 0) >= replicas and
         s.get("updatedReplicas", 0) >= replicas, "Workload replicas are not current and ready")
    if obj["kind"] == "Deployment":
        need(s.get("replicas") == replicas and
             s.get("updatedReplicas") == replicas and
             s.get("availableReplicas", 0) == replicas,
             "Deployment rollout is incomplete or has unavailable replicas")
    if obj["kind"] == "StatefulSet":
        need(s.get("currentRevision") and s.get("currentRevision") == s.get("updateRevision"),
             "StatefulSet revision is not current")


def owner(obj, uid):
    return any(o.get("uid") == uid and o.get("controller") is True
               for o in obj["metadata"].get("ownerReferences", []))


def csv_owner(obj, csv):
    # OLM references its CSV with controller:false; component owners remain strict.
    return any(o.get("uid") == csv["metadata"]["uid"] and
               o.get("name") == csv["metadata"]["name"] and
               o.get("kind") == "ClusterServiceVersion" and
               o.get("apiVersion", "").split("/", 1)[0] == "operators.coreos.com"
               for o in obj["metadata"].get("ownerReferences", []))


def app_ready(app, expected=None):
    source = app["spec"]["source"]
    revision = source.get("targetRevision", "")
    need(re.fullmatch(r"[0-9a-f]{40}", revision), "Stage040 Application revision is not immutable")
    need(not expected or expected == revision, "Stage040 differs from requested revision")
    need(source.get("path") == SOURCE, "Stage040 Application source path differs")
    s = app.get("status", {})
    need(s.get("sync", {}).get("status") == "Synced" and s.get("sync", {}).get("revision") == revision,
         "Stage040 has not synchronized its current revision")
    need(s.get("health", {}).get("status") == "Healthy", "Stage040 Application is not Healthy")
    op = s.get("operationState", {})
    need(op.get("phase") == "Succeeded", "Stage040 operation did not succeed")
    result = op.get("syncResult", {})
    need(result.get("revision") == revision and result.get("source", {}).get("path") == SOURCE,
         "Stage040 operation revision/path is stale")


def selector_matches(selector, labels):
    if not all(labels.get(k) == v for k, v in selector.get("matchLabels", {}).items()):
        return False
    for e in selector.get("matchExpressions", []):
        key, op, values = e["key"], e["operator"], e.get("values", [])
        if op == "In" and labels.get(key) not in values:
            return False
        if op == "NotIn" and labels.get(key) in values:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
        need(op in ("In", "NotIn", "Exists", "DoesNotExist"), "Unsupported native namespace selector")
    return True


def allows(listener, ns):
    rule = listener.get("allowedRoutes", {}).get("namespaces", {})
    return rule.get("from") == "Selector" and selector_matches(rule.get("selector", {}), ns["metadata"].get("labels", {}))


def reviewed_routes(listener, expected):
    need(listener.get("allowedRoutes") == expected["allowedRoutes"],
         "Gateway namespace selector differs from reviewed scope")


def route_ready(route, section, controller):
    need(controller, "Native GatewayClass controller is absent")
    matches = []
    for p in route.get("status", {}).get("parents", []):
        ref = p.get("parentRef", {})
        if (p.get("controllerName") == controller and
                ref.get("group", "gateway.networking.k8s.io") == "gateway.networking.k8s.io" and
                ref.get("kind", "Gateway") == "Gateway" and
                ref.get("name") == "maas-default-gateway" and
                ref.get("namespace", route["metadata"]["namespace"]) == "openshift-ingress"):
            need(ref.get("sectionName") in (None, section), "Unexpected generated route listener")
            matches.append(p)
    need(matches, "Generated route has no current Gateway attachment")
    for p in matches:
        for t in ("Accepted", "ResolvedRefs"):
            c = {c["type"]: c for c in p.get("conditions", [])}.get(t, {})
            need(c.get("status") == "True" and c.get("observedGeneration") == route["metadata"].get("generation"),
                 "Generated route attachment is not current and resolved")


def secret_keys(secret, keys):
    for key in keys:
        try:
            value = base64.b64decode(secret.get("data", {}).get(key, ""), validate=True)
        except (ValueError, TypeError):
            value = b""
        need(value and not any(x in value.lower() for x in (b"placeholder", b"replace-me")),
             "Runtime credential key is missing or invalid")


def contains_spec(actual, expected):
    # Kubernetes defaults may add fields; every authored field must still match.
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains_spec(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains_spec(a, e) for a, e in zip(actual, expected))
    return actual == expected


def rendered():
    deployed_revision = os.environ.get("RHOAI_STAGE040_DEPLOYED_REVISION")
    if deployed_revision:
        need(re.fullmatch(r"[0-9a-f]{40}", deployed_revision), "Deployed validation requires an immutable commit SHA")
        need(deployed_revision == os.environ.get("RHOAI_STAGE040_EXPECTED_REVISION"), "Deployed validation revision differs from expected Application revision")
        app_ready(get("application", APP, "openshift-gitops"), deployed_revision)
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", deployed_revision, SOURCE], capture_output=True, timeout=30)
        need(archive.returncode == 0, "Deployed source revision is not available locally")
        with tempfile.TemporaryDirectory(prefix="stage040-deployed-") as directory:
            destination = Path(directory)
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as stream:
                for member in stream.getmembers():
                    path = Path(member.name)
                    in_source = member.name.startswith(SOURCE + "/")
                    ancestor = member.isdir() and (member.name.rstrip("/") == SOURCE or SOURCE.startswith(member.name.rstrip("/") + "/"))
                    need(not path.is_absolute() and ".." not in path.parts and (in_source or ancestor), "Deployed source archive path is invalid")
                    target = destination / path
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        need(member.isfile(), "Deployed source archive contains a non-file resource")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(stream.extractfile(member).read())
            yaml = command(["oc", "kustomize", str(destination / SOURCE)])
    else:
        yaml = command(["oc", "kustomize", str(ROOT / SOURCE)])
    r = subprocess.run(["ruby", "-ryaml", "-rjson", "-e",
                        "puts JSON.generate(YAML.load_stream(STDIN.read).compact)"],
                       input=yaml, capture_output=True, text=True, timeout=30)
    need(r.returncode == 0, "Reviewed Stage040 manifests could not be read")
    return json.loads(r.stdout)


def main():
    # Safe even when directly invoked instead of through validate.sh.
    command(["/bin/bash", "-c", 'export REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in', "guard", str(ROOT)])
    if not os.environ.get("RHOAI_STAGE040_DEPLOYED_REVISION"):
        subprocess.run(["python3", str(ROOT / "scripts/platform/check-operator-policy.py"), str(ROOT / SOURCE), "--verify"], check=True)
    desired = rendered()
    app = get("application", APP, "openshift-gitops")
    app_ready(app, os.environ.get("RHOAI_STAGE040_EXPECTED_REVISION"))
    print("[PASS] Exact immutable Stage040 sync and successful operation")
    subscriptions = [o for o in desired if o["kind"] == "Subscription"]
    need(len(subscriptions) == 6, "Reviewed operator selection is incomplete")
    for d in subscriptions:
        m, spec = d["metadata"], d["spec"]
        s = get("subscription", m["name"], m["namespace"])
        need(spec["installPlanApproval"] in ("Automatic", "Manual") and
             all(s["spec"].get(k) == spec.get(k) for k in ("name", "channel", "source", "sourceNamespace", "startingCSV", "installPlanApproval")), "Operator selection differs from reviewed subscription")
        need(os.environ.get("RHOAI_STAGE040_DEPLOYED_REVISION") or spec["installPlanApproval"] == "Automatic", "Fresh-source validation requires Automatic approval")
        installed = s.get("status", {}).get("installedCSV")
        need(installed and installed == s.get("status", {}).get("currentCSV"), "Operator resolution is pending")
        csv = get("csv", installed, m["namespace"])
        need(csv.get("status", {}).get("phase") == "Succeeded", "Selected operator CSV did not succeed")
        for dep in csv["spec"].get("install", {}).get("spec", {}).get("deployments", []):
            native = get("deployment", dep["name"], m["namespace"])
            need(csv_owner(native, csv), "Operator workload has unexpected CSV owner")
            workload(native)
    print("[PASS] Six Automatic operators and current workloads")
    dsc = get("datasciencecluster", "default-dsc")
    current(dsc); condition(dsc, "Ready")
    for key in ("aigateway", "ogx", "kserve"):
        need(dsc["spec"]["components"][key]["managementState"] == "Managed", "Native component is not Managed")
        obj = get(key + "s.components.platform.opendatahub.io", "default-" + key)
        current(obj); condition(obj, "Ready")
        need(obj.get("status", {}).get("phase") == "Ready", "Native component phase is not Ready")
    need(dsc["spec"]["components"]["aigateway"]["modelsAsAService"]["managementState"] == "Managed", "Native MaaS is not enabled")
    dashboard = get("odhdashboardconfig", "odh-dashboard-config", "redhat-ods-applications")
    flags = dashboard["spec"]["dashboardConfig"]
    need(all(flags.get(k) is True for k in ("genAiStudio", "genAiTracing", "modelAsService", "vLLMDeploymentOnMaaS", "externalModels", "llmdTemplates", "guardrails", "agentConfigManagement", "promptManagement")), "Native dashboard feature configuration is not enabled; functional acceptance is separate")
    print("[PASS] Current native KServe/AIGateway/OGX components and feature flags")
    db = get("statefulset", "maas-postgres", "models-as-a-service-db")
    workload(db)
    pvc = get("pvc", "data-maas-postgres-0", "models-as-a-service-db")
    need(pvc.get("status", {}).get("phase") == "Bound" and not pvc["metadata"].get("deletionTimestamp"), "MaaS PostgreSQL PVC is not Bound")
    need(pvc["spec"].get("storageClassName") == "gp3-csi", "MaaS PostgreSQL storage class differs")
    secret_keys(get("secret", "maas-postgres-credentials", "models-as-a-service-db"), ("POSTGRESQL_USER", "POSTGRESQL_PASSWORD", "POSTGRESQL_DATABASE"))
    secret_keys(get("secret", "maas-db-config", "redhat-ai-gateway-infra"), ("DB_CONNECTION_URL",))
    print("[PASS] Current durable MaaS PostgreSQL and runtime credential presence")
    authorino = get("authorino", "authorino", "kuadrant-system")
    condition(authorino, "Ready")  # Selected CRD supplies no status.observedGeneration.
    need(contains_spec(authorino["spec"]["listener"]["tls"], {"enabled": True, "certSecretRef": {"name": "authorino-server-cert"}}), "Native Authorino TLS configuration differs")
    mounts = authorino["spec"].get("volumes", {}).get("items", [])
    need(any(v.get("mountPath") == "/etc/pki/tls/certs" and "authorino-service-ca" in v.get("configMaps", []) and {"key": "service-ca.crt", "path": "openshift-service-ca.crt"} in v.get("items", []) for v in mounts), "Native Authorino outbound CA mount is absent")
    ca = get("configmap", "authorino-service-ca", "kuadrant-system")
    need(ca["metadata"].get("annotations", {}).get("service.beta.openshift.io/inject-cabundle") == "true" and "BEGIN CERTIFICATE" in ca.get("data", {}).get("service-ca.crt", ""), "Native Authorino CA bundle is not populated")
    secret_keys(get("secret", "authorino-server-cert", "kuadrant-system"), ("tls.crt", "tls.key"))
    deployments = get("deployments", ns="kuadrant-system")["items"]
    owned = [d for d in deployments if owner(d, authorino["metadata"]["uid"])]
    need(owned, "Native Authorino owned workload is absent")
    for d in owned:
        workload(d)
        podspec = d["spec"]["template"]["spec"]
        volumes = {v["name"] for v in podspec.get("volumes", []) if "authorino-service-ca" in json.dumps(v)}
        need(any(m.get("name") in volumes and m.get("mountPath") == "/etc/pki/tls/certs" for c in podspec["containers"] for m in c.get("volumeMounts", [])), "Authorino owned workload does not project native CA")
    print("[PASS] Native Authorino TLS/CA configuration and current owned workload; live TLS requests pending")
    gateway = get("gateway", "maas-default-gateway", "openshift-ingress")
    gateway_class = get("gatewayclass", gateway["spec"]["gatewayClassName"])
    gateway_controller = gateway_class["spec"].get("controllerName")
    condition(gateway, "Accepted", True); condition(gateway, "Programmed", True)
    listeners = {l["name"]: l for l in gateway["spec"].get("listeners", [])}
    expected_gateway = next(o for o in desired if o["kind"] == "Gateway")
    expected_listeners = {l["name"]: l for l in expected_gateway["spec"]["listeners"]}
    need(set(listeners) == {"api", "qwen3-6", "qwen3-8"}, "Gateway listener set differs")
    domains = {l.get("hostname") for l in listeners.values()}
    need(len(domains) == 3 and all(h and "*" not in h and "placeholder" not in h for h in domains), "Gateway hostnames are unresolved or not isolated")
    namespaces = {n: get("namespace", n) for n in ("models-as-a-service", "internal-models", "external-models", "redhat-ai-gateway-infra")}
    for ns in (*namespaces, "redhat-ods-applications"):
        obj = namespaces.get(ns) or get("namespace", ns)
        need(obj["metadata"].get("labels", {}).get("maas-gateway-access") == "true", "Required MaaS namespace admission label is absent")
    listener_status = {l["name"]: l for l in gateway.get("status", {}).get("listeners", [])}
    for name, listener in listeners.items():
        reviewed_routes(listener, expected_listeners[name])
        ls = listener_status.get(name, {})
        cs = {c["type"]: c for c in ls.get("conditions", [])}
        need(all(cs.get(t, {}).get("status") == "True" and cs[t].get("observedGeneration") == gateway["metadata"]["generation"] for t in ("Accepted", "ResolvedRefs")), "Gateway listener conditions are not current")
        attached = ls.get("attachedRoutes", 0)
        need(attached >= 1 if name == "api" else attached == 1, "Gateway listener route count violates isolation")
        need(listener.get("port") == 443 and listener.get("protocol") == "HTTPS" and listener.get("tls", {}).get("mode") == "Terminate", "Gateway listener lacks native TLS")
        for ns, obj in namespaces.items():
            need(allows(listener, obj) == (ns in ("external-models", "redhat-ai-gateway-infra") if name == "api" else ns == "internal-models"), "Gateway namespace isolation differs")
    routes = get("httproutes.gateway.networking.k8s.io", ns="internal-models")["items"]
    api_routes = get("httproutes.gateway.networking.k8s.io", ns="redhat-ai-gateway-infra")["items"]
    ext_routes = get("httproutes.gateway.networking.k8s.io", ns="external-models")["items"]
    for route in api_routes + ext_routes:
        refs = route["spec"].get("parentRefs", [])
        if any(r.get("name") == "maas-default-gateway" for r in refs):
            need(all(r.get("sectionName") in (None, "api") for r in refs if r.get("name") == "maas-default-gateway"), "Non-model route targets inference listener")
            route_ready(route, "api", gateway_controller)
    need(any(any(r.get("name") == "maas-default-gateway" for r in x["spec"].get("parentRefs", [])) for x in api_routes), "Native MaaS API route is absent")
    models = [o for o in desired if o["kind"] == "LLMInferenceService"]
    need(len(models) == 2, "Reviewed two-model scope differs")
    workloads = sum((get(k, ns="internal-models")["items"] for k in ("deployments", "statefulsets", "leaderworkersets.leaderworkerset.x-k8s.io")), [])
    for d in models:
        obj = get("llminferenceservices.serving.kserve.io", d["metadata"]["name"], "internal-models")
        current(obj)
        replicas = obj["spec"].get("replicas", 1)
        need(type(replicas) is int and replicas >= 0, "Native model lifecycle replica value is invalid")
        delegated = "RespectIgnoreDifferences=true" in app["spec"].get("syncPolicy", {}).get("syncOptions", []) and any(
            entry.get("group") == "serving.kserve.io" and entry.get("kind") == "LLMInferenceService"
            and entry.get("name") == d["metadata"]["name"] and entry.get("namespace") == "internal-models"
            and "/spec/replicas" in entry.get("jsonPointers", []) for entry in app["spec"].get("ignoreDifferences", []))
        expected_spec = dict(d["spec"])
        if delegated:
            expected_spec.pop("replicas", None)
        need(contains_spec(obj["spec"], expected_spec), "LLMI differs from reviewed model/runtime configuration")
        parked = replicas == 0 and delegated
        if not parked:
            condition(obj, "Ready")
        section = d["spec"]["router"]["gateway"]["refs"][0]["sectionName"]
        need(obj["spec"]["router"]["gateway"]["refs"] == d["spec"]["router"]["gateway"]["refs"], "LLMI listener references differ")
        uids = {obj["metadata"]["uid"]}
        for _ in workloads:
            uids.update(w["metadata"]["uid"] for w in workloads if any(owner(w, uid) for uid in tuple(uids)))
        owned_workloads = [w for w in workloads if w["metadata"]["uid"] in uids]
        ready_workloads = [w for w in owned_workloads if w["kind"] in ("Deployment", "StatefulSet")]
        need(ready_workloads, "Native LLMI owned workload is absent")
        for w in ready_workloads:
            if parked and w["spec"].get("replicas", 1) == 0:
                current(w)
                need(all(w.get("status", {}).get(key, 0) == 0 for key in ("replicas", "readyReplicas", "updatedReplicas", "availableReplicas")), "Parked model still has compute replicas")
            else:
                workload(w)
        selected = [r for r in routes if owner(r, obj["metadata"]["uid"])]
        need(len(selected) == 1, "Native LLMI route ownership is not unique")
        refs = selected[0]["spec"].get("parentRefs", [])
        need(len(refs) == 1 and refs[0].get("sectionName") == section, "Native LLMI route listener differs")
        route_ready(selected[0], section, gateway_controller)
        if parked:
            print("[PASS] Explicitly delegated model compute is parked; configuration/route preserved, inference not qualified")
    need(len([r for r in routes if any(p.get("name") == "maas-default-gateway" for p in r["spec"].get("parentRefs", []))]) == 2, "Extra route would invalidate dedicated inference listeners")
    print("[PASS] Three-listener isolation, exact native model configuration/routes and active workloads; parked compute is separate from inference acceptance")
    for d in [o for o in desired if o["kind"] == "LLMInferenceServiceConfig"]:
        m = d["metadata"]
        obj = get("llminferenceserviceconfigs.serving.kserve.io", m["name"], m["namespace"])
        need(obj.get("spec") == d["spec"], "Reusable serving template specification differs")
        need(not obj["metadata"].get("ownerReferences") and not obj["metadata"].get("deletionTimestamp"), "Reusable serving template ownership differs")
        tracking = APP + ":serving.kserve.io/LLMInferenceServiceConfig:" + m["namespace"] + "/" + m["name"]
        need(obj["metadata"].get("annotations", {}).get("argocd.argoproj.io/tracking-id") == tracking, "Reusable serving template is not stage-owned")
        need(all(obj["metadata"].get("labels", {}).get(k) == v for k, v in m["labels"].items()), "Reusable serving template discovery labels differ")
        if m["labels"]["opendatahub.io/config-type"] == "router":
            need(obj["metadata"].get("annotations", {}).get("opendatahub.io/supported-topologies") == '["workload-single-node"]', "Router topology filtering differs")
    accelerators = get("llminferenceserviceconfigs.serving.kserve.io", ns="redhat-ods-applications")["items"]
    selected = [o for o in accelerators if o["metadata"].get("labels", {}).get("opendatahub.io/config-type") == "accelerator"]
    nvidia = [o for o in selected if o["metadata"]["name"].endswith("single-node-template-nvidia-cuda")]
    need(len(nvidia) == 1 and nvidia[0]["metadata"].get("annotations", {}).get("opendatahub.io/support-status") != "unsupported", "Supported single-node NVIDIA accelerator template is unavailable")
    images = [c.get("image", "") for c in nvidia[0]["spec"].get("template", {}).get("containers", []) if c.get("name") == "main"]
    need(len(images) == 1 and re.fullmatch(r"registry\.redhat\.io/.+@sha256:[0-9a-f]{64}", images[0]), "Native NVIDIA runtime image is not immutable")
    print("[PASS] Stage-owned single-node router/topology templates and native pinned NVIDIA accelerator configuration; dashboard interaction is separate")
    for d in [o for o in desired if o["kind"] in ("ExternalProvider", "ExternalModel", "MaaSModelRef")]:
        kind = d["kind"]
        ns, name = d["metadata"]["namespace"], d["metadata"]["name"]
        group = "maas.opendatahub.io" if kind == "MaaSModelRef" else "inference.opendatahub.io"
        obj = get(kind.lower() + "s." + group, name, ns)
        parked_ref = kind == "MaaSModelRef" and ns == "internal-models" and name == "qwen3-6-27b" and get("llminferenceservices.serving.kserve.io", name, ns)["spec"].get("replicas") == 0
        if not parked_ref:
            need(obj.get("status", {}).get("phase") == "Ready", "Native model registration phase is not Ready")
        if kind != "MaaSModelRef":
            condition(obj, "Ready", True)
            if kind == "ExternalProvider" and name == "redhat-models":
                endpoint = urlparse(os.environ.get("REDHAT_MODELS_BASE_URL", ""))
                need(endpoint.scheme == "https" and endpoint.port in (None, 443) and endpoint.path in ("", "/", "/v1", "/v1/") and endpoint.hostname and not endpoint.username and not endpoint.password and not endpoint.query and not endpoint.fragment, "Approved Red Hat provider input is unavailable")
                d["spec"]["endpoint"] = endpoint.hostname
            need(contains_spec(obj["spec"], d["spec"]), "External native configuration differs from reviewed spec")
        if kind == "ExternalProvider":
            sec = get("secret", obj["spec"]["auth"]["secretRef"]["name"], ns)
            secret_keys(sec, ("api-key",))
            need(sec["metadata"].get("labels", {}).get("inference.llm-d.ai/ipp-managed") == "true", "Provider Secret lacks native IPP discovery label")
        if kind == "ExternalModel":
            route_name = obj["status"].get("httpRouteName")
            need(route_name, "Native external model route status is absent")
            r = get("httproute", route_name, ns)
            need(owner(r, obj["metadata"]["uid"]), "External route is not owned by native model")
            route_ready(r, "api", gateway_controller)
        if kind == "MaaSModelRef":
            for t in (("GovernanceAttached",) if parked_ref else ("Ready", "GovernanceAttached", "RuntimeReady")):
                condition(obj, t, True)
            if parked_ref:
                runtime = conditions(obj).get("RuntimeReady", {})
                need(runtime.get("observedGeneration") == obj["metadata"]["generation"] and runtime.get("status") in ("True", "False"), "Parked model runtime observation is stale or absent")
                print("[PASS] Parked model reference governance/current native observation; runtime status is not inference qualification")
            need(obj["spec"].get("modelRef") == d["spec"]["modelRef"] and obj["spec"].get("tenantRef") == d["spec"].get("tenantRef"), "Native model reference differs")
            if not parked_ref:
                need(obj.get("status", {}).get("endpoint"), "Native model endpoint discovery is absent")
            if ns == "external-models":
                endpoint = "https://" + listeners["api"]["hostname"]
                if d["spec"].get("endpointOverride"):
                    need(obj["spec"].get("endpointOverride") == endpoint, "External endpoint override differs from the API hostname")
                else:
                    need(not obj["spec"].get("endpointOverride"), "Unexpected external endpoint override remains")
                need(obj["status"].get("endpoint") == endpoint, "External discovery does not select the API hostname")
    print("[PASS] Native external/provider/model references and credential presence; upstream entitlement/inference pending")
    command([sys.executable, str(ROOT / "stages/040-governed-models-as-a-service/publish-catalog-mcp.py"), "--validate", "--defer-if-absent"])
    print("[PASS] Studio catalog field or explicit deferred Stage060 prerequisite; session use is separate")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never emit command stderr, response bodies, private endpoints or Secret data.
        print("[FAIL] " + (str(error) if isinstance(error, RuntimeError) else "Native validation data could not be interpreted"))
        sys.exit(1)
