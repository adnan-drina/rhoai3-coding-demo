#!/usr/bin/env python3
"""Land-time counterexamples for migration-worker permissions.

The 2026-09-22 isolation demonstration failed workspace_identity: generated
workspace service accounts bound to operator-owned devworkspace-default-role
could read another run's Secret. DWO 0.43.0 still does that bind for any
name returned by common.ServiceAccountName(), including a DWOC
serviceAccountName used with disableCreation (SyncRBAC runs first). These
checks require the platform repair to create a per-run Role that is not that
default role, select it with destfile pod-overrides, and leave the operator
Role unpatched.

Not a live can-i qualification.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASE = REPO / "gitops" / "stages" / "050-advanced-app-platform" / "base"
TASK = BASE / "pipelines" / "build" / "task-provision-migration-run.yaml"
RBAC = BASE / "devspaces" / "migration-run-resources-rbac.yaml"
SKELETON = BASE / "rhdh" / "templates" / "app-migration" / "skeleton" / "devfile.yaml"
PATCH = REPO / "scripts" / "patch-workspace-maas-route.sh"

FORBIDDEN_WORKER_RESOURCES = {
    "secrets",
    "pods",
    "pods/exec",
    "serviceaccounts",
    "roles",
    "rolebindings",
    "devworkspaces",
    "devworkspaceroutings",
    "devworkspacetemplates",
    "devworkspaceoperatorconfigs",
}
FORBIDDEN_WORKER_VERBS = {"create", "patch", "update", "delete", "bind", "escalate"}

failures: list[str] = []


def fail(what: str) -> None:
    failures.append(what)


def need(cond: bool, what: str) -> None:
    if not cond:
        fail(what)


def text(path: Path) -> str:
    if not path.is_file():
        fail("%s is missing; the check that needs it cannot pass vacuously" % path.relative_to(REPO))
        return ""
    return path.read_text(encoding="utf-8")


def uncommented(path: Path) -> str:
    return re.sub(r"(?m)^\s*#.*$", "", text(path))


def documents(path: Path) -> list[str]:
    return [d for d in uncommented(path).split("\n---\n") if d.strip()]


def worker_role_block(task: str) -> str:
    blocks = re.findall(r"kind: Role\n(?:.*\n)*?        YAML", task)
    for block in blocks:
        if "migration-worker" in block and "devspace-ai-tools-init" in block:
            return block
    return ""


def main() -> int:
    task = uncommented(TASK)
    rbac = uncommented(RBAC)
    destfile = uncommented(SKELETON)
    gitops = "\n".join(
        re.sub(r"(?m)^\s*#.*$", "", p.read_text(encoding="utf-8"))
        for p in BASE.rglob("*.yaml")
    )

    need("kind: ServiceAccount" in task and "${RUN}-worker" in task,
         "provisioning does not create ServiceAccount ${RUN}-worker")
    need("pod-overrides:" in destfile and "serviceAccountName: ${{ values.name }}-worker" in destfile,
         "the factory destfile does not select ${{ values.name }}-worker via pod-overrides")
    need("disableCreation" not in destfile,
         "the factory destfile sets DWO disableCreation; that path binds the named SA to "
         "devworkspace-default-role")
    need("controller.devfile.io/devworkspace-config" not in destfile,
         "the factory destfile stamps a per-workspace DWOC; Che already injects "
         "openshift-devspaces/devworkspace-config, and a named serviceAccount there is "
         "bound to the default role")
    raw_destfile = text(SKELETON)
    need("rhoai3-bind-pod-kubeconfig:start" in raw_destfile and "rhoai3-bind-pod-kubeconfig:end" in raw_destfile,
         "postStart does not mark the replacement kubeconfig bind for extraction")
    bind = raw_destfile.split("rhoai3-bind-pod-kubeconfig:start", 1)[1].split(
        "rhoai3-bind-pod-kubeconfig:end", 1)[0]
    need("oc login" not in destfile,
         "the factory destfile still calls oc login, which merges leftover users and contexts")
    need("if [ ! -f /home/user/.kube/config ]" not in destfile,
         "postStart keeps a leftover kubeconfig; a previous identity's token would survive on the PVC")
    need("tokenFile" in bind,
         "postStart does not write a replacement kubeconfig bound to the projected tokenFile")
    need("|| true" not in bind,
         "kubeconfig bind still swallows failure and can print success for an older identity")
    need("missing projected ServiceAccount token" in bind,
         "a missing projected token does not refuse dest-init")
    need("--type merge" in text(PATCH) and "replace" not in uncommented(PATCH).lower(),
         "the MaaS hostAlias patch is not a merge; replacing pod-overrides would drop the worker SA")

    role = worker_role_block(task)
    need(bool(role), "the generated worker Role was not found in the provisioning Task")
    resources = set(re.findall(r'resources:\s*\[([^\]]*)\]', role))
    named = set()
    for raw in resources:
        named.update(item.strip().strip('"').strip("'") for item in raw.split(",") if item.strip())
    need(named <= {"configmaps", "securitycontextconstraints"},
         "the worker Role names resources %s beyond the minimum ConfigMap get and container-build SCC use"
         % sorted(named))
    for forbidden in FORBIDDEN_WORKER_RESOURCES:
        need(forbidden not in role,
             "the worker Role mentions %s; workers must not mutate receipts, RBAC, DevWorkspaces, "
             "Secrets or pods" % forbidden)
    for verb in FORBIDDEN_WORKER_VERBS:
        need(("verbs: [\"%s\"]" % verb) not in role and ("verbs: [%s]" % verb) not in role,
             "the worker Role grants %s" % verb)
    need('resourceNames: ["devspace-ai-tools-init"]' in role and 'verbs: ["get"]' in role,
         "the worker Role does not grant get on ConfigMap devspace-ai-tools-init, which postStart "
         "fetches when the volume is empty")
    need('resourceNames: ["container-build"]' in role and 'verbs: ["use"]' in role,
         "the worker Role does not grant use of SCC container-build; Che injects that SCC onto "
         "workspaces and DWO binds it only to the generated SA")

    need("kind: ClusterRole" in rbac and "migration-run-provisioner-container-build" in rbac,
         "the provisioner cannot copy SCC use onto the worker Role without already having that use")
    need('resourceNames: ["container-build"]' in rbac,
         "the provisioner's cluster permission is not limited to the named container-build SCC")
    need("resources: [\"serviceaccounts\"]" in rbac and "resources: [\"roles\", \"rolebindings\"]" in rbac,
         "the provisioner Role cannot create the per-run worker identity")
    provisioner_role = next((d for d in documents(RBAC) if "name: migration-run-resource-manager" in d and "kind: Role" in d), "")
    need("resourceNames:" not in provisioner_role,
         "the provisioner Role lists resourceNames; its authorization is namespace-wide for those kinds, "
         "and run labels only constrain the Task script")
    sa_doc = next((d for d in documents(RBAC) if "kind: ServiceAccount" in d), "")
    need("namespace: app-platform-build" in sa_doc,
         "the provisioner ServiceAccount is not confined to app-platform-build")
    need("devworkspace-default-role" not in gitops and "kind: Role\nmetadata:\n  name: devworkspace-default-role" not in gitops.replace("\r", ""),
         "GitOps patches operator-owned devworkspace-default-role")
    need("name: spring-petclinic-rest-legacy-v10" not in gitops,
         "GitOps names the existing v10 workspace; this repair must not touch that object")

    if failures:
        for item in failures:
            print("FAIL: %s" % item, file=sys.stderr)
        return 1
    print("OK: worker permission invariants (pod-overrides SA, minimum Role, default-role unpatched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
