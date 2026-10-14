#!/usr/bin/env python3
"""Move objects between Argo CD Applications without deleting or recreating any of them.

One tool for three changes to a stage's Applications (docs/OPERATIONS.md "Moving objects between Applications"):

  split    one Application becomes several components    --stage 040 --from 040-governed-models-as-a-service
  rename   an Application gets a new name                 --stage 060 --app 060-agent-console --from agent-console
  repath   an Application renders a new source.path      --stage 010            (same names, no --from)

The new Applications are the stage's manifests at --revision (gitops/argocd/app-of-apps/<NNN-stage>/*.yaml in that
commit), pinned to that commit and GIT_REPO_URL. Objects are taken over by rewriting their argocd.argoproj.io/tracking-id
annotation; the old Applications (no finalizer) are deleted without cascade at the end.

  scripts/platform/move-applications.py --stage NNN --revision SHA [--app NAME ...] [--from OLD ...] --dry-run
  scripts/platform/move-applications.py --stage NNN --revision SHA [--app NAME ...] [--from OLD ...] [--delete-leftovers]

Steps: guard and preflight (read only) -> stop automated sync on --from Applications -> apply the new Applications ->
start one sync for each that has not synced this source (carrying their own syncOptions, running any sync gate below) ->
wait until each is Synced, Healthy and successfully synced at the revision -> verify every recorded object now carries
its new owner's tracking id and the same UID -> delete the --from Applications -> optionally delete leftovers.

Safe to re-run: state (recorded UIDs) lives in ~/.local/state/rhoai3-coding-demo/move-applications/<stage>-<rev>/.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = "openshift-gitops"
TRACKING = "argocd.argoproj.io/tracking-id"
HOOK = "argocd.argoproj.io/hook"
HOOK_DELETE = "argocd.argoproj.io/hook-delete-policy"
STATE_ROOT = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "rhoai3-coding-demo/move-applications"

# Applications whose sync waits in a hook for a runtime step. The step runs once this sync's hook Job exists (so the
# sync has already applied the objects it reads and writes); running it earlier is overwritten by the sync itself.
SYNC_GATES = {
    "060-openshell-runtime": {
        "job": ("openshell", "openshell-runtime-prerequisites"),
        "command": ["python3", "stages/060-agent-runtime-and-agentops/setup-runtime.py", "--revision", "{revision}"],
    },
}


def log(message):
    print(message, flush=True)


def oc(*args, payload=None, check=True):
    result = subprocess.run(["oc", "--request-timeout=20s", *args], input=payload, capture_output=True, text=True, timeout=60)
    if check and result.returncode:
        raise RuntimeError("oc " + " ".join(args[:3]) + " failed: " + result.stderr.strip()[:300])
    return result


def get_json(*args):
    out = oc(*args, "-o", "json", "--ignore-not-found").stdout
    return json.loads(out) if out.strip() else None


def application(name):
    return get_json("get", "applications.argoproj.io", name, "-n", NS)


def guard():
    result = subprocess.run(["bash", "-c", 'REPO_ROOT="$1"; source "$1/scripts/shared/lib.sh"; load_env; check_oc_logged_in >&2; '
                             'printf "%s" "$GIT_REPO_URL"', "guard", str(ROOT)], capture_output=True, text=True)
    url = result.stdout.strip()
    # lib.sh logs to stdout; anything but a bare URL here would be written into every Application's repoURL.
    if result.returncode or not re.fullmatch(r"(https://|git@)\S+", url):
        raise RuntimeError(f"Cluster identity guard failed or GIT_REPO_URL is not a URL ({url!r}); nothing was read or changed")
    return url


def kind_arg(group, kind):
    return kind.lower() + "." + group if group else kind.lower()


def is_hook(obj):
    annotations = obj["metadata"].get("annotations", {})
    return HOOK in annotations and "BeforeHookCreation" in annotations.get(HOOK_DELETE, "")


class Plan:
    def __init__(self, args, repo_url):
        self.args, self.repo_url, self.revision = args, repo_url, args.revision
        self.state = STATE_ROOT / (args.stage + "-" + args.revision[:12])
        self.worktree = None

    # -- desired state at the revision ------------------------------------------------------------------------------
    def load(self):
        subprocess.run(["git", "-C", str(ROOT), "fetch", "-q", "origin"], check=True)
        pushed = subprocess.run(["git", "-C", str(ROOT), "branch", "-r", "--contains", self.revision], capture_output=True, text=True)
        if not pushed.stdout.strip():
            raise RuntimeError(self.revision + " is not on any pushed branch")
        self.tmp = tempfile.TemporaryDirectory()
        self.worktree = Path(self.tmp.name) / "rev"
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "-q", "--detach", str(self.worktree), self.revision], check=True)
        (self.worktree / ".env").symlink_to(ROOT / ".env")
        sys.path.insert(0, str(self.worktree / "scripts/shared"))
        import stage_apps  # the helper of the reviewed revision, not of this checkout
        self.sa = stage_apps
        desired = {a["metadata"]["name"]: a for a in stage_apps.components(self.args.stage, self.worktree, separate=True)}
        unknown = set(self.args.app or []) - set(desired)
        if unknown:
            raise RuntimeError("not Applications of Stage " + self.args.stage + " at the revision: " + ", ".join(sorted(unknown)))
        self.new = {n: a for n, a in desired.items() if not self.args.app or n in self.args.app}
        self.old = list(self.args.old or [])
        if set(self.old) & set(self.new):
            raise RuntimeError("--from names an Application that is also a target; a repath needs no --from")
        # Owner of every rendered object, with the tracking id its Application will write.
        self.owner = {}
        for name, app in self.new.items():
            for obj in self.sa.render(app["spec"]["source"]["path"], self.worktree):
                self.owner[self.tracking_suffix(obj, app)] = name

    def tracking_suffix(self, obj, app):
        api = obj["apiVersion"]
        group = api.split("/")[0] if "/" in api else ""
        meta = obj["metadata"]
        return group + "/" + obj["kind"] + ":" + (meta.get("namespace") or app["spec"]["destination"]["namespace"]) + "/" + meta["name"]

    def cleanup(self):
        if self.worktree:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(self.worktree)], capture_output=True)

    # -- the Applications to apply ----------------------------------------------------------------------------------
    def stamped(self, name):
        app = copy.deepcopy(self.new[name])
        app["spec"]["source"]["repoURL"] = self.repo_url
        app["spec"]["source"]["targetRevision"] = self.revision
        # Cluster-specific additions made at deploy time (Stage 040 Gateway hostnames, Stage 020 MachineSet replica
        # delegation) live only on the cluster: carry them over from the Application that currently owns the objects.
        source_app = application(name) or (application(self.old[0]) if len(self.old) == 1 and len(self.new) == 1 else None)
        if source_app:
            live = source_app["spec"]
            if live["source"].get("kustomize") and not app["spec"]["source"].get("kustomize"):
                app["spec"]["source"]["kustomize"] = live["source"]["kustomize"]
                log("  carry " + name + ": source.kustomize from " + source_app["metadata"]["name"])
            norm = lambda i: json.dumps({**i, "group": i.get("group", "")}, sort_keys=True)  # Argo drops group: ""
            have = [norm(i) for i in app["spec"].get("ignoreDifferences", [])]
            extra = [i for i in live.get("ignoreDifferences", []) if norm(i) not in have]
            if extra:
                app["spec"].setdefault("ignoreDifferences", []).extend(extra)
                log("  carry " + name + ": " + str(len(extra)) + " live ignoreDifferences entries from " + source_app["metadata"]["name"])
        return app

    # -- preflight --------------------------------------------------------------------------------------------------
    def preflight(self):
        self.state.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state, 0o700)
        recorded = self.state / "objects.json"
        sources = []
        for name in self.old + list(self.new):
            app = application(name)
            if not app:
                if name in self.old and not recorded.exists():
                    raise RuntimeError("--from Application " + name + " does not exist and no earlier run was recorded")
                continue
            if app["metadata"].get("finalizers"):
                raise RuntimeError(name + " has finalizers: deleting it would cascade")
            if app["metadata"].get("ownerReferences") or app["metadata"].get("deletionTimestamp"):
                raise RuntimeError(name + " is owned by something else or terminating")
            if app["spec"]["source"].get("repoURL") != self.repo_url:
                raise RuntimeError(name + " points at " + repr(app["spec"]["source"].get("repoURL")) + ", not " + self.repo_url
                                   + "; a move never changes the repository")
            sources.append(app)
        if len(self.old) > 1 or (len(self.old) == 1 and len(self.new) > 1):
            for name in self.old:
                app = application(name)
                if app and app["spec"]["source"].get("kustomize"):
                    raise RuntimeError(name + " has source.kustomize; a split cannot tell which component takes it")
        for name in self.new:
            self.render_diff(name)
        objects = {}
        old_names = set(self.old) | set(self.new)
        for app in sources:
            for res in app.get("status", {}).get("resources", []):
                group, kind, ns, obj_name = res.get("group", ""), res["kind"], res.get("namespace", ""), res["name"]
                obj = get_json("get", kind_arg(group, kind), obj_name, *(["-n", ns] if ns else []))
                if not obj:
                    continue
                tracking = obj["metadata"].get("annotations", {}).get(TRACKING, "")
                owner, _, suffix = tracking.partition(":")
                if owner not in old_names:
                    raise RuntimeError(kind + " " + ns + "/" + obj_name + " has foreign tracking id " + tracking)
                objects[tracking.split(":", 1)[1]] = {"uid": obj["metadata"]["uid"], "group": group, "kind": kind,
                                                      "namespace": ns, "name": obj_name, "hook": is_hook(obj), "from": owner}
        if recorded.exists():
            before = json.loads(recorded.read_text())
            changed = [k for k, v in objects.items() if k in before and before[k]["uid"] != v["uid"] and not v["hook"]]
            if changed:
                raise RuntimeError("object UIDs changed since the first run: " + ", ".join(changed))
            before.update({k: v for k, v in objects.items() if k not in before})
            objects = before
        if not self.args.dry_run:
            recorded.write_text(json.dumps(objects, indent=1))
        leftovers = sorted(k for k in objects if k not in self.owner)
        log("PASS " + str(len(objects)) + " live objects recorded; " + str(len(objects) - len(leftovers)) + " rendered by the new Applications"
            + ("; not rendered any more: " + ", ".join(leftovers) if leftovers else ""))
        self.objects = objects

    def render_diff(self, name):
        """Compare the new Application's render with what the Application now owning its objects renders live."""
        live = application(name) or (application(self.old[0]) if len(self.old) == 1 and len(self.new) == 1 else None)
        if not live:
            log("  " + name + ": new Application")
            return
        source = live["spec"]["source"]
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "-q", "--detach", d + "/live", source["targetRevision"]], check=True, capture_output=True)
            try:
                before = {self.sa.suffix(o): o for o in self.sa.render(source["path"], d + "/live")}
            finally:
                subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", d + "/live"], capture_output=True)
        after = {self.sa.suffix(o): o for o in self.sa.render(self.new[name]["spec"]["source"]["path"], self.worktree)}
        removed, added = sorted(set(before) - set(after)), sorted(set(after) - set(before))
        changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
        moved = source["path"] != self.new[name]["spec"]["source"]["path"]
        log("  " + name + ": " + live["metadata"]["name"] + "@" + source["targetRevision"][:8] + (" path " + source["path"] + " ->" if moved else "")
            + " " + self.new[name]["spec"]["source"]["path"] + "; render " + ("identical" if not (removed or added or changed) else
            "removed=" + str(removed) + " added=" + str(added) + " changed=" + str(changed)))

    # -- changes ----------------------------------------------------------------------------------------------------
    def stop_old(self):
        for name in self.old:
            app = application(name)
            if app and app["spec"].get("syncPolicy", {}).get("automated"):
                oc("patch", "applications.argoproj.io", name, "-n", NS, "--type", "merge", "-p", '{"spec":{"syncPolicy":{"automated":null}}}')
                log("  stopped automated sync on " + name)

    def apply_new(self):
        for name in self.ordered():
            oc("apply", "-f", "-", payload=json.dumps(self.stamped(name)))
            log("  applied " + name + " at " + self.revision[:8])

    def ordered(self):
        order = lambda n: int(self.new[n]["metadata"].get("annotations", {}).get("demo.rhoai.io/deploy-order", 10**6))
        return sorted(self.new, key=lambda n: (order(n), n))

    def start_syncs(self):
        for name in self.ordered():
            app = application(name)
            status, op = app.get("status", {}), app.get("status", {}).get("operationState", {})
            # Automated sync alone is not enough: when the render is unchanged (a re-point) Argo reports Synced at the
            # new revision without running an operation, and no hook or sync gate runs for this source.
            if app.get("operation") or op.get("phase") in ("Running", "Terminating"):
                log("  " + name + ": an operation is already running")
            elif status.get("sync", {}).get("status") == "Synced" and op.get("phase") == "Succeeded" and op.get("syncResult", {}).get("revision") == self.revision \
                    and op.get("syncResult", {}).get("source", {}).get("path") == app["spec"]["source"]["path"]:
                log("  " + name + ": already synced at " + self.revision[:8])
                continue
            else:
                # A bare operation.sync drops the Application's syncOptions (RespectIgnoreDifferences): always pass them.
                sync = {"revision": self.revision, "syncStrategy": {"hook": {}}}
                if app["spec"].get("syncPolicy", {}).get("syncOptions"):
                    sync["syncOptions"] = app["spec"]["syncPolicy"]["syncOptions"]
                patch = {"operation": {"initiatedBy": {"username": "move-applications"}, "sync": sync}}
                oc("patch", "applications.argoproj.io", name, "-n", NS, "--type", "merge", "-p", json.dumps(patch))
                log("  started sync of " + name + " at " + self.revision[:8] + " with syncOptions " + str(sync.get("syncOptions")))
            if name in SYNC_GATES:
                self.run_gate(name)

    def run_gate(self, name):
        gate = SYNC_GATES[name]
        ns, job = gate["job"]
        started = None
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            op = application(name).get("status", {}).get("operationState", {})
            if op.get("phase") == "Running" and op.get("syncResult", {}).get("revision", self.revision) == self.revision:
                started = op.get("startedAt")
            obj = get_json("get", "job", job, "-n", ns)
            if started and obj and obj["metadata"]["creationTimestamp"] >= started and not obj.get("status", {}).get("failed"):
                break
            time.sleep(3)
        else:
            raise RuntimeError(name + ": hook Job " + ns + "/" + job + " of this sync did not start within 10 minutes")
        command = [part.replace("{revision}", self.revision) for part in gate["command"]]
        log("  " + name + ": hook " + job + " is waiting; running " + " ".join(command))
        subprocess.run(command, cwd=self.worktree, check=True)

    def wait(self):
        deadline = time.monotonic() + self.args.timeout
        while True:
            problems = []
            for name in self.ordered():
                desired, app = self.new[name], application(name)
                if not app:
                    problems.append(name + ": missing")
                    continue
                self.sa.DESTINATION = desired["spec"]["destination"]  # Stage 060/010 side Applications target their own namespace
                found = self.sa.app_problems(app, self.revision, self.repo_url, desired["spec"]["source"]["path"], self.sa.accepted_health(desired))
                if "RespectIgnoreDifferences=true" not in desired["spec"].get("syncPolicy", {}).get("syncOptions", []):
                    found = [p for p in found if not p.endswith("RespectIgnoreDifferences is off")]
                problems += found
            if not problems:
                log("PASS every Application Synced and Healthy at " + self.revision[:8])
                return
            if time.monotonic() > deadline:
                raise RuntimeError("not reconciled in time (old Applications kept, automated sync off): " + "; ".join(problems))
            log("  waiting: " + "; ".join(problems)[:400])
            time.sleep(15)

    def verify(self):
        bad, hooks = [], []
        for suffix, v in self.objects.items():
            owner = self.owner.get(suffix)
            if not owner:
                continue
            obj = get_json("get", kind_arg(v["group"], v["kind"]), v["name"], *(["-n", v["namespace"]] if v["namespace"] else []))
            if not obj:
                (hooks if v["hook"] else bad).append(suffix)
                continue
            if v["hook"]:
                hooks.append(suffix)
            tracking = obj["metadata"].get("annotations", {}).get(TRACKING, "")
            if (obj["metadata"]["uid"] != v["uid"] and not v["hook"]) or tracking != owner + ":" + suffix:
                bad.append(suffix + " (tracking " + tracking + ")")
        if bad:
            raise RuntimeError("not moved cleanly: " + ", ".join(bad))
        log("PASS objects carry their new owners' tracking ids with unchanged UIDs"
            + (" (sync hooks are recreated by design: " + ", ".join(hooks) + ")" if hooks else ""))

    def delete_old(self):
        for name in self.old:
            app = application(name)
            if not app:
                continue
            if app["metadata"].get("finalizers"):
                raise RuntimeError(name + " gained a finalizer; not deleting")
            oc("delete", "applications.argoproj.io", name, "-n", NS, "--wait=true")
            log("  deleted " + name + " (no cascade)")

    def leftovers(self):
        names = set(self.old)
        for suffix, v in sorted(self.objects.items()):
            if suffix in self.owner:
                continue
            args = [kind_arg(v["group"], v["kind"]), v["name"], *(["-n", v["namespace"]] if v["namespace"] else [])]
            obj = get_json("get", *args)
            if not obj:
                continue
            owner = obj["metadata"].get("annotations", {}).get(TRACKING, "").split(":", 1)[0]
            if self.args.delete_leftovers and owner in names:
                oc("delete", *args, "--wait=true")
                log("  deleted leftover " + suffix)
            else:
                log("  leftover " + suffix + " (tracked by " + (owner or "nothing") + "); not deleted"
                    + ("" if self.args.delete_leftovers else ": re-run with --delete-leftovers after review"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", required=True, help="three-digit stage id, e.g. 040")
    parser.add_argument("--revision", required=True, help="full pushed commit SHA holding the new Application manifests")
    parser.add_argument("--app", action="append", help="limit to these Applications of the stage (default: all)")
    parser.add_argument("--from", dest="old", action="append", help="Application(s) to retire once their objects moved")
    parser.add_argument("--dry-run", action="store_true", help="read-only preflight; prints what would change")
    parser.add_argument("--delete-leftovers", action="store_true", help="delete objects no new Application renders that the --from Applications still track")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds to wait for reconciliation (default 1800)")
    args = parser.parse_args()
    if len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision):
        parser.error("--revision must be a full 40-character commit SHA")
    plan = Plan(args, guard())
    try:
        log("== Preflight: Stage " + args.stage + " at " + args.revision[:8] + (" (dry run)" if args.dry_run else ""))
        plan.load()
        log("  new: " + ", ".join(plan.ordered()) + ("; retire: " + ", ".join(plan.old) if plan.old else ""))
        plan.preflight()
        if args.dry_run:
            for name in plan.ordered():
                plan.stamped(name)
            log("DRY RUN: no changes made.")
            return 0
        log("== Stop automated sync on the Applications being retired")
        plan.stop_old()
        log("== Apply the new Applications")
        plan.apply_new()
        log("== Start one sync for Applications that have not synced this source")
        plan.start_syncs()
        log("== Wait for reconciliation")
        plan.wait()
        log("== Verify ownership and UIDs")
        plan.verify()
        log("== Retire the old Applications")
        plan.delete_old()
        log("== Objects no new Application renders")
        plan.leftovers()
        log("DONE Stage " + args.stage + " Applications at " + args.revision[:8] + ".")
        return 0
    finally:
        plan.cleanup()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit("ERROR: " + str(error))
