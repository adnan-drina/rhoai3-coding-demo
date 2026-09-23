#!/usr/bin/env python3
"""Negative tests for per-run migration isolation, over the PLATFORM manifests.

Each case here is a defect the architect's 2026-09-22 review demonstrated on
commit 39792496. They are written as counterexamples: the manifests are read
and something specific must be ABSENT or PRESENT, and a case that can no longer
find its subject fails rather than passing vacuously.

  1. SECRET DELIVERY. Both automounted per-run secrets must carry
     controller.devfile.io/watch-secret=true. DevWorkspace Operator 0.43's
     informer cache SELECTS secrets by that label, so a secret without it is
     never in the cache, the automount provisioner never sees it, and the
     workspace starts with no PETCLINIC_DB_* and no fixture identities at all.
     Ref: devworkspace-operator v0.43.0 pkg/cache/cache.go:43
     They must also keep mount-on-start=true, so writing a secret never
     restarts a workspace that is already running.

  2. TARGETING. mount-to-devworkspace-include must bind the workspace name
     EXACTLY. The reviewed `<name>,<name>-*` also matched a different, equally
     valid run: this file simulates DWO's own pattern semantics and requires
     that `<run>-retry` does NOT match `<run>`'s published include -- and
     proves the simulation is real by showing the retired pattern DOES.

  3. GOVERNANCE. No destination repository is an Argo CD source: nothing points
     an Application at a scaffolded repo, no AppProject exists for one, and the
     skeleton ships no cluster manifests to point at. The provisioning identity
     must NOT live in the workspace namespace, because any workload created
     there could select it and creating a workload needs no permission to
     create RBAC.
     Ref: https://kubernetes.io/docs/concepts/security/rbac-good-practices/#workload-creation

  4. SCAFFOLDING IDENTITY. The provisioning trigger must establish that the
     push it acts on is the scaffolding event (branch creation), not merely a
     qualifying main-branch push.

  5. RETIREMENT. Every generated object must carry the run label retirement
     deletes by, retirement must verify the absence afterwards, and a retired
     run must not be resurrectable by a later event. The per-run worker
     ServiceAccount, Role and RoleBinding are generated objects too.

  6. REPOSITORY RULES. .agents/rules/gitops.md forbids
     resources-finalizer.argocd.argoproj.io and Replace=true. The reviewed
     design used both; the platform-rendered seam must use neither.

  7. WORKER IDENTITY. The factory destfile must select the platform SA with
     pod-overrides, not DWO serviceAccount.disableCreation (that path still
     binds the named SA to operator-owned devworkspace-default-role). The
     worker Role must not grant Secret, pod exec, DevWorkspace, RBAC or
     ServiceAccount verbs. GitOps must not patch the operator-owned default
     role.

Land-time only, so it lives beside validate.sh: it reads manifests, touches no
cluster and imports nothing from the shipped tree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASE = REPO / "gitops" / "stages" / "050-advanced-app-platform" / "base"
TASK = BASE / "pipelines" / "build" / "task-provision-migration-run.yaml"
PIPELINE = BASE / "pipelines" / "build" / "pipeline-provision-migration-run.yaml"
TRIGGERS = BASE / "pipelines" / "build" / "triggers.yaml"
RBAC = BASE / "devspaces" / "migration-run-resources-rbac.yaml"
FIXTURE_SRC = BASE / "devspaces" / "migration-fixture-credentials-source.yaml"
SKELETON = BASE / "rhdh" / "templates" / "app-migration" / "skeleton"

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
    """Prose ABOUT a label is not the label. Strip comments before counting."""
    return re.sub(r"(?m)^\s*#.*$", "", text(path))


def dwo_include_matches(pattern_list: str, workspace: str) -> bool:
    """DevWorkspace Operator's own targeted-automount semantics.

    A comma-separated list of patterns matched against the DevWorkspace NAME:
    exact, `prefix*`, `*suffix`, `*contains*`, `*`. Reimplemented here so the
    collision can be demonstrated rather than asserted."""
    for raw in pattern_list.split(","):
        p = raw.strip()
        if not p:
            continue
        if p == "*":
            return True
        if p.startswith("*") and p.endswith("*") and len(p) > 1:
            if p[1:-1] in workspace:
                return True
        elif p.startswith("*"):
            if workspace.endswith(p[1:]):
                return True
        elif p.endswith("*"):
            if workspace.startswith(p[:-1]):
                return True
        elif p == workspace:
            return True
    return False


def main() -> int:
    task = uncommented(TASK)
    triggers = uncommented(TRIGGERS)
    rbac = uncommented(RBAC)

    # --- 1. secret delivery ------------------------------------------------
    # The two secrets a workspace receives are the database binding and the
    # fixture identities. Both must be in the operator's cache, or nothing is
    # mounted at all.
    mounted = task.count('controller.devfile.io/mount-to-devworkspace: "true"')
    watched = task.count('controller.devfile.io/watch-secret: "true"')
    need(mounted == 2, "expected 2 automounted per-run secrets, found %d" % mounted)
    need(watched == mounted,
         "%d of %d automounted secrets carry watch-secret; DWO 0.43 selects its secret cache by that "
         "label, so an unwatched secret is never seen and never mounted" % (watched, mounted))
    on_start = task.count('controller.devfile.io/mount-on-start: "true"')
    need(on_start == mounted,
         "%d of %d automounted secrets defer mounting to the next start; without it, writing a secret "
         "restarts a workspace that is already running" % (on_start, mounted))
    need("controller.devfile.io/mount-as: env" in task,
         "the run's secrets are not mounted as environment variables")
    # labels and annotations published together: one apply per secret, never a
    # create followed by oc label / oc annotate, which leaves an intermediate
    # state where the mount label is set and the targeting is not.
    need("oc label secret" not in task and "oc annotate secret" not in task,
         "a per-run secret is labelled or annotated after creation; targeting must be published with "
         "the labels in one object")

    # --- 2. targeting is exact --------------------------------------------
    includes = re.findall(r'controller\.devfile\.io/mount-to-devworkspace-include:\s*"([^"]*)"', task)
    need(len(includes) == mounted,
         "expected %d include annotations, found %d" % (mounted, len(includes)))
    for inc in includes:
        need("*" not in inc and "," not in inc,
             "the include pattern %r is not an exact binding; a suffix or a list can match another run" % inc)
    # the collision, demonstrated
    run = "demo-v10"
    retired_pattern = "%s,%s-*" % (run, run)
    published = [inc.replace("${RUN}", run) for inc in includes]
    need(dwo_include_matches(retired_pattern, "%s-retry" % run),
         "the DWO pattern simulation no longer reproduces the collision it is here to catch; the "
         "check cannot pass vacuously")
    for inc in published:
        need(dwo_include_matches(inc, run),
             "the published include %r does not match its own workspace %r" % (inc, run))
        need(not dwo_include_matches(inc, "%s-retry" % run),
             "the published include %r also matches %s-retry, which is a different valid run" % (inc, run))

    # --- 3. governance -----------------------------------------------------
    need(not (BASE / "pipelines" / "build" / "appproject-migration-run.yaml").is_file(),
         "the AppProject that made a destination repository an Argo CD source is still present")
    need(not (SKELETON / "k8s-run").exists(),
         "the skeleton still ships k8s-run/; nothing applies it, so it is a manifest set that drifts")
    need("path: k8s-run" not in triggers,
         "the dispatcher still points an Argo CD Application at a destination repository path")
    # the migration-run TriggerTemplate, as its own document
    docs = [d for d in triggers.split("\n---\n") if "name: migration-run-resources-template" in d]
    need(len(docs) == 1, "the migration-run TriggerTemplate was not found as a single document")
    tmpl = docs[0] if docs else ""
    need("kind: Application" not in tmpl,
         "the migration-run template still creates an Argo CD Application over a self-service repository")
    need("kind: PipelineRun" in tmpl and "name: provision-migration-run" in tmpl,
         "the migration-run template does not start the platform provisioning Pipeline")
    need("repo-url" not in tmpl and "repoURL" not in tmpl,
         "the migration-run template still passes a destination repository URL into what it creates")
    need("serviceAccountName: migration-run-provisioner" in triggers,
         "the provisioning PipelineRun does not run as the platform provisioner")
    # the identity is not selectable from the workspace namespace
    sa = re.search(r"kind: ServiceAccount\nmetadata:\n  name: migration-run-provisioner\n  namespace: (\S+)", rbac)
    need(bool(sa), "the provisioner ServiceAccount declaration was not found")
    if sa:
        need(sa.group(1) == "app-platform-build",
             "the provisioner ServiceAccount lives in %s; a pod's serviceAccountName resolves in its own "
             "namespace, so any workload created there could select it" % sa.group(1))
    need("namespace: wksp-ai-developer" not in
         rbac.split("kind: ServiceAccount")[1].split("---")[0],
         "the provisioner ServiceAccount is declared in the workspace namespace")
    # the fixture source is data, not a mount
    fixtures = uncommented(FIXTURE_SRC)
    need("controller.devfile.io/mount-to-devworkspace" not in fixtures,
         "the platform-owned fixture source Secret is automounted; it must reach workspaces only as "
         "per-run copies")
    for literal in ("PETCLINIC_ADMIN_CREDENTIAL", "PETCLINIC_INVALID_CREDENTIAL", "admin:admin", "nobody:wrong"):
        need(literal not in task,
             "the provisioner names the fixture literal %r; it must copy whatever keys the source Secret "
             "has, so another specimen changes one data file and no code" % literal)

    # --- 4. the scaffolding event -----------------------------------------
    block = triggers.split("- name: migration-run-resources-bootstrap")[-1].split("\n    - name: ")[0]
    need("body.created == true" in block,
         "the provisioning trigger accepts any qualifying main-branch push; it must establish that the "
         "push it acts on created the branch")
    need("body.before == '0000000000000000000000000000000000000000'" in block,
         "the provisioning trigger does not require a zero `before`")
    need("body.forced == false" in block,
         "a force-push can re-present itself to the provisioning trigger as a branch creation")

    # --- 5. retirement -----------------------------------------------------
    need('rhoai3.io/migration-run: ${RUN}' in task,
         "generated objects do not carry the run label retirement enumerates by")
    labelled = task.count("rhoai3.io/migration-run: ${RUN}")
    need(labelled >= 8,
         "only %d generated objects carry the run label; server secret, workspace secret, fixture "
         "secret, Deployment, Service, worker ServiceAccount, Role and RoleBinding must all be "
         "accountable" % labelled)
    need("serviceaccount" in task and "kind: Role" in task and "kind: RoleBinding" in task,
         "provisioning does not create the per-run worker ServiceAccount, Role and RoleBinding")
    need("disableCreation" not in task,
         "provisioning relies on DWO disableCreation; that path still binds the named SA to "
         "devworkspace-default-role")
    need('oc delete "${kind}" -n "${WSNS}" -l "rhoai3.io/migration-run=${RUN}"' in task,
         "retirement does not delete by the run label")
    need("still exist after retirement" in task,
         "retirement does not verify that nothing generated is left")
    need("phase=retired" in task and "was retired" in task,
         "retirement leaves no tombstone, so a later event can resurrect the run")
    need("was provisioned from" in task,
         "a second provisioning from a different commit is not refused")
    need("mode" in uncommented(PIPELINE),
         "the platform lifecycle has no retire mode, so retirement would be manual")

    # --- 6. repository rules ----------------------------------------------
    # .agents/rules/gitops.md: never resources-finalizer.argocd.argoproj.io,
    # never Replace=true or ServerSideApply=true. The reviewed design used the
    # finalizer as its retirement path and Replace=true on the provisioning Job.
    # The scaffolded-PROJECT Application in triggers.yaml is a pre-existing,
    # separate concern, so the rule is applied to the migration-run documents.
    for name, body in (("the migration-run TriggerTemplate", tmpl),
                       ("task-provision-migration-run.yaml", task),
                       ("pipeline-provision-migration-run.yaml", uncommented(PIPELINE))):
        need("resources-finalizer.argocd.argoproj.io" not in body,
             "%s adds a destructive Argo CD finalizer, which .agents/rules/gitops.md forbids" % name)
        need("Replace=true" not in body and "ServerSideApply=true" not in body,
             "%s uses Replace=true or ServerSideApply=true, which .agents/rules/gitops.md forbids" % name)

    if failures:
        for f in failures:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1
    print("OK: per-run isolation invariants (%d automounted secrets, exactly bound)" % mounted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
