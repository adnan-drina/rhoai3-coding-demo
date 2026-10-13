#!/usr/bin/env python3
"""Component Applications of a regrouped stage.

A regrouped stage keeps one Argo CD Application per component in
gitops/argocd/app-of-apps/<NNN-stage>/<component>.yaml. The components of a stage are always
deployed together at one reviewed revision, in the order of their demo.rhoai.io/deploy-order
annotation; the stage's base/ kustomization renders exactly their union, so validators keep
reading one desired state.

Import it from Python (sys.path.insert(0, "<repo>/scripts/shared"); import stage_apps) or use the CLI:

  stage_apps.py names STAGE
  stage_apps.py applications STAGE --revision SHA --repo-url URL   # JSON List to `oc apply -f -`
  stage_apps.py status STAGE [--revision SHA]                      # exit 1 unless all reconciled
  stage_apps.py owner STAGE KIND NAME [NAMESPACE]                  # component that renders it
  stage_apps.py check-static STAGE                                 # disjoint components == base
"""
import argparse
import copy
import functools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "openshift-gitops"
DESTINATION = {"server": "https://kubernetes.default.svc", "namespace": NAMESPACE}
ORDER = "demo.rhoai.io/deploy-order"
# Health states besides Healthy a component may report by design, e.g. "Suspended" for a deliberately stopped model.
ACCEPTED_HEALTH = "demo.rhoai.io/accepted-health"
TRACKING = "argocd.argoproj.io/tracking-id"


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
        if not re.fullmatch(r"\d+", str(meta.get("annotations", {}).get(ORDER, ""))):
            raise RuntimeError(meta["name"] + " needs a numeric " + ORDER + " annotation")
    if len({a["metadata"]["name"] for a in apps}) != len(apps) or not apps:
        raise RuntimeError("Stage " + stage + " component names must be unique")
    return tuple(sorted(apps, key=lambda a: (int(a["metadata"]["annotations"][ORDER]), a["metadata"]["name"])))


def components(stage, root=ROOT):
    """Component Application manifests in deploy order (deep copies)."""
    return [copy.deepcopy(a) for a in _components(stage, str(root))]


def names(stage, root=ROOT):
    return [a["metadata"]["name"] for a in _components(stage, str(root))]


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
    for app in _components(stage, root):
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
    return value == "" or value.split(":", 1)[0] in names(stage, root)


def accepted_health(app):
    value = app.get("metadata", {}).get("annotations", {}).get(ACCEPTED_HEALTH, "")
    return {"Healthy"} | {h.strip() for h in value.split(",") if h.strip()}


def app_problems(app, revision=None, repo_url=None, path=None, accepted=("Healthy",)):
    """Reasons an Application is not exactly reconciled at an immutable revision; empty when ready."""
    problems = []
    meta, spec, status = app["metadata"], app["spec"], app.get("status", {})
    source = spec.get("source", {})
    name = meta.get("name", "?")
    target = source.get("targetRevision", "")
    if meta.get("ownerReferences") or meta.get("deletionTimestamp") or spec.get("sources"):
        problems.append(name + ": foreign, terminating or multi-source")
    if spec.get("project") != "rhoai-demo" or spec.get("destination") != DESTINATION:
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


def stage_problems(stage, revision=None, repo_url=None, root=ROOT):
    """Problems across every component of the stage (missing, drifted, or mixed revisions)."""
    problems, revisions = [], set()
    for desired in _components(stage, str(root)):
        name = desired["metadata"]["name"]
        app = get_application(name)
        if not app:
            problems.append(name + ": missing")
            continue
        revisions.add(app["spec"].get("source", {}).get("targetRevision"))
        problems += app_problems(app, revision, repo_url, desired["spec"]["source"]["path"], accepted_health(desired))
    if len(revisions) > 1:
        problems.append("components are at different revisions")
    return problems


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


def stamped(stage, revision, repo_url, root=ROOT):
    """Component Applications pinned to one reviewed revision and repository."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("A 40-character commit SHA is required")
    apps = components(stage, root)
    for app in apps:
        app["spec"]["source"]["repoURL"] = repo_url
        app["spec"]["source"]["targetRevision"] = revision
    return apps


def check_static(stage, root=ROOT):
    """Components render disjoint object sets whose union is exactly the stage base render."""
    owners(stage, root)  # raises on overlap
    base = {}
    apps = _components(stage, str(root))
    base_path = Path(apps[0]["spec"]["source"]["path"]).parent.parent / "base"
    for obj in render(base_path, root):
        base[suffix(obj)] = obj
    union = {}
    for app in apps:
        for obj in render(app["spec"]["source"]["path"], root):
            union[suffix(obj)] = obj
    missing, extra = sorted(set(base) - set(union)), sorted(set(union) - set(base))
    changed = sorted(k for k in set(base) & set(union) if base[k] != union[k])
    if missing or extra or changed:
        raise RuntimeError("components differ from base: missing=" + str(missing) + " extra=" + str(extra) + " changed=" + str(changed))
    return len(union)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("names").add_argument("stage")
    p = sub.add_parser("applications")
    p.add_argument("stage"); p.add_argument("--revision", required=True); p.add_argument("--repo-url", required=True)
    p = sub.add_parser("status")
    p.add_argument("stage"); p.add_argument("--revision"); p.add_argument("--repo-url")
    p = sub.add_parser("owner")
    p.add_argument("stage"); p.add_argument("kind"); p.add_argument("name"); p.add_argument("namespace", nargs="?"); p.add_argument("--group", default="")
    sub.add_parser("check-static").add_argument("stage")
    args = parser.parse_args()
    if args.command == "names":
        print("\n".join(names(args.stage)))
    elif args.command == "applications":
        print(json.dumps({"apiVersion": "v1", "kind": "List", "items": stamped(args.stage, args.revision, args.repo_url)}))
    elif args.command == "status":
        problems = stage_problems(args.stage, args.revision, args.repo_url)
        for name in names(args.stage):
            print(("FAIL " if any(p.startswith(name + ":") for p in problems) else "OK   ") + name)
        for problem in problems:
            print("  - " + problem)
        return 1 if problems else 0
    elif args.command == "owner":
        print(owner(args.stage, args.kind, args.name, args.namespace, args.group))
    elif args.command == "check-static":
        print("PASS Stage " + args.stage + ": " + str(len(names(args.stage))) + " components render " + str(check_static(args.stage)) + " objects, disjoint and equal to base")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        sys.exit("ERROR: " + str(error))
