"""Typed repair execution for an issued unit (V26-1): planning, the pinned
executor, complete-diff inspection, journaled application and the record
(not a CLI; typed-repair.py and brief.py use it).

A compat-mapping `migration_recipes` row whose implementation.kind is
`typed-repair` names an operation of the harness executor
(fix-until-green/typed-repair, OpenRewrite LST, our own recipes). For the ISSUED
unit only, `plan()` derives the executor requests from facts already sealed or
planned -- the scope's implementation obligations and handler-parameter
targets, and the plan-semantics requirements the card owns -- and never widens
the write set: a candidate path outside it is reported, not requested.

`execute()` runs each request against the current candidate, reads the
complete staged patch, refuses it when any path is outside the issued write
set or the request's candidates or when the candidate changed underneath, and
applies it through a journal so an interruption never leaves part of a patch
(`recover()` restores the originals first). Every attempt writes one record
(rhoai3.typed-repair-record/v1). The record is evidence of an edit, never of
the requirement: acceptance stays run-verify.sh + advance.py, and a no-op
("already-in-required-form") establishes nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from _loop_common import candidate_sha256, ensure_hermes_lib

ensure_hermes_lib()
from planner.canonical import load_json  # noqa: E402
from planner.paths import LOOP_DIR  # noqa: E402

KIND = "typed-repair"
RECORD_SCHEMA = "rhoai3.typed-repair-record/v1"
REQUEST_SCHEMA = "rhoai3.typed-repair-request/v1"
RECORD_DIR = LOOP_DIR / "typed-repair"
JOURNAL = RECORD_DIR / "apply-journal.json"
LEDGER = RECORD_DIR / "records.jsonl"
CLASSPATH = Path("verification") / "build" / ".work" / "classpath.txt"
FROZEN_CLASSPATH = Path("evidence") / "build" / "classpath.txt"
CATALOG = Path(".hermes") / "planning" / "catalogs" / "compat-mapping.json"
PINS = Path(".hermes") / "pins.json"
IMAGE_JAR = Path("/opt/rhoai3/typed-repair/typed-repair.jar")
UCB = "org.springframework.web.util.UriComponentsBuilder"
TIMEOUT_S = 600
COMMAND = "python3 .hermes/skills/migration/fix-until-green/scripts/typed-repair.py --root . --cluster %s"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_text(p: Path) -> str:
    return _sha(p) if p.is_file() else ""


def stem(cluster_id: str) -> str:
    return str(cluster_id).replace(":", "-").replace("/", "-")


def typed_recipes(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The migration_recipes rows executed by the typed executor."""
    rows = (catalog or {}).get("migration_recipes") or {}
    return {str(k): dict(v) for k, v in rows.items()
            if k != "note" and isinstance(v, dict) and (v.get("implementation") or {}).get("kind") == KIND}


def _catalog(root: Path) -> dict[str, Any]:
    p = Path(root) / CATALOG
    try:
        return load_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def scope_rows(root: Path, scope: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(implementation obligations, target symbols) of a sealed scope, an
    objective envelope's constituents included (each by its own sealed
    inventory, as worklist.objective_children reads it)."""
    if not isinstance(scope, dict):
        return [], []
    docs = [scope]
    if scope.get("children"):
        try:
            from planner.worklist import objective_children
            docs += [d for _c, d in objective_children(Path(root), scope) if isinstance(d, dict)]
        except Exception:
            pass
    impl: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for d in docs:
        impl += [r for r in d.get("implementation_obligations") or [] if isinstance(r, dict)]
        targets += [t for t in d.get("target_symbols") or [] if isinstance(t, dict)]
    return impl, targets


def owned_requirements(root: Path, write_set: list[str], own: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The planned requirements (plan semantics v1) this card owns, with their facts."""
    from planner.paths import PLAN_SEMANTICS
    p = Path(root) / PLAN_SEMANTICS
    if not p.is_file():
        return []
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return []
    out = []
    for r in ((doc.get("plan") or {}).get("requirements") or []):
        if not isinstance(r, dict) or r.get("status") != "applicable":
            continue
        if own is not None:
            if str(r.get("id")) not in own.get("requirements", set()):
                continue
        elif not set(r.get("paths") or []) & set(write_set):
            continue
        out.append(r)
    return out


