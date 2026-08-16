#!/usr/bin/env python3
"""Post-workflow handover mint (A-4 / A-5 / A-8).

Fail-closed: tasks.md User-Story phases → typed partition receipt + bodies.
Parents are transcribed from the Dependencies section (not inferred).
File-granular ownership is a distinct step after grouping. Endpoint coverage
is vs M1 inventory. OBJECT spec-kit hooks (V20-5 advisory).

Does not call hermes unless --parent is passed (then mint-m3-wave.sh).

Usage:
  python3 handover-mint.py <root> --dry-run
  python3 handover-mint.py <root> --write
  python3 handover-mint.py <root> --write --parent <wave_holder>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent


def _migration_root(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if (cur / "migration.yaml").is_file():
            return cur
        if cur == cur.parent:
            raise SystemExit("cannot find project root (migration.yaml) (SR-2)")
        cur = cur.parent


_READY = (
    _migration_root(_SCRIPTS)
    / ".hermes"
    / "skills"
    / "sdd"
    / "check-spec-readiness"
    / "scripts"
)
if str(_READY) not in sys.path:
    sys.path.insert(0, str(_READY))

from specimen_agnostic import (  # noqa: E402
    is_test_source_rel,
    load_json,
    resolve_inventory_path,
)

PHASE_HEADING = re.compile(r"^## Phase\s+(\d+|N):\s+(.+?)\s*$", re.I)
DEPS_HEADING = re.compile(r"^## Dependencies\b", re.I)
CHECKBOX = re.compile(r"^- \[[ xX]\]\s+(.+)$")
PATH_TOKEN = re.compile(
    r"(?<![\w./])((?:src|tests)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+|pom\.xml)(?![\w./])"
)
US_HEADING = re.compile(r"User Story\s+(\d+)", re.I)
US_TAG = re.compile(r"\[US(\d+)\]")
INDEPENDENT_TEST = re.compile(
    r"\*\*Independent Test\*\*:\s*(.+)", re.I
)
PRIORITY = re.compile(r"Priority:\s*(P\d+)", re.I)
SETUP_DEPS = re.compile(r"\*\*Setup\b.*\*\*:\s*(.+)", re.I)
FOUND_DEPS = re.compile(r"\*\*Foundational\b.*\*\*:\s*(.+)", re.I)
US_ALL_DEPS = re.compile(
    r"\*\*User Stories\b.*\*\*:\s*(.+)", re.I
)
POLISH_DEPS = re.compile(r"\*\*Polish\b.*\*\*:\s*(.+)", re.I)
US_LINE_DEPS = re.compile(
    r"\*\*User Story\s+(\d+)\b.*\*\*:\s*(.+)", re.I
)
DEPENDS_ON_US = re.compile(
    r"Depends on User Story\s+(\d+)|Depends on US(\d+)", re.I
)

KIND_SETUP = "setup"
KIND_FOUNDATIONAL = "foundational"
KIND_USER_STORY = "user_story"
KIND_POLISH = "polish"

RECEIPT_SOURCE = "handover-mint"
RECEIPT_SCHEMA = "rhoai3.partition-receipt/v1"
SRC_CAP = 40
BUILD_CAP = 12
DUAL_STACK_MIN = 20


class HandoverError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Phase:
    heading: str
    kind: str
    story_id: str
    body: str
    files: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    independent_test: str = ""
    priority: str = ""
    parents: list[str] = field(default_factory=list)
    operand_class: list[str] = field(default_factory=list)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    workspace_kind: str = "dir"
    endpoints: list[str] = field(default_factory=list)


def _die(code: str, detail: str) -> None:
    raise HandoverError(code, detail)


def _norm_path(raw: str) -> str:
    p = raw.replace("\\", "/").strip().lstrip("./")
    if not p or ".." in Path(p).parts or p.startswith("/"):
        _die("PATH_ILLEGAL", f"refusing path {raw!r}")
    return p


def _is_pom(path: str) -> bool:
    return path == "pom.xml" or path.endswith("/pom.xml")


def _kind_and_id(title: str, body: str) -> tuple[str, str]:
    low = title.lower()
    if "user story" in low:
        m = US_HEADING.search(title)
        if not m:
            _die("STORY_ID", f"user-story phase heading has no number: {title!r}")
        n = m.group(1)
        tags = set(US_TAG.findall(body))
        if tags and tags != {n}:
            _die(
                "STORY_ID_MISMATCH",
                f"heading US{n} vs task tags {sorted(tags)}",
            )
        return KIND_USER_STORY, f"US{n}"
    if "setup" in low:
        return KIND_SETUP, KIND_SETUP
    if "foundational" in low:
        return KIND_FOUNDATIONAL, KIND_FOUNDATIONAL
    if "polish" in low:
        return KIND_POLISH, KIND_POLISH
    _die("PHASE_KIND", f"unrecognised phase heading: {title!r}")
    raise AssertionError("unreachable")


def parse_phases(text: str) -> list[Phase]:
    lines = text.splitlines()
    starts: list[tuple[int, str, str]] = []
    deps_at: int | None = None
    for i, line in enumerate(lines):
        if DEPS_HEADING.match(line):
            deps_at = i
            break
        m = PHASE_HEADING.match(line)
        if m:
            starts.append((i, m.group(1), m.group(2).strip()))
    if not starts:
        _die("TASKS_MD", "no '## Phase N:' headings")
    if deps_at is None:
        _die(
            "DEPENDENCIES_MISSING",
            "tasks.md has no '## Dependencies' section — parents cannot be transcribed",
        )
    phases: list[Phase] = []
    for idx, (start, _num, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else deps_at
        body = "\n".join(lines[start + 1 : end])
        kind, sid = _kind_and_id(title, body)
        checklist = [m.group(0) for line in body.splitlines() if (m := CHECKBOX.match(line))]
        files: list[str] = []
        for line in body.splitlines():
            for raw in PATH_TOKEN.findall(line):
                p = _norm_path(raw)
                if p not in files:
                    files.append(p)
        ind = ""
        im = INDEPENDENT_TEST.search(body)
        if im:
            ind = im.group(1).strip()
        pri = ""
        pm = PRIORITY.search(title)
        if pm:
            pri = pm.group(1)
        phases.append(
            Phase(
                heading=title,
                kind=kind,
                story_id=sid,
                body=body,
                files=files,
                checklist=checklist,
                independent_test=ind,
                priority=pri,
            )
        )
    seen: set[str] = set()
    for ph in phases:
        if ph.story_id in seen:
            _die("STORY_ID", f"duplicate story_id {ph.story_id!r}")
        seen.add(ph.story_id)
    return phases


def transcribe_parents(text: str, phases: list[Phase]) -> None:
    deps_at = None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if DEPS_HEADING.match(line):
            deps_at = i
            break
    assert deps_at is not None
    block = "\n".join(lines[deps_at:])
    by_id = {p.story_id: p for p in phases}
    us_ids = [p.story_id for p in phases if p.kind == KIND_USER_STORY]

    setup_line = SETUP_DEPS.search(block)
    found_line = FOUND_DEPS.search(block)
    us_all = US_ALL_DEPS.search(block)
    polish_line = POLISH_DEPS.search(block)
    if KIND_SETUP in by_id:
        if not setup_line:
            _die("DEPENDENCIES_MISSING", "Setup bullet missing from Dependencies")
        if re.search(r"no dependencies", setup_line.group(1), re.I):
            by_id[KIND_SETUP].parents = []
        else:
            _die("DEPENDENCIES", f"Setup is not 'No dependencies': {setup_line.group(1)!r}")
    if KIND_FOUNDATIONAL in by_id:
        if not found_line:
            _die("DEPENDENCIES_MISSING", "Foundational bullet missing from Dependencies")
        if re.search(r"depends on setup", found_line.group(1), re.I):
            if KIND_SETUP not in by_id:
                _die("DEPENDENCIES", "Foundational depends on Setup but Setup phase is absent")
            by_id[KIND_FOUNDATIONAL].parents = [KIND_SETUP]
        else:
            _die("DEPENDENCIES", f"Foundational parents not transcribed: {found_line.group(1)!r}")
    default_us_parents = [KIND_FOUNDATIONAL]
    if us_ids:
        if not us_all or not re.search(r"depend on Foundational", us_all.group(1), re.I):
            _die(
                "DEPENDENCIES_MISSING",
                "User Stories bullet must say they depend on Foundational",
            )
        if KIND_FOUNDATIONAL not in by_id:
            _die("DEPENDENCIES", "user stories depend on Foundational but that phase is absent")
    per_us: dict[str, list[str]] = {sid: list(default_us_parents) for sid in us_ids}
    for m in US_LINE_DEPS.finditer(block):
        sid = f"US{m.group(1)}"
        rest = m.group(2)
        extra: list[str] = []
        for dm in DEPENDS_ON_US.finditer(rest):
            n = dm.group(1) or dm.group(2)
            extra.append(f"US{n}")
        if extra:
            per_us[sid] = default_us_parents + extra
    for sid, parents in per_us.items():
        if sid in by_id:
            by_id[sid].parents = parents
    if KIND_POLISH in by_id:
        if not polish_line or not re.search(
            r"depends on all desired user stories", polish_line.group(1), re.I
        ):
            _die("DEPENDENCIES_MISSING", "Polish bullet must depend on all user stories")
        by_id[KIND_POLISH].parents = list(us_ids)


def assign_ownership(phases: list[Phase]) -> str:
    """A-5: one dest file, one owner. pom owner unique (earliest claimant)."""
    claimants: dict[str, list[str]] = {}
    for ph in phases:
        for f in ph.files:
            claimants.setdefault(f, []).append(ph.story_id)
    pom_owner = ""
    overlaps: list[str] = []
    for path, owners in claimants.items():
        uniq = list(dict.fromkeys(owners))
        if len(uniq) <= 1:
            if _is_pom(path) and uniq:
                pom_owner = uniq[0]
            continue
        if _is_pom(path):
            pom_owner = uniq[0]
            for ph in phases:
                if ph.story_id != pom_owner:
                    ph.files = [f for f in ph.files if not _is_pom(f)]
            continue
        overlaps.append(f"{path}:{'+'.join(uniq)}")
    if overlaps:
        _die("FILE_OVERLAP", "; ".join(overlaps))
    pom_writers = [
        ph.story_id for ph in phases if any(_is_pom(f) for f in ph.files)
    ]
    if len(pom_writers) > 1:
        _die("POM_OWNER", f"pom.xml still claimed by {pom_writers}")
    if pom_writers:
        pom_owner = pom_writers[0]
    return pom_owner


def _classes_for(ph: Phase) -> list[str]:
    classes: list[str] = []

    def add(token: str) -> None:
        if token not in classes:
            classes.append(token)

    for p in ph.files:
        name = Path(p).name
        if _is_pom(p) or p.startswith("src/main/resources/") or p.startswith("src/test/resources/"):
            add("build_config")
        elif is_test_source_rel(p):
            add("test")
        elif "RestController" in name or name.endswith("Resource.java"):
            add("rest")
        elif "Repository" in name or "Entity" in name:
            add("persistence")
        elif p.startswith("src/") and p.endswith(".java"):
            add("src_code")
        elif p.endswith(".properties") or p.endswith(".yml") or p.endswith(".yaml"):
            add("config")
    if ph.kind == KIND_USER_STORY:
        add("user_story")
    if not classes:
        _die("OPERAND_CLASS", f"{ph.story_id}: no classifiable files {ph.files!r}")
    return classes


def _proves_for(ph: Phase) -> list[str]:
    from_ind = [_norm_path(x) for x in PATH_TOKEN.findall(ph.independent_test)]
    from_ind = [p for p in from_ind if is_test_source_rel(p) and p in ph.files]
    if from_ind:
        return from_ind
    return [p for p in ph.files if is_test_source_rel(p)]


def stamp_oracles(phases: list[Phase]) -> None:
    for ph in phases:
        if not ph.files:
            _die("FILES_IN_SCOPE", f"{ph.story_id}: empty files_in_scope after ownership")
        ph.operand_class = _classes_for(ph)
        src_n = len([p for p in ph.files if p.startswith("src/")])
        build_only = all(
            c in {"build_config", "config", "pom"} for c in ph.operand_class
        )
        cap = BUILD_CAP if build_only else SRC_CAP
        measured = src_n if not build_only else len(ph.files)
        if measured > cap:
            _die(
                "BODY_SIZE",
                f"{ph.story_id}: measured={measured} > max={cap} — decompose the phase "
                "(R-V14.4; do not raise the wall)",
            )
        lower = [p.lower() for p in ph.files]
        if (
            not build_only
            and any("/jpa/" in p or p.endswith("/jpa") for p in lower)
            and any("/jdbc/" in p or p.endswith("/jdbc") for p in lower)
            and src_n >= DUAL_STACK_MIN
        ):
            _die(
                "BODY_SIZE",
                f"{ph.story_id}: JPA+JDBC trees with measured={src_n}≥{DUAL_STACK_MIN} "
                "— split (R-V14.4)",
            )
        proves = _proves_for(ph)
        if build_only and not proves:
            ph.acceptance_criteria = [
                {"check": "build_resolves", "cmd": "mvn -q compile"}
            ]
            continue
        if ph.kind == KIND_USER_STORY and not ph.independent_test:
            _die(
                "PHASE_AC",
                f"{ph.story_id}: user-story phase has no Independent Test",
            )
        if not proves:
            _die(
                "PHASE_AC",
                f"{ph.story_id}: phase AC cannot be a test (no proving test in "
                "write-set) — phase-decomposition defect, do not loosen the oracle",
            )
        check = "http_semantics"
        if "rest" not in ph.operand_class and "persistence" in ph.operand_class:
            check = "mapping_valid"
        elif "rest" not in ph.operand_class and "build_config" in ph.operand_class:
            check = "build_resolves"
            ph.acceptance_criteria = [
                {"check": check, "cmd": "mvn -q compile"}
            ]
            continue
        ph.acceptance_criteria = [
            {
                "check": check,
                "cmd": "mvn -q test",
                "proves": proves,
            }
        ]


def stamp_workspaces(phases: list[Phase]) -> None:
    for ph in phases:
        extra = [p for p in ph.parents if p != KIND_FOUNDATIONAL]
        if ph.kind == KIND_USER_STORY and not extra:
            ph.workspace_kind = "worktree"
        else:
            ph.workspace_kind = "dir"


def cover_endpoints(phases: list[Phase], inventory: dict[str, Any]) -> None:
    eps = inventory.get("entry_points") or []
    if not isinstance(eps, list) or not eps:
        _die("INVENTORY", "inventory has no entry_points")
    http = [e for e in eps if isinstance(e, dict) and e.get("kind") == "http"]
    if not http:
        _die("INVENTORY", "inventory has no HTTP entry_points")
    file_owner = {}
    for ph in phases:
        for f in ph.files:
            file_owner[f] = ph.story_id
    uncovered: list[str] = []
    multi: list[str] = []
    claimed: dict[str, list[str]] = {ph.story_id: [] for ph in phases}
    for ep in http:
        f = _norm_path(str(ep.get("file") or ""))
        sym = str(ep.get("symbol") or "")
        key = f"{f}#{sym}" if sym else f
        owner = file_owner.get(f)
        if not owner:
            uncovered.append(key)
            continue
        claimed[owner].append(key)
    if uncovered:
        _die(
            "endpoints_uncovered",
            f"count={len(uncovered)} " + " ".join(uncovered[:12]),
        )
    if multi:
        _die("endpoints_multi", "; ".join(multi))
    for ph in phases:
        ph.endpoints = claimed.get(ph.story_id, [])


def _resolve_explicit(root: Path, explicit: str, code: str) -> Path:
    p = Path(explicit)
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.extend([Path.cwd() / p, root / p])
    for c in candidates:
        if c.is_file():
            return c
    _die(code, f"missing {explicit}")
    raise AssertionError("unreachable")


def find_tasks_md(root: Path, explicit: str) -> Path:
    if explicit:
        return _resolve_explicit(root, explicit, "TASKS_MD")
    hits = (
        sorted(p for p in (root / "specs").glob("**/tasks.md") if p.is_file())
        if (root / "specs").is_dir()
        else []
    )
    root_tasks = root / "tasks.md"
    if root_tasks.is_file():
        hits.append(root_tasks)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        _die("TASKS_MD", f"multiple tasks.md files: {[str(h) for h in hits]}")
    _die("TASKS_MD", "no tasks.md under specs/ or root")
    raise AssertionError("unreachable")


def load_inventory(root: Path, explicit: str) -> tuple[Path, dict[str, Any]]:
    if explicit:
        p = _resolve_explicit(root, explicit, "INVENTORY")
        data = load_json(p)
        if not isinstance(data, dict):
            _die("INVENTORY", f"invalid {p}")
        return p, data
    path = resolve_inventory_path(root, "", allow_specimen_fixture=False)
    data = load_json(path) if path else None
    if not isinstance(data, dict) or not path:
        _die("INVENTORY", "missing evidence/entry-point-inventory.json")
    return path, data


def path_a_partition_on_disk(root: Path) -> None:
    part = root / "evidence" / "briefs" / "partition.json"
    if not part.is_file():
        return
    data = load_json(part)
    if not isinstance(data, dict) or data.get("source") != RECEIPT_SOURCE:
        _die(
            "PATH_A_PARTITION",
            "existing evidence/briefs/partition.json is not a handover-mint "
            "receipt — refuse as Path-A input (rm it; do not author stories there)",
        )


def build_receipt(
    *,
    tasks_md: Path,
    inventory_path: Path,
    phases: list[Phase],
    pom_owner: str,
    root: Path,
) -> dict[str, Any]:
    def rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(root.resolve()))
        except ValueError:
            return str(p)

    stories = []
    for ph in phases:
        stories.append(
            {
                "story_id": ph.story_id,
                "heading": ph.heading,
                "kind": ph.kind,
                "priority": ph.priority or None,
                "parents": list(ph.parents),
                "dependencies": list(ph.parents),
                "operand_class": list(ph.operand_class),
                "files_in_scope": list(ph.files),
                "files_writable": list(ph.files),
                "acceptance_criteria": list(ph.acceptance_criteria),
                "phase_checklist": list(ph.checklist),
                "workspace_kind": ph.workspace_kind,
                "endpoints": list(ph.endpoints),
                "independent_test": ph.independent_test,
            }
        )
    return {
        "schema": RECEIPT_SCHEMA,
        "source": RECEIPT_SOURCE,
        "architect_bind": "E-20260816T115106Z",
        "tasks_md": rel(tasks_md),
        "inventory": rel(inventory_path),
        "pom_owner": pom_owner,
        "stories": stories,
    }


def assemble_bodies(root: Path) -> int:
    spec_path = _READY / "assemble-m3-bodies-from-partition.py"
    proc = subprocess.run(
        [sys.executable, str(spec_path), str(root), "--write"],
        cwd=str(root),
    )
    return proc.returncode


def mint_wave(root: Path, parent: str, dry_run: bool) -> int:
    script = _SCRIPTS / "mint-m3-wave.sh"
    cmd = ["bash", str(script), "--parent", parent]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(cmd, cwd=str(root)).returncode


def run(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    tasks_md = find_tasks_md(root, args.tasks)
    text = tasks_md.read_text(encoding="utf-8")
    phases = parse_phases(text)
    transcribe_parents(text, phases)
    pom_owner = assign_ownership(phases)
    stamp_oracles(phases)
    stamp_workspaces(phases)
    inv_path, inventory = load_inventory(root, args.inventory)
    cover_endpoints(phases, inventory)
    receipt = build_receipt(
        tasks_md=tasks_md,
        inventory_path=inv_path,
        phases=phases,
        pom_owner=pom_owner,
        root=root,
    )
    if args.write or args.parent:
        path_a_partition_on_disk(root)
        out = root / "evidence" / "briefs" / "partition.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote handover receipt {out} stories={len(phases)} pom_owner={pom_owner}")
        rc = assemble_bodies(root)
        if rc != 0:
            _die("ASSEMBLE", f"assemble-m3-bodies-from-partition.py exited {rc}")
        if args.parent:
            mrc = mint_wave(root, args.parent, dry_run=False)
            if mrc != 0:
                _die("MINT", f"mint-m3-wave.sh exited {mrc}")
    else:
        print(
            f"OK: handover-mint dry-run stories={len(phases)} "
            f"pom_owner={pom_owner or '-'} "
            f"ids={[p.story_id for p in phases]}"
        )
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--inventory", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--parent", default="")
    ap.add_argument("--print-receipt", action="store_true")
    args = ap.parse_args()
    if args.parent:
        args.write = True
    if not args.write:
        args.dry_run = True
    root = Path(args.root).resolve()
    try:
        receipt = run(root, args)
    except HandoverError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.print_receipt or args.dry_run:
        print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
