"""The run's activation, held OUTSIDE the product repository (B8).

v12 (2026-09-24, card t_b33f25fa): the pilot seal lived only as dest-init's
uncommitted edit of `.hermes/pins.json`. A worker ran
`git checkout -- .hermes/pins.json`, the committed golden `not-activated`
came back, admission turned INCONCLUSIVE PLANNER_NOT_ACTIVATED after an
ACCEPTED step, K4 minted nothing, and the board went idle with `git status`
clean.

So the activation is run control, not a harness default:

* `activation.json` -- the planner block ({activation, pilot{...}}) for THIS
  run, written by dest-init (the authorization) and by the M1 bind (the
  bundle digest), each write atomic and the file left read-only;
* `journal.jsonl` -- one line per event (recorded, bound), append-only, so a
  missing activation can be told from one that never existed.

Both live under `<projects>/.platform/run-control/` (the platform's own tree
beside the destination), which no `git checkout`, `reset`, `stash` or
`clean` inside the destination can reach. Readers never fall back to the
golden pins once the run-control directory exists. The directory can be
moved for tests with RHOAI3_RUN_CONTROL_DIR.

What this is NOT: an authority boundary against a process with the
workspace's own UID. A same-UID file is accidental-Git protection plus K2's
refusal of worker writes and mutating git; a writer outside the worker's
write authority is a platform lifecycle change still to be made.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any

ACTIVATION = "activation.json"
JOURNAL = "journal.jsonl"
RELEASE = "release.json"
SCHEMA = "rhoai3.run-control/v1"
MISSING = "run-control-missing"


def run_control_dir(root: Path) -> Path:
    env = (os.environ.get("RHOAI3_RUN_CONTROL_DIR") or "").strip()
    return Path(env) if env else Path(root).resolve().parent / ".platform" / "run-control"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_readonly(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.chmod(0o644)
        tmp.unlink()
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(0o444)
    if path.exists():
        path.chmod(0o644)
    os.replace(tmp, path)


def journal(root: Path) -> list[dict[str, Any]]:
    p = run_control_dir(root) / JOURNAL
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _append(root: Path, row: dict[str, Any]) -> None:
    p = run_control_dir(root) / JOURNAL
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(row, at=row.get("at") or _now()), sort_keys=True) + "\n")


def read_activation(root: Path) -> dict[str, Any] | None:
    """The run's planner block, or None when no activation file exists."""
    p = run_control_dir(root) / ACTIVATION
    if not p.is_file():
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    planner = doc.get("planner") if isinstance(doc, dict) else None
    return planner if isinstance(planner, dict) else None


def write_activation(root: Path, planner: dict[str, Any], event: str, detail: str = "") -> None:
    _write_readonly(run_control_dir(root) / ACTIVATION, {"schema": SCHEMA, "planner": planner, "written_at": _now()})
    seal = planner.get("pilot") if isinstance(planner.get("pilot"), dict) else {}
    _append(root, {"event": event, "activation": planner.get("activation"), "run_id": seal.get("run_id", ""),
                   "evidence_bundle_sha256": seal.get("evidence_bundle_sha256", ""), "detail": detail})


def in_use(root: Path) -> bool:
    """Run control governs this destination: dest-init created it."""
    return run_control_dir(root).is_dir()


def planner_block(root: Path, repo_planner: dict[str, Any]) -> dict[str, Any]:
    """The planner block every reader must use.

    Without a run-control directory (a destination created before it, a
    fixture) the repository's own pins answer, exactly as before. With one,
    the repository's pins are never read for activation: the activation file
    answers, and when it is gone the journal says whether it ever existed."""
    if not in_use(root):
        return repo_planner
    act = read_activation(root)
    if act is not None:
        return act
    events = journal(root)
    last = events[-1] if events else {}
    return {"activation": MISSING, "note": "run control %s has no %s" % (run_control_dir(root), ACTIVATION),
            "last_event": last}


def missing_gap(root: Path, block: dict[str, Any]) -> str:
    last = block.get("last_event") or {}
    return ("RUN_ACTIVATION_MISSING: run %s was %s at %s to bundle %s; expected control object %s, observed missing; "
            "successor dispatch suspended"
            % (last.get("run_id") or "unknown", last.get("event") or "never recorded", last.get("at") or "unknown time",
               str(last.get("evidence_bundle_sha256") or "unbound")[:16] or "unbound",
               run_control_dir(root) / ACTIVATION))


