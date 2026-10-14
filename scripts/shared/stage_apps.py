#!/usr/bin/env python3
"""Component Applications of a regrouped stage.

A regrouped stage keeps one Argo CD Application per component in
gitops/argocd/app-of-apps/<NNN-stage>/<component>.yaml, rendering gitops/stages/<NNN-stage>/<component>/.
Components with a demo.rhoai.io/deploy-order annotation are deployed together by the stage deploy.sh at
one reviewed revision, in that order. Components with a demo.rhoai.io/deploy-script annotation instead are
deployed by that script (their own revision and procedure). The kustomization at gitops/stages/<NNN-stage>/
renders exactly the union of all components, so validators read one desired state.

Import it from Python (sys.path.insert(0, "<repo>/scripts/shared"); import stage_apps) or use the CLI:

  stage_apps.py select STAGE --ref REF --repo-url URL               # reviewed, published commit of the stage source
  stage_apps.py deploy STAGE --revision SHA --repo-url URL [--resync] # apply, sync and wait for every component
  stage_apps.py names STAGE
  stage_apps.py applications STAGE --revision SHA --repo-url URL   # JSON List to `oc apply -f -`
  stage_apps.py status STAGE [--revision SHA]                      # exit 1 unless all reconciled
  stage_apps.py owner STAGE KIND NAME [NAMESPACE]                  # component that renders it
  stage_apps.py delegated STAGE KIND NAME [NAMESPACE] [--group G]  # fields the live owner leaves to later stages
  stage_apps.py check-static STAGE                                 # disjoint components == base
"""
import argparse
import copy
import functools
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "openshift-gitops"
DESTINATION = {"server": "https://kubernetes.default.svc", "namespace": NAMESPACE}
ORDER = "demo.rhoai.io/deploy-order"
# Components deployed by their own script rather than the stage deploy.sh.
SCRIPT = "demo.rhoai.io/deploy-script"
# Health states besides Healthy a component may report by design, e.g. "Suspended" for a deliberately stopped model.
ACCEPTED_HEALTH = "demo.rhoai.io/accepted-health"
TRACKING = "argocd.argoproj.io/tracking-id"
# "sequential": deploy() applies, syncs and waits for each deploy-order group before the next (sync waves order hooks
# only inside one Application; Stage 070's later components' hooks need the earlier ones).
DEPLOY_MODE = "demo.rhoai.io/deploy-mode"


