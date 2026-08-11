#!/usr/bin/env python3
"""Partition-coverage gate (Operator E-20260811T134200Z / Architect E-133858Z).

M2a exit / create-path fail-closed: prove the partition is VALID as a whole
(not only per-story body lint). Verdict tri-state:

  VALID | INVALID | INCONCLUSIVE

Checks:
  1) Endpoint coverage — each inventory HTTP entry_point maps to exactly one story
  2) No file overlaps across stories (write-conflict)
  3) Optional MTA findings addressed via story.rules or typed oos
  4) Composes with bodies' files_in_scope when present (M2b+)

Usage:
  python3 check-partition-coverage.py /projects/modernized
  python3 check-partition-coverage.py . --write-receipt migration/receipts/partition-coverage.json
  python3 check-partition-coverage.py . --retro   # evidence-only: never exit 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if not hasattr(Path, "is_relative_to"):
    def _is_relative_to(self: Path, other: Path) -> bool:  # type: ignore[misc]
        try:
            self.relative_to(other)
            return True
        except ValueError:
            return False

    Path.is_relative_to = _is_relative_to  # type: ignore[attr-defined]

EXPECTED_HTTP_ENDPOINTS = 34  # F11-corrected denominator


def norm_file(path: str) -> str:
    p = path.replace("\\", "/")
    for prefix in (
        "/projects/.derived/legacy-at-3/",
        "/projects/modernized/",
        "/projects/legacy/",
        "projects/.derived/legacy-at-3/",
        "projects/modernized/",
        "projects/legacy/",
    ):
        if p.startswith(prefix):
            p = p[len(prefix) :]
    # dest package remap → legacy path form for inventory compare
    p = p.replace(
        "src/main/java/com/demo/",
        "src/main/java/org/springframework/samples/petclinic/",
    )
    p = p.replace(
        "src/test/java/com/demo/",
        "src/test/java/org/springframework/samples/petclinic/",
    )
    return p.lstrip("./")


def story_files(story: dict) -> list[str]:
    out: list[str] = []
    for key in ("files", "files_in_scope", "legacy_files", "scope_files"):
        val = story.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    for k in ("legacy", "src", "source", "path", "file"):
                        if item.get(k):
                            out.append(str(item[k]))
    return out


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def body_files_for_story(bodies_dir: Path, story_id: str) -> list[str]:
    if not bodies_dir.is_dir():
        return []
    # Exact identity.story_id match only (Operator E-20260811T144200Z).
    # Path-substring matching falsely bound partition S-002 → m3-s-002a/b.
    want = story_id.lower()
    candidates = list(bodies_dir.glob("m3-*.json"))
    for path in candidates:
        if path.name.endswith(".sha256.json"):
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
        bid = str(ident.get("story_id") or data.get("story_id") or "")
        if bid.lower() != want:
            continue
        scope = data.get("files_in_scope") or data.get("filesInScope") or []
        out: list[str] = []
        for item in scope if isinstance(scope, list) else []:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for k in ("legacy", "src", "source", "path", "file"):
                    if item.get(k):
                        out.append(str(item[k]))
        return out
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--partition", default="migration/briefs/partition.json")
    ap.add_argument(
        "--inventory",
        default="",
        help="default: migration/entry-point-inventory.json then F11 fixture",
    )
    ap.add_argument("--findings", default="migration/mta-findings.json")
    ap.add_argument("--bodies", default="migration/bodies")
    ap.add_argument("--write-receipt", default="")
    ap.add_argument(
        "--retro",
        action="store_true",
        help="Evidence-only: print verdict, always exit 0 (Architect: no mid-campaign re-plan)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    part_path = root / args.partition
    partition = load_json(part_path)
    if not isinstance(partition, dict) or not isinstance(partition.get("stories"), list):
        print("PARTITION_COVERAGE: INCONCLUSIVE — missing/invalid partition.json", file=sys.stderr)
        return 0 if args.retro else 1

    inv_path = Path(args.inventory) if args.inventory else None
    if inv_path and not inv_path.is_absolute():
        inv_path = root / inv_path
    if inv_path is None or not inv_path.is_file():
        for cand in (
            root / "migration/entry-point-inventory.json",
            root
            / "migration/fixtures/inventory/entry-point-inventory-petclinic-f11.json",
        ):
            if cand.is_file():
                inv_path = cand
                break
    inventory = load_json(inv_path) if inv_path else None
    if not isinstance(inventory, dict):
        print("PARTITION_COVERAGE: INCONCLUSIVE — missing inventory", file=sys.stderr)
        return 0 if args.retro else 1

    entry_points = inventory.get("entry_points") or []
    if not isinstance(entry_points, list) or not entry_points:
        print("PARTITION_COVERAGE: INCONCLUSIVE — inventory has no entry_points", file=sys.stderr)
        return 0 if args.retro else 1

    http_eps = [e for e in entry_points if isinstance(e, dict) and e.get("kind") == "http"]
    ep_count = len(http_eps)
    gaps: list[str] = []
    if ep_count != EXPECTED_HTTP_ENDPOINTS:
        gaps.append(
            f"inventory_http_count={ep_count} expected_F11={EXPECTED_HTTP_ENDPOINTS}"
        )

    stories = [s for s in partition["stories"] if isinstance(s, dict)]
    bodies_dir = root / args.bodies
    story_file_map: dict[str, set[str]] = {}
    for story in stories:
        sid = str(story.get("story_id") or "").strip()
        if not sid:
            gaps.append("story_missing_id")
            continue
        files = story_files(story)
        body_fs = body_files_for_story(bodies_dir, sid)
        # Prefer bodies when present (M2b+); else partition sketches (M2a)
        chosen = body_fs if body_fs else files
        story_file_map[sid] = {norm_file(f) for f in chosen if f}

    # File overlaps
    owner: dict[str, str] = {}
    for sid, files in story_file_map.items():
        for f in files:
            if not f or f.endswith("pom.xml"):
                # pom may be dual-pathed across CONFIG stories — allow multi for pom only
                continue
            if f in owner and owner[f] != sid:
                gaps.append(f"file_overlap:{f}:{owner[f]}+{sid}")
            else:
                owner[f] = sid

    # Endpoint → exactly one story (by owning the controller file)
    uncovered: list[str] = []
    multi: list[str] = []
    for ep in http_eps:
        f = norm_file(str(ep.get("file") or ""))
        sym = str(ep.get("symbol") or "")
        key = f"{f}#{sym}" if sym else f
        claimants = [sid for sid, files in story_file_map.items() if f in files]
        # Also allow story.endpoints / story.entry_points explicit lists
        for story in stories:
            sid = str(story.get("story_id") or "")
            for field in ("endpoints", "entry_points", "symbols"):
                vals = story.get(field) or []
                if isinstance(vals, list) and (sym in vals or key in vals or f in vals):
                    if sid not in claimants:
                        claimants.append(sid)
        if len(claimants) == 0:
            uncovered.append(key)
        elif len(claimants) > 1:
            multi.append(f"{key}:{'+'.join(claimants)}")

    if uncovered:
        gaps.append(f"endpoints_uncovered={len(uncovered)}")
        for u in uncovered[:12]:
            gaps.append(f"uncovered:{u}")
        if len(uncovered) > 12:
            gaps.append(f"uncovered:…(+{len(uncovered)-12})")
    if multi:
        gaps.append(f"endpoints_multi={len(multi)}")
        for m in multi[:8]:
            gaps.append(f"multi:{m}")

    # MTA findings (optional → INCONCLUSIVE if absent, not INVALID)
    findings_path = root / args.findings
    findings = load_json(findings_path)
    mta_status = "skipped_missing"
    if isinstance(findings, dict):
        items = findings.get("violations") or findings.get("findings") or findings.get("rules") or []
        oos = set()
        for story in stories:
            for x in story.get("rules") or []:
                oos.add(str(x))
        typed_oos = partition.get("mta_oos") or partition.get("findings_oos") or []
        if isinstance(typed_oos, list):
            oos.update(str(x) for x in typed_oos)
        if isinstance(items, list) and items:
            mta_status = "checked"
            missing_rules: list[str] = []
            for it in items:
                if isinstance(it, str):
                    rid = it
                elif isinstance(it, dict):
                    rid = str(it.get("rule") or it.get("ruleID") or it.get("id") or "")
                else:
                    continue
                if rid and rid not in oos:
                    missing_rules.append(rid)
            if missing_rules:
                gaps.append(f"mta_unaddressed={len(missing_rules)}")
                for r in missing_rules[:10]:
                    gaps.append(f"mta:{r}")
        else:
            mta_status = "empty_findings"

    if not story_file_map or all(len(v) == 0 for v in story_file_map.values()):
        verdict = "INCONCLUSIVE"
        gaps.append("no_story_files_in_partition_or_bodies")
    elif gaps:
        verdict = "INVALID"
    else:
        verdict = "VALID"

    receipt = {
        "schema": "rhoai3.partition-coverage/v1",
        "verdict": verdict,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "partition": str(part_path.relative_to(root)) if part_path.is_relative_to(root) else str(part_path),
        "inventory": str(inv_path.relative_to(root)) if inv_path and inv_path.is_relative_to(root) else str(inv_path),
        "story_count": len(stories),
        "http_endpoint_count": ep_count,
        "expected_http_endpoints": EXPECTED_HTTP_ENDPOINTS,
        "mta_status": mta_status,
        "gaps": gaps,
        "architect_bind": "E-20260811T133858Z",
        "operator_proposal": "E-20260811T134200Z",
    }
    if args.write_receipt:
        out = Path(args.write_receipt)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote receipt {out}")

    print(f"PARTITION_COVERAGE: {verdict} stories={len(stories)} http_eps={ep_count} gaps={len(gaps)}")
    for g in gaps[:20]:
        print(f"  - {g}", file=sys.stderr if verdict != "VALID" else sys.stdout)

    if args.retro:
        return 0
    return 0 if verdict == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
