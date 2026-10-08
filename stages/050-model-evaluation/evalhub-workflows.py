#!/usr/bin/env python3
"""Native tenant EvalHub discovery and retained collection qualification.

No model request is submitted by this helper. Product contract: EvalHub
90648741f29f5421f24601d8b2c32909852bc365 and installed OpenAPI CollectionConfig.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
TENANT = "demo-sandbox"
NAME = "coding-instruction-check"
TAG = "rhoai3-coding-demo"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


studio = load("studio", ROOT / "stages/040-governed-models-as-a-service/studio-api.py")
native = load("evaluation_api", Path(__file__).with_name("service-api.py"))


def items(response):
    result = response.get("items")
    if not isinstance(result, list) or not all(isinstance(i, dict) and i.get("resource", {}).get("id") for i in result):
        raise RuntimeError("Installed EvalHub resource-list schema differs.")
    if response.get("total_count", len(result)) > len(result):
        raise RuntimeError("Discovery is paginated; bounded qualification cannot assume complete inventory.")
    return result


def qualify_collection(request, providers):
    matching = [p for p in providers if p["resource"]["id"] == "lm_evaluation_harness"]
    if len(matching) != 1 or not any(b["id"] == "ifeval" for b in matching[0].get("benchmarks", [])):
        raise RuntimeError("Required native IFEval benchmark is unavailable.")
    desired = {"name": NAME, "category": "instruction_following",
               "description": "Bounded instruction-following integration check; not a full coding benchmark.",
               "tags": [TAG, "bounded-demo"], "pass_criteria": {"threshold": 0.6},
               "benchmarks": [{"id": "ifeval", "provider_id": "lm_evaluation_harness", "weight": 1,
                               "primary_score": {"metric": "inst_level_strict_acc", "lower_is_better": False},
                               "pass_criteria": {"threshold": 0.6},
                               "parameters": {"num_fewshot": 0, "limit": 2}}]}
    existing = [c for c in items(request("api/v1/evaluations/collections")) if c.get("name") == NAME]
    if len(existing) > 1:
        raise RuntimeError("Collection name is ambiguous; no adoption or overwrite.")
    created = False
    if not existing:
        collection = request("api/v1/evaluations/collections", desired, expected_status=201)
        created = True
    else:
        collection = existing[0]
    identity = collection.get("resource", {})
    if identity.get("tenant") != TENANT or TAG not in collection.get("tags", []):
        raise RuntimeError("Collection ownership/tenant differs; no overwrite.")
    collection_id = identity["id"]
    path = "api/v1/evaluations/collections/" + quote(collection_id, safe="")
    loaded = request(path)
    for field in ["name", "category", "tags", "pass_criteria", "benchmarks"]:
        if loaded.get(field) != desired[field]:
            raise RuntimeError("Native persisted collection differs from the bounded reviewed definition.")
    return {"id": collection_id, "tenant": TENANT, "created": created,
            "read_after_write": True, "benchmarks": 1, "example_limit": 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--persona-kubeconfig", required=True)
    parser.add_argument("--qualify-collection", action="store_true")
    args = parser.parse_args()
    studio.guard()
    studio.stage_ready("050", args.expected_revision)
    studio.guard(args.persona_kubeconfig)
    discovery = json.loads(studio.oc("get", "configmap", "evalhub-discovery", "-n", TENANT, "-o", "json"))["data"]
    ca = json.loads(studio.oc("get", "configmap", "evalhub-service-ca", "-n", TENANT, "-o", "json"))["data"]["service-ca.crt"]
    token = studio.oc("--kubeconfig", args.persona_kubeconfig, "whoami", "--show-token").strip()
    with native.api("evalhub", "evalhub", discovery["evalhub.url"], ca, token, TENANT) as request:
        health = request("api/v1/health")
        if health.get("status") != "healthy":
            raise RuntimeError("Native evaluation service is not healthy.")
        providers = items(request("api/v1/evaluations/providers?benchmarks=true"))
        collections = items(request("api/v1/evaluations/collections"))
        receipt = {"tenant": TENANT, "providers": [p["resource"]["id"] for p in providers],
                   "provider_benchmarks": sum(len(p.get("benchmarks", [])) for p in providers),
                   "collections": [c["resource"]["id"] for c in collections],
                   "model_requests_submitted": 0}
        if args.qualify_collection:
            receipt["retained_custom_collection"] = qualify_collection(request, providers)
        print(json.dumps(receipt))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError, OSError):
        raise SystemExit("Native EvalHub qualification failed; no model job was submitted. Private diagnostics remain unprinted.")
