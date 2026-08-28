#!/usr/bin/env python3
"""Partition-coverage gate (Operator E-20260811T134200Z / Architect E-133858Z).

M2 exit / create-path fail-closed: prove the partition is VALID as a whole
(not only per-story body lint). Verdict tri-state:

  VALID | INVALID | INCONCLUSIVE

Checks:
  1) Endpoint coverage — each inventory HTTP entry_point maps to exactly one
     story via transcribed ``story.endpoints`` ∩ inventory ``http_method``+
     ``http_path`` / ``symbol`` (A-8). Do **not** join inventory ``file`` to
     dest write-set paths (Architect ``E-20260817T152824Z``; that RestController
     vs Resource lookup is not A-8). HTTP coverage stays 1:1 (endpoints_multi).
  2) Unique ``pom.xml`` writer (DD3 / Architect E-20260814T205052Z). Non-pom
     ``file_overlap`` is dropped while serial (same invented gate as mint
     ``FILE_OVERLAP``, ``131858Z`` / ``152824Z``). Do **not** stamp
     ``sequence_after`` to nurse coverage. Restore in-flight overlap only
     when C-1(a) is claimed.
  3) MTA findings **presence** (WC-8): missing file is INCONCLUSIVE (never a
     silent VALID). Create-path does **not** require every rule id on
     ``story.rules`` / ``mta_oos`` (Architect ``E-20260817T154012Z`` /
     ``E-20260817T154847Z`` — that join is the migration output). Addressed
     findings stay M1 ``check-findings-handoff`` and M5 WC-5 rescan.
  4) Composes with bodies' files_in_scope when present (M2+)
  5) Write-set subset (E-20260819T104254Z): each body's files_writable as
     written is ⊆ that story's declared partition frame (files_writable,
     else files, else files_in_scope). Does **not** rewrite dest leaves
     through intra_package_maps — that hid entity/ extras beside model/.
     Partition dual-frame (same basename under both mapped leaves) is
     INVALID. Coverage still does not join inventory.file to dest write-set.
  6) Type-inventory dest twins (when ``evidence/type-inventory.json`` is
     present): every **non-generated, not-superseded** ``types[].dest_file``
     must appear in ≥1 story write-set. A dest_file MAY be declared
     superseded (partition or story ``supersedes``) by a named non-empty
     successor set; covered iff every successor is owned. Incomplete
     successor sets are gaps. Same dest_file on N stories is VALID (non-pom).
     Report **all** uncovered rows. Gap ``types_uncovered=N``. Missing file
     is skip, not INVALID.

Specimen-agnostic (Operator E-20260811T150800Z): HTTP denominator and package
rewrites are derived from inventory / migration.yaml — never hardcoded.

Usage:
  python3 check-partition-coverage.py /projects/modernized
    python3 check-partition-coverage.py . --write-receipt evidence/receipts/partition-coverage.json
  python3 check-partition-coverage.py . --retro   # evidence-only: never exit 1
  # --write-receipt also writes evidence/receipts/gates/check-spec-readiness.json
  # (runner schema for assert-pinned-gates-ran).
  # Default partition: evidence/partition.json, else evidence/briefs/partition.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
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

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _ensure_hermes_lib() -> None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            s = str(lib)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")
_ensure_hermes_lib()

from http_join import invented_route_gaps  # noqa: E402
from partition_story_consistency import extra_story_gaps  # noqa: E402
from specimen_agnostic import (  # noqa: E402
    acceptance_unsatisfiable_files,
    collect_supersedes,
    dest_path_as_written,
    inventory_http_expected,
    intra_package_maps,
    load_json,
    path_rewrites,
    resolve_inventory_path,
    resolve_partition_path,
    rewrite_across,
    story_declared_writeset,
    type_inventory_supersede_gaps,
    type_inventory_uncovered,
)


def make_norm_file(root: Path):
    rewrites = path_rewrites(root)
    leaves = intra_package_maps(root)

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
        return rewrite_across(
            p.lstrip("./"), rewrites, to_dest=False, leaf_pairs=leaves
        )

    return norm_file


def story_files(story: dict) -> list[str]:
    out: list[str] = []
    for key in ("files_writable", "files", "files_in_scope", "legacy_files", "scope_files"):
        val = story.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    for k in ("dest", "dst", "legacy", "src", "source", "path", "file"):
                        if item.get(k):
                            out.append(str(item[k]))
    return out


def partition_dual_frame_gaps(
    files: set[str], pairs: list[tuple[str, str]]
) -> list[str]:
    """Refuse a partition story that declares both mapped dest leaves."""
    gaps: list[str] = []
    for dest_leaf, leg_leaf in pairs:
        dtok = "/" + str(dest_leaf).strip("/").strip() + "/"
        ltok = "/" + str(leg_leaf).strip("/").strip() + "/"
        if dtok in {"//", "/"} or ltok in {"//", "/"} or dtok == ltok:
            continue
        dest_names: set[str] = set()
        leg_names: set[str] = set()
        for f in files:
            fl = f.replace("\\", "/")
            if not fl.endswith(".java"):
                continue
            name = fl.rsplit("/", 1)[-1]
            padded = f"/{fl}/"
            if dtok in padded or dtok in fl:
                dest_names.add(name)
            if ltok in padded or ltok in fl:
                leg_names.add(name)
        for name in sorted(dest_names & leg_names):
            gaps.append(f"partition_dual_frame:{name}")
    return gaps



def sequence_refs(body: dict) -> set[str]:
    """Carried story ids only — no filename/title/regex (SR-9)."""
    refs: set[str] = set()
    for key in ("sequence_after", "dependencies"):
        raw = body.get(key)
        if raw is None and isinstance(body.get("identity"), dict):
            raw = body["identity"].get(key)
        if isinstance(raw, str) and raw.strip():
            raw = [raw]
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                refs.add(item.strip())
            elif isinstance(item, dict):
                sid = item.get("story_id")
                if sid:
                    refs.add(str(sid).strip())
    return refs


def load_body_doc(path: Path) -> dict | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("body"), dict):
        return data["body"]
    return data


def _is_pom_rel(rel: str) -> bool:
    return Path(str(rel).replace("\\", "/")).name == "pom.xml"


def _endpoint_tokens(ep: str) -> set[str]:
    """Transcribed story.endpoints tokens (path-only or METHOD path). Not mint."""
    s = " ".join(str(ep).split())
    out = {s} if s else set()
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[1].strip():
        out.add(parts[1].strip())
    return out


def _row_tokens(row: dict) -> set[str]:
    method = str(row.get("http_method") or "").strip().upper()
    path = str(row.get("http_path") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    out: set[str] = set()
    if path:
        out.add(path)
        if method:
            out.add(f"{method} {path}")
    if symbol:
        out.add(symbol)
    return {x for x in out if x}


def _story_claims_http(story: dict, row: dict) -> bool:
    wanted: set[str] = set()
    for ep in story.get("endpoints") or []:
        wanted |= _endpoint_tokens(str(ep))
    return bool(wanted & _row_tokens(row))


def _carried_story_id(data: dict) -> str:
    ident = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    return str(ident.get("story_id") or data.get("story_id") or "").strip()


def body_files_for_story(bodies_dir: Path, story_id: str) -> list[str]:
    if not bodies_dir.is_dir():
        return []
    # Glob enumerates files; identity is the JSON field (SR-9c).
    for path in bodies_dir.glob("*.json"):
        if path.name.endswith(".sha256.json"):
            continue
        data = load_body_doc(path)
        if not isinstance(data, dict):
            continue
        if _carried_story_id(data) != story_id:
            continue
        out: list[str] = []
        for key in ("files_writable", "write_set", "files_in_scope", "filesInScope"):
            scope = data.get(key) or []
            if not isinstance(scope, list):
                continue
            for item in scope:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict):
                    for k in ("legacy", "src", "source", "path", "file", "dest"):
                        if item.get(k):
                            out.append(str(item[k]))
        return out
    return []


def body_sequence_map(bodies_dir: Path, story_ids: list[str]) -> dict[str, set[str]]:
    """Map each partition story_id -> carried sequence_after/dependencies ids."""
    out: dict[str, set[str]] = {sid: set() for sid in story_ids}
    if not bodies_dir.is_dir():
        return out
    wanted = set(story_ids)
    for path in bodies_dir.glob("*.json"):
        if path.name.endswith(".sha256.json"):
            continue
        data = load_body_doc(path)
        if not isinstance(data, dict):
            continue
        bid = _carried_story_id(data)
        if bid not in wanted:
            continue
        out[bid] = sequence_refs(data)
    return out


def _emit_gate_receipt(root: Path, rc: int) -> None:
    hit = (
        Path(__file__).resolve().parents[3]
        / "gates"
        / "assert-pinned-gates-ran"
        / "scripts"
        / "script_gate_receipt.py"
    )
    spec = importlib.util.spec_from_file_location("script_gate_receipt", hit)
    if spec is None or spec.loader is None:
        print("FAIL: script_gate_receipt.py missing", file=sys.stderr)
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    argv = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    mod.emit_script_receipt(root, "check-spec-readiness", rc, __file__, argv)


def _finish(args: argparse.Namespace, root: Path, rc: int) -> int:
    if args.write_receipt:
        _emit_gate_receipt(root, rc)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--partition",
        default="",
        help="Override partition path. Default: evidence/partition.json, "
        "then evidence/briefs/partition.json. Refusal names every path looked at.",
    )
    ap.add_argument("--inventory", default="")
    ap.add_argument(
        "--allow-specimen-fixture",
        action="store_true",
        help="Permit falling back to .hermes/skills/sdd/check-spec-readiness/fixtures/inventory/* specimen inventories",
    )
    ap.add_argument("--findings", default="evidence/mta-findings.json")
    ap.add_argument("--bodies", default="evidence/bodies")
    ap.add_argument("--write-receipt", default="")
    ap.add_argument("--retro", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    norm_file = make_norm_file(root)

    part_path, looked = resolve_partition_path(root, args.partition)
    partition = load_json(part_path) if part_path is not None else None
    if not isinstance(partition, dict) or not isinstance(partition.get("stories"), list):
        looked_s = "; ".join(looked) if looked else "(none)"
        where = str(part_path) if part_path is not None else looked_s
        print(
            "PARTITION_COVERAGE: INCONCLUSIVE — missing/invalid partition.json "
            f"(looked: {looked_s}; resolved: {where})",
            file=sys.stderr,
        )
        return _finish(args, root, 0 if args.retro else 1)

    inv_path = resolve_inventory_path(
        root,
        args.inventory,
        allow_specimen_fixture=bool(args.allow_specimen_fixture),
    )
    inventory = load_json(inv_path) if inv_path else None
    if not isinstance(inventory, dict):
        print("PARTITION_COVERAGE: INCONCLUSIVE — missing inventory", file=sys.stderr)
        return _finish(args, root, 0 if args.retro else 1)

    entry_points = inventory.get("entry_points") or []
    if not isinstance(entry_points, list) or not entry_points:
        print("PARTITION_COVERAGE: INCONCLUSIVE — inventory has no entry_points", file=sys.stderr)
        return _finish(args, root, 0 if args.retro else 1)

    http_eps = [e for e in entry_points if isinstance(e, dict) and e.get("kind") == "http"]
    ep_count = len(http_eps)
    expected_http = inventory_http_expected(inventory)
    gaps: list[str] = []
    declared = None
    totals = inventory.get("totals") if isinstance(inventory.get("totals"), dict) else {}
    for key in ("http_endpoints", "http", "endpoints_http", "expected_http_endpoints"):
        if key in totals:
            try:
                declared = int(totals[key])
            except (TypeError, ValueError):
                declared = None
            break
    if declared is not None and declared != ep_count:
        gaps.append(f"inventory_http_count={ep_count} inventory_totals_declared={declared}")

    stories = [s for s in partition["stories"] if isinstance(s, dict)]
    bodies_dir = root / args.bodies
    leaf_pairs = intra_package_maps(root)
    story_file_map: dict[str, set[str]] = {}
    for story in stories:
        sid = str(story.get("story_id") or "").strip()
        if not sid:
            gaps.append("story_missing_id")
            continue
        files = story_files(story)
        body_fs = body_files_for_story(bodies_dir, sid)
        chosen = body_fs if body_fs else files
        story_file_map[sid] = {norm_file(f) for f in chosen if f}
        declared_writeset = {
            dest_path_as_written(f) for f in story_declared_writeset(story) if f
        }
        body_as_written = {dest_path_as_written(f) for f in body_fs if f}
        if declared_writeset and body_as_written:
            extras = sorted(body_as_written - declared_writeset)
            if extras:
                gaps.append(f"writeset_not_subset:{sid}:{len(extras)}")
                for extra in extras[:8]:
                    gaps.append(f"writeset_extra:{sid}:{extra}")
        if declared_writeset and leaf_pairs:
            gaps.extend(partition_dual_frame_gaps(declared_writeset, leaf_pairs))
        for missing in acceptance_unsatisfiable_files(story):
            gaps.append(f"acceptance_unsatisfiable:{sid}:{missing}")

    owner: dict[str, str] = {}
    for sid, files in story_file_map.items():
        for f in files:
            if not f:
                continue
            if f in owner and owner[f] != sid:
                prev = owner[f]
                # Serial: non-pom overlap is A-5 (one in-flight card), not a
                # partition refuse. Unique pom.xml stays (DD3 / 152824Z).
                if not _is_pom_rel(f):
                    continue
                gaps.append(f"file_overlap:{f}:{prev}+{sid}")
            else:
                owner[f] = sid

    uncovered: list[str] = []
    multi: list[str] = []
    for ep in http_eps:
        f = norm_file(str(ep.get("file") or ""))
        sym = str(ep.get("symbol") or "")
        key = f"{f}#{sym}" if sym else f
        # A-8: transcribed route/symbol, not inventory.file ∈ dest write-set.
        claimants = [
            str(story.get("story_id") or "")
            for story in stories
            if str(story.get("story_id") or "") and _story_claims_http(story, ep)
        ]
        if len(claimants) == 0:
            uncovered.append(key)
        elif len(claimants) > 1:
            multi.append(f"{key}:{'+'.join(claimants)}")

    if uncovered:
        gaps.append(f"endpoints_uncovered={len(uncovered)}")
        gaps.append(
            "endpoints_field=story.endpoints METHOD /path (A-8; "
            "check-spec-readiness SKILL.md Contracts)"
        )
        for u in uncovered:
            gaps.append(f"uncovered:{u}")
    if multi:
        gaps.append(f"endpoints_multi={len(multi)}")
        for m in multi:
            gaps.append(f"multi:{m}")

    gaps.extend(invented_route_gaps(root, stories, inventory))
    gaps.extend(extra_story_gaps(stories))

    owned_dest: set[str] = set()
    for story in stories:
        for f in story_files(story):
            if f:
                owned_dest.add(dest_path_as_written(f))
        sid = str(story.get("story_id") or "").strip()
        if sid:
            for f in body_files_for_story(bodies_dir, sid):
                if f:
                    owned_dest.add(dest_path_as_written(f))
    supersedes = collect_supersedes(partition, stories)
    for g in type_inventory_supersede_gaps(owned_dest, supersedes):
        gaps.append(g)
    missing_types = type_inventory_uncovered(root, owned_dest, supersedes)
    if missing_types:
        gaps.append(f"types_uncovered={len(missing_types)}")
        for u in missing_types:
            gaps.append(f"uncovered-type:{u}")

    findings_path = root / args.findings
    findings = load_json(findings_path)
    mta_status = "skipped_missing"
    if not findings_path.is_file() or not isinstance(findings, dict):
        # WC-8: missing findings is INCONCLUSIVE, never a silent VALID.
        mta_status = "skipped_missing"
        gaps.append("mta_skipped_missing")
    else:
        # Presence only at create (154012Z / 154847Z). Do not join rule IDs
        # to story.rules — findings are legacy-tree, bodies are dest-tree.
        items = findings.get("violations") or findings.get("findings") or findings.get("rules") or []
        if items:
            mta_status = "checked"
        else:
            mta_status = "empty_findings"

    if any(
        g.startswith(
            ("acceptance_unsatisfiable:", "stale_ac:", "implicit_pom")
        )
        for g in gaps
    ):
        gaps.append(
            "unsatisfiable_acceptance_is_block_not_complete "
            "(kanban_block; do not kanban_complete)"
        )

    coverage_gaps = [g for g in gaps if g != "mta_skipped_missing"]
    if not story_file_map or all(len(v) == 0 for v in story_file_map.values()):
        verdict = "INCONCLUSIVE"
        gaps.append("no_story_files_in_partition_or_bodies")
    elif coverage_gaps:
        verdict = "INVALID"
    elif mta_status == "skipped_missing":
        verdict = "INCONCLUSIVE"
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
        "expected_http_endpoints": expected_http,
        "mta_status": mta_status,
        "gaps": gaps,
        "architect_bind": "E-20260811T133858Z",
        "operator_proposal": "E-20260811T134200Z",
        "portability_bind": "E-20260811T150800Z",
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
        return _finish(args, root, 0)
    return _finish(args, root, 0 if verdict == "VALID" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
