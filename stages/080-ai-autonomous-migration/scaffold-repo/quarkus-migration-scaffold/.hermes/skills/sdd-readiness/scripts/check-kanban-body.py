#!/usr/bin/env python3
"""W2 §6.1 — typed Kanban body vocabulary + stable failure codes.

Looks for body objects in:
  - migration/tasks/*.json  (field body, or whole object if phase+refs present)
  - migration/bodies/*.json
  - migration/kanban/*.json (field body)

Idle (exit 0) when no body artifacts exist.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "M1": ("harvest_referent",),
    "M2": ("mta_findings", "m1_findings_ack"),
    "M3": ("brief_identity_ack", "legacy_locus"),
    "M4": ("story_tip",),
    "M5": ("m4_verdict", "mta_rescan_input"),
    "FACTORY": ("m5_accept",),
}

ALLOWED_EXTRA: dict[str, frozenset[str]] = {
    "M1": frozenset({"legacy_at_3_manifest"}),
    "M2": frozenset({"entry_point_inventory", "brief_draft"}),
    "M3": frozenset({"spec_path", "plan_path", "derive_apply_log", "legacy_locus"}),
    "M4": frozenset({"g1_fixture", "g2_fixture"}),
    "M5": frozenset({"g3_baseline", "g4_inventory"}),
    "FACTORY": frozenset(),
}

# All known keys = required ∪ allowed for any phase
ALL_KEYS = frozenset(
    k for keys in REQUIRED_KEYS.values() for k in keys
) | frozenset(k for extra in ALLOWED_EXTRA.values() for k in extra)

INLINE_MARKERS = re.compile(
    r"(?i)(BEGIN\s+FINDINGS|BEGIN\s+BLOB|-----BEGIN|"
    r"<html|package\s+com\.|class\s+\w+\s*\{)"
)


def fail(code: str, detail: str) -> None:
    print(f"{code}: {detail}", file=sys.stderr)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def bodies_from(path: Path) -> list[tuple[str, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    out: list[tuple[str, dict]] = []
    for i, obj in enumerate(items):
        if not isinstance(obj, dict):
            continue
        label = str(path) if len(items) == 1 else f"{path}[{i}]"
        if isinstance(obj.get("body"), dict):
            out.append((label + ".body", obj["body"]))
        elif "phase" in obj and ("refs" in obj or "task_id" in obj):
            out.append((label, obj))
    return out


def check_body(label: str, body: dict, root: Path) -> int:
    bad = 0
    if not isinstance(body, dict):
        fail("BODY_SCHEMA", "body must be typed object with task_id, role, phase, refs[]")
        return 1
    tid = body.get("task_id") or body.get("id")
    role = body.get("role")
    phase = str(body.get("phase") or "").upper()
    refs = body.get("refs")
    if not tid or not role or not phase or not isinstance(refs, list):
        fail(
            "BODY_SCHEMA",
            "body must be typed object with task_id, role, phase, refs[]",
        )
        bad = 1
        return bad

    # inline content heuristic
    raw = json.dumps(body)
    if len(raw) > 12000 or INLINE_MARKERS.search(raw):
        # allow if only short strings in refs
        fail(
            "BODY_INLINE",
            "body must not carry derived content (digest refs only)",
        )
        bad = 1

    vocab = set(REQUIRED_KEYS.get(phase, ())) | set(ALLOWED_EXTRA.get(phase, frozenset()))
    if phase not in REQUIRED_KEYS:
        fail("BODY_SCHEMA", f"body must be typed object with task_id, role, phase, refs[]")
        bad = 1
        return bad

    seen: dict[str, dict] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            fail("BODY_SCHEMA", "body must be typed object with task_id, role, phase, refs[]")
            bad = 1
            continue
        key = str(ref.get("key") or "")
        if key not in ALL_KEYS and key not in vocab:
            fail("BODY_REF_UNKNOWN", f"key={key} not in phase vocabulary")
            bad = 1
            continue
        if key not in vocab:
            fail("BODY_REF_UNKNOWN", f"key={key} not in phase vocabulary")
            bad = 1
            continue
        seen[key] = ref
        path_s = str(ref.get("path") or "")
        exp = str(ref.get("sha256") or "").lower()
        if path_s and exp:
            p = (root / path_s).resolve() if not Path(path_s).is_absolute() else Path(path_s)
            # Also try relative to root without resolve escape
            if not p.is_file():
                p = root / path_s
            if p.is_file():
                actual = sha256_file(p)
                if actual != exp:
                    fail(
                        "BODY_REF_DIGEST",
                        f"key={key} path={path_s} expected={exp} actual={actual}",
                    )
                    bad = 1
            # missing file: digest check deferred (path may be workspace-only)
            # do not BODY_REF_DIGEST on missing — create-time may precede files

    for req in REQUIRED_KEYS[phase]:
        if req not in seen:
            fail("BODY_REF_MISSING", f"phase={phase} missing ref key={req}")
            bad = 1

    if phase == "M3":
        scope = body.get("files_in_scope") or body.get("filesInScope")
        if not isinstance(scope, list) or not scope:
            fail("BODY_SCOPE", "M3 requires non-empty files_in_scope")
            bad = 1

    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    files: list[Path] = []
    for d in (
        root / "migration/tasks",
        root / "migration/bodies",
        root / "migration/kanban",
    ):
        if d.is_dir():
            files.extend(sorted(d.glob("*.json")))
    pairs: list[tuple[str, dict]] = []
    for f in files:
        try:
            pairs.extend(bodies_from(f))
        except Exception as e:
            print(f"FAIL: {f.relative_to(root)}: {e}", file=sys.stderr)
            return 1

    if not pairs:
        print("OK: no Kanban body artifacts — §6.1 body lint idle")
        return 0

    bad = 0
    for label, body in pairs:
        rel = label.replace(str(root) + "/", "")
        bad |= check_body(rel, body, root)

    if bad:
        print(f"Kanban body checks FAILED ({len(pairs)} body(ies)).", file=sys.stderr)
        return 1
    print(f"OK: Kanban body §6.1 checks passed ({len(pairs)} body(ies)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