def record_release(root: Path, digest: str, source: str) -> None:
    """The harness release this run was created with (B10), written once."""
    p = run_control_dir(root) / RELEASE
    if p.is_file():
        return
    _write_readonly(p, {"schema": SCHEMA, "harness_release_sha256": digest, "source": source, "recorded_at": _now()})
    _append(root, {"event": "release-recorded", "detail": digest})


def recorded_release(root: Path) -> str:
    p = run_control_dir(root) / RELEASE
    if not p.is_file():
        return ""
    doc = json.loads(p.read_text(encoding="utf-8"))
    return str((doc or {}).get("harness_release_sha256") or "")


RELEASE_TREES = ("kernel", "lib", "skills")


def harness_release_digest(root: Path) -> str:
    """One digest over the harness the run executes: every file under
    .hermes/{kernel,lib,skills}, by relative path and content. Bytecode caches
    are not part of a release."""
    import hashlib
    h = hashlib.sha256()
    base = Path(root) / ".hermes"
    for tree in RELEASE_TREES:
        for p in sorted((base / tree).rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            h.update(p.relative_to(base).as_posix().encode("utf-8") + b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def release_gaps(root: Path) -> list[str]:
    """B10: the run executes the harness release it was created with. Empty
    when run control records none (older destinations) or they agree."""
    if not in_use(root):
        return []
    want = recorded_release(root)
    if not want:
        return []
    got = harness_release_digest(root)
    if got == want:
        return []
    return ["HARNESS_RELEASE_MISMATCH: expected %s (recorded at run creation in %s), observed %s; no task dispatched. "
            "A harness change mid-run is an assisted continuation and must be recorded with rebase_release, never "
            "picked up silently" % (want[:16], run_control_dir(root) / RELEASE, got[:16])]


def rebase_release(root: Path, reason: str) -> str:
    """The assisted-maintenance route: after an Operator-installed harness,
    record the new release digest with the reason. Journaled permanently, so
    the run's record says it was assisted."""
    got = harness_release_digest(root)
    old = recorded_release(root)
    _write_readonly(run_control_dir(root) / RELEASE, {"schema": SCHEMA, "harness_release_sha256": got,
                                                       "source": "assisted-rebase", "previous": old,
                                                       "reason": reason, "recorded_at": _now()})
    _append(root, {"event": "release-rebased-assisted", "detail": "%s -> %s: %s" % (old[:16], got[:16], reason)})
    return got


PROFILE = "profile.json"


def managed_profile_path() -> Path:
    return Path(os.environ.get("HERMES_MANAGED_DIR") or "/projects/.platform/hermes") / "model-profile.json"


def _read_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def record_profile(root: Path, source: str) -> None:
    """B4: pin the model profile the run's worker config was generated from,
    once, on the run's first start."""
    p = run_control_dir(root) / PROFILE
    cur = _read_profile(managed_profile_path())
    if p.is_file() or not cur.get("digest"):
        return
    _write_readonly(p, {"schema": SCHEMA, "profile": cur, "source": source, "recorded_at": _now()})
    _append(root, {"event": "profile-recorded", "detail": cur["digest"]})


def _diff(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out.extend(_diff(a.get(k), b.get(k), "%s.%s" % (path, k) if path else str(k)))
        return out
    return [] if a == b else ["%s: expected %s, got %s" % (path, json.dumps(a), json.dumps(b))]


def profile_gaps(root: Path) -> list[str]:
    """B4: the worker config in force was generated from the profile the run
    was created with. Empty without a pin (older destinations)."""
    if not in_use(root):
        return []
    pinned = _read_profile(run_control_dir(root) / PROFILE).get("profile") or {}
    if not pinned.get("digest"):
        return []
    cur = _read_profile(managed_profile_path())
    if cur.get("digest") == pinned["digest"]:
        return []
    fields = _diff({k: pinned.get(k) for k in ("default_model", "profiles")},
                   {k: cur.get(k) for k in ("default_model", "profiles")})
    return ["MODEL_PROFILE_MISMATCH: profile %s pinned at run creation, runtime %s; %s; source %s. A model or "
            "sampling change mid-run is a new run or an assisted continuation, never picked up silently"
            % (pinned["digest"][:16], str(cur.get("digest") or "missing")[:16],
               "; ".join(fields[:3]) or "the runtime profile is missing", managed_profile_path())]


def run_gaps(root: Path) -> list[str]:
    """Everything a run must still be what it was created as (B10 + B4)."""
    return release_gaps(root) + profile_gaps(root)
