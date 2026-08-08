#!/usr/bin/env python3
"""AD-H §19 — cheap lint of generation provenance for non-trivial IMPLEMENT.

Sources:
  - migration/provenance/*.json
  - migration/tasks/*.json / migration/kanban/*.json fields:
      provenance | metadata | completion_metadata

Fail closed if IMPLEMENT complete / non-trivial packet lacks worker_session_id
or other mandatory fields. Require derive apply log in artifacts[] when
derive_apply_log / harvest claims present.

Idle (exit 0) when no provenance-bearing IMPLEMENT artifacts exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MANDATORY = (
    "task_id",
    "worker_session_id",
    "soul_sha",
    "skill_tips",
    "model_id",
    "citations",
)

APPLY_LOG_HINTS = (
    "free-primitives-apply-log.json",
    "migration/derived/free-primitives-apply-log.json",
    "derive_apply_log",
)


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def is_implement(obj: dict) -> bool:
    phase = str(obj.get("phase") or obj.get("m_phase") or "").upper()
    role = str(obj.get("role") or "").lower().replace("_", "-")
    if phase in {"M3", "IMPLEMENT"}:
        return True
    if role in {"implementer", "implement", "worker"}:
        return True
    return False


def is_trivial(obj: dict) -> bool:
    for key in ("trivial", "is_trivial", "isTrivial"):
        if obj.get(key) in (True, "true", "yes", 1):
            return True
    return False


def claims_complete(obj: dict) -> bool:
    status = str(obj.get("status") or obj.get("state") or "").lower()
    if status in {"done", "complete", "completed", "closed"}:
        return True
    if obj.get("kanban_complete") in (True, "true", 1):
        return True
    return False


def provenance_of(obj: dict) -> dict | None:
    for key in ("provenance", "metadata", "completion_metadata", "completionMetadata"):
        v = obj.get(key)
        if isinstance(v, dict) and (
            "worker_session_id" in v
            or "soul_sha" in v
            or "citations" in v
            or "skill_tips" in v
        ):
            return v
    # whole object is a provenance export
    if "worker_session_id" in obj or "soul_sha" in obj:
        return obj
    return None


def check_prov(label: str, prov: dict, *, require_apply_log: bool) -> int:
    bad = 0
    tid = prov.get("task_id") or prov.get("id")
    if not tid:
        print(f"FAIL: {label}: missing task_id (AD-H §19)", file=sys.stderr)
        bad = 1
    sess = prov.get("worker_session_id") or prov.get("workerSessionId")
    if not sess:
        print(
            f"FAIL: {label}: missing worker_session_id — fail closed (AD-H §19)",
            file=sys.stderr,
        )
        bad = 1
    for field in ("soul_sha", "skill_tips", "model_id"):
        key_alt = {"soul_sha": "soulSha", "skill_tips": "skillTips", "model_id": "modelId"}.get(
            field, field
        )
        if prov.get(field) in (None, "") and prov.get(key_alt) in (None, ""):
            print(f"FAIL: {label}: missing {field} (AD-H §19)", file=sys.stderr)
            bad = 1
    model = str(prov.get("model_id") or prov.get("modelId") or "")
    gap = prov.get("model_id_gap")
    if gap is None:
        gap = prov.get("modelIdGap")
    if model.lower() == "unknown":
        if gap not in (True, "true", "yes", 1):
            print(
                f"FAIL: {label}: model_id=unknown requires model_id_gap=true "
                f"(named reproducibility gap; AD-H §19 / Architect E-20260808T081557Z)",
                file=sys.stderr,
            )
            bad = 1
    cites = prov.get("citations") or prov.get("citation") or {}
    if not isinstance(cites, dict):
        print(f"FAIL: {label}: citations must be object (AD-H §19 / §17)", file=sys.stderr)
        bad = 1
    else:
        brief = cites.get("brief_or_story_id") or cites.get("brief_id") or cites.get("story_id")
        locus = cites.get("legacy_locus") or cites.get("locus")
        if not brief or not locus:
            print(
                f"FAIL: {label}: citations need brief_or_story_id + legacy_locus",
                file=sys.stderr,
            )
            bad = 1

    artifacts = prov.get("artifacts") or []
    if not isinstance(artifacts, list):
        artifacts = []
    if require_apply_log:
        joined = " ".join(str(a) for a in artifacts)
        if not any(h in joined for h in APPLY_LOG_HINTS):
            print(
                f"FAIL: {label}: derive apply log must appear in artifacts[] (W2 §12.3)",
                file=sys.stderr,
            )
            bad = 1
    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    checked = 0
    bad = 0

    # Standalone provenance exports always checked
    prov_dir = root / "migration/provenance"
    if prov_dir.is_dir():
        for path in sorted(prov_dir.glob("*.json")):
            rel = str(path.relative_to(root))
            try:
                for obj in load_items(path):
                    if not isinstance(obj, dict):
                        continue
                    checked += 1
                    need_log = any(
                        "derive" in str(a).lower() or "harvest" in str(a).lower()
                        for a in (obj.get("artifacts") or [])
                    ) or bool(obj.get("require_derive_log"))
                    # Always require apply log hint if artifacts empty but flag set;
                    # for exports that mention derive in citations path, soft: check if
                    # skill_tips includes derive-legacy-boot3
                    tips = obj.get("skill_tips") or {}
                    if isinstance(tips, dict) and "derive-legacy-boot3" in tips:
                        need_log = True
                    bad |= check_prov(rel, obj, require_apply_log=need_log)
            except Exception as e:
                print(f"FAIL: {rel}: {e}", file=sys.stderr)
                bad = 1

    for d in (root / "migration/tasks", root / "migration/kanban"):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            rel = str(path.relative_to(root))
            try:
                items = load_items(path)
            except Exception as e:
                print(f"FAIL: {rel}: {e}", file=sys.stderr)
                bad = 1
                continue
            for i, obj in enumerate(items):
                if not isinstance(obj, dict) or not is_implement(obj):
                    continue
                if is_trivial(obj):
                    continue
                prov = provenance_of(obj)
                # Only fail closed when complete OR provenance block present
                if prov is None and not claims_complete(obj):
                    continue
                checked += 1
                label = rel if len(items) == 1 else f"{rel}[{i}]"
                if prov is None:
                    print(
                        f"FAIL: {label}: IMPLEMENT complete missing provenance "
                        f"(worker_session_id required)",
                        file=sys.stderr,
                    )
                    bad = 1
                    continue
                # merge task_id from outer if needed
                if not prov.get("task_id") and (obj.get("id") or obj.get("task_id")):
                    prov = {**prov, "task_id": obj.get("id") or obj.get("task_id")}
                tips = prov.get("skill_tips") or {}
                need_log = isinstance(tips, dict) and "derive-legacy-boot3" in tips
                refs = (obj.get("body") or {}).get("refs") if isinstance(obj.get("body"), dict) else []
                if isinstance(refs, list) and any(
                    isinstance(r, dict) and r.get("key") == "derive_apply_log" for r in refs
                ):
                    need_log = True
                bad |= check_prov(label, prov, require_apply_log=need_log)

    if checked == 0:
        print("OK: no IMPLEMENT provenance artifacts — §19 lint idle")
        return 0
    if bad:
        print(f"Provenance checks FAILED ({checked} artifact(s)).", file=sys.stderr)
        return 1
    print(f"OK: AD-H §19 provenance checks passed ({checked} artifact(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
