#!/usr/bin/env python3
"""Deterministic M3 body assembler (Architect E-20260814T181701Z / T-8 AMEND).

Copies partition fields. Exit cmds come from phase acceptance criteria.
`operand_class` is a set (string or list) used for B-16 skill attachment
and class-legal names — not the exit selector. Unknown tokens fail-closed.
`user_story` is AC-sourced. OBJECT a default `mvn -q test` on every card.

Mint-schema stamps (not oracles): role/task_id, AD-002E skills exit, F6
transform_class from the closed operand_class map, measured operand_count,
brief_identity_ack pending, legacy_locus digest **and path** of the harvest
file that was hashed (not a dest-relative alias). HTTP stories join M1
`entry-point-inventory.json` on transcribed route/symbol (A-8) and stamp
**that row's** harvest file — never dest `*Resource.java` looked up in
`/projects/legacy` (Architect `E-20260817T150714Z`). setup/foundational/polish
stamp M1 `evidence/derived/legacy-at-3.json` (no Java-file locus). Mint
refuses unless sha256(resolve(path)) equals the stamped digest (pending
fail-closed except creation-time ack keys). SR-13/L2a: a test-shaped `mvn … test` or `mvn … verify` must name
`proves` test source(s) in this story's write-set — an unrelated dest
`src/test` file must not satisfy the oracle. curl / scripts are not
card exits. Assembler copies test paths already in `files_writable`
onto `proves`; it does not invent a test file (L4). DD3: every story
gets identity.extensions_declared
(T-3 path heuristic); the sole pom.xml writer also declares M1
evidence/required-extensions.json so apply is the sibling union
(including that set). Non-writers omit extensions_apply (key absent).

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
    AC_SOURCED_OPERAND_CLASSES,
    DEFAULT_TEST_CMD,
    PREFERRED_SEMANTIC_EXIT_CMD,
    ac_sourced_operand_classes,
    exit_cmd_discriminating_errors,
    filter_attach_skills_for_write_set,
    is_test_source_rel,
    known_operand_classes,
    parse_operand_classes,
    preferred_semantic_exit_for,
    refs_path_sha_errors,
    semantic_exit_cmd_is_maven,
    semantic_exit_cmd_ok,
    skills_for_operand_classes,
    stamp_dd3_extensions,
    stamp_operand_class,
    unknown_operand_classes,
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
    worker wrote dest `pom.xml`. `rel` must already be a harvest-relative
    path (inventory `file`, not dest `*Resource.java`).
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


_NO_JAVA_LOCUS_KINDS = frozenset({"setup", "foundational", "polish"})


def _load_inventory(root: Path) -> list[dict]:
    path = root / "evidence/entry-point-inventory.json"
    if not path.is_file():
        raise ValueError("legacy_locus: missing evidence/entry-point-inventory.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("entry_points") or []
    if not isinstance(rows, list):
        raise ValueError("legacy_locus: inventory entry_points is not a list")
    return [r for r in rows if isinstance(r, dict)]


def _endpoint_tokens(ep: str) -> set[str]:
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


def _inventory_row_for_story(story: dict, rows: list[dict]) -> dict:
    wanted: set[str] = set()
    for ep in story.get("endpoints") or []:
        wanted |= _endpoint_tokens(str(ep))
    for row in rows:
        if wanted & _row_tokens(row):
            return row
    sid = str(story.get("story_id") or "")
    raise ValueError(
        f"{sid}: legacy_locus: no inventory row for endpoints "
        f"{list(story.get('endpoints') or [])!r} (A-8 join; not dest filename)"
    )


def _harvest_referent_locus(root: Path) -> tuple[str, str]:
    ref = root / "evidence/derived/legacy-at-3.json"
    if not ref.is_file():
        raise ValueError(
            "legacy_locus: setup/foundational/polish need "
            "evidence/derived/legacy-at-3.json (M1 harvest_referent); "
            "no Java-file lookup"
        )
    resolved = ref.resolve()
    return resolved.as_posix(), _sha256_file(resolved)


def _stamp_legacy_locus(story: dict, root: Path) -> tuple[str, str]:
    kind = str(story.get("kind") or "").strip().lower()
    if kind in _NO_JAVA_LOCUS_KINDS:
        return _harvest_referent_locus(root)
    row = _inventory_row_for_story(story, _load_inventory(root))
    rel = _dest_rel(str(row.get("file") or ""))
    if not rel:
        raise ValueError(f"{story.get('story_id')}: inventory row has empty file")
    return _legacy_locus(root, rel)


def _acceptance_exits(story: dict) -> list[dict]:
    for key in ("acceptance_criteria", "exit_criteria", "done_when"):
        raw = story.get(key)
        if not isinstance(raw, list) or not raw:
            continue
        out: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            cmd = item.get("cmd")
            check = str(item.get("check") or "").strip()
            if not (isinstance(cmd, str) and cmd.strip() and check):
                continue
            entry = {"check": check, "cmd": cmd.strip()}
            if "proves" in item:
                entry["proves"] = item["proves"]
            if item.get("assert"):
                entry["assert"] = item["assert"]
            out.append(entry)
        if out:
            return out
    return []


def _semantic_exit_from_item(item: dict, fis: list[str], sid: str) -> dict:
    check = str(item.get("check") or "").strip()
    cmd = str(item.get("cmd") or "").strip()
    if not semantic_exit_cmd_ok(check, cmd):
        raise ValueError(
            f"{sid}: exit {check!r} cmd {cmd!r} is not a discriminating "
            f"Maven vehicle (mvn test|verify|test-compile, or compile for "
            f"build_resolves; curl/scripts are not card exits — SR-13)"
        )
    semantic_exit: dict = {"check": check, "cmd": cmd}
    if "assert" in item:
        semantic_exit["assert"] = item["assert"]
    proves = item.get("proves")
    ok_mvn, mvn_parts = semantic_exit_cmd_is_maven(cmd)
    if ok_mvn and mvn_parts and mvn_parts[-1] in {"test", "verify"}:
        if isinstance(proves, list) and proves:
            semantic_exit["proves"] = proves
        else:
            inferred = [p for p in fis if is_test_source_rel(p)]
            if inferred:
                semantic_exit["proves"] = inferred
    elif proves:
        semantic_exit["proves"] = proves
    return semantic_exit


def assemble_one(story: dict, root: Path, *, measured_operands) -> dict:
    sid = str(story.get("story_id") or "").strip()
    ident_src = story.get("identity") if isinstance(story.get("identity"), dict) else {}
    raw_oc = story.get("operand_class")
    if raw_oc is None:
        raw_oc = ident_src.get("operand_class")
    classes = parse_operand_classes(raw_oc)
    if not sid:
        raise ValueError("partition story missing story_id")
    if not classes:
        raise ValueError(f"{sid}: missing operand_class (OBJECT dropping the field)")
    unknown = unknown_operand_classes(classes)
    if unknown:
        raise ValueError(
            f"{sid}: unknown operand_class={unknown!r} — no legal exit set "
            "(T-8 fail-closed, Architect E-20260814T181701Z)"
        )
    known = known_operand_classes(classes)
    ac_only = ac_sourced_operand_classes(classes)
    if not known and not ac_only:
        raise ValueError(
            f"{sid}: unknown operand_class={classes!r} — no legal exit set "
            "(T-8 fail-closed, Architect E-20260814T181701Z)"
        )
    fis = [_dest_rel(_paths(x)) for x in (story.get("files_in_scope") or [])]
    fis = [p for p in fis if p]
    if not fis:
        raise ValueError(f"{sid}: empty files_in_scope (PB-2 / S-012)")

    ac = _acceptance_exits(story)
    semantic_exits: list[dict] = []
    if ac:
        semantic_exits = [_semantic_exit_from_item(x, fis, sid) for x in ac]
    elif len(classes) != 1 or classes[0] in AC_SOURCED_OPERAND_CLASSES:
        raise ValueError(
            f"{sid}: multi-class / user_story card needs acceptance_criteria "
            f"cmds (T-8 AMEND; OBJECT default {DEFAULT_TEST_CMD!r})"
        )
    else:
        oc = classes[0]
        check = preferred_semantic_exit_for(oc)
        if not check:
            raise ValueError(f"{sid}: operand_class={oc!r} has no preferred stamp")
        cmd = PREFERRED_SEMANTIC_EXIT_CMD.get(check, check)
        if cmd == DEFAULT_TEST_CMD:
            proves = [p for p in fis if is_test_source_rel(p)]
            if not proves:
                raise ValueError(
                    f"{sid}: OBJECT default {DEFAULT_TEST_CMD!r} — stamp "
                    "acceptance_criteria or include the proving test in "
                    "files_in_scope (T-8 AMEND / SR-13)"
                )
            semantic_exits = [
                _semantic_exit_from_item(
                    {"check": check, "cmd": cmd, "proves": proves}, fis, sid
                )
            ]
        else:
            semantic_exits = [_semantic_exit_from_item({"check": check, "cmd": cmd}, fis, sid)]

    oc_stamp = stamp_operand_class(classes)
    oc_for_transform = classes[0]
    for c in classes:
        if c in TRANSFORM_CLASS_FOR_OPERAND:
            oc_for_transform = c
            break
    tc = str(
        ident_src.get("transform_class")
        or story.get("transform_class")
        or TRANSFORM_CLASS_FOR_OPERAND.get(oc_for_transform, DEFAULT_TRANSFORM_CLASS)
    ).upper()
    g2 = str(
        ident_src.get("g2_applicability") or story.get("g2_applicability") or DEFAULT_G2
    ).lower()
    locus_path, locus_sha = _stamp_legacy_locus(story, root)
    operand_skills = filter_attach_skills_for_write_set(
        skills_for_operand_classes(classes), fis
    )

    body = {
        "phase": "M3",
        "role": "implementer",
        "task_id": sid,
        "task_type": "implementing",
        "identity": {
            "story_id": sid,
            "operand_class": oc_stamp,
            "operand_skills": operand_skills,
            "transform_class": tc,
            "g2_applicability": g2,
            "sizing_basis": "operand_count",
        },
        "files_in_scope": fis,
        "files_writable": list(fis),
        "phase_checklist": list(story.get("phase_checklist") or []),
        "exit_criteria": [
            *semantic_exits,
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
    parents = story.get("parents") or ident_src.get("parents") or []
    if isinstance(parents, list) and parents:
        body["identity"]["parents"] = [str(x) for x in parents if str(x).strip()]
    wk = story.get("workspace_kind") or ident_src.get("workspace_kind")
    if wk:
        body["identity"]["workspace_kind"] = str(wk)
    if not body["phase_checklist"]:
        body.pop("phase_checklist", None)
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
        stamp_dd3_extensions([body for _, body in assembled], root=root)
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
