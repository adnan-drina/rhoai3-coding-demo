"""Run control: what this run was created as, written by the PLATFORM (B8, R1, R3).

v12 (2026-09-24, card t_b33f25fa): the pilot seal lived only as dest-init's
uncommitted edit of `.hermes/pins.json`; a worker's `git checkout` removed it
and the loop stopped in silence. The first v13 attempt moved it to a same-UID
directory, which a release review showed was still worker-writable, and whose
absence silently switched every check off (R1).

The contract is now:

* WHETHER a run is governed by run control is fixed by the factory, not by
  anything on disk: the run declaration in the destination's INITIAL commit
  (`run-budget.json` `run_control`) names the contract, the read-only control
  root and the state directory. That commit is immutable; no file deleted or
  environment variable set later changes it. A declaration without
  `run_control` is a legacy run (v12 and earlier) and keeps `pins.json`.
* The control root is a ConfigMap the platform provisioner writes from the
  validated scaffolding event and mounts READ-ONLY into this one workspace
  (`<run>-run-control`, mount-on-start). The coding worker's identity has no
  write access to it. It carries:
    contract.json  run id, scaffolding commit, activation and its authorization
    profile.json   the model profile pinned for this run
    release-rebase.json (optional)  an Operator-recorded assisted harness change
* The state directory holds the one narrow operation left to the harness: the
  write-once binding of the M1 evidence bundle digest (binding.json), which
  must name the run the platform authorized. K2 refuses worker writes there.

For a governed run a missing, empty, malformed, foreign or unreadable record
REFUSES; nothing in the pod writes a pin, so a restart cannot re-bless what
was lost. Digests are recomputed from content, never trusted as stored.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "rhoai3.run-control/v1"
CONTRACT = "contract.json"
PROFILE = "profile.json"
REBASE = "release-rebase.json"
BINDING = "binding.json"
JOURNAL = "journal.jsonl"
RELEASE_TREES = (".hermes/kernel", ".hermes/lib", ".hermes/skills")
DECLARATION = "run-budget.json"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def declared(root: Path) -> dict[str, Any] | None:
    """The run-control declaration in the destination's initial commit, or
    None for a legacy run (no declaration, or one without run_control, or no
    git history at all). A declaration that names run control but is
    unusable is returned with an `error`."""
    roots = _git(root, "rev-list", "--max-parents=0", "HEAD")
    shas = roots.stdout.split() if roots.returncode == 0 else []
    if len(shas) != 1:
        return None
    blob = _git(root, "show", "%s:%s" % (shas[0], DECLARATION))
    if blob.returncode != 0:
        return None
    try:
        doc = json.loads(blob.stdout)
    except ValueError:
        return None
    rc = doc.get("run_control") if isinstance(doc, dict) else None
    if rc is None:
        return None
    out: dict[str, Any] = {"initial_commit": shas[0], "run_id": str(doc.get("run_id") or "")}
    if not isinstance(rc, dict) or rc.get("contract") != CONTRACT_SCHEMA:
        return dict(out, error="the initial commit's %s declares run_control %r, not %s" % (DECLARATION, rc, CONTRACT_SCHEMA))
    for key in ("root", "state"):
        v = str(rc.get(key) or "")
        if not v.startswith("/"):
            return dict(out, error="the initial commit's %s run_control.%s %r is not an absolute path" % (DECLARATION, key, v))
        out[key] = Path(v)
    return out


def in_use(root: Path) -> bool:
    return declared(root) is not None


def _read_json(path: Path) -> tuple[Any, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        return None, "unreadable (%s)" % exc
    if not text.strip():
        return None, "empty"
    try:
        return json.loads(text), ""
    except ValueError as exc:
        return None, "malformed (%s)" % exc


def contract(root: Path) -> tuple[dict[str, Any], list[str]]:
    """(contract doc, gaps) for a governed run; ({}, []) for a legacy run."""
    decl = declared(root)
    if decl is None:
        return {}, []
    if decl.get("error"):
        return {}, ["RUN_CONTROL_DECLARATION: %s" % decl["error"]]
    path = decl["root"] / CONTRACT
    doc, why = _read_json(path)
    if why:
        return {}, ["RUN_CONTROL_MISSING: %s is %s; this run is declared under %s in its initial commit %s, so nothing "
                    "is dispatched, measured or minted without the platform's record" % (path, why, CONTRACT_SCHEMA,
                                                                                          decl["initial_commit"][:12])]
    if not isinstance(doc, dict) or doc.get("schema") != CONTRACT_SCHEMA:
        return {}, ["RUN_CONTROL_MALFORMED: %s has schema %r, not %s" % (
            path, doc.get("schema") if isinstance(doc, dict) else type(doc).__name__, CONTRACT_SCHEMA)]
    gaps = []
    if str(doc.get("run_id") or "") != decl["run_id"]:
        gaps.append("RUN_ACTIVATION_FOREIGN: the platform record names run %r and this destination's declaration names %r"
                    % (doc.get("run_id"), decl["run_id"]))
    if str(doc.get("scaffold_commit") or "") != decl["initial_commit"]:
        gaps.append("RUN_ACTIVATION_FOREIGN: the platform record was provisioned from commit %s and this destination "
                    "begins at %s" % (str(doc.get("scaffold_commit") or "none")[:12], decl["initial_commit"][:12]))
    if str(doc.get("activation") or "") not in ("pilot", "activated"):
        gaps.append("RUN_CONTROL_MALFORMED: %s activation is %r" % (path, doc.get("activation")))
    if not str(doc.get("authorized_by") or "").strip():
        gaps.append("RUN_CONTROL_MALFORMED: %s names no authorizer" % path)
    return (doc if not gaps else {}), gaps


def _binding(decl: dict[str, Any]) -> dict[str, Any]:
    doc, _why = _read_json(decl["state"] / BINDING)
    return doc if isinstance(doc, dict) else {}


def planner_block(root: Path, repo_planner: dict[str, Any]) -> dict[str, Any]:
    """The planner block every activation reader uses. Legacy runs: the
    repository's pins, as before v13. Governed runs: the platform contract
    plus the write-once M1 binding, never pins.json; a gap is carried as-is."""
    decl = declared(root)
    if decl is None:
        return repo_planner
    doc, gaps = contract(root)
    if gaps:
        return {"activation": "refused", "gap": gaps[0]}
    bound = _binding(decl)
    if bound and str(bound.get("run_id") or "") != decl["run_id"]:
        return {"activation": "refused", "gap": "RUN_ACTIVATION_FOREIGN: %s binds run %r, not %r"
                % (decl["state"] / BINDING, bound.get("run_id"), decl["run_id"])}
    if doc["activation"] == "activated":
        return {"activation": "activated"}
    return {"activation": "pilot", "pilot": {
        "run_id": decl["run_id"], "authorized_by": str(doc["authorized_by"]),
        "evidence_bundle_sha256": str(bound.get("evidence_bundle_sha256") or ""),
        "authorization": dict(doc.get("authorization") or {}, source="platform-provisioner")}}


def bind(root: Path, digest: str, detail: str = "") -> tuple[bool, str]:
    """The narrow harness operation: bind the M1 evidence bundle digest, once,
    for the run the platform authorized. (ok, message)."""
    decl = declared(root)
    if decl is None or decl.get("error"):
        return False, "not a run-control run"
    doc, gaps = contract(root)
    if gaps:
        return False, gaps[0]
    if doc["activation"] != "pilot":
        return False, "activation is %r; nothing to bind" % doc["activation"]
    path = decl["state"] / BINDING
    cur, why = _read_json(path)
    if not why:
        if isinstance(cur, dict) and cur.get("evidence_bundle_sha256") == digest:
            return True, "already bound to %s" % digest[:16]
        return False, "RUN_BINDING_EXISTS: %s already binds %s; a binding is never rewritten" % (
            path, str((cur or {}).get("evidence_bundle_sha256") or "?")[:16])
    if why != "missing":
        return False, "RUN_BINDING_UNREADABLE: %s is %s" % (path, why)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"schema": CONTRACT_SCHEMA, "run_id": decl["run_id"], "evidence_bundle_sha256": digest,
           "bound_at": _now(), "detail": detail}
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)  # write-once, even under a race
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    with open(decl["state"] / JOURNAL, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": "bound", "at": rec["bound_at"], "run_id": decl["run_id"],
                             "evidence_bundle_sha256": digest}, sort_keys=True) + "\n")
    return True, "bound to %s" % digest[:16]


def release_gaps(root: Path) -> list[str]:
    """B10: the harness trees are exactly the release the platform recorded
    (the scaffolding commit, or an Operator-recorded assisted rebase in the
    read-only control root). Changed, deleted and untracked files -- ignored
    ones included, bytecode caches excepted -- are all drift."""
    decl = declared(root)
    if decl is None:
        return []
    _doc, gaps = contract(root)
    if gaps:
        return gaps
    commit, source = decl["initial_commit"], "the scaffolding commit"
    rebase, why = _read_json(decl["root"] / REBASE)
    if not why and isinstance(rebase, dict) and str(rebase.get("commit") or ""):
        commit, source = str(rebase["commit"]), "the assisted rebase recorded by the Operator (%s)" % rebase.get("reason", "")
    elif why not in ("", "missing"):
        return ["RUN_CONTROL_MALFORMED: %s is %s" % (decl["root"] / REBASE, why)]
    if _git(root, "cat-file", "-e", "%s^{commit}" % commit).returncode != 0:
        return ["HARNESS_RELEASE_MISMATCH: the recorded release %s is not a commit of this destination" % commit[:12]]
    diff = _git(root, "diff", "--name-only", commit, "--", *RELEASE_TREES)
    if diff.returncode != 0:
        return ["HARNESS_RELEASE_MISMATCH: the harness could not be compared with %s (%s)" % (commit[:12], diff.stderr.strip()[:200])]
    other = _git(root, "ls-files", "--others", "--", *RELEASE_TREES)
    changed = sorted({p for p in (diff.stdout + "\n" + other.stdout).splitlines()
                      if p.strip() and "__pycache__" not in p and not p.endswith(".pyc")})
    if not changed:
        return []
    return ["HARNESS_RELEASE_MISMATCH: %d harness file(s) differ from %s %s: %s; no task dispatched. A mid-run harness "
            "change is an assisted continuation the Operator records in the run-control ConfigMap (%s), never picked "
            "up silently" % (len(changed), source, commit[:12], ", ".join(changed[:3]), REBASE)]


def profile_digest(doc: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"default_model": doc.get("default_model"), "profiles": doc.get("profiles")},
                                     sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def managed_dir() -> Path:
    return Path(os.environ.get("HERMES_MANAGED_DIR") or "/projects/.platform/hermes")


def _diff(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out.extend(_diff(a.get(k), b.get(k), "%s.%s" % (path, k) if path else str(k)))
        return out
    return [] if a == b else ["%s: expected %s, got %s" % (path, json.dumps(a), json.dumps(b))]


def _effective_config_gaps(pinned: dict[str, Any]) -> list[str]:
    """The worker's generated Hermes config carries exactly the pinned profile
    for its default model: provider, context and output caps, and the request
    body on the provider AND on every auxiliary slot that calls the main model."""
    cfg_path = managed_dir() / "config.yaml"
    if not cfg_path.is_file():
        return ["the worker config %s is missing" % cfg_path]
    try:
        from planner.yamlite import load_yaml
        cfg = load_yaml(cfg_path)
    except Exception as exc:  # noqa: BLE001 - any unreadable config is a gap
        return ["the worker config %s is unreadable (%s)" % (cfg_path, exc)]
    model_id = str(pinned.get("default_model") or "")
    prof = (pinned.get("profiles") or {}).get(model_id) or {}
    out: list[str] = []
    m = cfg.get("model") or {}
    for key, want in (("default", model_id), ("provider", prof.get("provider")),
                      ("context_length", prof.get("context_length")), ("max_tokens", prof.get("max_tokens"))):
        if m.get(key) != want:
            out.append("config model.%s: expected %s, got %s" % (key, json.dumps(want), json.dumps(m.get(key))))
    prov = ((cfg.get("providers") or {}).get(str(prof.get("provider") or "")) or {})
    out.extend("config providers.%s.extra_body.%s" % (prof.get("provider"), d) for d in _diff(prof.get("request_body"), prov.get("extra_body")))
    # R2: auxiliary calls carry no max_tokens of their own, so the quota's
    # per-request output bound is part of their body
    q = prof.get("quota") or {}
    aux_body = dict(prof.get("request_body") or {}, **({"max_tokens": q["max_output_tokens"]} if q.get("max_output_tokens") else {}))
    for slot, aux in sorted((cfg.get("auxiliary") or {}).items()):
        if isinstance(aux, dict) and aux.get("enabled", True) is not False and str(aux.get("provider") or "auto") == "auto":
            out.extend("config auxiliary.%s.extra_body.%s" % (slot, d) for d in _diff(aux_body, aux.get("extra_body")))
    # R2: the allowance the admission counted is the one the runtime paces
    if q:
        env_path = managed_dir() / ".env"
        env = dict(l.split("=", 1) for l in (env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else [])
                   if "=" in l and not l.lstrip().startswith("#"))
        if str(q.get("accounting_mode") or "request") == "token":
            # V15-1: reserved-and-settled tokens (runtime 0010); no request ceiling
            want = {"RHOAI3_ACCOUNTING_MODE": "token",
                    "RHOAI3_TOKEN_BUDGET": "%s/%s" % (q.get("token_allowance_per_window"), q.get("window_seconds")),
                    "RHOAI3_TOKEN_RESERVATION": str(q.get("reservation_tokens"))}
            bad = ["%s=%s (expected %s)" % (k, env.get(k), v) for k, v in want.items() if env.get(k) != v]
            if env.get("RHOAI3_REQUEST_BUDGET"):
                bad.append("RHOAI3_REQUEST_BUDGET=%s is set in token mode" % env.get("RHOAI3_REQUEST_BUDGET"))
            if not env.get("RHOAI3_REQUEST_LEDGER"):
                bad.append("RHOAI3_REQUEST_LEDGER unset")
            if bad:
                out.append("the token accounting is not configured for the pinned allowance (%s: %s)" % (env_path, "; ".join(bad)))
        else:
            want = "%s/%s" % (q.get("max_requests_per_window"), q.get("window_seconds"))
            if env.get("RHOAI3_REQUEST_BUDGET") != want or not env.get("RHOAI3_REQUEST_LEDGER"):
                out.append("the request pacer is not configured for the pinned allowance (%s RHOAI3_REQUEST_BUDGET=%s, "
                           "expected %s, ledger %s)" % (env_path, env.get("RHOAI3_REQUEST_BUDGET"), want,
                                                         env.get("RHOAI3_REQUEST_LEDGER") or "unset"))
    return out


def profile_gaps(root: Path) -> list[str]:
    """B4: the pinned profile (read-only control root), the profile the worker
    config was generated from, and the generated config itself all agree --
    each digest recomputed from content."""
    decl = declared(root)
    if decl is None:
        return []
    _doc, gaps = contract(root)
    if gaps:
        return gaps
    pinned, why = _read_json(decl["root"] / PROFILE)
    if why or not isinstance(pinned, dict) or not pinned.get("profiles"):
        return ["MODEL_PROFILE_MISMATCH: the pinned profile %s is %s" % (decl["root"] / PROFILE, why or "without profiles")]
    want = profile_digest(pinned)
    eff, why = _read_json(managed_dir() / "model-profile.json")
    if why or not isinstance(eff, dict):
        return ["MODEL_PROFILE_MISMATCH: pinned %s, the runtime profile %s is %s"
                % (want[:16], managed_dir() / "model-profile.json", why or "malformed")]
    got = profile_digest(eff)
    if got != want:
        fields = _diff({k: pinned.get(k) for k in ("default_model", "profiles")},
                       {k: eff.get(k) for k in ("default_model", "profiles")})
        return ["MODEL_PROFILE_MISMATCH: pinned %s, runtime %s; %s" % (want[:16], got[:16], "; ".join(fields[:3]))]
    cfg = _effective_config_gaps(pinned)
    if cfg:
        return ["MODEL_PROFILE_MISMATCH: the generated worker config does not carry the pinned profile %s: %s"
                % (want[:16], "; ".join(cfg[:3]))]
    return []


IMAGE_STAMP = Path("/opt/rhoai3/080.pins")


def runtime_gaps(root: Path, stamp: Path | None = None) -> list[str]:
    """A governed run needs the Hermes runtime its harness was qualified on:
    the image's build stamp names the patched source tree (B11/B3/B4/R2 patch
    series), and it must be the one `pins.json` `hermes_agent.patched_tree`
    names. An unpatched or other image would run without the loop halt, the
    truncation and quota stops, or the request pacer. Legacy runs: no gap."""
    if declared(root) is None:
        return []
    try:
        want = str(((json.loads((Path(root) / ".hermes/pins.json").read_text(encoding="utf-8")).get("pins") or {})
                    .get("hermes_agent") or {}).get("patched_tree") or "")
    except (OSError, ValueError):
        want = ""
    if not want:
        return ["HERMES_RUNTIME_UNPINNED: .hermes/pins.json names no hermes_agent.patched_tree for this governed run"]
    stamp = Path(stamp or IMAGE_STAMP)
    try:
        lines = stamp.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return ["HERMES_RUNTIME_UNPATCHED: the image build stamp %s is unreadable (%s); expected patched tree %s"
                % (stamp, exc.__class__.__name__, want[:12])]
    got = next((l.split("=", 1)[1].strip() for l in lines if l.startswith("hermes.patched_tree=")), "")
    if got != want:
        return ["HERMES_RUNTIME_UNPATCHED: the image's Hermes tree is %s, the harness is qualified on %s (%s)"
                % (got[:12] or "unpatched", want[:12], stamp)]
    return []


def run_gaps(root: Path) -> list[str]:
    """Everything a governed run must still be what it was created as."""
    out: list[str] = []
    for g in release_gaps(root) + profile_gaps(root):
        if g not in out:
            out.append(g)
    return out
