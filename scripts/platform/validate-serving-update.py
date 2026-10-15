#!/usr/bin/env python3
"""Read-only native prerequisites for an already installed serving stage.

Parked capacity is not an update prerequisite; broken scheduled workloads are.
First-time stage installation retains its complete infrastructure validation.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
import stage_apps  # noqa: E402

STAGES = ("030", "040")  # checked through their component Applications
ENV = dict(os.environ)


def get(kind, name, namespace=None):
    args = ["oc", "--request-timeout=10s", "get", kind, name, "-o", "json"]
    if namespace:
        args += ["-n", namespace]
    result = subprocess.run(args, env=ENV, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Native update prerequisite API unavailable: " + kind + " " + (namespace + "/" if namespace else "") + name)
    return json.loads(result.stdout)


def validate(stage):
    problems = stage_apps.stage_problems(stage, repo_url=ENV["GIT_REPO_URL"], separate=True)
    assert not problems, "Existing serving source must be reconciled before update: " + "; ".join(problems)
    validate_platform()


def validate_platform():
    dsc = get("datasciencecluster", "default-dsc")
    assert dsc["spec"]["components"]["kserve"]["managementState"] == "Managed" and any(c.get("type") == "KserveReady" and c.get("status") == "True" for c in dsc["status"].get("conditions", [])), "Native KServe is not ready"
    policy = get("clusterpolicy", "gpu-cluster-policy")
    assert policy["status"].get("state") == "ready", "Native GPU ClusterPolicy is not ready"
    # The Subscription updates automatically within the reviewed v26.7 channel, so read the installed CSV from it.
    subscription = get("subscription", "gpu-operator-certified", "nvidia-gpu-operator")
    installed = subscription.get("status", {}).get("installedCSV", "")
    assert subscription["spec"].get("channel") == "v26.7" and installed.startswith("gpu-operator-certified.v26.7."), "Reviewed GPU operator channel/version differs"
    csv = get("clusterserviceversion", installed, "nvidia-gpu-operator")
    assert csv["status"].get("phase") == "Succeeded", "Reviewed GPU operator is not installed"
    for workload in ["nvidia-operator-validator", "nvidia-dcgm-exporter"]:
        ds = get("daemonset", workload, "nvidia-gpu-operator")
        current = ds["status"]
        count = current.get("desiredNumberScheduled", 0)
        assert any(o.get("uid") == policy["metadata"]["uid"] and o.get("controller") for o in ds["metadata"].get("ownerReferences", [])), "Native GPU workload owner differs"
        assert current.get("observedGeneration") == ds["metadata"]["generation"] and current.get("numberReady", 0) == count and current.get("updatedNumberScheduled", 0) == count, "Scheduled native GPU workload is not current/ready"
    print("PASS Existing native serving/GPU installation and scheduled workloads; parked capacity is not an update prerequisite")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    guard = 'set -euo pipefail; set +x; source "$1/scripts/shared/lib.sh"; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env >/dev/null; check_oc_logged_in >/dev/null; python3 -c "$2"'
    code = 'import os,json; print(json.dumps({k:os.environ[k] for k in ["KUBECONFIG","PATH","GIT_REPO_URL"] if k in os.environ}))'
    checked = subprocess.run(["/bin/bash", "-c", guard, "guard", str(root), code], capture_output=True, text=True, timeout=30)
    if checked.returncode:
        raise RuntimeError("Project cluster identity guard failed")
    ENV.update(json.loads(checked.stdout))
    os.environ.update(ENV)  # stage_apps reads Applications with the guarded environment
    validate(args.stage)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, AssertionError, KeyError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit("[FAIL] " + str(error))
