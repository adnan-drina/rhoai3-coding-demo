#!/usr/bin/env python3
"""The migration-run provisioner's run-control record (B8 / R3), run locally.

The real task script (extracted verbatim from task-provision-migration-run.yaml)
runs against a fake `oc` that records every object applied. It proves:
  * the positive path: <run>-run-control is written with contract.json (run,
    scaffolding commit, activation, authorization) and profile.json (the
    platform's model profile table, verbatim), mounted as a FILE volume at
    /etc/rhoai3/run-control, into exactly this workspace, on start only
  * the harness reader accepts exactly what the platform wrote (the golden
    run_control.contract against a destination whose initial commit is that
    scaffolding commit)
  * a re-delivered event for the same commit leaves the record untouched; an
    event for another commit, and a missing profile table, are refused
  * the worker identity the task creates has no write verb at all -- it can
    read devspace-ai-tools-init and use one SCC, nothing else
Run under two run names.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE / "task-provision-migration-run.yaml"
REPO = HERE.parents[5]
PROFILES = HERE.parents[1] / "devspaces" / "model-profiles.json"
GOLDEN_LIB = REPO / "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/lib"

FAKE_OC = r'''#!/usr/bin/env python3
import json, os, sys
state = os.environ["FAKE_STATE"]
args = [a for a in sys.argv[1:] if not a.startswith("--request-timeout")]
db = json.load(open(state)) if os.path.exists(state) else {"objects": {}, "applied": []}
def save(): json.dump(db, open(state, "w"))
def arg(flag):
    return args[args.index(flag) + 1] if flag in args else ""
if args[:2] == ["create", "configmap"] and "--dry-run=client" in args:
    name = args[2]
    data = {a.split("=", 1)[0][len("--from-literal="):]: a.split("=", 1)[1] for a in args if a.startswith("--from-literal=")}
    print(json.dumps({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name}, "data": data}))
elif args[:2] == ["create", "configmap"]:
    name = args[2]
    if ("ConfigMap", name) in [tuple(k.split("/", 1)) for k in db["objects"]]:
        print("AlreadyExists", file=sys.stderr); sys.exit(1)
    db["objects"]["ConfigMap/" + name] = {"data": {}}; save()
elif args[:2] == ["apply", "-f"]:
    text = sys.stdin.read()
    db["applied"].append(text)
    for doc in text.split("\n---\n"):
        kind = next((l.split(":", 1)[1].strip() for l in doc.splitlines() if l.startswith("kind:")), "")
        name = next((l.split(":", 1)[1].strip() for l in doc.splitlines() if l.strip().startswith("name:")), "")
        if kind and name:
            db["objects"][kind + "/" + name] = {"text": doc}
    save()
elif args[:2] == ["get", "configmap"]:
    name = args[2]
    if name == "migration-model-profiles":
        if os.environ.get("FAKE_NO_PROFILES"): sys.exit(1)
        print(open(os.environ["FAKE_PROFILES"]).read(), end="")
    elif name.endswith("-run-control"):
        rec = db["objects"].get("ConfigMap/" + name)
        if rec and "text" in rec:
            m = [l for l in rec["text"].splitlines() if l.strip().startswith("contract.json:")]
            print(json.loads(m[0].split(":", 1)[1].strip()) if m else "", end="")
        elif os.environ.get("FAKE_FOREIGN_CONTROL") and name.endswith("-run-control"):
            print(json.dumps({"scaffold_commit": "f" * 40}), end="")
    # receipts, locks and others: absent
elif args[:2] == ["get", "secret"]:
    if "go-template={{range $k,$v := .data}}{{$k}}{{\"\\n\"}}{{end}}" in args or any("range $k" in a for a in args):
        print("FIXTURE_USER\nFIXTURE_PASSWORD")
    elif any("index .data" in a for a in args):
        print("dmFsdWU=", end="")
elif args[:2] == ["delete", "configmap"]:
    db["objects"].pop("ConfigMap/" + args[2], None); save()
elif args[:1] in (["delete"], ["label"]):
    pass
sys.exit(0)
'''


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _script() -> str:
    text = TASK.read_text(encoding="utf-8")
    body = text.split("      script: |\n", 1)[1].split("\n      # tekton.dev/v1 renamed", 1)[0]
    return "\n".join(l[8:] if l.startswith("        ") else l.strip() for l in body.splitlines()) + "\n"


def _provision(td: Path, run: str, commit: str, **env_extra: str) -> tuple[int, str, dict]:
    bindir = td / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "oc").write_text(FAKE_OC, encoding="utf-8")
    (bindir / "oc").chmod(0o755)
    results = td / "results"
    results.mkdir(exist_ok=True)
    script = _script().replace("$(results.outcome.path)", str(results / "outcome")).replace(
        "$(results.receipt.path)", str(results / "receipt"))
    (td / "provision.sh").write_text(script, encoding="utf-8")
    env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ["PATH"]), FAKE_STATE=str(td / "state.json"),
               FAKE_PROFILES=str(PROFILES), TASKRUN="provision-%s-abc" % run, RUN=run, SCAFFOLD=commit,
               WSNS="wksp-ai-developer", MODE="provision", FIXTURE_SRC="migration-fixture-credentials",
               DB_IMAGE="registry.example/postgresql@sha256:" + "1" * 64,
               CLI_IMAGE="registry.example/ose-cli@sha256:" + "2" * 64, **env_extra)
    p = subprocess.run(["bash", str(td / "provision.sh")], env=env, capture_output=True, text=True)
    state = json.loads((td / "state.json").read_text()) if (td / "state.json").exists() else {"objects": {}, "applied": []}
    return p.returncode, p.stdout + p.stderr, state


def _yaml_value(doc: str, key: str) -> str:
    m = re.search(r"^\s*%s:\s*(.+)$" % re.escape(key), doc, re.M)
    return m.group(1).strip().strip('"') if m else ""


def _case(run: str) -> int:
    commit = subprocess.run(["git", "hash-object", "--stdin"], input=run, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        rc, out, st = _provision(td, run, commit)
        if rc != 0:
            return _fail("provisioning succeeds (%s): %s" % (run, out[-800:]))
        ctl = st["objects"].get("ConfigMap/%s-run-control" % run, {}).get("text", "")
        if not ctl:
            return _fail("the run-control record is written (%s): %s" % (run, sorted(st["objects"])))
        for key, want in (("controller.devfile.io/mount-as", "file"), ("controller.devfile.io/mount-path", "/etc/rhoai3/run-control"),
                          ("controller.devfile.io/mount-on-start", "true"), ("controller.devfile.io/mount-to-devworkspace-include", run),
                          ("rhoai3.io/migration-run", run)):
            if _yaml_value(ctl, key) != want:
                return _fail("run control %s is %r, not %r" % (key, _yaml_value(ctl, key), want))
        contract = json.loads(json.loads(_yaml_value_raw(ctl, "contract.json")))
        profile = json.loads(json.loads(_yaml_value_raw(ctl, "profile.json")))
        if contract.get("run_id") != run or contract.get("scaffold_commit") != commit or contract.get("activation") != "pilot" \
                or not contract.get("authorized_by", "").startswith("provision-migration-run:"):
            return _fail("the contract names the run, its scaffolding commit and the platform authorizer: %s" % contract)
        if profile != json.loads(PROFILES.read_text()):
            return _fail("the pinned profile is the platform table verbatim")
        # the worker identity has no write verb at all
        role = next(t for t in st["applied"] if "kind: Role\n" in t and "%s-worker" % run in t)
        verbs = set(re.findall(r'verbs:\s*\[([^\]]*)\]', role))
        if any(v not in ('"get"', '"use"') for grp in verbs for v in [x.strip() for x in grp.split(",")]):
            return _fail("the worker role grants only get and use: %s" % verbs)
        # the golden reader accepts exactly what the platform wrote
        _governed_reader_check = _reader_accepts(td, run, contract, profile)
        if _governed_reader_check:
            return _fail(_governed_reader_check)
        # a re-delivered event leaves the record untouched; another commit is refused
        before = st["objects"]["ConfigMap/%s-run-control" % run]["text"]
        rc, out, st = _provision(td, run, commit)
        if rc != 0 or "already records" not in out or st["objects"]["ConfigMap/%s-run-control" % run]["text"] != before:
            return _fail("a re-delivered event leaves the record untouched: %s" % out[-400:])
    with tempfile.TemporaryDirectory() as d:
        rc, out, st = _provision(Path(d), run, commit, FAKE_FOREIGN_CONTROL="1")
        if rc == 0 or "records scaffolding commit" not in out:
            return _fail("a record for another commit refuses: %s" % out[-400:])
    with tempfile.TemporaryDirectory() as d:
        rc, out, st = _provision(Path(d), run, commit, FAKE_NO_PROFILES="1")
        if rc == 0 or "no usable default profile" not in out or any(k.endswith("-run-control") for k in st["objects"]):
            return _fail("a missing profile table refuses and writes no record: %s" % out[-400:])
    return 0


def _yaml_value_raw(doc: str, key: str) -> str:
    m = re.search(r"^\s*%s:\s*(.+)$" % re.escape(key), doc, re.M)
    return m.group(1).strip() if m else '""'


def _reader_accepts(td: Path, run: str, contract: dict, profile: dict) -> str:
    """'' when the golden reader accepts the platform's record for a
    destination whose initial commit carries the factory declaration."""
    root = td / "dest"
    control = td / "etc-run-control"
    control.mkdir()
    (control / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    root.mkdir()
    (root / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run, "run_control": {
        "contract": "rhoai3.run-control/v1", "root": str(control), "state": str(td / "state-dir")}}), encoding="utf-8")
    g = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a],  # noqa: E731
                                  capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    g("add", "-A")
    g("commit", "-q", "-m", "scaffold")
    contract = dict(contract, scaffold_commit=g("rev-parse", "HEAD"))   # the fixture's own scaffolding commit
    (control / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    sys.path.insert(0, str(GOLDEN_LIB))
    from planner import run_control
    doc, gaps = run_control.contract(root)
    if gaps or doc.get("run_id") != run:
        return "the golden reader accepts the platform record: %s" % gaps
    ok, msg = run_control.bind(root, "a" * 64, "M1")
    if not ok:
        return "the platform-authorized run binds its M1 bundle: %s" % msg
    return ""


def main() -> int:
    if _case("orders-migration") or _case("spring-petclinic-rest-legacy-v13"):
        return 1
    print("OK: provision-migration-run run control (the record is written once from the validated event, mounted as a "
          "read-only file volume into exactly this workspace; the golden reader accepts it; a re-delivery leaves it "
          "untouched; another commit and a missing profile table refuse; the worker role has no write verb)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