def _site_of(subject: str, path: str) -> dict[str, str] | None:
    """<type>#<member>(<params>)|<parameter> -> a handler site."""
    if "#" not in subject or "|" not in subject:
        return None
    head, param = subject.rsplit("|", 1)
    typ, member = head.split("#", 1)
    return {"path": path, "type": typ, "member": member.split("(", 1)[0], "parameter": param}


def plan(root: Path, scope: dict[str, Any] | None, write_set: list[str], requirements: list[dict[str, Any]],
         catalog: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """(executor requests, skipped) for the issued unit, from sealed and planned facts only."""
    recipes = typed_recipes(catalog if catalog is not None else _catalog(root))
    ws = set(write_set)
    requests: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    impl, targets = scope_rows(root, scope)

    frag = recipes.get("spring-data-fragment-impl")
    if frag:
        rows = [dict(r, _from="seal") for r in impl if isinstance(r.get("cdi"), dict) and r.get("verify") != "template"]
        for req in requirements:
            if str((req.get("recipe") or {}).get("id") or "") == "spring-data-fragment-impl":
                try:
                    from planner.requirement_checks import _fragment_rows
                    rows += [dict(r, _from="requirement:%s" % req.get("id")) for r in _fragment_rows(req)]
                except Exception as exc:  # the planner's own row builder is the only source of the contract
                    skipped.append({"recipe": "spring-data-fragment-impl", "reason": "requirement %s: %s" % (req.get("id"), exc)})
        seen: set[str] = set()
        for r in rows:
            key = "%s|%s" % (r.get("type"), r.get("path"))
            if key in seen:
                continue
            seen.add(key)
            path = str(r.get("path") or "")
            if path not in ws:
                skipped.append({"recipe": "spring-data-fragment-impl",
                                "reason": "%s is outside the issued write set; the executor never widens it" % path})
                continue
            cdi = r.get("cdi") or {}
            requests.append({
                "recipe": "spring-data-fragment-impl", "recipe_version": str(frag.get("version") or ""),
                "operation": str((frag.get("implementation") or {}).get("operation") or ""),
                "source": r["_from"], "candidate_paths": [path],
                "target": {"parent": r.get("parent"), "type": r.get("type"), "path": path,
                           "resolution": str(r.get("resolution") or "owed"), "scope": cdi.get("scope"),
                           "typed": cdi.get("typed"), "types": list(cdi.get("types") or [])},
            })

    uri = recipes.get("handler-uri-parameter")
    if uri:
        sites: dict[tuple[str, str, str, str], dict[str, str]] = {}
        for t in targets:
            if t.get("handler_parameter") and str(t.get("from") or "") == UCB:
                for s in t.get("sites") or []:
                    if isinstance(s, dict):
                        site = {"path": str(s.get("path") or ""), "type": str(s.get("type") or ""),
                                "member": str(s.get("member") or ""), "parameter": str(s.get("parameter") or "")}
                        sites[(site["path"], site["type"], site["member"], site["parameter"])] = site
        for req in requirements:
            if str((req.get("recipe") or {}).get("id") or "") != "handler-uri-parameter":
                continue
            if str((req.get("facts") or {}).get("parameter_type") or "") != UCB:
                continue
            paths = list(req.get("paths") or [])
            site = _site_of(str(req.get("subject") or ""), paths[0] if len(paths) == 1 else "")
            if site and site["path"]:
                sites[(site["path"], site["type"], site["member"], site["parameter"])] = site
            else:
                skipped.append({"recipe": "handler-uri-parameter", "reason": "requirement %s names no single handler site"
                                % req.get("id")})
        inside = [s for k, s in sorted(sites.items()) if s["path"] in ws]
        for k, s in sorted(sites.items()):
            if s["path"] not in ws:
                skipped.append({"recipe": "handler-uri-parameter",
                                "reason": "%s is outside the issued write set; the executor never widens it" % s["path"]})
        if inside:
            requests.append({
                "recipe": "handler-uri-parameter", "recipe_version": str(uri.get("version") or ""),
                "operation": str((uri.get("implementation") or {}).get("operation") or ""),
                "source": "seal+requirements", "candidate_paths": sorted({s["path"] for s in inside}),
                "target": {"sites": inside},
            })
    return requests, skipped


# ---------------------------------------------------------------- executor identity

def pins(root: Path) -> dict[str, Any]:
    p = Path(root) / PINS
    try:
        return ((load_json(p) or {}).get("pins") or {}).get("typed_repair") or {}
    except (OSError, ValueError):
        return {}


def executor(root: Path) -> dict[str, Any]:
    """{jar, sha256, pinned, reason}: the pinned executor jar, or why none may run.
    RHOAI3_TYPED_REPAIR_JAR names a jar explicitly; a qualification test may set
    RHOAI3_TYPED_REPAIR_UNPINNED=1 to run a freshly built jar, and its record then
    says pinned: false -- a real run never does."""
    pin = pins(root)
    want = str((pin.get("executor") or {}).get("jar_sha256") or "")
    cands = [Path(os.environ["RHOAI3_TYPED_REPAIR_JAR"])] if os.environ.get("RHOAI3_TYPED_REPAIR_JAR") else []
    cands += [IMAGE_JAR]   # never a build inside the harness tree: it would be release drift
    jar = next((c for c in cands if c.is_file()), None)
    if jar is None:
        return {"jar": "", "sha256": "", "pinned": False,
                "reason": "the typed repair executor is not installed (%s)" % ", ".join(str(c) for c in cands)}
    got = _sha(jar)
    if os.environ.get("RHOAI3_TYPED_REPAIR_UNPINNED") == "1":
        return {"jar": str(jar), "sha256": got, "pinned": False, "reason": ""}
    if not want or got != want:
        return {"jar": str(jar), "sha256": got, "pinned": False,
                "reason": "the executor jar %s (sha256 %s) is not the pinned typed_repair.executor.jar_sha256 %s"
                          % (jar, got[:12], want[:12] or "(none)")}
    return {"jar": str(jar), "sha256": got, "pinned": True, "reason": ""}


# ---------------------------------------------------------------- inputs

def sources(root: Path) -> list[str]:
    """Every Java source the build compiles: src/main/java and the generator outputs."""
    from planner.dest_model import generated_source_dirs
    root = Path(root)
    out = sorted(str(p.relative_to(root)) for p in (root / "src" / "main" / "java").rglob("*.java"))
    for d in generated_source_dirs(root):
        out += sorted(str(p.relative_to(root)) if str(p).startswith(str(root)) else str(p) for p in Path(d).rglob("*.java"))
    return out


def classpath(root: Path) -> tuple[list[str], str]:
    p = Path(root) / CLASSPATH
    if not p.is_file() or not p.stat().st_size:
        return [], ""
    text = p.read_text(encoding="utf-8").strip()
    return [e for e in text.split(os.pathsep) if e], _sha(p)


def api_jars(root: Path, fqn: str) -> list[dict[str, str]]:
    """The frozen SOURCE's own jar(s) that define `fqn` (evidence/build/classpath.txt,
    recorded by M1): the retired API is attributed from the source's dependency,
    never from a guess. [] when M1 recorded no classpath or none defines it."""
    p = Path(root) / FROZEN_CLASSPATH
    if not p.is_file():
        return []
    entry = fqn.replace(".", "/") + ".class"
    out = []
    for e in p.read_text(encoding="utf-8").strip().split(os.pathsep):
        if not e.endswith(".jar") or not os.path.isfile(e):
            continue
        try:
            with zipfile.ZipFile(e) as z:
                if entry in z.namelist():
                    out.append({"jar": e, "sha256": _sha(Path(e)), "provides": fqn, "origin": str(FROZEN_CLASSPATH)})
        except (OSError, zipfile.BadZipFile):
            continue
    return out


# ---------------------------------------------------------------- journaled application

def recover(root: Path) -> dict[str, Any] | None:
    """An interrupted application: put every file back to its recorded original
    (nothing of a partial patch survives), then drop the journal."""
    j = Path(root) / JOURNAL
    if not j.is_file():
        return None
    try:
        doc = load_json(j)
    except (OSError, ValueError):
        doc = {}
    restored = []
    for f in doc.get("files") or []:
        dst = Path(root) / str(f.get("path") or "")
        bak = Path(root) / str(f.get("backup") or "")
        if bak.is_file() and _sha_text(dst) != str(f.get("before_sha256") or ""):
            shutil.copyfile(bak, dst)
            restored.append(str(f.get("path")))
    j.unlink()
    return {"recovered": True, "attempt": doc.get("attempt"), "restored": restored,
            "detail": "an interrupted typed-repair application was rolled back to the candidate it started from"}


def _apply(root: Path, attempt_dir: Path, staged: dict[str, Path], before: dict[str, str],
           crash_after: int | None = None) -> None:
    """Write every staged file, journaled. `crash_after` (tests only) stops
    after that many files to simulate an interruption."""
    bak_dir = attempt_dir / "backup"
    files = []
    for rel in sorted(staged):
        b = bak_dir / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(root) / rel, b)
        files.append({"path": rel, "before_sha256": before[rel], "after_sha256": _sha(staged[rel]),
                      "backup": str(b.relative_to(root))})
    j = Path(root) / JOURNAL
    j.parent.mkdir(parents=True, exist_ok=True)
    j.write_text(json.dumps({"attempt": attempt_dir.name, "files": files, "started_at": _now()}, indent=2), encoding="utf-8")
    for n, rel in enumerate(sorted(staged)):
        if crash_after is not None and n >= crash_after:
            raise KeyboardInterrupt("simulated interruption")
        dst = Path(root) / rel
        tmp = dst.with_name(dst.name + ".typed-repair.tmp")
        shutil.copyfile(staged[rel], tmp)
        os.replace(tmp, dst)
    j.unlink()


