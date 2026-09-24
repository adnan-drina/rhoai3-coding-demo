#!/usr/bin/env python3
"""Check factory reuse links; --live also probes installed admission with dry runs.

No workspace, pod, or migration task is created. The cluster guard is run for
each API invocation; admission is tested by the API server, not a CEL imitation.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
POLICY = "migration-workspace-run-name"


def check_links() -> None:
    templates = ROOT / "gitops/stages/050-advanced-app-platform/base/rhdh/templates"
    for name in ("app-migration", "agentic-quarkus-scaffold"):
        text = (templates / name / "template.yaml").read_text()
        link = re.search(r"(?m)^\s+devspacesUrl: (.+)$", text).group(1)
        # Exercise the emitted URL, leaving the independently supplied host out.
        target = link.rsplit("/#", 1)[1].replace("${{ parameters.name }}", "creation-probe")
        repo, query = target.split("?", 1)
        params = parse_qs(query, keep_blank_values=True)
        assert repo == "https://github.com/adnan-drina/creation-probe", repo
        assert params == {"revision": ["main"], "existing": ["creation-probe"]}, params
        if name == "app-migration":
            devfile = (templates / name / "skeleton/devfile.yaml").read_text()
            assert re.search(r"checkoutFrom:\s+revision: main\b", devfile)
        print(f"PASS: {name} reopens its named main workspace")


def oc(*args: str, body: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", "-c",
         'source "$1/scripts/lib.sh"\nload_env\ncheck_oc_logged_in >&2\n'
         'shift\nexec oc --request-timeout=10s "$@"',
         "workspace-creation-check", str(ROOT), *args],
        input=json.dumps(body) if body is not None else None,
        text=True, capture_output=True, timeout=35,
    )


def check_live(namespace: str) -> None:
    for kind in ("validatingadmissionpolicy", "validatingadmissionpolicybinding"):
        result = oc("get", kind, POLICY, "-o", "json")
        assert result.returncode == 0, result.stderr
        resource = json.loads(result.stdout)
        if kind == "validatingadmissionpolicy":
            assert resource["spec"]["failurePolicy"] == "Fail"
            rules = resource["spec"]["matchConstraints"]["resourceRules"]
            assert len(rules) == 1 and rules[0]["operations"] == ["CREATE"]
            assert not resource.get("status", {}).get("typeChecking", {}).get("expressionWarnings"), resource.get("status")
        else:
            assert resource["spec"]["policyName"] == POLICY
            assert resource["spec"]["validationActions"] == ["Deny"]

    run = "migration-creation-admission-probe"
    base = {
        "apiVersion": "workspace.devfile.io/v1alpha2", "kind": "DevWorkspace",
        "metadata": {"name": run, "namespace": namespace},
        "spec": {"started": False, "template": {"components": [{
            "name": "development-tooling", "container": {
                "image": "registry.access.redhat.com/ubi9/ubi-minimal:latest",
                "env": [{"name": "MIGRATION_RUN_NAME", "value": run}],
            },
        }]}},
    }
    cases = []
    cases.append(("canonical name", copy.deepcopy(base), True))
    suffix = copy.deepcopy(base)
    suffix["metadata"]["name"] += "-mdmn"
    cases.append(("suffixed duplicate", suffix, False))
    missing = copy.deepcopy(base)
    del missing["spec"]["template"]["components"][0]["container"]["env"][0]["value"]
    cases.append(("missing run value", missing, False))
    empty = copy.deepcopy(base)
    empty["spec"]["template"]["components"][0]["container"]["env"][0]["value"] = ""
    cases.append(("empty run value", empty, False))
    conflict = copy.deepcopy(base)
    conflict["spec"]["template"]["components"].append({
        "name": "another-container", "container": {
            "image": "registry.access.redhat.com/ubi9/ubi-minimal:latest",
            "env": [{"name": "MIGRATION_RUN_NAME", "value": "another-run"}],
        },
    })
    cases.append(("conflicting run declarations", conflict, False))
    generated = copy.deepcopy(base)
    del generated["metadata"]["name"]
    generated["metadata"]["generateName"] = run + "-"
    cases.append(("generated suffix", generated, False))
    ordinary = copy.deepcopy(suffix)
    del ordinary["spec"]["template"]["components"][0]["container"]["env"]
    cases.append(("non-migration workspace", ordinary, True))

    for label, workspace, allowed in cases:
        result = oc("create", "--dry-run=server", "-n", namespace, "-f", "-", "-o", "json", body=workspace)
        if allowed:
            assert result.returncode == 0, f"{label}: {result.stderr}"
        else:
            assert result.returncode != 0 and POLICY in result.stderr, f"{label}: {result.stderr}"
            assert "Migration workspace name must equal MIGRATION_RUN_NAME" in result.stderr, result.stderr
        print(f"PASS: {label} {'allowed' if allowed else 'refused'} by server dry run")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--namespace", default="wksp-ai-developer")
    args = parser.parse_args()
    check_links()
    if args.live:
        check_live(args.namespace)