def load_yaml_stream(text):
    result = subprocess.run(["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_stream(STDIN.read).compact)"],
                            input=text, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError("YAML could not be read")
    return json.loads(result.stdout)


def stage_dir(stage, root=ROOT):
    matches = [p for p in (Path(root) / "gitops/argocd/app-of-apps").glob(stage + "-*") if p.is_dir()]
    if len(matches) != 1:
        raise RuntimeError("Stage " + stage + " has no component Application directory")
    return matches[0]


def is_regrouped(stage, root=ROOT):
    return any(p.is_dir() for p in (Path(root) / "gitops/argocd/app-of-apps").glob(stage + "-*"))


@functools.lru_cache(maxsize=None)
def _components(stage, root):
    apps = []
    for path in sorted(stage_dir(stage, root).glob("*.yaml")):
        docs = load_yaml_stream(path.read_text())
        if len(docs) != 1 or docs[0].get("kind") != "Application":
            raise RuntimeError(path.name + " must hold exactly one Application")
        apps.append(docs[0])
    for app in apps:
        meta = app["metadata"]
        if not meta["name"].startswith(stage + "-") or meta.get("labels", {}).get("demo.rhoai.io/stage") != stage:
            raise RuntimeError(meta["name"] + " must carry the stage prefix and label")
        annotations = meta.get("annotations", {})
        ordered = re.fullmatch(r"\d+", str(annotations.get(ORDER, ""))) is not None
        if ordered == bool(annotations.get(SCRIPT)):
            raise RuntimeError(meta["name"] + " needs either a numeric " + ORDER + " or a " + SCRIPT + " annotation")
    if len({a["metadata"]["name"] for a in apps}) != len(apps) or not apps:
        raise RuntimeError("Stage " + stage + " component names must be unique")
    key = lambda a: (int(a["metadata"]["annotations"].get(ORDER, 10**6)), a["metadata"]["name"])
    return tuple(sorted(apps, key=key))


def _deployed(stage, root, separate):
    return tuple(a for a in _components(stage, root) if separate or ORDER in a["metadata"].get("annotations", {}))


def components(stage, root=ROOT, separate=False):
    """Component Application manifests in deploy order (deep copies); separate=True adds script-deployed ones."""
    return [copy.deepcopy(a) for a in _deployed(stage, str(root), separate)]


def names(stage, root=ROOT, separate=False):
    return [a["metadata"]["name"] for a in _deployed(stage, str(root), separate)]


def render(path, root=ROOT):
    result = subprocess.run(["oc", "kustomize", str(Path(root) / path)], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError("kustomize build failed for " + str(path))
    return load_yaml_stream(result.stdout)


def suffix(obj, group=None):
    """Tracking-id suffix '<group>/<kind>:<namespace>/<name>'; cluster-scoped objects use the destination namespace."""
    if group is None:
        api = obj["apiVersion"]
        group = api.split("/")[0] if "/" in api else ""
    meta = obj["metadata"]
    return group + "/" + obj["kind"] + ":" + (meta.get("namespace") or NAMESPACE) + "/" + meta["name"]


@functools.lru_cache(maxsize=None)
def _owners(stage, root):
    owners = {}
    for app in _components(stage, root):  # every component, including script-deployed ones
        for obj in render(app["spec"]["source"]["path"], root):
            key = suffix(obj)
            if key in owners:
                raise RuntimeError(key + " is rendered by both " + owners[key] + " and " + app["metadata"]["name"])
            owners[key] = app["metadata"]["name"]
    return owners


def owners(stage, root=ROOT):
    """Map of tracking suffix -> component Application name for every rendered object."""
    return dict(_owners(stage, str(root)))


def owner(stage, kind, name, namespace=None, group="", root=ROOT):
    key = group + "/" + kind + ":" + (namespace or NAMESPACE) + "/" + name
    found = _owners(stage, str(root)).get(key)
    if not found:
        raise RuntimeError(key + " is not rendered by any Stage " + stage + " component")
    return found


def tracking_id(obj):
    return obj.get("metadata", {}).get("annotations", {}).get(TRACKING, "")


def expected_tracking(stage, obj, root=ROOT):
    key = suffix(obj)
    found = _owners(stage, str(root)).get(key)
    if not found:
        raise RuntimeError(key + " is not rendered by any Stage " + stage + " component")
    return found + ":" + key


def tracked(stage, obj, root=ROOT):
    """True when obj carries the exact tracking id of the component that renders it."""
    try:
        return tracking_id(obj) == expected_tracking(stage, obj, root)
    except RuntimeError:
        return False


def runtime_tracking_ok(stage, obj, root=ROOT):
    """For runtime-created objects (not rendered): untracked, or tracked by one of the stage's components."""
    value = tracking_id(obj)
    return value == "" or value.split(":", 1)[0] in names(stage, root, separate=True)


def accepted_health(app):
    value = app.get("metadata", {}).get("annotations", {}).get(ACCEPTED_HEALTH, "")
    return {"Healthy"} | {h.strip() for h in value.split(",") if h.strip()}


def app_problems(app, revision=None, repo_url=None, path=None, accepted=("Healthy",), destination=None):
    """Reasons an Application is not exactly reconciled at an immutable revision; empty when ready."""
    problems = []
    meta, spec, status = app["metadata"], app["spec"], app.get("status", {})
    source = spec.get("source", {})
    name = meta.get("name", "?")
    target = source.get("targetRevision", "")
    if meta.get("ownerReferences") or meta.get("deletionTimestamp") or spec.get("sources"):
        problems.append(name + ": foreign, terminating or multi-source")
    if spec.get("project") != "rhoai-demo" or spec.get("destination") != (destination or DESTINATION):
        problems.append(name + ": project or destination differs")
    if repo_url and source.get("repoURL") != repo_url:
        problems.append(name + ": repository differs")
    if path and source.get("path") != path:
        problems.append(name + ": source path differs")
    if not re.fullmatch(r"[0-9a-f]{40}", target) or (revision and target != revision):
        problems.append(name + ": revision is not the reviewed immutable commit")
    if "RespectIgnoreDifferences=true" not in spec.get("syncPolicy", {}).get("syncOptions", []):
        problems.append(name + ": RespectIgnoreDifferences is off")
    op = status.get("operationState", {})
    result = op.get("syncResult", {})
    if status.get("sync", {}).get("status") != "Synced" or status.get("sync", {}).get("revision") != target:
        problems.append(name + ": not Synced at its revision")
    if status.get("health", {}).get("status") not in accepted:
        problems.append(name + ": health " + str(status.get("health", {}).get("status")))
    if op.get("phase") != "Succeeded" or result.get("revision") != target or result.get("source", {}).get("path") != source.get("path"):
        problems.append(name + ": last operation is not a successful sync of this source")
    return problems


def get_application(name):
    result = subprocess.run(["oc", "--request-timeout=10s", "get", "applications.argoproj.io", name, "-n", NAMESPACE,
                             "--ignore-not-found", "-o", "json"], capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError("Application read failed")
    return json.loads(result.stdout) if result.stdout.strip() else None


def stage_problems(stage, revision=None, repo_url=None, root=ROOT, separate=False):
    """Problems across the stage's components (missing, drifted, or mixed revisions).

    separate=True also checks the components a component script deploys (all of Stages 030 and 060, two of 010);
    validation uses it, so a stage is never reported ready with nothing checked."""
    problems, revisions = [], set()
    desired_apps = _deployed(stage, str(root), separate)
    if not desired_apps:
        return ["Stage " + stage + " has no component Applications to check"]
    for desired in desired_apps:
        name = desired["metadata"]["name"]
        app = get_application(name)
        if not app:
            problems.append(name + ": missing")
            continue
        revisions.add(app["spec"].get("source", {}).get("targetRevision"))
        problems += app_problems(app, revision, repo_url, desired["spec"]["source"]["path"], accepted_health(desired),
                                 desired["spec"]["destination"])
    if len(revisions) > 1:
        problems.append("components are at different revisions")
    return problems


def sync_operation(app, initiator):
    """One hook-strategy sync of the Application's current target, carrying its own syncOptions (a bare operation.sync
    drops them, so RespectIgnoreDifferences would not apply) and its automated prune setting."""
    sync = {"revision": app["spec"]["source"]["targetRevision"], "syncStrategy": {"hook": {}}}
    policy = app["spec"].get("syncPolicy", {})
    if policy.get("syncOptions"):
        sync["syncOptions"] = policy["syncOptions"]
    if (policy.get("automated") or {}).get("prune"):
        sync["prune"] = True
    return {"operation": {"initiatedBy": {"username": initiator}, "sync": sync}}


def synced_this_source(app):
    op = app.get("status", {}).get("operationState", {})
    result, source = op.get("syncResult", {}), app["spec"]["source"]
    return (op.get("phase") == "Succeeded" and result.get("revision") == source.get("targetRevision")
            and result.get("source", {}).get("path") == source.get("path"))


def start_syncs(stage, root=ROOT, only=None, force=False, initiator="stage-deploy"):
    """Start one sync for each deployed component whose last operation is not a successful sync of its current source
    (every one with force=True, which re-runs its hooks).

    Argo CD reports Synced at a new revision without running an operation when the render is unchanged, so automated
    sync alone never runs hooks or produces the operation stage_problems() requires."""
    started = []
    for desired in _deployed(stage, str(root), bool(only)):
        name = desired["metadata"]["name"]
        if only and name not in only:
            continue
        app = get_application(name)
        if not app:
            continue
        operation = app.get("status", {}).get("operationState", {})
        if app.get("operation") or operation.get("phase") in ("Running", "Terminating"):
            continue
        if synced_this_source(app) and not force:
            continue
        result = subprocess.run(["oc", "--request-timeout=10s", "patch", "applications.argoproj.io", name, "-n", NAMESPACE,
                                 "--type", "merge", "-p", json.dumps(sync_operation(app, initiator))],
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError("Could not start a sync of " + name)
        started.append(name)
    return started


def delegated(stage, kind, name, namespace=None, group="", root=ROOT):
    """JSON pointers the live component owning an object leaves to later stages (empty unless it respects them)."""
    app = get_application(owner(stage, kind, name, namespace, group, root))
    if not app or "RespectIgnoreDifferences=true" not in app["spec"].get("syncPolicy", {}).get("syncOptions", []):
        return set()
    return {p for i in app["spec"].get("ignoreDifferences", [])
            if i.get("group", "") == group and i.get("kind") == kind and i.get("name") == name
            and i.get("namespace") == namespace for p in i.get("jsonPointers", [])}


def stage_revision(stage, root=ROOT):
    """The single revision all components are pinned to (raises when absent or mixed)."""
    revisions = set()
    for name in names(stage, root):
        app = get_application(name)
        if not app:
            raise RuntimeError(name + " is missing")
        revisions.add(app["spec"]["source"].get("targetRevision"))
    if len(revisions) != 1:
        raise RuntimeError("Stage " + stage + " components are at different revisions")
    return revisions.pop()


def scope(stage, root=ROOT):
    """Repository paths that make up a stage's deployed source."""
    name = stage_dir(stage, root).name
    return ["gitops/stages/" + name, "gitops/argocd/app-of-apps/" + name, "stages/" + name, "scripts/shared"]


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True, timeout=60).stdout


def select_revision(stage, ref, repo_url, root=ROOT, extra=()):
    """The full commit of ref, provided the stage source in the checkout is exactly that commit (no edits, nothing
    untracked) and the configured repository advertises it: only reviewed, published source is deployed."""
    commit = git(root, "rev-parse", "--verify", ref + "^{commit}").strip()
    paths = scope(stage, root) + list(extra)
    if subprocess.run(["git", "-C", str(root), "diff", "--quiet", commit, "--", *paths], timeout=60).returncode:
        raise RuntimeError("Stage " + stage + " source differs from " + commit[:12] + "; commit and publish it first")
    if git(root, "ls-files", "--others", "--exclude-standard", "--", *paths).strip():
        raise RuntimeError("Untracked Stage " + stage + " source is not in " + commit[:12])
    advertised = {line.split()[0] for line in git(root, "ls-remote", repo_url).splitlines() if line.strip()}
    if commit not in advertised:
        raise RuntimeError(commit[:12] + " is not advertised by " + repo_url + " (push it first)")
    return commit


def failed_at(app, revision):
    """True when the last operation for this revision ended Failed or Error and nothing is running: waiting longer
    cannot help (inspect the hook that failed)."""
    op = app.get("status", {}).get("operationState", {})
    op_revision = op.get("syncResult", {}).get("revision") or op.get("operation", {}).get("sync", {}).get("revision")
    return not app.get("operation") and op_revision == revision and op.get("phase") in ("Failed", "Error")


def wait_for(stage, names, revision, repo_url, timeout, root=ROOT, reader=None, clock=time.monotonic, sleep=time.sleep):
    """Wait until every named component is reconciled at revision; raise on a failed operation or the deadline."""
    reader = reader or get_application
    desired = {a["metadata"]["name"]: a for a in _deployed(stage, str(root), True)}
    deadline = clock() + timeout
    while True:
        problems = []
        for name in names:
            app = reader(name)
            if not app:
                problems.append(name + ": missing")
                continue
            if failed_at(app, revision):
                raise RuntimeError(name + ": sync at " + revision[:12] + " failed; inspect its hooks")
            want = desired[name]
            problems += app_problems(app, revision, repo_url, want["spec"]["source"]["path"], accepted_health(want),
                                     want["spec"]["destination"])
        if not problems:
            return
        if clock() >= deadline:
            raise RuntimeError("not reconciled in time: " + "; ".join(problems))
        sleep(min(10, max(0, deadline - clock())))


def deploy_groups(apps):
    """Deploy-order groups: one group per order value when any component asks for sequential deploys, else one."""
    if not any(a["metadata"].get("annotations", {}).get(DEPLOY_MODE) == "sequential" for a in apps):
        return [apps]
    groups = {}
    for app in apps:
        groups.setdefault(int(app["metadata"]["annotations"][ORDER]), []).append(app)
    return [groups[k] for k in sorted(groups)]


def deploy(stage, revision, repo_url, timeout=1800, resync=False, root=ROOT, log=print, wait=True):
    """Apply every deploy-order component pinned to revision, start a sync where its current source has not been
    synced (all of them with resync), and wait until each is reconciled; sequential groups wait in between.

    wait=False returns after the syncs started, for a stage whose own setup step must run before its components can
    become healthy (Stage 050 AI services); it then calls wait_for itself. A sequential stage always waits."""
    summary = []
    groups = deploy_groups(stamped(stage, revision, repo_url, root))
    if not wait and len(groups) > 1:
        raise RuntimeError("Stage " + stage + " deploys sequentially and must wait between its groups")
    for group in groups:
        names = [a["metadata"]["name"] for a in group]
        for app in group:
            out = subprocess.run(["oc", "--request-timeout=15s", "apply", "-f", "-"], input=json.dumps(app),
                                 capture_output=True, text=True, timeout=60)
            if out.returncode:
                raise RuntimeError("Could not apply " + app["metadata"]["name"] + ": " + out.stderr.strip()[:300])
            summary.append(out.stdout.strip())
        started = start_syncs(stage, root, only=names, force=resync)
        log("applied " + ", ".join(names) + " at " + revision[:12] + ("; started sync of " + ", ".join(started) if started else "; no sync needed"))
        if not wait:
            return summary
        wait_for(stage, names, revision, repo_url, timeout, root)
        log("PASS " + ", ".join(names) + " Synced and Healthy at " + revision[:12])
    return summary


def stamped(stage, revision, repo_url, root=ROOT):
    """Component Applications pinned to one reviewed revision and repository."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("A 40-character commit SHA is required")
    apps = components(stage, root)
    for app in apps:
        app["spec"]["source"]["repoURL"] = repo_url
        app["spec"]["source"]["targetRevision"] = revision
    return apps


def aggregate_path(stage, root=ROOT):
    """The stage's union kustomization: gitops/stages/<NNN-stage>/ (each component path is a child folder)."""
    roots = {Path(a["spec"]["source"]["path"]).parent for a in _components(stage, str(root))}
    if len(roots) != 1:
        raise RuntimeError("Stage " + stage + " components must be folders of one stage directory")
    return roots.pop()


# Cluster-scoped kinds the stages render. Any other kind must set metadata.namespace itself: the Application
# destination namespace is never relied on to place an object.
CLUSTER_SCOPED = {
    ("", "Namespace"), ("rbac.authorization.k8s.io", "ClusterRole"), ("rbac.authorization.k8s.io", "ClusterRoleBinding"),
    ("user.openshift.io", "Group"), ("operator.openshift.io", "Console"), ("operator.openshift.io", "LeaderWorkerSetOperator"),
    ("observability.openshift.io", "UIPlugin"), ("nvidia.com", "ClusterPolicy"), ("kueue.x-k8s.io", "ClusterQueue"),
    ("kueue.x-k8s.io", "ResourceFlavor"), ("datasciencecluster.opendatahub.io", "DataScienceCluster"),
    ("dscinitialization.opendatahub.io", "DSCInitialization"), ("services.platform.opendatahub.io", "Auth"),
    ("mlflow.opendatahub.io", "MLflow"), ("policy.networking.k8s.io", "AdminNetworkPolicy"),
    ("policy.networking.k8s.io", "BaselineAdminNetworkPolicy"), ("imageregistry.operator.openshift.io", "Config"),
    ("oauth.openshift.io", "OAuthClient"), ("console.openshift.io", "ConsoleLink"),
    ("admissionregistration.k8s.io", "ValidatingAdmissionPolicy"), ("admissionregistration.k8s.io", "ValidatingAdmissionPolicyBinding"),
}


def check_static(stage, root=ROOT):
    """Components render disjoint object sets whose union is exactly the stage base render; namespaced objects set
    their own namespace."""
    owners(stage, root)  # raises on overlap
    base = {}
    apps = _components(stage, str(root))
    for obj in render(aggregate_path(stage, root), root):
        base[suffix(obj)] = obj
    union = {}
    unplaced = []
    for app in apps:
        for obj in render(app["spec"]["source"]["path"], root):
            union[suffix(obj)] = obj
            api = obj["apiVersion"]
            if not obj["metadata"].get("namespace") and (api.split("/")[0] if "/" in api else "", obj["kind"]) not in CLUSTER_SCOPED:
                unplaced.append(app["metadata"]["name"] + ": " + obj["kind"] + "/" + obj["metadata"]["name"])
    if unplaced:
        raise RuntimeError("namespaced objects must set metadata.namespace (add the kind to CLUSTER_SCOPED only if it is "
                           "cluster-scoped): " + ", ".join(unplaced))
    missing, extra = sorted(set(base) - set(union)), sorted(set(union) - set(base))
    changed = sorted(k for k in set(base) & set(union) if base[k] != union[k])
    if missing or extra or changed:
        raise RuntimeError("components differ from base: missing=" + str(missing) + " extra=" + str(extra) + " changed=" + str(changed))
    return len(union)


WRITES = "demo.rhoai.io/writes-delegated"
DELEGATED_KINDS = {"DataScienceCluster", "OdhDashboardConfig"}


def check_delegations(root=ROOT):
    """Hook Jobs in later stages declare the shared-singleton fields they patch (annotation demo.rhoai.io/writes-delegated,
    "Kind:/json/pointer" entries); 010-rhoai-platform must delegate exactly those fields, each to one writer."""
    root = Path(root)
    app = load_yaml_stream((root / "gitops/argocd/app-of-apps/010-openshift-ai-platform-foundation/rhoai-platform.yaml").read_text())[0]
    delegated = {i["kind"] + ":" + p for i in app["spec"].get("ignoreDifferences", []) if i.get("kind") in DELEGATED_KINDS
                 for p in i.get("jsonPointers", [])}
    writers, problems = {}, []
    for stage_path in sorted((root / "gitops/stages").glob("0[2-9]0-*")):
        stage = stage_path.name[:3]
        if not is_regrouped(stage, root):
            continue
        for component in _components(stage, str(root)):
            for obj in render(component["spec"]["source"]["path"], root):
                if obj["kind"] != "Job":
                    continue
                name = component["metadata"]["name"] + "/Job/" + obj["metadata"]["name"]
                declared = [w.strip() for w in obj["metadata"].get("annotations", {}).get(WRITES, "").split(",") if w.strip()]
                script = json.dumps(obj["spec"]["template"]["spec"]).lower()
                if not declared and re.search(r"patch\s+(datasciencecluster|odhdashboardconfig)", script):
                    problems.append(name + " patches a shared singleton but does not declare " + WRITES)
                for field in declared:
                    writers.setdefault(field, []).append(name)
    for field, names in sorted(writers.items()):
        if field not in delegated:
            problems.append(field + " is written by " + ", ".join(names) + " but 010-rhoai-platform does not delegate it")
        if len(names) > 1:
            problems.append(field + " has several writers: " + ", ".join(names))
    for field in sorted(delegated - set(writers)):
        problems.append(field + " is delegated by 010-rhoai-platform but no hook Job declares that it writes it")
    if problems:
        raise RuntimeError("delegation mismatch: " + "; ".join(problems))
    return len(delegated)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("names").add_argument("stage")
    p = sub.add_parser("select")
    p.add_argument("stage"); p.add_argument("--ref", default="HEAD"); p.add_argument("--repo-url", required=True)
    p.add_argument("--extra", action="append", default=[], help="another path the stage deploys from (repeatable)")
    p = sub.add_parser("deploy")
    p.add_argument("stage"); p.add_argument("--revision", required=True); p.add_argument("--repo-url", required=True)
    p.add_argument("--timeout", type=int, default=1800, help="seconds per deploy group")
    p.add_argument("--resync", action="store_true", help="sync every component even if this source is already synced (re-runs hooks)")
    p.add_argument("--no-wait", action="store_true", help="return once the syncs started (run the stage's setup, then `wait`)")
    p = sub.add_parser("wait")
    p.add_argument("stage"); p.add_argument("--revision", required=True); p.add_argument("--repo-url", required=True)
    p.add_argument("--timeout", type=int, default=1800)
    p = sub.add_parser("applications")
    p.add_argument("stage"); p.add_argument("--revision", required=True); p.add_argument("--repo-url", required=True)
    p = sub.add_parser("status")
    p.add_argument("stage"); p.add_argument("--revision"); p.add_argument("--repo-url")
    p = sub.add_parser("owner")
    p.add_argument("stage"); p.add_argument("kind"); p.add_argument("name"); p.add_argument("namespace", nargs="?"); p.add_argument("--group", default="")
    p = sub.add_parser("delegated")
    p.add_argument("stage"); p.add_argument("kind"); p.add_argument("name"); p.add_argument("namespace", nargs="?"); p.add_argument("--group", default="")
    sub.add_parser("check-static").add_argument("stage")
    sub.add_parser("check-delegations")
    p = sub.add_parser("sync")
    p.add_argument("stage"); p.add_argument("--app", action="append", help="limit to these Applications (also deploy-script ones)")
    args = parser.parse_args()
    if args.command == "names":
        print("\n".join(names(args.stage)))
    elif args.command == "select":
        print(select_revision(args.stage, args.ref, args.repo_url, extra=args.extra))
    elif args.command == "deploy":
        for line in deploy(args.stage, args.revision, args.repo_url, args.timeout, args.resync,
                           log=lambda m: print(m, flush=True), wait=not args.no_wait):
            print("  " + line)
    elif args.command == "wait":
        wait_for(args.stage, names(args.stage), args.revision, args.repo_url, args.timeout)
        print("PASS Stage " + args.stage + " components Synced and Healthy at " + args.revision[:12])
    elif args.command == "applications":
        print(json.dumps({"apiVersion": "v1", "kind": "List", "items": stamped(args.stage, args.revision, args.repo_url)}))
    elif args.command == "status":
        problems = stage_problems(args.stage, args.revision, args.repo_url, separate=True)
        for name in names(args.stage, separate=True):
            print(("FAIL " if any(p.startswith(name + ":") for p in problems) else "OK   ") + name)
        for problem in problems:
            print("  - " + problem)
        return 1 if problems else 0
    elif args.command == "owner":
        print(owner(args.stage, args.kind, args.name, args.namespace, args.group))
    elif args.command == "delegated":
        print("\n".join(sorted(delegated(args.stage, args.kind, args.name, args.namespace, args.group))))
    elif args.command == "check-delegations":
        print("PASS " + str(check_delegations()) + " Stage 010 delegated fields, each written by exactly one declared hook Job")
    elif args.command == "sync":
        for name in start_syncs(args.stage, only=args.app):
            print("started sync of " + name)
    elif args.command == "check-static":
        print("PASS Stage " + args.stage + ": " + str(len(names(args.stage, separate=True))) + " components render " + str(check_static(args.stage)) + " objects, disjoint and equal to " + str(aggregate_path(args.stage)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        sys.exit("ERROR: " + str(error))