Invoke = Callable[[Path, Path, Path], "subprocess.CompletedProcess[str]"]


def _java(jar: Path, request: Path, out: Path) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(["java", "-jar", str(jar), "--request", str(request), "--out", str(out)],
                          text=True, capture_output=True, timeout=TIMEOUT_S)


def execute(root: Path, cluster_id: str, requests: list[dict[str, Any]], write_set: list[str], *,
            invoke: Invoke | None = None, exe: dict[str, Any] | None = None,
            crash_after: int | None = None) -> list[dict[str, Any]]:
    """Run each request; inspect; apply or refuse; record. Returns the records."""
    root = Path(root)
    records = []
    exe = exe if exe is not None else executor(root)
    cp, cp_sha = classpath(root)
    for req in requests:
        t0 = time.time()
        rec: dict[str, Any] = {
            "schema": RECORD_SCHEMA, "at": _now(), "cluster": cluster_id,
            "card": (os.environ.get("HERMES_KANBAN_TASK") or "").strip(),
            "run": (os.environ.get("HERMES_KANBAN_RUN_ID") or "").strip(),
            "recipe": {"id": req["recipe"], "version": req.get("recipe_version"), "operation": req.get("operation")},
            "source": req.get("source"), "target": req.get("target"),
            "executor": {k: exe.get(k) for k in ("jar", "sha256", "pinned")},
            "classpath": {"path": str(CLASSPATH), "sha256": cp_sha, "entries": len(cp)},
            "candidate": {"before": candidate_sha256(root)},
            "establishes_requirement": False,
            "acceptance": "run-verify.sh --mode acceptance and advance.py judge this candidate; this record is not a check",
        }
        outcome, reasons, changed, matched = "", [], [], []
        if exe.get("reason"):
            outcome, reasons = "unresolved", [exe["reason"]]
        elif not cp:
            outcome, reasons = "unresolved", ["no measured classpath of this candidate (%s): run-verify.sh writes it" % CLASSPATH]
        attempt = root / RECORD_DIR / stem(cluster_id) / ("%s-%d" % (req["recipe"], int(t0 * 1000)))
        if not outcome:
            attempt.mkdir(parents=True, exist_ok=True)
            api = api_jars(root, UCB) if req["recipe"] == "handler-uri-parameter" else []
            rec["api_classpath"] = api
            before = {p: _sha_text(root / p) for p in req["candidate_paths"]}
            body = {"schema": REQUEST_SCHEMA, "recipe": req["recipe"], "recipe_version": req.get("recipe_version"),
                    "operation": req.get("operation"), "root": str(root), "sources": sources(root), "classpath": cp,
                    "api_classpath": [a["jar"] for a in api], "allowed_paths": sorted(write_set),
                    "candidate_paths": req["candidate_paths"], "target": req["target"]}
            (attempt / "request.json").write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
            out = attempt / "out"
            try:
                proc = (invoke or (lambda j, r, o: _java(j, r, o)))(Path(exe["jar"]), attempt / "request.json", out)
                rec["executor_rc"] = proc.returncode
                result = load_json(out / "result.json") if (out / "result.json").is_file() else None
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                result, proc = None, None
                reasons.append("the executor did not complete: %s" % exc)
            if not isinstance(result, dict):
                outcome = "failed"
                reasons.append("the executor wrote no result record%s" % (
                    (": " + (proc.stderr or proc.stdout)[-400:]) if proc is not None else ""))
            else:
                outcome = str(result.get("outcome") or "failed")
                reasons += [str(r) for r in result.get("reasons") or []]
                matched = list(result.get("matched_symbols") or [])
                rec["executor_result"] = {k: result.get(k) for k in ("executor", "recipe", "actions", "parse",
                                                                     "required_symbols", "elapsed_ms")}
                if outcome == "applied":
                    outcome, changed = _inspect_and_apply(root, req, write_set, result, out, before, attempt, reasons,
                                                          crash_after)
        rec.update({"outcome": outcome, "reasons": reasons, "matched_symbols": matched, "changed_files": changed,
                    "elapsed_ms": int((time.time() - t0) * 1000)})
        rec["candidate"]["after"] = candidate_sha256(root)
        rec["candidate_files"] = {p: _sha_text(root / p) for p in req["candidate_paths"]}
        if outcome == "already-in-required-form":
            rec["note"] = "no edit: the required form is already present; a no-op establishes nothing"
        records.append(rec)
        _write_record(root, cluster_id, rec, attempt if attempt.is_dir() else None)
    return records


