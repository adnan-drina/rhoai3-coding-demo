#!/usr/bin/env python3
"""Deterministic M3 body assembler (Architect E-20260814T181701Z).

Copies partition fields. Stamps the singleton class-legal exit. Does not invent
oracles. Unknown operand_class refuses (T-8 fail-closed).

Mint-schema stamps (not oracles): role/task_id, AD-002E skills exit, F6
transform_class from the closed operand_class map, measured operand_count,
brief_identity_ack pending, legacy_locus digest **and path** of the harvest
file that was hashed (not a dest-relative alias). Mint refuses unless
sha256(resolve(path)) equals the stamped digest (pending fail-closed except
creation-time ack keys). SR-13/L2a: a test-shaped `mvn … test` must name
`proves` test source(s) in this story's write-set — an unrelated dest
`src/test` file must not satisfy the oracle. Assembler copies test paths
already in `files_writable` onto `proves`; it does not invent a test file
(L4). DD3: every story gets identity.extensions_declared
(T-3 path heuristic); the sole pom.xml writer gets identity.extensions_apply
= sorted unique union. Non-writers omit extensions_apply (key absent).

Does not mint. Does not dispatch a worker.

Usage:
  python3 assemble-m3-bodies-from-partition.py <root> [--dry-run]
  python3 assemble-m3-bodies-from-partition.py <root> --write
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from specimen_agnostic import (  # noqa: E402
    OPERAND_CLASS_SEMANTIC_EXITS,
    PREFERRED_SEMANTIC_EXIT_CMD,
    exit_cmd_discriminating_errors,
    is_test_source_rel,
    preferred_semantic_exit_for,
    refs_path_sha_errors,
    semantic_exit_cmd_is_maven,
    semantic_exit_cmd_ok,
    stamp_dd3_extensions,
)

# F6 closed map — partition stories do not carry transform_class.
# CONFIG for build/config; HARVEST for code translation. Not a per-story invent.
TRANSFORM_CLASS_FOR_OPERAND: dict[str, str] = {
    "build_config": "CONFIG",
    "build-config": "CONFIG",
    "config": "CONFIG",
    "pom": "CONFIG",
}
DEFAULT_TRANSFORM_CLASS = "HARVEST"
DEFAULT_G2 = "not_applicable"

SKILLS_EXIT = {
    "check": "skills",
    "assert": "AD-002E: consult or skills_unused; silence invalid",
}

_PREFIXES = (
    "/projects/.derived/legacy-at-3/",
    "/projects/modernized/",
    "/projects/legacy/",
    "projects/.derived/legacy-at-3/",
    "projects/modernized/",
    "projects/legacy/",
)


def _load_measured_operands():
    path = Path(__file__).with_name("check-operand-count.py")
    spec = importlib.util.spec_from_file_location("check_operand_count", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load check-operand-count.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.measured_operands


def _paths(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("path", "file", "dest", "dst", "src"):
            if item.get(k):
                return str(item[k])
    return ""


def _dest_rel(path: str) -> str:
    p = path.replace("\\", "/").strip()
    for prefix in _PREFIXES:
        if p.startswith(prefix):
            p = p[len(prefix) :]
            break
    return p.lstrip("./")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_locus(root: Path, rel: str) -> tuple[str, str]:
    """Hash the harvest file and stamp *that* path, not a dest-relative alias.

    Architect E-20260814T212425Z: returning dest-relative `rel` while hashing
    `.derived/legacy-at-3/<rel>` made the ref self-invalidating once the
    worker wrote dest `pom.xml`.
    """
    rel = _dest_rel(rel)
    candidates = [
        Path("/projects/.derived/legacy-at-3") / rel,
        root.parent / ".derived" / "legacy-at-3" / rel,
        Path("/projects/legacy") / rel,
        root / rel,
    ]
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved.as_posix(), _sha256_file(resolved)
    raise ValueError(f"legacy_locus: no file for {rel!r}")


def assemble_one(story: dict, root: Path, *, measured_operands) -> dict:
    sid = str(story.get("story_id") or "").strip()
    oc = str(story.get("operand_class") or "").strip()
    if not sid:
        raise ValueError("partition story missing story_id")
    if oc not in OPERAND_CLASS_SEMANTIC_EXITS:
        raise ValueError(
            f"{sid}: unknown operand_class={oc!r} — no legal exit set "
            "(T-8 fail-closed, Architect E-20260814T181701Z)"
        )
    check = preferred_semantic_exit_for(oc)
    if not check:
        raise ValueError(f"{sid}: operand_class={oc!r} has no preferred stamp")
    fis = [_dest_rel(_paths(x)) for x in (story.get("files_in_scope") or [])]
    fis = [p for p in fis if p]
    if not fis:
        raise ValueError(f"{sid}: empty files_in_scope (PB-2 / S-012)")
    cmd = PREFERRED_SEMANTIC_EXIT_CMD.get(check, check)
    if not semantic_exit_cmd_ok(check, cmd):
        raise ValueError(
            f"{sid}: exit {check!r} cmd {cmd!r} is not a Maven invocation "
            "(stamp `mvn -q compile` or `mvn -q test`; prose belongs in assert; "
            "evaluator runs cmd via shell=True)"
        )
    semantic_exit: dict = {"check": check, "cmd": cmd}
    ok_mvn, mvn_parts = semantic_exit_cmd_is_maven(cmd)
    if ok_mvn and mvn_parts and mvn_parts[-1] == "test":
        proves = [p for p in fis if is_test_source_rel(p)]
        if proves:
            semantic_exit["proves"] = proves

    ident_src = story.get("identity") if isinstance(story.get("identity"), dict) else {}
    tc = str(
        ident_src.get("transform_class")
        or story.get("transform_class")
        or TRANSFORM_CLASS_FOR_OPERAND.get(oc, DEFAULT_TRANSFORM_CLASS)
    ).upper()
    g2 = str(
        ident_src.get("g2_applicability") or story.get("g2_applicability") or DEFAULT_G2
    ).lower()
    locus_path, locus_sha = _legacy_locus(root, fis[0])

    body = {
        "phase": "M3",
        "role": "implementer",
        "task_id": sid,
        "task_type": "implementing",
        "identity": {
            "story_id": sid,
            "operand_class": oc,
            "transform_class": tc,
            "g2_applicability": g2,
            "sizing_basis": "operand_count",
        },
        "files_in_scope": fis,
        "files_writable": list(fis),
        "exit_criteria": [
            semantic_exit,
            dict(SKILLS_EXIT),
        ],
        "refs": [
            {
                "key": "brief_identity_ack",
                "path": "evidence/acks/brief-identity.ack",
                "sha256": "pending",
            },
            {
                "key": "legacy_locus",
                "path": locus_path,
                "sha256": locus_sha,
            },
        ],
    }
    oracle_errs = refs_path_sha_errors(root, body["refs"])
    if oracle_errs:
        raise ValueError(f"{sid}: refs path-sha oracle: {oracle_errs[0]}")
    disc = exit_cmd_discriminating_errors(root, body)
    if disc:
        raise ValueError(f"{sid}: SR-13 discriminating-exit: {disc[0]}")
    measured = measured_operands(body)
    if not measured:
        raise ValueError(
            f"{sid}: no measurable dest operands after copy "
            f"(files_writable={fis!r})"
        )
    body["identity"]["operand_count"] = len(measured)
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.write and args.dry_run:
        print("assemble-m3-bodies: use --dry-run or --write, not both", file=sys.stderr)
        return 2
    if not args.write:
        args.dry_run = True

    root = Path(args.root).resolve()
    part = root / "evidence/briefs/partition.json"
    if not part.is_file():
        print(f"FAIL: missing {part}", file=sys.stderr)
        return 1
    data = json.loads(part.read_text(encoding="utf-8"))
    stories = data.get("stories") or data.get("units") or []
    out_dir = root / "evidence/bodies"
    measured_operands = _load_measured_operands()
    assembled: list[tuple[str, dict]] = []
    for s in stories:
        if not isinstance(s, dict):
            continue
        try:
            body = assemble_one(s, root, measured_operands=measured_operands)
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        sid = body["identity"]["story_id"]
        assembled.append((sid, body))

    if not assembled:
        print("FAIL: partition has zero stories", file=sys.stderr)
        return 1

    try:
        stamp_dd3_extensions([body for _, body in assembled])
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    for sid, body in assembled:
        oc = body["identity"]["operand_class"]
        check = body["exit_criteria"][0]["check"]
        n = body["identity"]["operand_count"]
        dest = out_dir / f"m3-{sid}.json"
        print(
            f"{sid} operand_class={oc} exit={check} "
            f"operand_count={n} -> {dest}"
        )
        if args.write:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"OK: assemble-m3-bodies {mode} n={len(assembled)} (no mint)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
