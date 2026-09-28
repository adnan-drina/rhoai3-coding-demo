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
  * the board protocol: the run's request is read from run-budget.json AT the
    scaffolding commit (content-addressed URL; served here from a file:// root)
    and becomes the contract's selection; an outcome board (v2 native control,
    or the retired v1) carries the
    PLATFORM's execution state (disabled by default, enabled only by the task
    parameter, qualification refused) and measurement-trust decision; a run
    without a request, an unreadable request and a declaration naming another
    run select nothing; the golden reader's select_protocol agrees with every
    record the platform writes
Run under two run names.

Retirement runs the same script against a second fake API (FAKE_RETIRE_OC) that
models Argo CD's cascade finalizer (an Application being deleted stays until no
pod in its namespace mounts the project's maven-cache claim), namespace
termination, Tekton's cascade to pods, and one-shot API failures. It proves:
  * the run's workspace objects, owned delivery PipelineRuns and their pods,
    the Application project-<run> and the <run>-dev namespace are removed IN
    THAT ORDER (a failed seed run's pods before the Application delete), and
    no finalizer is ever patched away
  * the tombstone stays, names the destination repository for its owner, and
    is labelled as a receipt (the admission policy's parameter) before any
    deletion; no repository is deleted
  * a second retirement is a no-op success; absent resources are fine
  * an API failure and a finalizer that cannot complete in time both stop at
    `retiring`, and a retry converges
  * run x-v2 never touches x-v23; an ownership mismatch refuses with nothing
    deleted; other runs' Applications and namespaces and another namespace's
    maven-cache claim are preserved
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
# The golden reader. On main the scaffold subtree is not the golden source and
# may predate run control; GOLDEN_LIB points the check at a golden checkout.
GOLDEN_LIB = Path(os.environ.get("GOLDEN_LIB") or
                  REPO / "stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/lib")
READER = (GOLDEN_LIB / "planner/run_control.py").is_file()

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


def _serve_request(td: Path, run: str, commit: str, decl: dict | None) -> None:
    """The content-addressed raw endpoint the task reads the request from."""
    f = td / "raw" / "owner" / run / commit / "run-budget.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    if decl is None:
        if f.exists():
            f.unlink()
        return
    f.write_text(json.dumps(decl), encoding="utf-8")


def _param_default(name: str) -> str:
    """The Task's declared default for a param: the value a run gets when the pipeline passes none."""
    m = re.search(r"\n    - name: %s\n(?:      (?!default:).*\n)*?      default: \"?([^\"\n]*)\"?\n" % re.escape(name),
                  TASK.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("FAIL: Task param %s declares no default" % name)
    return m.group(1).strip()


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
               CLI_IMAGE="registry.example/ose-cli@sha256:" + "2" * 64,
               **dict({"OB_EXECUTION": _param_default("outcome-board-execution"),
                       "OB_TRUST": _param_default("outcome-board-measurement-trust"), "REQUEST_OWNER": "owner",
                       "REQUEST_RAW_BASE": (td / "raw").as_uri()}, **env_extra))
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
        _governed_reader_check = _reader_accepts(td, run, contract, profile) if READER else ""
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
    return _protocol_cases(run, commit)


SERIAL, OUTCOME, NATIVE = "serial-loop/v1", "outcome-board/v1", "outcome-board/v2"
# the Task defaults (2026-09-27): a new outcome-board run starts enabled under the decided trust
DEFAULT_OB = {"execution": "enabled", "measurement_trust": "cooperative-receipts"}


def _contract_of(st: dict, run: str) -> dict:
    ctl = st["objects"].get("ConfigMap/%s-run-control" % run, {}).get("text", "")
    return json.loads(json.loads(_yaml_value_raw(ctl, "contract.json"))) if ctl else {}


def _protocol_cases(run: str, commit: str) -> int:
    base = {"schema": "rhoai3.run-budget/v2", "run_id": run}
    cases = (
        # (declaration served, env, want board_protocol, want outcome_board, want request state prefix)
        (dict(base), {}, None, None, "read"),                                               # legacy: no request
        (None, {}, None, None, "unreadable"),                                               # nothing served
        (dict(base, board_protocol=SERIAL), {}, SERIAL, None, "read"),
        (dict(base, board_protocol=OUTCOME), {}, OUTCOME, DEFAULT_OB, "read"),
        (dict(base, board_protocol=OUTCOME), {"OB_EXECUTION": "disabled", "OB_TRUST": ""}, OUTCOME, {"execution": "disabled"}, "read"),
        (dict(base, board_protocol=OUTCOME), {"OB_EXECUTION": "enabled", "OB_TRUST": "cooperative-receipts"},
         OUTCOME, {"execution": "enabled", "measurement_trust": "cooperative-receipts"}, "read"),
        (dict(base, board_protocol=NATIVE), {}, NATIVE, DEFAULT_OB, "read"),                # default since 2026-09-27
        (dict(base, board_protocol=NATIVE), {"OB_EXECUTION": "disabled", "OB_TRUST": ""}, NATIVE, {"execution": "disabled"}, "read"),
        (dict(base, board_protocol=NATIVE), {"OB_EXECUTION": "enabled", "OB_TRUST": "cooperative-receipts"},
         NATIVE, {"execution": "enabled", "measurement_trust": "cooperative-receipts"}, "read"),
        (dict(base, board_protocol="board/v9"), {}, None, None, "read"),                    # recorded, never selected
        (dict(base, run_id="another-run", board_protocol=OUTCOME), {}, None, None, "unreadable"),
    )
    for decl, env, want_p, want_b, want_state in cases:
        with tempfile.TemporaryDirectory() as d:
            td = Path(d)
            _serve_request(td, run, commit, decl)
            rc, out, st = _provision(td, run, commit, **env)
            if rc != 0:
                return _fail("provisioning with request %r succeeds: %s" % (decl, out[-600:]))
            c = _contract_of(st, run)
            if c.get("board_protocol") != want_p or c.get("outcome_board") != want_b:
                return _fail("request %r env %r selects %r / %r, want %r / %r" % (
                    decl, env, c.get("board_protocol"), c.get("outcome_board"), want_p, want_b))
            req = c.get("protocol_request") or {}
            if not str(req.get("state") or "").startswith(want_state) or req.get("source") != "run-budget.json@" + commit:
                return _fail("the request read is recorded: %r" % req)
            if READER:
                gap = _selection_agrees(td, run, c, decl)
                if gap:
                    return _fail(gap)
    for bad in ("qualification", "enabled-ish", ""):
        with tempfile.TemporaryDirectory() as d:
            rc, out, st = _provision(Path(d), run, commit, OB_EXECUTION=bad)
            if rc == 0 or "outcome-board-execution must be" not in out or any(k.endswith("-run-control") for k in st["objects"]):
                return _fail("execution %r is refused before anything is written: %s" % (bad, out[-300:]))
    return 0


def _selection_agrees(td: Path, run: str, contract: dict, decl: dict | None) -> str:
    """The golden reader, on a destination whose initial commit carries the
    served declaration (or none), reads a consistent selection from exactly the
    contract the platform wrote."""
    root, control = td / "sel-dest", td / "sel-control"
    control.mkdir()
    root.mkdir()
    d = dict(decl or {"schema": "rhoai3.run-budget/v2", "run_id": run})
    d["run_id"] = run
    d["run_control"] = {"contract": "rhoai3.run-control/v1", "root": str(control), "state": str(td / "sel-state")}
    (root / "run-budget.json").write_text(json.dumps(d), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "s"], check=True)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (control / "contract.json").write_text(json.dumps(dict(contract, scaffold_commit=head)), encoding="utf-8")
    sys.path.insert(0, str(GOLDEN_LIB))
    from planner import outcome_protocol
    sel = outcome_protocol.select_protocol(root)
    requested = d.get("board_protocol")
    if requested in (None, SERIAL) and contract.get("board_protocol") in (None, SERIAL):
        return "" if (sel.protocol, sel.errors) == (SERIAL, []) else "serial selection refused: %s" % sel.as_dict()
    for version in (OUTCOME, NATIVE):
        if requested == version and contract.get("board_protocol") == version:
            return "" if (sel.protocol, sel.errors) == (version, []) else "outcome selection refused: %s" % sel.as_dict()
    # an unknown request is refused by the reader, never run serial
    return "" if sel.errors and sel.outcome else "an inconsistent record was not refused: %s" % sel.as_dict()


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


# --------------------------------------------------------------------------
# Retirement: a fake API with finalizers, cascades and one-shot failures.
# --------------------------------------------------------------------------
FAKE_RETIRE_OC = r"""#!/usr/bin/env python3
import json, os, sys
state = os.environ["FAKE_STATE"]
args = [a for a in sys.argv[1:] if not a.startswith("--request-timeout")]
db = json.load(open(state))
KINDS = {"application.argoproj.io": "application", "pipelinerun.tekton.dev": "pipelinerun", "pod": "pod",
         "pods": "pod", "namespace": "namespace", "configmap": "configmap", "secret": "secret",
         "deployment": "deployment", "service": "service", "serviceaccount": "serviceaccount", "role": "role",
         "rolebinding": "rolebinding"}
NAMEFORM = {"application": "application.argoproj.io", "pipelinerun": "pipelinerun.tekton.dev"}
def save(): json.dump(db, open(state, "w"), indent=1)
def opt(flag):
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args): return args[i + 1]
        if a.startswith(flag + "="): return a.split("=", 1)[1]
    return None
def positional():
    out, skip = [], False
    for a in args[1:]:
        if skip: skip = False; continue
        if a in ("-n", "-l", "-o", "-f"): skip = True; continue
        if a.startswith("-"): continue
        out.append(a)
    return out
def key(kind, ns, name): return "%s/%s/%s" % (kind, ns or "", name)
def split(k): kind, ns, name = k.split("/", 2); return kind, ns, name
def matches(obj, sel):
    for term in [s for s in (sel or "").split(",") if s]:
        if "=" in term:
            k, v = term.split("=", 1)
            if obj.get("labels", {}).get(k) != v: return False
        elif term not in obj.get("labels", {}): return False
    return True
def log(*entry): db["log"].append(list(entry))
def fail_once(op):
    if op in db.get("fail", []) and op not in db.setdefault("failed", []):
        db["failed"].append(op); log("FAILED", op); save()
        print("Error from server (InternalError): injected " + op, file=sys.stderr); sys.exit(1)
def reconcile():
    # Argo CD's resources-finalizer: an Application being deleted removes what it
    # manages and goes away only once no pod in its namespace mounts maven-cache.
    for k, o in list(db["objects"].items()):
        kind, ns, name = split(k)
        if kind == "application" and o.get("deleting") and k in db["objects"]:
            dest = o["spec"]["destination"]["namespace"]
            holders = [p for p, po in db["objects"].items() if split(p)[0] == "pod" and split(p)[1] == dest
                       and "maven-cache" in po.get("claims", [])]
            if holders: continue
            db["objects"].pop(key("pvc", dest, "maven-cache"), None)
            db["objects"].pop(k); log("finalized", k)
        if kind == "namespace" and o.get("deleting") and k in db["objects"]:
            for p in [p for p in db["objects"] if split(p)[1] == name]:
                db["objects"].pop(p)
            db["objects"].pop(k); log("finalized", k)
    save()
def remove(k):
    kind, ns, name = split(k)
    o = db["objects"][k]
    if kind in ("application", "namespace"):
        o["deleting"] = True; log("delete", k); return
    db["objects"].pop(k); log("delete", k)
    if kind == "pipelinerun" and not os.environ.get("FAKE_NO_GC"):
        for p in [p for p, po in db["objects"].items() if split(p)[0] == "pod" and split(p)[1] == ns
                  and po.get("labels", {}).get("tekton.dev/pipelineRun") == name]:
            db["objects"].pop(p); log("gc", p)
verb = args[0]
if verb in ("patch", "edit", "replace", "annotate"):
    log(verb, " ".join(args)); save(); sys.exit(0)
ns = opt("-n")
if verb == "create" and args[1] == "configmap" and "--dry-run=client" in args:
    data = dict(a[len("--from-literal="):].split("=", 1) for a in args if a.startswith("--from-literal="))
    print(json.dumps({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": args[2], "namespace": ns}, "data": data}))
    sys.exit(0)
if verb == "create" and args[1] == "configmap":
    k = key("configmap", ns, args[2])
    if k in db["objects"]: print("AlreadyExists", file=sys.stderr); sys.exit(1)
    db["objects"][k] = {"labels": {}, "data": {}}; log("lock", k); save(); sys.exit(0)
if verb == "apply":
    doc = json.loads(sys.stdin.read())
    k = key("configmap", doc["metadata"]["namespace"] or ns, doc["metadata"]["name"])
    fail_once("apply " + k)
    obj = db["objects"].setdefault(k, {"labels": {}, "data": {}})
    obj["data"] = doc["data"]; log("apply", k, doc["data"].get("phase")); save(); sys.exit(0)
if verb == "label":
    k = key("configmap", ns, args[2])
    for a in args[3:]:
        if "=" in a and not a.startswith("-"):
            kk, v = a.split("=", 1); db["objects"][k]["labels"][kk] = v
    log("label", k); save(); sys.exit(0)
if verb == "get":
    reconcile()
    pos = positional()
    kinds = [KINDS[x] for x in pos[0].split(",")]
    name = pos[1] if len(pos) > 1 else None
    fmt = opt("-o") or ""
    fail_once("get " + ",".join(kinds))
    found = []
    for k, o in sorted(db["objects"].items()):
        kind, ons, oname = split(k)
        if kind not in kinds: continue
        if kind != "namespace" and ons != (ns or ""): continue
        if name is not None and oname != name: continue
        if not matches(o, opt("-l")): continue
        found.append((k, o))
    if name is not None and not found:
        if "--ignore-not-found" in args: sys.exit(0)
        print("NotFound", file=sys.stderr); sys.exit(1)
    if fmt == "name":
        for k, o in found:
            kind, _, oname = split(k); print("%s/%s" % (NAMEFORM.get(kind, kind), oname))
    elif fmt == "json":
        k, o = found[0]; kind, ons, oname = split(k)
        meta = {"name": oname, "labels": o.get("labels", {}), "finalizers": o.get("finalizers", [])}
        if ons: meta["namespace"] = ons
        if o.get("deleting"): meta["deletionTimestamp"] = "2026-09-28T00:00:00Z"
        print(json.dumps({"metadata": meta, "spec": o.get("spec", {})}))
    elif fmt.startswith("jsonpath={.data."):
        field = fmt[len("jsonpath={.data."):-1]
        print(found[0][1].get("data", {}).get(field, "") if found else "", end="")
    sys.exit(0)
if verb == "delete":
    pos = positional()
    if "/" in pos[0]:
        kname, oname = pos[0].split("/", 1); kind, name = KINDS[kname], oname
    else:
        kind, name = KINDS[pos[0]], (pos[1] if len(pos) > 1 else None)
    fail_once("delete " + kind)
    targets = [k for k, o in db["objects"].items() if split(k)[0] == kind
               and (kind == "namespace" or split(k)[1] == (ns or ""))
               and (name is None or split(k)[2] == name) and matches(o, opt("-l"))]
    if name is not None and not targets and "--ignore-not-found" not in args:
        print("NotFound", file=sys.stderr); sys.exit(1)
    for k in targets:
        remove(k)
    if kind == "application" and os.environ.get("FAKE_LATE_PUSH") and targets:
        # a push lands while the Application finalizes: a new delivery run holds the cache
        dest = db["objects"][targets[0]]["spec"]["destination"]["namespace"]
        run = dest[:-len("-dev")]
        db["objects"][key("pipelinerun", dest, run + "-push-late")] = {"labels": {"app.kubernetes.io/name": run, "tekton.dev/pipeline": "app-push"}}
        db["objects"][key("pod", dest, run + "-push-late-maven-build-pod")] = {
            "labels": {"app.kubernetes.io/name": run, "tekton.dev/pipelineRun": run + "-push-late"}, "claims": ["maven-cache"]}
        log("late-push", dest)
    save(); sys.exit(0)
print("unhandled: " + " ".join(args), file=sys.stderr); sys.exit(2)
"""

WSNS = "wksp-ai-developer"


def _project(objects: dict, run: str, *, receipt: str | None = "provisioned", seed_failed: bool = True) -> None:
    """One provisioned run as the platform leaves it: workspace objects, receipt,
    the trigger-created Application, its namespace, claim and a failed seed run."""
    ns = run + "-dev"
    lab = {"rhoai3.io/migration-run": run}
    for kind, name in (("secret", run + "-parity-db"), ("secret", run + "-parity-postgres"), ("deployment", run + "-parity-postgres"),
                       ("service", run + "-parity-postgres"), ("serviceaccount", run + "-worker"), ("role", run + "-worker"),
                       ("rolebinding", run + "-worker"), ("configmap", run + "-run-control")):
        objects["%s/%s/%s" % (kind, WSNS, name)] = {"labels": dict(lab)}
    if receipt:
        objects["configmap/%s/migration-run-%s" % (WSNS, run)] = {
            "labels": {"rhoai3.io/purpose": "stage-080-parity", "rhoai3.io/migration-run-receipt": run},
            "data": {"run": run, "phase": receipt, "scaffoldCommit": "a" * 40}}
    objects["application/openshift-gitops/project-" + run] = {
        "labels": {"rhoai3.redhat.com/scaffolded-project": "true", "triggers.tekton.dev/trigger": "scaffolded-project-bootstrap"},
        "finalizers": ["resources-finalizer.argocd.argoproj.io"],
        "spec": {"project": "scaffolded-projects", "destination": {"namespace": ns, "server": "https://kubernetes.default.svc"},
                 "source": {"kustomize": {"namespace": ns}},
                 "syncPolicy": {"managedNamespaceMetadata": {"labels": {"app.kubernetes.io/part-of": run,
                                                                        "rhoai3.redhat.com/pipeline-project": "true"}}}}}
    objects["namespace//" + ns] = {"labels": {"app.kubernetes.io/part-of": run, "rhoai3.redhat.com/pipeline-project": "true"}}
    objects["pvc/%s/maven-cache" % ns] = {"labels": {}}
    if seed_failed:
        pr = run + "-seed-z52wj"
        objects["pipelinerun/%s/%s" % (ns, pr)] = {"labels": {"app.kubernetes.io/name": run, "tekton.dev/pipeline": "app-push"},
                                                   "status": "Failed"}
        for task, claims in (("clone-source", []), ("maven-build", ["maven-cache"])):
            objects["pod/%s/%s-%s-pod" % (ns, pr, task)] = {
                "labels": {"app.kubernetes.io/name": run, "tekton.dev/pipelineRun": pr, "tekton.dev/pipeline": "app-push"},
                "claims": claims}


def _shared(objects: dict) -> None:
    """A platform project with its own maven-cache claim held by a running build."""
    objects["namespace//coolstore-dev"] = {"labels": {"app.kubernetes.io/part-of": "coolstore", "rhoai3.redhat.com/pipeline-project": "true"}}
    objects["pvc/coolstore-dev/maven-cache"] = {"labels": {}}
    objects["pod/coolstore-dev/coolstore-push-x-maven-build-pod"] = {
        "labels": {"app.kubernetes.io/name": "coolstore-inventory-service", "tekton.dev/pipelineRun": "coolstore-push-x"},
        "claims": ["maven-cache"]}


def _retire(td: Path, run: str, objects: dict | None = None, **env_extra: str) -> tuple[int, str, dict]:
    bindir = td / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "oc").write_text(FAKE_RETIRE_OC, encoding="utf-8")
    (bindir / "oc").chmod(0o755)
    results = td / "results"
    results.mkdir(exist_ok=True)
    state = td / "state.json"
    if objects is not None:
        fail = [f for f in env_extra.pop("FAKE_FAIL", "").split("|") if f]
        state.write_text(json.dumps({"objects": objects, "log": [], "fail": fail}), encoding="utf-8")
    else:
        st = json.loads(state.read_text())
        st["log"] = []
        state.write_text(json.dumps(st), encoding="utf-8")
    script = _script().replace("$(results.outcome.path)", str(results / "outcome")).replace(
        "$(results.receipt.path)", str(results / "receipt"))
    (td / "retire.sh").write_text(script, encoding="utf-8")
    env = dict(os.environ, PATH="%s:%s" % (bindir, os.environ["PATH"]), FAKE_STATE=str(state),
               TASKRUN="retire-%s-abc" % run, RUN=run, SCAFFOLD="retire", WSNS=WSNS, MODE="retire",
               FIXTURE_SRC="migration-fixture-credentials", DB_IMAGE="", CLI_IMAGE="", OB_EXECUTION="enabled",
               OB_TRUST="", REQUEST_OWNER="owner", REQUEST_RAW_BASE="file:///nonexistent",
               RETIRE_WAIT_SECONDS="2", RETIRE_POLL_SECONDS="1", **env_extra)
    p = subprocess.run(["bash", str(td / "retire.sh")], env=env, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr, json.loads(state.read_text())


def _mutations(st: dict) -> list:
    """Every state change except taking and releasing the per-run lock."""
    return [e for e in st["log"] if e[0] not in ("lock",) and not (e[0] == "delete" and e[1].endswith("-lock"))]


def _run_keys(st: dict, run: str) -> list:
    """Everything the run owns except its tombstone: exact names and equality labels only."""
    ns = run + "-dev"
    return sorted(k for k, o in st["objects"].items() if k.split("/")[1] == ns or k == "namespace//" + ns
                  or k == "application/openshift-gitops/project-" + run
                  or o.get("labels", {}).get("rhoai3.io/migration-run") == run)


def _retire_cases() -> int:
    run, sibling = "x-v2", "x-v23"
    tomb = "configmap/%s/migration-run-%s" % (WSNS, run)
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        objects: dict = {}
        _project(objects, run)
        _project(objects, sibling)
        _shared(objects)
        before_others = {k: v for k, v in objects.items() if k not in _run_keys({"objects": objects}, run) and k != tomb}
        rc, out, st = _retire(td, run, objects, FAKE_NO_GC="1")
        if rc != 0 or "retired x-v2" not in out:
            return _fail("retirement of a provisioned run with a failed seed run succeeds: %s" % out[-1200:])
        left = _run_keys(st, run)
        if left:
            return _fail("nothing of x-v2 remains but its tombstone: %s" % left)
        others = {k: v for k, v in st["objects"].items() if k != tomb}
        if others != before_others:
            return _fail("other runs and shared components are untouched: %s" % sorted(set(before_others) ^ set(others)))
        t = st["objects"].get(tomb) or {}
        if t.get("data", {}).get("phase") != "retired" or t["data"].get("destinationRepository") != "https://github.com/owner/x-v2" \
                or "owner of the Git organization" not in t["data"].get("destinationRepositoryDisposition", "") \
                or t.get("labels", {}).get("rhoai3.io/migration-run-receipt") != run:
            return _fail("the tombstone is kept, labelled as a receipt, and names the repository for its owner: %s" % t)
        log = st["log"]
        idx = lambda pred: [i for i, e in enumerate(log) if pred(e)]  # noqa: E731
        app_del = idx(lambda e: e[:2] == ["delete", "application/openshift-gitops/project-x-v2"])
        pod_del = idx(lambda e: e[0] == "delete" and e[1].startswith("pod/x-v2-dev/"))
        pr_del = idx(lambda e: e[0] == "delete" and e[1].startswith("pipelinerun/x-v2-dev/"))
        ns_del = idx(lambda e: e[:2] == ["delete", "namespace//x-v2-dev"])
        app_gone = idx(lambda e: e[:2] == ["finalized", "application/openshift-gitops/project-x-v2"])
        intent = idx(lambda e: e[0] == "apply" and e[2] == "retiring")
        first_delete = idx(lambda e: e[0] == "delete" and not e[1].endswith("-lock"))
        if not (app_del and pod_del and pr_del and ns_del and app_gone and intent):
            return _fail("each retirement step happened: %s" % log)
        if not (intent[0] < first_delete[0] and max(pod_del + pr_del) < app_del[0] < app_gone[0] < ns_del[0]):
            return _fail("order: intent, delivery runs and their pods, Application, its finalization, namespace: %s" % log)
        if any(e[0] in ("patch", "edit", "replace", "annotate") for e in log):
            return _fail("no finalizer is patched away: %s" % [e for e in log if e[0] == "patch"])
        if any(e[0] == "delete" and ("x-v23" in e[1] or "coolstore" in e[1]) for e in log):
            return _fail("x-v2 never selects x-v23 or a shared namespace: %s" % log)
        # a second retirement is a no-op success
        rc, out, st2 = _retire(td, run)
        if rc != 0 or "already retired" not in out or _mutations(st2) or st2["objects"].get(tomb) != t:
            return _fail("a second retirement changes nothing: %s %s" % (_mutations(st2), out[-400:]))

    # the late push: a delivery run started while the Application finalizes is removed too
    with tempfile.TemporaryDirectory() as d:
        objects = {}
        _project(objects, run)
        rc, out, st = _retire(Path(d), run, objects, FAKE_LATE_PUSH="1")
        if rc != 0 or _run_keys(st, run) or not any(e[0] == "late-push" for e in st["log"]):
            return _fail("a delivery run started during retirement is removed and retirement converges: %s" % out[-800:])

    # absent resources: a receipt and nothing else; and no receipt at all
    for receipt in ("provisioned", None):
        with tempfile.TemporaryDirectory() as d:
            objects = {}
            _project(objects, run, receipt=receipt)
            for k in [k for k in objects if not k.startswith("configmap/%s/migration-run-" % WSNS)]:
                objects.pop(k)
            rc, out, st = _retire(Path(d), run, objects)
            if rc != 0 or (st["objects"].get(tomb) or {}).get("data", {}).get("phase") != "retired":
                return _fail("retirement with absent resources succeeds (receipt %r): %s" % (receipt, out[-600:]))

    # partial failure then retry, at every kind of step
    for fail in ("delete pipelinerun", "delete application", "delete namespace", "get application", "delete secret"):
        with tempfile.TemporaryDirectory() as d:
            td = Path(d)
            objects = {}
            _project(objects, run)
            _project(objects, sibling)
            objects[tomb]["labels"] = {}   # a receipt the admission policy cannot see yet
            rc, out, st = _retire(td, run, objects, FAKE_FAIL=fail)
            if rc == 0:
                return _fail("an injected API failure (%s) stops retirement: %s" % (fail, out[-400:]))
            t = st["objects"].get(tomb) or {}
            if fail != "get application" and t.get("data", {}).get("phase") != "retiring":
                return _fail("a failed retirement (%s) leaves the tombstone at retiring: %s" % (fail, t))
            if fail != "get application" and t.get("labels", {}).get("rhoai3.io/migration-run-receipt") != run:
                return _fail("the retiring tombstone is labelled for the admission policy before any deletion (%s): %s" % (fail, t))
            if fail == "get application" and _mutations(st) != [["FAILED", "get application"]]:
                return _fail("a failed read before the ownership check changes nothing: %s" % _mutations(st))
            if any(k.endswith("-lock") for k in st["objects"]):
                return _fail("a failed retirement releases its lock (%s)" % fail)
            rc, out, st = _retire(td, run)
            if rc != 0 or _run_keys(st, run) or (st["objects"].get(tomb) or {}).get("data", {}).get("phase") != "retired":
                return _fail("the retry after %s converges: %s" % (fail, out[-800:]))
            if not _run_keys(st, sibling):
                return _fail("the retry after %s leaves x-v23 alone" % fail)

    # a finalizer that cannot complete in time: nothing is stripped; retry converges
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        objects = {}
        _project(objects, run)
        blocker = "pod/x-v2-dev/debug-shell"   # not a delivery run of this run: never selected
        objects[blocker] = {"labels": {}, "claims": ["maven-cache"]}
        rc, out, st = _retire(td, run, objects)
        app = st["objects"].get("application/openshift-gitops/project-x-v2") or {}
        if rc == 0 or "RETIRE_INCOMPLETE" not in out or app.get("finalizers") != ["resources-finalizer.argocd.argoproj.io"] \
                or (st["objects"][tomb]["data"]["phase"] != "retiring") or blocker not in st["objects"] \
                or any(e[0] == "patch" for e in st["log"]):
            return _fail("a blocked finalizer ends RETIRE_INCOMPLETE with the finalizer intact: %s" % out[-800:])
        st["objects"].pop(blocker)   # the Operator resolves the blocker
        (td / "state.json").write_text(json.dumps(st), encoding="utf-8")
        rc, out, st = _retire(td, run)
        if rc != 0 or _run_keys(st, run):
            return _fail("the retry after a blocked finalizer converges: %s" % out[-800:])

    # ownership mismatch: refused, nothing deleted, receipt unchanged
    mismatches = {
        "app deploys elsewhere": lambda o: o["application/openshift-gitops/project-x-v2"]["spec"]["destination"].update(namespace="x-v23-dev"),
        "app labelled for another run": lambda o: o["application/openshift-gitops/project-x-v2"]["labels"].update({"rhoai3.io/migration-run": "x-v23"}),
        "app in another AppProject": lambda o: o["application/openshift-gitops/project-x-v2"]["spec"].update(project="default"),
        "app not scaffolded": lambda o: o["application/openshift-gitops/project-x-v2"]["labels"].pop("rhoai3.redhat.com/scaffolded-project"),
        "namespace of another project": lambda o: o["namespace//x-v2-dev"]["labels"].update({"app.kubernetes.io/part-of": "x-v23"}),
        "receipt names another run": lambda o: o[tomb]["data"].update(run="x-v23"),
        "no receipt links the project": lambda o: o.pop(tomb),
    }
    for label, mutate in mismatches.items():
        with tempfile.TemporaryDirectory() as d:
            objects = {}
            _project(objects, run)
            _project(objects, sibling)
            mutate(objects)
            before = json.loads(json.dumps(objects))
            rc, out, st = _retire(Path(d), run, objects)
            if rc == 0 or "RETIRE_OWNERSHIP_MISMATCH" not in out or _mutations(st) or st["objects"] != before:
                return _fail("ownership mismatch (%s) refuses with nothing changed: %s %s" % (label, _mutations(st), out[-500:]))
    return 0


def _admission_contract() -> int:
    """The recreation refusal is wired to the tombstone the Task writes."""
    text = (HERE / "pipeline-provision-migration-run.yaml").read_text(encoding="utf-8")
    body = re.sub(r"(?m)^\s*#.*$", "", text)
    need = ("kind: ValidatingAdmissionPolicy\n", "kind: ValidatingAdmissionPolicyBinding\n", 'operations: ["CREATE"]',
            "rhoai3.io/migration-run-receipt", "operator: Exists", "parameterNotFoundAction: Allow",
            "object.spec.project == 'scaffolded-projects'", "'project-' + variables.retiredRun",
            "variables.retiredRun + '-dev'", "['retiring', 'retired']")
    missing = [n for n in need if n not in body]
    if missing:
        return _fail("the admission policy refuses recreating a tombstoned run's project: missing %s" % missing)
    task = re.sub(r"(?m)^\s*#.*$", "", TASK.read_text(encoding="utf-8"))
    if re.search(r"patch\b[^\n]*finalizers|finalizers[^\n]*null", task):
        return _fail("the Task never edits a finalizer")
    if re.search(r"(api\.github\.com|gh repo delete|DELETE[^\n]*github)", task):
        return _fail("the Task never deletes a repository")
    return 0


def main() -> int:
    if _case("orders-migration") or _case("spring-petclinic-rest-legacy-v13"):
        return 1
    if _retire_cases() or _admission_contract():
        return 1
    if not READER:
        print("SKIP: golden reader check -- %s has no planner/run_control.py (set GOLDEN_LIB to a golden checkout)" % GOLDEN_LIB)
    print("OK: provision-migration-run run control (the record is written once from the validated event, mounted as a "
          "read-only file volume into exactly this workspace; the golden reader accepts it; a re-delivery leaves it "
          "untouched; another commit and a missing profile table refuse; the worker role has no write verb; the run's own "
          "board_protocol request becomes the selection, outcome-board/v1 carries the platform's execution state "
          "(the Task default: enabled under cooperative-receipts since 2026-09-27; disabled when set; qualification refused), and the golden reader agrees with every record); retirement removes the run's workspace objects, delivery runs, "
          "project Application and namespace in finalizer-permitting order, keeps a tombstone naming the repository, is "
          "idempotent, converges after failure, refuses an ownership mismatch and never selects a similar run's project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