def _inspect_and_apply(root: Path, req: dict[str, Any], write_set: list[str], result: dict[str, Any], out: Path,
                       before: dict[str, str], attempt: Path, reasons: list[str],
                       crash_after: int | None) -> tuple[str, list[str]]:
    """The complete staged diff, checked against the grant, then applied whole or not at all."""
    changes = [c for c in result.get("changes") or [] if isinstance(c, dict)]
    paths = [str(c.get("path") or "") for c in changes]
    staged_root = out / "staged"
    on_disk = sorted(str(p.relative_to(staged_root)) for p in staged_root.rglob("*") if p.is_file()) if staged_root.is_dir() else []
    bad = [p for p in paths if p not in write_set or p not in req["candidate_paths"]]
    if not changes:
        reasons.append("the executor reported applied but staged no change")
        return "failed", []
    if bad or sorted(paths) != on_disk:
        reasons.append("the staged patch touches %s outside the issued write set or the request's candidates (staged %s): "
                       "refused, nothing applied" % (", ".join(bad) or "unlisted files", ", ".join(on_disk)))
        return "failed", []
    moved = [p for p in paths if _sha_text(Path(root) / p) != before.get(p)]
    if moved:
        reasons.append("the candidate changed under the executor (%s): refused, nothing applied" % ", ".join(moved))
        return "failed", []
    patch = (out / "patch.diff").read_text(encoding="utf-8") if (out / "patch.diff").is_file() else ""
    if not patch.strip():
        reasons.append("the executor staged files but no complete diff to inspect")
        return "failed", []
    try:
        _apply(root, attempt, {p: staged_root / p for p in paths}, before, crash_after)
    except KeyboardInterrupt:
        raise
    except OSError as exc:
        recover(root)
        reasons.append("the application failed and was rolled back: %s" % exc)
        return "failed", []
    return "applied", sorted(paths)


