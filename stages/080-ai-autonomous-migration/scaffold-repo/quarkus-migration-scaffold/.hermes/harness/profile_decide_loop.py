#!/usr/bin/env python3
"""ADR-32 / O-PROFSEATARCH — harness-owned PROFILE decide loop.

Iterates undecided profile-units: project ADR-31 anchors → classify →
profile_roles.upsert. Replaces MiniMax N=20 mchat batch seats as the
happy path (hourly quota is not helped by more MiniMax sessions).

Backends (O-PROFCLASSIFYVAL): each returns a judgment value; harness upserts.
  dry-run         — deterministic fixture classify (instruments)
  opencode-qwen   — OpenCode worker, JSON judgment per unit (default live)
  hermes-orch     — MiniMax Hermes escape (JSON judgment; not upsert CLI)

Usage:
  profile_decide_loop.py run --root DIR --legacy PATH \\
      [--backend opencode-qwen|dry-run|hermes-orch] \\
      [--max-units N] [--unit-timeout SECS]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from model import load as model_load  # type: ignore
from model import profile_units  # type: ignore
from profile_anchors import anchors_for_unit  # type: ignore
from profile_roles import (  # type: ignore
    evaluate_roles,
    upsert_decision,
)

REDESIGN_HINTS = (
    "@Service",
    "@Component",
    "@RestController",
    "@Controller",
    "@Path",
    "@ApplicationScoped",
    "@Singleton",
    "@SpringBootApplication",
    "@Repository",
    "@Configuration",
)


def _undecided_units(root: Path, legacy: Optional[str]) -> list[dict]:
    model = model_load(root)
    ev = evaluate_roles(root, legacy=legacy)
    need = set(ev.get("undecided") or [])
    out = []
    for u in profile_units(model):
        fqn = u.get("legacy_fqn") or u.get("key") or ""
        if fqn in need:
            out.append(u)
    return out


def _pick_dry_run(unit: dict, anchors: list[dict]) -> dict[str, Any]:
    """Specimen-agnostic heuristic for instruments / offline."""
    if not anchors:
        raise RuntimeError(f"no anchors for {unit.get('legacy_fqn')}")
    role = "HARVEST"
    chosen = anchors[0]
    for a in anchors:
        tok = str(a.get("token") or "")
        if any(h in tok for h in REDESIGN_HINTS):
            role = "REDESIGN"
            chosen = a
            break
    # Stereotype on declaration class name alone is weak; prefer annotation hits.
    simple = (unit.get("legacy_fqn") or "").rsplit(".", 1)[-1]
    if simple.endswith(("Service", "ServiceImpl", "Resource", "Controller", "Endpoint")):
        role = "REDESIGN"
    if simple.endswith(("Application",)) or "SpringBootApplication" in str(
        chosen.get("token")
    ):
        role = "REDESIGN"
    return {
        "role": role,
        "rationale": f"dry-run: {role} from projected anchor {chosen.get('kind')}",
        "path": chosen["path"],
        "line": int(chosen["line"]),
        "token": chosen["token"],
    }


def _parse_classify_payload(blob: str, anchors: list[dict]) -> Optional[dict[str, Any]]:
    """O-PROFCLASSIFYVAL — extract a judgment object from model text (not tool side-effects)."""
    # Prefer fenced or bare JSON objects containing "role".
    candidates: list[str] = []
    for m in re.finditer(r"\{[^{}]*\"role\"[^{}]*\}", blob, re.S):
        candidates.append(m.group(0))
    saw_role_json = False
    for raw in candidates:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        role = str(obj.get("role") or "").upper()
        if role not in ("HARVEST", "REDESIGN"):
            continue
        saw_role_json = True
        path = str(obj.get("path") or "")
        try:
            line = int(obj.get("line"))
        except (TypeError, ValueError):
            continue
        token = str(obj.get("token") or "")
        rationale = str(obj.get("rationale") or f"classify: {role}").strip()
        # Membership: must match a projected anchor exactly.
        for a in anchors:
            if (
                str(a.get("path")) == path
                and int(a.get("line")) == line
                and str(a.get("token")) == token
            ):
                return {
                    "role": role,
                    "rationale": rationale,
                    "path": path,
                    "line": line,
                    "token": token,
                }
    # Role JSON present but non-member / malformed evidence — refuse (do not
    # prose-fallback on the same blob; that would launder invented anchors).
    if saw_role_json:
        return None
    # Prose fallback: "→ HARVEST" / "REDESIGN" + first matching anchor token mentioned.
    role = None
    if re.search(r"\bREDESIGN\b", blob, re.I):
        role = "REDESIGN"
    elif re.search(r"\bHARVEST\b", blob, re.I):
        role = "HARVEST"
    if not role or not anchors:
        return None
    chosen = anchors[0]
    for a in anchors:
        tok = str(a.get("token") or "")
        if tok and tok in blob:
            chosen = a
            break
    return {
        "role": role,
        "rationale": f"classify (prose): {role}",
        "path": chosen["path"],
        "line": int(chosen["line"]),
        "token": chosen["token"],
    }


def _upsert_from_dec(
    root: Path, *, fqn: str, dec: dict[str, Any], legacy: str
) -> None:
    rc = upsert_decision(
        root,
        fqn=fqn,
        role=dec["role"],
        rationale=dec["rationale"],
        evidence={
            "path": dec["path"],
            "line": int(dec["line"]),
            "token": dec["token"],
        },
        legacy=legacy,
    )
    if rc != 0:
        raise RuntimeError(f"upsert rc={rc}")


def _classify_opencode(
    root: Path,
    unit: dict,
    anchors: list[dict],
    *,
    worker_model: str,
    unit_timeout: int,
    skilldir: Path,
    legacy: str,
) -> dict[str, Any]:
    """O-PROFCLASSIFYVAL — model returns a judgment; harness upserts.

    Asking the model to run the upsert CLI led to correct prose answers that
    never persisted (OwnerMapper / CallMonitoringAspect). Dry-run already had
    the right shape: return a value, harness writes.
    """
    fqn = unit.get("legacy_fqn") or unit.get("key") or "?"
    lp = unit.get("legacy_path") or ""
    anchor_lines = []
    for a in anchors[:10]:
        anchor_lines.append(
            f"  - path={a.get('path')} line={a.get('line')} token={a.get('token')!r} "
            f"[{a.get('kind')}]"
        )
    packet = "\n".join(
        [
            "PROFILE classify — ONE unit only.",
            f"FQN: {fqn}",
            f"legacy_path: {lp}",
            "SELECT exactly one projected evidence anchor below (do not invent path/line/token).",
            "Reply with ONLY this JSON object (no shell, no file edits, no other units):",
            '{"role":"HARVEST"|"REDESIGN","rationale":"…","path":"…","line":N,"token":"…"}',
            "Anchors:",
            *anchor_lines,
            "Rules: HARVEST=data/DTO/mapper/value; REDESIGN=service/endpoint/config/runtime.",
            "Do NOT edit architecture-profile.md. Do NOT rewrite profile-decisions.json.",
            "Do NOT run profile_roles.py — the harness will persist your JSON.",
        ]
    )
    slog = Path("/tmp") / f"profile-classify-{re.sub(r'[^A-Za-z0-9_.-]', '_', fqn)}.log"
    cmd = [
        "timeout",
        str(unit_timeout),
        "opencode",
        "run",
        packet,
        "-m",
        worker_model,
        "--auto",
        "--format",
        "json",
        "-f",
        str(skilldir / "ANALYSIS.md"),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=unit_timeout + 30,
        )
        blob = (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or "")
        slog.write_text(blob, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"opencode classify failed for {fqn}: {e}") from e

    # Already persisted via accidental tool-call — accept (compat).
    ev = evaluate_roles(root, legacy=legacy)
    if fqn not in set(ev.get("undecided") or []):
        return {"role": "PERSISTED", "fqn": fqn}

    # Extract text parts from OpenCode JSONL for parsing.
    texts: list[str] = []
    for line in (proc.stdout or "").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            texts.append(line)
            continue
        part = o.get("part") if isinstance(o, dict) else None
        if isinstance(part, dict) and part.get("type") == "text":
            texts.append(str(part.get("text") or ""))
        elif isinstance(o, dict) and "text" in o:
            texts.append(str(o.get("text") or ""))
    parse_blob = "\n".join(texts) if texts else blob
    dec = _parse_classify_payload(parse_blob, anchors)
    if not dec:
        raise RuntimeError(
            f"opencode classify returned no usable judgment for {fqn} "
            f"(rc={proc.returncode}; see {slog})"
        )
    _upsert_from_dec(root, fqn=fqn, dec=dec, legacy=legacy)
    return dec


def _classify_hermes(
    root: Path,
    unit: dict,
    anchors: list[dict],
    *,
    orch_provider: str,
    orch_model: str,
    unit_timeout: int,
    legacy: str,
) -> dict[str, Any]:
    """O-PROFCLASSIFYVAL — hermes returns judgment JSON; harness upserts."""
    fqn = unit.get("legacy_fqn") or unit.get("key") or "?"
    anchor_lines = []
    for a in anchors[:10]:
        anchor_lines.append(
            f"  - path={a.get('path')} line={a.get('line')} token={a.get('token')!r}"
        )
    prompt = "\n".join(
        [
            "ONE unit PROFILE classify. O-PROFCLASSIFYVAL.",
            f"FQN: {fqn}",
            "Reply with ONLY this JSON (no shell, no file edits):",
            '{"role":"HARVEST"|"REDESIGN","rationale":"…","path":"…","line":N,"token":"…"}',
            "SELECT one projected evidence anchor:",
            *anchor_lines,
            "Prefer REDESIGN if an anchor token is a CDI/Spring stereotype.",
            "Do NOT run profile_roles.py — harness persists your JSON.",
        ]
    )
    cmd = [
        "timeout",
        str(unit_timeout),
        "hermes",
        "chat",
        "--provider",
        orch_provider,
        "--model",
        orch_model,
        "-q",
        prompt,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=unit_timeout + 30,
        check=False,
    )
    blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # O-PROFSEATEXIT / ADR-32 G-4: hermes often exits 0 under MiniMax 429 —
    # surface throttle explicitly so the loop can park, not silently continue.
    if re.search(r"429|Too Many Requests|Rate limit|rate.?limit", blob, re.I):
        raise RuntimeError(f"hermes classify rate-limited for {fqn} (rc={proc.returncode})")
    ev = evaluate_roles(root, legacy=legacy)
    if fqn not in set(ev.get("undecided") or []):
        return {"role": "PERSISTED", "fqn": fqn}
    dec = _parse_classify_payload(blob, anchors)
    if not dec:
        raise RuntimeError(f"hermes classify returned no usable judgment for {fqn}")
    _upsert_from_dec(root, fqn=fqn, dec=dec, legacy=legacy)
    return dec


def _park_blocked(root: Path, fqn: str, reason: str) -> None:
    """ADR-32 G-2 — park failed units; do not livelock the decide loop."""
    path = root / "migration" / "profile-blocked.json"
    data: dict[str, Any] = {"blocked": []}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"blocked": []}
    blocked = list(data.get("blocked") or [])
    blocked = [b for b in blocked if (b.get("fqn") if isinstance(b, dict) else None) != fqn]
    blocked.append({"fqn": fqn, "reason": reason})
    data["blocked"] = blocked
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_blocked(root: Path, blocked: list[Any]) -> None:
    path = root / "migration" / "profile-blocked.json"
    if not blocked:
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                path.write_text(json.dumps({"blocked": []}, indent=2) + "\n", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"blocked": blocked}, indent=2) + "\n", encoding="utf-8"
    )


def _unpark_blocked(root: Path, fqn: str) -> None:
    """O-PROFBLOCKUNPARK / W4-485 — remove recovered units from the park list.

    Park was dedupe-on-ADD only; a later OK left stale blocked rows and the
    operator line kept counting them as blocked forever.
    """
    path = root / "migration" / "profile-blocked.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    blocked = list(data.get("blocked") or [])
    new_blocked = [
        b for b in blocked if not (isinstance(b, dict) and b.get("fqn") == fqn)
    ]
    if len(new_blocked) == len(blocked):
        return
    _write_blocked(root, new_blocked)


def _reconcile_blocked(root: Path, *, legacy: str) -> int:
    """Drop parked rows whose FQN is no longer undecided (SoT).

    Covers recoveries outside this loop's OK path (prior tip, mechanical
    close, pass boundary) so profile-blocked.json cannot lie forever.
    """
    path = root / "migration" / "profile-blocked.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    blocked = list(data.get("blocked") or [])
    if not blocked:
        _write_blocked(root, [])
        return 0
    need = set(evaluate_roles(root, legacy=legacy).get("undecided") or [])
    kept: list[Any] = []
    dropped = 0
    for b in blocked:
        fqn = b.get("fqn") if isinstance(b, dict) else None
        if fqn and fqn not in need:
            dropped += 1
            continue
        kept.append(b)
    if dropped:
        _write_blocked(root, kept)
        _log(f"O-PROFBLOCKUNPARK: reconciled dropped={dropped} remaining={len(kept)}")
    return dropped


def _write_progress(root: Path, *, legacy: str, active: str, ok: int, fail: int) -> None:
    """O-PROFDECIDEHB — one-line status for outer-loop 60s heartbeat.

    Denominator is evaluate_roles().total (profile-units / graded SoT), never
    raw model.units length — avoids /89 vs /79 dual counters (W4-479).
    """
    try:
        ev = evaluate_roles(root, legacy=legacy)
        named = int(ev.get("named") or 0)
        total = int(ev.get("total") or 0)
        simple = active.rsplit(".", 1)[-1] if active else "?"
        line = (
            f"credited={named}/{total} active={simple} ok={ok} fail={fail} "
            f"undecided={len(ev.get('undecided') or [])}"
        )
        Path("/tmp/outer-heartbeat-progress.txt").write_text(line + "\n", encoding="utf-8")
    except OSError:
        pass


def _log(msg: str, *, err: bool = False) -> None:
    """Flush so redirected decide logs / heartbeats see lines immediately."""
    stream = sys.stderr if err else sys.stdout
    print(msg, file=stream, flush=True)


def _classify_unit(
    root: Path,
    u: dict,
    anchors: list[dict],
    *,
    backend: str,
    legacy: str,
    worker_model: str,
    unit_timeout: int,
    skilldir: Path,
    orch_provider: str,
    orch_model: str,
) -> dict[str, Any]:
    """Dispatch one classify backend; always returns a judgment or raises."""
    fqn = u.get("legacy_fqn") or u.get("key") or "?"
    if backend == "dry-run":
        dec = _pick_dry_run(u, anchors)
        _upsert_from_dec(root, fqn=fqn, dec=dec, legacy=legacy)
        return dec
    if backend in ("opencode-qwen", "opencode"):
        return _classify_opencode(
            root,
            u,
            anchors,
            worker_model=worker_model,
            unit_timeout=unit_timeout,
            skilldir=skilldir,
            legacy=legacy,
        )
    if backend in ("hermes-orch", "hermes"):
        return _classify_hermes(
            root,
            u,
            anchors,
            orch_provider=orch_provider,
            orch_model=orch_model,
            unit_timeout=unit_timeout,
            legacy=legacy,
        )
    # Instrument-only: always raise so O-PROFCLASCESC escalate path is observable.
    if backend in ("fail", "always-fail"):
        raise RuntimeError("instrument fail backend (classify refused)")
    raise RuntimeError(f"unknown backend {backend}")


def run_loop(
    root: Path,
    *,
    legacy: Optional[str],
    backend: str,
    max_units: int,
    unit_timeout: int,
    worker_model: str,
    orch_provider: str,
    orch_model: str,
    retries: int = 2,
    escalate_backend: Optional[str] = None,
) -> int:
    legacy = legacy or "/projects/legacy"
    skilldir = HERE.parent / "skills" / "migration-harness"
    # O-PROFCLASCESC / ADR-32: per-unit MiniMax backstop after primary retries.
    # Empty/no-judgment Qwen seats (CallMonitoringAspect / W4-482) must not park
    # while hermes-orch exists only as a run-level --backend switch.
    if escalate_backend is None:
        default_esc = (
            "hermes-orch"
            if backend in ("opencode-qwen", "opencode")
            else "none"
        )
        escalate_backend = os.environ.get(
            "PROFILE_CLASSIFY_ESCALATE_BACKEND", default_esc
        )
    if str(escalate_backend).lower() in ("", "none", "off", "-"):
        escalate_backend = ""

    def _backend_family(name: str) -> str:
        if name in ("opencode-qwen", "opencode"):
            return "opencode"
        if name in ("hermes-orch", "hermes"):
            return "hermes"
        return name

    # O-PROFBLOCKUNPARK — clear stale parks before counting undecided work.
    _reconcile_blocked(root, legacy=legacy)
    # O-PROFCOVSTALE / ADR-32 G-1: loop condition uses evaluate_roles() SoT only.
    units = _undecided_units(root, legacy)
    if max_units > 0:
        units = units[:max_units]
    _log(
        f"O-PROFSEATARCH: backend={backend} escalate={escalate_backend or 'off'} "
        f"undecided={len(units)} timeout={unit_timeout}s retries={retries}"
    )
    _write_progress(root, legacy=legacy, active="starting", ok=0, fail=0)
    ok = 0
    fail = 0
    for u in units:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        _write_progress(root, legacy=legacy, active=fqn, ok=ok, fail=fail)
        anchors = anchors_for_unit(root, u, legacy=legacy)
        if not anchors:
            _log(f"O-PROFSEATARCH: SKIP {fqn} — no anchors", err=True)
            _park_blocked(root, fqn, "no-anchors")
            fail += 1
            continue
        last_err = ""
        landed = False
        for attempt in range(1, max(1, retries) + 1):
            try:
                _classify_unit(
                    root,
                    u,
                    anchors,
                    backend=backend,
                    legacy=legacy,
                    worker_model=worker_model,
                    unit_timeout=unit_timeout,
                    skilldir=skilldir,
                    orch_provider=orch_provider,
                    orch_model=orch_model,
                )
                landed = True
                break
            except Exception as e:  # noqa: BLE001 — per-unit continue
                last_err = str(e)
                _log(
                    f"O-PROFSEATARCH: RETRY {fqn} attempt={attempt}/{retries}: {e}",
                    err=True,
                )
        # O-PROFCLASCESC — one escape seat per unit when primary backend exhausted.
        if (
            not landed
            and escalate_backend
            and _backend_family(escalate_backend) != _backend_family(backend)
        ):
            try:
                _log(
                    f"O-PROFCLASCESC: escalate {fqn} → {escalate_backend}",
                    err=True,
                )
                _classify_unit(
                    root,
                    u,
                    anchors,
                    backend=escalate_backend,
                    legacy=legacy,
                    worker_model=worker_model,
                    unit_timeout=unit_timeout,
                    skilldir=skilldir,
                    orch_provider=orch_provider,
                    orch_model=orch_model,
                )
                landed = True
                last_err = ""
            except Exception as e:  # noqa: BLE001
                last_err = f"escalate({escalate_backend}): {e}"
                _log(f"O-PROFCLASCESC: FAIL {fqn}: {e}", err=True)
        if landed:
            ok += 1
            _unpark_blocked(root, fqn)
            _log(f"O-PROFSEATARCH: OK {fqn}")
        else:
            fail += 1
            _park_blocked(root, fqn, last_err or "classify-failed")
            _log(f"O-PROFSEATARCH: FAIL {fqn}: {last_err}", err=True)
        _write_progress(root, legacy=legacy, active=fqn, ok=ok, fail=fail)
    _reconcile_blocked(root, legacy=legacy)
    ev = evaluate_roles(root, legacy=legacy)
    _log(
        f"O-PROFSEATARCH: done ok={ok} fail={fail} "
        f"remaining_undecided={len(ev.get('undecided') or [])} "
        f"credited={ev.get('named')}/{ev.get('total')} "
        f"authored={ev.get('authored')}"
    )
    _write_progress(root, legacy=legacy, active="done", ok=ok, fail=fail)
    return 0 if fail == 0 or ok > 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="PROFILE class-role decide loop")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--root", default=".")
    p.add_argument("--legacy", default="/projects/legacy")
    p.add_argument(
        "--backend",
        default=os.environ.get("PROFILE_CLASSIFY_BACKEND", "opencode-qwen"),
    )
    p.add_argument("--max-units", type=int, default=0, help="0 = all undecided")
    p.add_argument(
        "--unit-timeout",
        type=int,
        default=int(os.environ.get("PROFILE_CLASSIFY_TIMEOUT", "180")),
    )
    p.add_argument(
        "--worker-model",
        default=os.environ.get("WORKER_MODEL", "qwen27b/qwen3-6-27b"),
    )
    p.add_argument(
        "--orch-provider",
        default=os.environ.get("ORCH_PROVIDER", "custom:maas-m2"),
    )
    p.add_argument(
        "--orch-model", default=os.environ.get("ORCH_MODEL", "minimax-m2")
    )
    p.add_argument(
        "--escalate-backend",
        default=None,
        help="O-PROFCLASCESC per-unit backstop (default: hermes-orch for opencode)",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("PROFILE_CLASSIFY_RETRIES", "2")),
        help="Primary classify attempts per unit before O-PROFCLASCESC escalate",
    )
    args = ap.parse_args()
    if args.cmd == "run":
        return run_loop(
            Path(args.root).resolve(),
            legacy=args.legacy,
            backend=args.backend,
            max_units=args.max_units,
            unit_timeout=args.unit_timeout,
            worker_model=args.worker_model,
            orch_provider=args.orch_provider,
            orch_model=args.orch_model,
            retries=args.retries,
            escalate_backend=args.escalate_backend,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
