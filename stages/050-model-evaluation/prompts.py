#!/usr/bin/env python3
"""Seed/verify retained sample prompts through the shipped native MLflow BFF.

No inference is performed. Seed mode is explicit and repeatable: existing
versions must match the reviewed sample content; foreign prompts are refused.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

root = Path(__file__).resolve().parents[2]
module = importlib.util.spec_from_file_location("studio_api", root / "stages/040-governed-models-as-a-service/studio-api.py")
studio = importlib.util.module_from_spec(module)
module.loader.exec_module(studio)

GLOBAL = "ai-curated-prompts"
NAME = "governed-code-review"
TEMPLATES = (
    "Review the supplied {{language}} code. Explain correctness and security issues without inventing test results.",
    "Review the supplied {{language}} code. Explain correctness and security issues without inventing test results. Separate observed evidence from assumptions.",
)
OWNER = "rhoai3-coding-demo"


def path(workspace, suffix="", **query):
    return "/mlflow/api/v1/prompts" + suffix + "?" + urlencode({"workspace": workspace, **query})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-revision", required=True, help="Reviewed Stage050 revision")
    parser.add_argument("--seed", action="store_true", help="Create only missing reviewed sample versions")
    parser.add_argument("--persona-kubeconfig", help="Existing developer identity for read-only local/global consumption proof")
    args = parser.parse_args()
    studio.guard()
    if args.persona_kubeconfig:
        if args.seed:
            raise RuntimeError("Curated seed uses an administrator; persona mode is read-only.")
        studio.guard(args.persona_kubeconfig)
    studio.stage_ready("050", args.expected_revision)
    dashboard = json.loads(studio.oc("get", "odhdashboardconfig", "odh-dashboard-config", "-n", "redhat-ods-applications", "-o", "json"))["spec"]
    if dashboard.get("globalMLflowNamespaces") != [GLOBAL]:
        raise RuntimeError("Native global prompt namespace differs from the dedicated curated workspace.")
    namespace = json.loads(studio.oc("get", "namespace", GLOBAL, "-o", "json"))
    if namespace["metadata"].get("labels", {}).get("opendatahub.io/global-mlflow-workspace") != "mlflow":
        raise RuntimeError("Native global workspace reconciliation label is missing.")
    receipts = []
    with studio.bff("odh-dashboard-mlflow-ui", 8343, args.persona_kubeconfig) as request:
        for workspace in (GLOBAL, studio.NAMESPACE):
            listing = request("GET", path(workspace, filter_name=NAME))["data"]
            if listing.get("failed_namespaces") or listing.get("next_page_token"):
                raise RuntimeError("Prompt discovery is incomplete or a configured namespace is unauthorized.")
            matching = [p for p in listing.get("prompts", []) if p["name"] == NAME
                        and p.get("scope", {}).get("namespace") == workspace
                        and p.get("scope", {}).get("type") == "project"]
            if len(matching) > 1:
                raise RuntimeError("Duplicate scoped sample prompt discovery.")
            if matching and matching[0].get("tags", {}).get("demo.owner") != OWNER:
                raise RuntimeError("Existing sample name belongs to another owner; refusing append.")
            existing = int(matching[0]["latest_version"]) if matching else 0
            for version, template in enumerate(TEMPLATES, 1):
                if version > existing:
                    if not args.seed:
                        raise RuntimeError("Reviewed prompt versions are not registered; run explicit seed after deployment.")
                    result = request("POST", path(workspace), {"name": NAME, "template": template,
                        "commit_message": "Reviewed public demo instructions version " + str(version),
                        "tags": {"demo.owner": OWNER}, "create_only": version == 1})["data"]
                    if int(result["version"]) != version:
                        raise RuntimeError("Concurrent prompt registration changed the expected version sequence.")
                result = request("GET", path(workspace, "/" + NAME, version=version))["data"]
                if result.get("template") != template or int(result["version"]) != version:
                    raise RuntimeError("Persisted prompt version differs from reviewed public instructions.")
                receipts.append({"workspace": workspace, "name": NAME, "version": version,
                                 "template_sha256": hashlib.sha256(template.encode()).hexdigest()})
    if args.persona_kubeconfig:
        with studio.bff(identity_kubeconfig=args.persona_kubeconfig) as request:
            listing = request("GET", studio.endpoint("mlflow/prompts"))["data"]
            global_prompts = [p for p in listing.get("prompts", []) if p.get("name") == NAME
                              and p.get("scope", {}).get("namespace") == GLOBAL
                              and p.get("scope", {}).get("type") == "global"]
            if len(global_prompts) != 1 or global_prompts[0]["scope"].get("read_only") is not True:
                raise RuntimeError("Studio did not expose the curated prompt as globally read-only.")
            for version, template in enumerate(TEMPLATES, 1):
                loaded = request("GET", studio.endpoint("mlflow/prompts/" + NAME, workspace=GLOBAL, version=version))["data"]
                if loaded.get("template") != template:
                    raise RuntimeError("Studio global prompt load differs from the retained version.")
        result = subprocess.run(["oc", "--kubeconfig", args.persona_kubeconfig, "auth", "can-i", "create",
                                        "registeredmodels.mlflow.kubeflow.org", "-n", GLOBAL],
                                       capture_output=True, text=True, timeout=20)
        if result.stdout.strip() != "no" or result.returncode != 1:
            raise RuntimeError("Developer global curation denial was not verified.")
    print(json.dumps({"scope": "native prompt registration/load/version persistence", "prompts": receipts}))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit("[FAIL] " + str(error))
    except Exception:
        raise SystemExit("[FAIL] Native prompt contract could not be verified; no private response was printed.")
