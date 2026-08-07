#!/usr/bin/env python3
"""O-K3TYPED / F-k3-typed — per-story K3 counts from typed NM decisions.

K3 evidences adopt/defer *decisions*, not substring hits in roadmap prose.
SoT after sync: ``model.nm_decisions`` (rule-id → adopt|defer), intersected with
``model.stories[].findings`` (plus findings on story units).

Roadmap markdown is a *source to sync from*, never the enforcement count
for ledger rows (W4-623 / Opus P1).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

_HARNESS = Path(__file__).resolve().parent


def _model_path(root: Path) -> Path:
    return Path(root) / "migration" / "model.json"


def model_load(root: Path) -> dict:
    p = _model_path(root)
    if not p.is_file():
        return {"stories": [], "units": [], "findings": [], "nm_decisions": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def model_save(root: Path, model: dict) -> None:
    p = _model_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(model, indent=2, sort_keys=False) + "\n", encoding="utf-8")


_DECISION_RE = re.compile(
    r"(?im)^\|\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?\s*\|\s*"
    r"(adopt|defer)\s*\|"
)
_BULLET_RE = re.compile(
    r"(?im)^[-*]\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?\s*:\s*(adopt|defer)\b"
)


def parse_nm_decisions(roadmap_text: str) -> dict[str, str]:
    """Parse adopt/defer from Non-mandatory table/bullets → rule-id map."""
    out: dict[str, str] = {}
    # Prefer the NM section when present so prose elsewhere cannot pollute.
    m = re.search(
        r"(?ims)^##\s+Non-mandatory decisions\b.*?(?=^##\s|\Z)",
        roadmap_text,
    )
    blob = m.group(0) if m else roadmap_text
    for rx in (_DECISION_RE, _BULLET_RE):
        for mm in rx.finditer(blob):
            rid = mm.group(1).strip()
            dec = mm.group(2).strip().lower()
            if rid and dec in ("adopt", "defer"):
                out[rid] = dec
    return out


def story_finding_ids(model: dict, sid: str) -> set[str]:
    """Finding ids owned by ``sid`` (story.findings ∪ unit.findings)."""
    want = str(sid or "").strip()
    units_by_key = {
        str(u.get("key") or ""): u
        for u in (model.get("units") or [])
        if isinstance(u, dict) and u.get("key")
    }
    out: set[str] = set()
    for st in model.get("stories") or []:
        if not isinstance(st, dict):
            continue
        if str(st.get("id") or "").strip() != want:
            continue
        for fid in st.get("findings") or []:
            if fid:
                out.add(str(fid))
        for k in st.get("units") or []:
            u = units_by_key.get(k if isinstance(k, str) else "") or {}
            for fid in u.get("findings") or []:
                if fid:
                    out.add(str(fid))
        break
    return out


def sync_nm_decisions(root: Path, model: Optional[dict] = None) -> dict:
    """Sync roadmap NM table → ``model.nm_decisions`` (typed SoT)."""
    root = Path(root)
    model = model or model_load(root)
    roadmap = root / "migration" / "roadmap.md"
    text = roadmap.read_text(encoding="utf-8", errors="replace") if roadmap.is_file() else ""
    decisions = parse_nm_decisions(text)
    model["nm_decisions"] = decisions
    prov = model.setdefault("provenance", {})
    prov["nm_decisions_source"] = "roadmap-nm-sync"
    prov["nm_decisions_n"] = len(decisions)
    model_save(root, model)
    return model


def k3_count_for_story(model: dict, sid: str) -> tuple[int, str]:
    """Return (count, note) for one story from typed nm_decisions ∩ findings.

    - no story-owned findings → (0, none-applicable)
    - findings but zero decided → (0, pending)  # caller may leave silent
    - N decided → (N, typed)
    """
    decisions = {
        str(k): str(v).lower()
        for k, v in (model.get("nm_decisions") or {}).items()
        if str(v).lower() in ("adopt", "defer")
    }
    fids = story_finding_ids(model, sid)
    if not fids:
        return 0, "none-applicable (no story-owned findings)"
    n = sum(1 for fid in fids if fid in decisions)
    if n == 0:
        return 0, "pending (story findings lack nm_decisions)"
    return n, "typed nm_decisions ∩ story findings (O-K3TYPED)"


def k3_counts(root: Path, *, sync: bool = True) -> dict[str, dict[str, Any]]:
    """All stories → {sid: {n, note}}."""
    root = Path(root)
    model = sync_nm_decisions(root) if sync else model_load(root)
    out: dict[str, dict[str, Any]] = {}
    for st in model.get("stories") or []:
        if not isinstance(st, dict):
            continue
        sid = str(st.get("id") or "").strip()
        if not sid:
            continue
        n, note = k3_count_for_story(model, sid)
        out[sid] = {"n": n, "note": note}
    return out


def seed_ledger(root: Path) -> int:
    """Record per-story K3 rows via evidence-liveness.sh (honest counts)."""
    import os
    import subprocess

    root = Path(root)
    counts = k3_counts(root, sync=True)
    script = _HARNESS / "evidence-liveness.sh"
    if not script.is_file():
        print("O-K3TYPED RED: missing evidence-liveness.sh", file=sys.stderr)
        return 2
    seeded = 0
    for sid, info in sorted(counts.items()):
        n = int(info["n"])
        note = str(info["note"])
        if n == 0 and note.startswith("pending"):
            # Leave silent → check RED until decisions exist for owned findings.
            continue
        rows = n if n > 0 else 1
        env = os.environ.copy()
        env["ORACLE_ROOT"] = str(root)
        subprocess.run(
            ["bash", str(script), "record", sid, "K3", str(rows), note],
            cwd=str(root),
            env=env,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        seeded += 1
    print(f"O-K3TYPED: seeded stories={seeded} (F-k3-typed)")
    return 0


def _cli(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="k3_evidence.py")
    ap.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_sync = sub.add_parser("sync", help="Sync roadmap NM → model.nm_decisions")
    p_counts = sub.add_parser("counts", help="Print per-story K3 counts as JSON")
    p_seed = sub.add_parser("seed", help="Seed evidence-liveness K3 from typed counts")
    p_one = sub.add_parser("count", help="Print one story count")
    p_one.add_argument("--sid", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.cmd == "sync":
        m = sync_nm_decisions(root)
        print(json.dumps(m.get("nm_decisions") or {}, indent=2, sort_keys=True))
        return 0
    if args.cmd == "counts":
        print(json.dumps(k3_counts(root, sync=True), indent=2, sort_keys=True))
        return 0
    if args.cmd == "count":
        m = sync_nm_decisions(root)
        n, note = k3_count_for_story(m, args.sid)
        print(f"{args.sid}\t{n}\t{note}")
        return 0
    if args.cmd == "seed":
        return seed_ledger(root)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