def _write_record(root: Path, cluster_id: str, rec: dict[str, Any], attempt: Path | None) -> None:
    d = Path(root) / RECORD_DIR
    d.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, indent=2, sort_keys=True)
    if attempt is not None:
        (attempt / "record.json").write_text(text + "\n", encoding="utf-8")
    latest = d / (stem(cluster_id) + ".json")
    doc = {}
    if latest.is_file():
        try:
            doc = load_json(latest)
        except (OSError, ValueError):
            doc = {}
    doc = dict(doc or {}, schema=RECORD_SCHEMA + "#latest", cluster=cluster_id)
    doc.setdefault("by_recipe_target", {})
    doc["by_recipe_target"][_target_key(rec)] = rec
    tmp = latest.with_name(latest.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, latest)
    with open(d / LEDGER.name, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def _target_key(rec: dict[str, Any]) -> str:
    return "%s|%s" % (rec["recipe"]["id"], json.dumps(rec.get("target"), sort_keys=True))


def latest(root: Path, cluster_id: str) -> list[dict[str, Any]]:
    p = Path(root) / RECORD_DIR / (stem(cluster_id) + ".json")
    if not p.is_file():
        return []
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return []
    return [r for _k, r in sorted((doc.get("by_recipe_target") or {}).items()) if isinstance(r, dict)]


def brief_section(root: Path, cluster_id: str, requests: list[dict[str, Any]], skipped: list[dict[str, str]],
                  catalog: dict[str, Any]) -> dict[str, Any] | None:
    """What brief.py shows: the FIRST ACTION while a request has no current
    record, the unresolved reasons that send the unit back to the bounded agent
    procedure, and the next step after an applied or already-correct result."""
    if not requests and not skipped:
        return None
    recs = {_target_key(r): r for r in latest(root, cluster_id)}
    rows, pending = [], []
    recipes = typed_recipes(catalog)
    for req in requests:
        r = recs.get(_target_key({"recipe": {"id": req["recipe"]}, "target": req["target"]}))
        # current: the files this request covers are exactly as the last attempt left them
        current = bool(r) and bool(r.get("candidate_files")) and all(
            _sha_text(Path(root) / p) == h for p, h in (r.get("candidate_files") or {}).items())
        fallback = (recipes.get(req["recipe"]) or {}).get("implementation", {}).get("fallback") or {}
        row = {"recipe": req["recipe"], "candidates": req["candidate_paths"],
               "last_outcome": r.get("outcome") if r else None, "current": current}
        if r and current and r.get("outcome") in ("unresolved", "failed"):
            row["unresolved"] = r.get("reasons") or []
            row["fallback"] = ("the bounded agent repair (REQUIRED SHAPE, %s): %s"
                               % (fallback.get("kind") or "agent-bounded", " ".join(str(fallback.get("architecture") or "").split())))
        elif r and current and r.get("outcome") == "applied":
            row["next"] = ("applied %s: run run-verify.sh --mode acceptance, then advance.py -- the edit is judged like any "
                           "other; do not re-run the executor" % ", ".join(r.get("changed_files") or []))
        elif r and current and r.get("outcome") == "already-in-required-form":
            row["next"] = "already in the required form (no edit; this establishes nothing): the checks still judge it"
        else:
            pending.append(req["recipe"])
        rows.append(row)
    out = {"requests": rows, "skipped": skipped,
           "rule": ("The typed executor applies the catalog's qualified transformation inside the issued write set "
                    "and records it; it never completes the card. Unresolved returns to the bounded agent repair with "
                    "the reason below; no extra attempt is granted.")}
    if pending:
        out["first_action"] = COMMAND % cluster_id
    return out


def digest_lines(section: dict[str, Any] | None) -> list[str]:
    if not section:
        return []
    out = []
    if section.get("first_action"):
        out.append("FIRST ACTION (typed repair, %s): %s -- then run-verify.sh --mode acceptance and advance.py"
                   % (", ".join(sorted({r["recipe"] for r in section["requests"] if r.get("last_outcome") is None
                                        or not r.get("current")})), section["first_action"]))
    for r in section.get("requests") or []:
        if r.get("unresolved"):
            out.append("TYPED REPAIR UNRESOLVED (%s, %s): %s" % (r["recipe"], ", ".join(r["candidates"]),
                                                               "; ".join(r["unresolved"])[:600]))
            out.append("  continue with %s" % r.get("fallback", "the bounded agent repair")[:900])
        elif r.get("next"):
            out.append("TYPED REPAIR (%s): %s" % (r["recipe"], r["next"]))
    for s in section.get("skipped") or []:
        out.append("TYPED REPAIR NOT REQUESTED (%s): %s" % (s["recipe"], s["reason"]))
    return out
