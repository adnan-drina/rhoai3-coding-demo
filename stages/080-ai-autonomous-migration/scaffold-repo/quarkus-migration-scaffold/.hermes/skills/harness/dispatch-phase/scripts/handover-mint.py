#!/usr/bin/env python3
"""Post-workflow handover mint (A-4 / A-5 / A-8).

Fail-closed: tasks.md User-Story phases → typed partition receipt + bodies.
Parents come from the import graph (types a story imports that another
phase owns). Dependencies-section prose is an additional signal, never
the sole source. File-granular ownership is a distinct step after grouping.
Endpoint coverage is vs M1 inventory. OBJECT spec-kit hooks (V20-5 advisory).
Domain `## Phase N:` headings mint as kind `phase` id `P{N}` (Architect
E-20260817T013303Z). Do not infer Setup/Foundational from title prose.
A heading `[USn]` tag is the native spec-kit story token (same as task lines).

Does not call hermes. --parent / --ensure-wave-holder REFUSE (mint-m3-wave retired; holder follows mint-m3-hermes.md).

Usage:
  python3 handover-mint.py <root> --dry-run
  python3 handover-mint.py <root> --write
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
    OPERAND_CLASS_SEMANTIC_EXITS,
    OracleUnmappedError,
    exit_for,
    is_test_source_rel,
    load_json,
    resolve_inventory_path,
    resolve_java_source,
)
from type_graph import IMP_RE, strip_java_comments  # noqa: E402

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
# Native speckit: `- **Phase 7 (US1)**: Depends on Phases 2-6`
PHASE_N_DEPS = re.compile(
    r"^\s*[-*]\s+\*\*Phase\s+(\d+)\b[^*]*\*\*:\s*(.+)$",
    re.I | re.M,
)
PHASE_RANGE = re.compile(r"Phases?\s+(\d+)\s*[-–—]\s*(\d+)", re.I)
PHASE_ONE = re.compile(r"\bPhase\s+(\d+)\b", re.I)

KIND_SETUP = "setup"
KIND_FOUNDATIONAL = "foundational"
KIND_USER_STORY = "user_story"
KIND_POLISH = "polish"
KIND_PHASE = "phase"

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
    extended_proves: list[str] = field(default_factory=list)
    phase_num: int | None = None


def _die(code: str, detail: str) -> None:
    raise HandoverError(code, detail)


def _norm_path(raw: str) -> str:
    p = raw.replace("\\", "/").strip().lstrip("./")
    if not p or ".." in Path(p).parts or p.startswith("/"):
        _die("PATH_ILLEGAL", f"refusing path {raw!r}")
    return p


def _is_pom(path: str) -> bool:
    return path == "pom.xml" or path.endswith("/pom.xml")


def _kind_and_id(title: str, body: str, num: str) -> tuple[str, str]:
    """Kind from closed tokens; else id is P{heading number}, not title prose.

    Architect E-20260817T013303Z: do not alias 'foundations'→foundational.
    """
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
    tagged = US_TAG.search(title)
    if tagged:
        n = tagged.group(1)
        tags = set(US_TAG.findall(body))
        if tags and tags != {n}:
            _die(
                "STORY_ID_MISMATCH",
                f"heading US{n} vs task tags {sorted(tags)}",
            )
        return KIND_USER_STORY, f"US{n}"
    if not str(num).isdigit():
        _die("PHASE_KIND", f"unrecognised phase heading: {title!r}")
    return KIND_PHASE, f"P{int(num)}"


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
            "tasks.md has no '## Dependencies' section — parents cannot be transcribed. "
            "Add ## Dependencies; parents also come from the import graph (F-6), not prose alone.",
        )
    phases: list[Phase] = []
    for idx, (start, num, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else deps_at
        body = "\n".join(lines[start + 1 : end])
        kind, sid = _kind_and_id(title, body, num)
        checklist = [m.group(0) for line in body.splitlines() if (m := CHECKBOX.match(line))]
        files: list[str] = []
        for line in body.splitlines():
            # spec-kit has no create/amend distinction. Extract every path
            # token; pom uniqueness is earliest-claimant in assign_ownership.
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
                phase_num=int(num) if str(num).isdigit() else None,
            )
        )
    seen: set[str] = set()
    for ph in phases:
        if ph.story_id in seen:
            _die("STORY_ID", f"duplicate story_id {ph.story_id!r}")
        seen.add(ph.story_id)
    _resolve_backtick_test_oracles(phases)
    return phases


def _resolve_backtick_test_oracles(phases: list[Phase]) -> None:
    """Native speckit Extend lines name `FooTest` without a path.

    Map those names onto test files already listed by an earlier phase so
    later stories have proves without taking write-set ownership (A-5).
    """
    known: dict[str, str] = {}
    for ph in phases:
        for p in ph.files:
            if is_test_source_rel(p):
                known.setdefault(Path(p).stem, p)
        if ph.kind != KIND_USER_STORY:
            continue
        for line in ph.body.splitlines():
            if not _is_amend_existing_line(line):
                continue
            if not re.match(r"(?i)^- \[[ xX]\].*\bExtend\b", line):
                continue
            for name in BACKTICK_TEST.findall(line):
                path = known.get(name)
                if path and path not in ph.extended_proves:
                    ph.extended_proves.append(path)


AMEND_EXISTING = re.compile(
    r"^- \[[ xX]\]\s+(?:T\d+\s+)?(?:\[P\]\s+)?(?:\[US\d+\]\s+)?"
    r"(?:"
    r"Extend\b"
    r"|Add create/update/delete\b"
    r"|Add POST(?:\s*,\s*|/)PUT(?:\s*,\s*|/)DELETE\b"
    r"|Verify\b"
    r"|Add\b.+\sto\s+`?pom\.xml"
    r"|Create\b.+\(extend existing file\)"
    r"|Create\b.+\badd POST(?:\s*,\s*|/)PUT(?:\s*,\s*|/)DELETE tests"
    r")",
    re.I,
)
BACKTICK_TEST = re.compile(r"`([A-Za-z][A-Za-z0-9_]*Test)`")


def _is_amend_existing_line(line: str) -> bool:
    return bool(CHECKBOX.match(line) and AMEND_EXISTING.search(line))


def _parents_from_rest(rest: str, by_id: dict[str, Phase]) -> list[str]:
    parents: list[str] = []

    def add(sid: str) -> None:
        if sid in by_id and sid not in parents:
            parents.append(sid)

    if re.search(r"depends on foundational|after foundational", rest, re.I):
        add(KIND_FOUNDATIONAL)
    if re.search(r"depends on setup|after setup", rest, re.I):
        add(KIND_SETUP)
    for dm in DEPENDS_ON_US.finditer(rest):
        n = dm.group(1) or dm.group(2)
        add(f"US{n}")
    return parents


def _parents_from_phase_n_rest(
    rest: str,
    self_id: str,
    by_num: dict[int, str],
    all_ids: list[str],
    us_ids: list[str],
) -> list[str]:
    if re.search(r"no dependencies", rest, re.I):
        return []
    if re.search(r"depends on all phases", rest, re.I):
        return [sid for sid in all_ids if sid != self_id]
    if re.search(r"depends on all (?:desired )?user stories", rest, re.I):
        return [sid for sid in us_ids if sid != self_id]
    parents: list[str] = []
    consumed: set[int] = set()

    def add_num(n: int) -> None:
        sid = by_num.get(n)
        if sid and sid != self_id and sid not in parents:
            parents.append(sid)

    for m in PHASE_RANGE.finditer(rest):
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = min(a, b), max(a, b)
        for n in range(lo, hi + 1):
            consumed.add(n)
            add_num(n)
    for m in PHASE_ONE.finditer(rest):
        n = int(m.group(1))
        if n in consumed:
            continue
        add_num(n)
    return parents


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
    by_num = {p.phase_num: p.story_id for p in phases if p.phase_num is not None}
    all_ids = [p.story_id for p in phases]
    us_ids = [p.story_id for p in phases if p.kind == KIND_USER_STORY]
    for m in PHASE_N_DEPS.finditer(block):
        n = int(m.group(1))
        sid = by_num.get(n)
        if not sid:
            _die("DEPENDENCIES", f"Phase {n} bullet has no matching heading")
        by_id[sid].parents = _parents_from_phase_n_rest(
            m.group(2), sid, by_num, all_ids, us_ids
        )

    setup_line = SETUP_DEPS.search(block)
    found_line = FOUND_DEPS.search(block)
    us_all = US_ALL_DEPS.search(block)
    polish_line = POLISH_DEPS.search(block)
    if KIND_SETUP in by_id:
        setup_from_phase_n = bool(
            by_id[KIND_SETUP].phase_num is not None
            and any(
                int(m.group(1)) == by_id[KIND_SETUP].phase_num
                for m in PHASE_N_DEPS.finditer(block)
            )
        )
        if not setup_from_phase_n:
            if not setup_line:
                _die("DEPENDENCIES_MISSING", "Setup bullet missing from Dependencies")
            if re.search(r"no dependencies", setup_line.group(1), re.I):
                by_id[KIND_SETUP].parents = []
            else:
                _die("DEPENDENCIES", f"Setup is not 'No dependencies': {setup_line.group(1)!r}")
    if KIND_FOUNDATIONAL in by_id:
        found_from_phase_n = bool(
            by_id[KIND_FOUNDATIONAL].phase_num is not None
            and any(
                int(m.group(1)) == by_id[KIND_FOUNDATIONAL].phase_num
                for m in PHASE_N_DEPS.finditer(block)
            )
        )
        if not found_from_phase_n:
            if not found_line:
                _die("DEPENDENCIES_MISSING", "Foundational bullet missing from Dependencies")
            if re.search(r"depends on setup", found_line.group(1), re.I):
                if KIND_SETUP not in by_id:
                    _die("DEPENDENCIES", "Foundational depends on Setup but Setup phase is absent")
                by_id[KIND_FOUNDATIONAL].parents = [KIND_SETUP]
            else:
                _die("DEPENDENCIES", f"Foundational parents not transcribed: {found_line.group(1)!r}")
    default_us_parents = [KIND_FOUNDATIONAL] if KIND_FOUNDATIONAL in by_id else []
    per_us: dict[str, list[str]] = {}
    if us_ids:
        collective = bool(
            us_all and re.search(r"depend on Foundational", us_all.group(1), re.I)
        )
        if collective:
            if KIND_FOUNDATIONAL not in by_id:
                _die("DEPENDENCIES", "user stories depend on Foundational but that phase is absent")
            for sid in us_ids:
                if not by_id[sid].parents:
                    per_us[sid] = list(default_us_parents)
        for m in US_LINE_DEPS.finditer(block):
            sid = f"US{m.group(1)}"
            rest = m.group(2)
            parsed = _parents_from_rest(rest, by_id)
            extra = [x for x in parsed if x.startswith("US")]
            base = [x for x in parsed if not x.startswith("US")]
            if not base and collective:
                base = list(default_us_parents)
            if not base and not extra:
                continue
            per_us[sid] = base + extra
        for sid, parents in per_us.items():
            if sid in by_id and not by_id[sid].parents:
                by_id[sid].parents = parents
        # Missing US parents are filled from the import graph after this
        # transcription (merge_import_parents / assert_parents_resolved).
    if KIND_POLISH in by_id and not by_id[KIND_POLISH].parents:
        if not polish_line or not re.search(
            r"depends on all (?:desired )?user stories", polish_line.group(1), re.I
        ):
            _die("DEPENDENCIES_MISSING", "Polish bullet must depend on all user stories")
        by_id[KIND_POLISH].parents = list(us_ids)


def assign_ownership(phases: list[Phase]) -> str:
    """A-5 is one dest file, one in-flight card — not one owner per phase.

    Architect E-20260817T131858Z: mint-time FILE_OVERLAP (cross-phase artifact disjointness)
    is not A-5. Dropped while serial. Restore a runtime in-flight check when
    C-1(a) is claimed. pom.xml still unique owner (earliest claimant); later
    phases keep non-pom shared paths in their write-sets.
    """
    pom_owner = ""
    for ph in phases:
        for f in ph.files:
            if _is_pom(f):
                pom_owner = ph.story_id
                break
        if pom_owner:
            break
    if pom_owner:
        for ph in phases:
            if ph.story_id != pom_owner:
                ph.files = [f for f in ph.files if not _is_pom(f)]
    pom_writers = [
        ph.story_id for ph in phases if any(_is_pom(f) for f in ph.files)
    ]
    if len(pom_writers) > 1:
        _die(
            "POM_OWNER",
            f"pom.xml still claimed by {pom_writers}. "
            "Ownership is earliest claimant (assign_ownership); keep one "
            f"Create pom.xml on {pom_writers[0]} and drop later PATH_TOKEN "
            "claims.",
        )
    if pom_writers:
        pom_owner = pom_writers[0]
    if not pom_owner:
        mentions = _pom_mention_lines(phases)
        _die(
            "POM_OWNER",
            "tasks.md PATH_TOKEN extracted 0 pom.xml owners. "
            "Ownership is earliest claimant — one phase must Create pom.xml. "
            "Surface=tasks.md checklists (PATH_TOKEN). "
            f"Lines mentioning pom.xml: {mentions or 'none'}",
        )
    return pom_owner


def _pom_mention_lines(phases: list[Phase]) -> list[str]:
    out: list[str] = []
    for ph in phases:
        for line in ph.body.splitlines():
            if "pom.xml" in line:
                out.append(f"{ph.story_id}:{line.strip()[:120]}")
    return out


def _is_service_java(rel: str) -> bool:
    name = Path(str(rel).replace("\\", "/")).name
    return name.endswith("Service.java") or name.endswith("ServiceImpl.java")


def assert_foundational_no_service(phases: list[Phase]) -> None:
    """H-6 / T0 #3: whole-domain facade is not foundational write-set."""
    for ph in phases:
        if ph.kind != KIND_FOUNDATIONAL and ph.story_id != KIND_FOUNDATIONAL:
            continue
        hits = [f for f in ph.files if _is_service_java(f)]
        if hits:
            _die(
                "T0_3_SERVICE",
                "foundational files_writable includes "
                f"{hits}. Surface=tasks.md PATH_TOKEN on the Foundational "
                "phase. T0 #3: a whole-domain *Service.java is not "
                "foundational (Architect 205707Z / 062422Z). "
                "split per aggregate so each story owns the service "
                "methods for its own entities. Do not relocate the domain "
                "into foundational to green topo.",
            )


def _would_cycle(child: str, parent: str, by_id: dict[str, Phase]) -> bool:
    if child == parent:
        return True
    seen: set[str] = set()
    stack = [parent]
    while stack:
        cur = stack.pop()
        if cur == child:
            return True
        if not cur or cur in seen:
            continue
        seen.add(cur)
        nxt = by_id.get(cur)
        if nxt:
            stack.extend(nxt.parents)
    return False


def merge_import_parents(root: Path, phases: list[Phase]) -> None:
    """F-6: story A parents story B when A imports a type B owns.

    Prose parents from transcribe_parents stay. Import-graph edges that
    would cycle are CYCLE_IMPORT (H-5) — do not silent-drop (Review test C).
    """
    by_id = {p.story_id: p for p in phases}
    owners: dict[str, str] = {}
    for ph in phases:
        for f in ph.files:
            rel = str(f).replace("\\", "/")
            if not rel.endswith(".java"):
                continue
            owners[rel] = ph.story_id
            owners[Path(rel).name] = ph.story_id
            owners[Path(rel).stem] = ph.story_id
    for ph in phases:
        for f in ph.files:
            rel = str(f).replace("\\", "/")
            if not rel.endswith(".java"):
                continue
            path = resolve_java_source(root, rel)
            if path is None:
                continue
            try:
                text = strip_java_comments(
                    path.read_text(encoding="utf-8", errors="ignore")
                )
            except OSError:
                continue
            for m in IMP_RE.finditer(text):
                name = m.group(1).rsplit(".", 1)[-1]
                owner = owners.get(name)
                if not owner or owner == ph.story_id or owner not in by_id:
                    continue
                if _would_cycle(ph.story_id, owner, by_id):
                    _die(
                        "CYCLE_IMPORT",
                        f"{ph.story_id} imports {name} owned by {owner}, "
                        f"but parenting {ph.story_id} on {owner} cycles "
                        f"(parents {ph.story_id}={list(ph.parents)} "
                        f"{owner}={list(by_id[owner].parents)}). "
                        f"Surface=Java import in {rel}. "
                        "Parent the owning story, or split if this is a "
                        "whole-domain facade. Do not hoist the shared type "
                        "to an earlier phase (Architect 064012Z).",
                    )
                if owner not in ph.parents:
                    ph.parents.append(owner)


def assert_parents_resolved(phases: list[Phase]) -> None:
    by_id = {p.story_id: p for p in phases}
    us_ids = [p.story_id for p in phases if p.kind == KIND_USER_STORY]
    missing = [sid for sid in us_ids if not by_id[sid].parents]
    if missing:
        _die(
            "DEPENDENCIES_MISSING",
            "each user story needs a Dependencies bullet "
            "(Phase-N 'Depends on Phases …', per-story native speckit, or collective "
            "'User Stories (Phase 3+) depend on Foundational') "
            "and/or the import graph (a type this story imports that another "
            "phase owns). Parents come from the import graph (F-6), not prose. "
            "Surface=tasks.md ## Dependencies plus dest/legacy "
            f"Java imports. missing parents for {missing}",
        )
    if us_ids and KIND_FOUNDATIONAL in by_id:
        omitted = [
            sid
            for sid in us_ids
            if KIND_FOUNDATIONAL not in (by_id[sid].parents or [])
        ]
        if omitted:
            _die(
                "DEPENDENCIES",
                "Foundational must be in parents of every user-story phase "
                "(Architect E-20260816T192444Z). Surface=import graph plus "
                f"Dependencies prose; omitted by {omitted}",
            )


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
    in_scope = [p for p in ph.files if is_test_source_rel(p)]
    if in_scope:
        return in_scope
    if ph.extended_proves:
        return list(ph.extended_proves)
    # Native speckit later stories Extend tests owned by an earlier phase.
    # Those paths are oracles, not a second write-set claim.
    extended: list[str] = []
    for line in ph.body.splitlines():
        if not CHECKBOX.match(line) or not AMEND_EXISTING.search(line):
            continue
        for raw in PATH_TOKEN.findall(line):
            p = _norm_path(raw)
            if is_test_source_rel(p) and p not in extended:
                extended.append(p)
    return extended


def _stamp_exit(
    ph: Phase, proves: list[str], *, polish_empty: bool
) -> None:
    if not OPERAND_CLASS_SEMANTIC_EXITS:
        _die(
            "ORACLE_UNMAPPED",
            "OPERAND_CLASS_SEMANTIC_EXITS is empty. Map lives in "
            "specimen_agnostic.exit_for / OPERAND_CLASS_SEMANTIC_EXITS — "
            "give this story a classifiable write-set (rest needs a test path).",
        )
    try:
        ph.acceptance_criteria = exit_for(
            ph.story_id, ph.operand_class, proves, polish_empty=polish_empty
        )
    except OracleUnmappedError as e:
        _die(
            "ORACLE_UNMAPPED",
            f"{e}. Map is specimen_agnostic.OPERAND_CLASS_SEMANTIC_EXITS "
            "(exit_for). Rest without a test path is unmapped — add the test "
            "file to the write-set; do not stamp build_resolves.",
        )


def stamp_oracles(phases: list[Phase]) -> None:
    for ph in phases:
        if not ph.files:
            if ph.kind == KIND_POLISH:
                ph.operand_class = ["build_config"]
                _stamp_exit(ph, [], polish_empty=True)
                continue
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
        if ph.kind == KIND_USER_STORY and not ph.independent_test:
            _die(
                "PHASE_AC",
                f"{ph.story_id}: user-story phase has no Independent Test",
            )
        _stamp_exit(ph, proves, polish_empty=False)


def stamp_workspaces(phases: list[Phase]) -> None:
    for ph in phases:
        extra = [p for p in ph.parents if p != KIND_FOUNDATIONAL]
        if ph.kind == KIND_USER_STORY and not extra:
            ph.workspace_kind = "worktree"
        else:
            ph.workspace_kind = "dir"


def _norm_http_path(raw: str) -> str:
    p = (raw or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1:
        p = p.rstrip("/")
    return re.sub(r"\{[^}]+\}", "{var}", p)


def _transcribed_http(ph: Phase) -> tuple[set[str], set[str], set[str]]:
    """Routes, methods, and inventory symbols named in the phase body."""
    body = ph.body or ""
    methods = {m.upper() for m in re.findall(r"\b(GET|POST|PUT|DELETE|PATCH)\b", body, re.I)}
    methods.update(
        m.upper() for m in re.findall(r"@(GET|POST|PUT|DELETE|PATCH)\b", body, re.I)
    )
    paths = {_norm_http_path(p) for p in re.findall(r'@Path\(\s*"([^"]+)"\)', body)}
    paths.update(
        _norm_http_path(p)
        for p in re.findall(
            r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_./{}*|-]*)",
            body,
            re.I,
        )
    )
    symbols = set(re.findall(r"\b([A-Za-z]\w*#[A-Za-z]\w*)\b", body))
    symbols.update(re.findall(r"`([A-Za-z]\w*#[A-Za-z]\w*)`", body))
    return paths, methods, symbols


def _path_covered(ep_path: str, paths: set[str]) -> bool:
    ep_path = _norm_http_path(ep_path)
    if not ep_path:
        return False
    for p in paths:
        if not p:
            continue
        if ep_path == p or ep_path.startswith(p + "/"):
            return True
    return False


def _inventory_servlet_prefix(inventory: dict[str, Any]) -> str:
    """Shared first-segment prefix of inventory HTTP paths (e.g. /api).

    Native Spec Kit writes JAX-RS ``@Path("/owners")`` plus ``GET /``; M1
    inventory records the servlet-mounted path ``/api/owners``. The prefix
    is taken from the inventory, not hardcoded, and never applied to
    ``@Path("/")`` (that would claim every ``/api/...`` route).
    """
    segs_list: list[list[str]] = []
    for ep in inventory.get("entry_points") or []:
        if not isinstance(ep, dict) or ep.get("kind") != "http":
            continue
        p = _norm_http_path(str(ep.get("http_path") or ""))
        if not p or p == "/":
            continue
        segs_list.append([s for s in p.split("/") if s])
    if not segs_list:
        return ""
    common = segs_list[0]
    for segs in segs_list[1:]:
        n = 0
        while n < len(common) and n < len(segs) and common[n] == segs[n]:
            n += 1
        common = common[:n]
        if not common:
            return ""
    return "/" + "/".join(common)


def _jaxrs_class_paths(body: str) -> set[str]:
    return {
        _norm_http_path(p)
        for p in re.findall(r'@Path\(\s*"([^"]+)"\)', body or "")
    }


def _with_servlet_prefix(jaxrs: set[str], prefix: str) -> set[str]:
    extra: set[str] = set()
    if not prefix:
        return extra
    for p in jaxrs:
        if not p or p == "/":
            continue
        if p == prefix or p.startswith(prefix + "/"):
            continue
        extra.add(_norm_http_path(prefix.rstrip("/") + (p if p.startswith("/") else "/" + p)))
    return extra


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
            # Earliest claimant (same rule as pom). Last-writer made F-1
            # amend-line extraction skip A-8 inherit (owner_sid == self).
            if f not in file_owner:
                file_owner[f] = ph.story_id
    prefix = _inventory_servlet_prefix(inventory)
    transcribed: dict[str, tuple[set[str], set[str], set[str]]] = {}
    jaxrs_only: dict[str, set[str]] = {}
    for ph in phases:
        paths, methods, symbols = _transcribed_http(ph)
        jaxrs = set(_jaxrs_class_paths(ph.body)) | _with_servlet_prefix(
            _jaxrs_class_paths(ph.body), prefix
        )
        jaxrs_only[ph.story_id] = jaxrs
        transcribed[ph.story_id] = (set(paths) | jaxrs, methods, symbols)
    # A-8 amend inherit (Architect E-20260817T015216Z): Add POST/PUT/DELETE or
    # Extend naming a dest path owned by an earlier phase inherits *that file's*
    # transcribed routes (the Create line's @Path / GET /…), not the whole
    # owner's phase. Methods stay from the amend body. Not a RestController mapper.
    file_routes: dict[str, set[str]] = {}
    for ph in phases:
        for line in ph.body.splitlines():
            if not CHECKBOX.match(line):
                continue
            line_paths = set(_jaxrs_class_paths(line)) | _with_servlet_prefix(
                _jaxrs_class_paths(line), prefix
            )
            # GET / on a Create line is class-relative, not HTTP root. Inherit
            # @Path only so US2 POST does not also claim `/` (endpoints_multi).
            line_paths = {p for p in line_paths if p and p != "/"}
            if not line_paths:
                continue
            for raw in PATH_TOKEN.findall(line):
                dest = _norm_path(raw)
                file_routes.setdefault(dest, set()).update(line_paths)
    for ph in phases:
        extra: set[str] = set()
        for line in ph.body.splitlines():
            if not _is_amend_existing_line(line):
                continue
            for raw in PATH_TOKEN.findall(line):
                dest = _norm_path(raw)
                owner_sid = file_owner.get(dest)
                if owner_sid and owner_sid != ph.story_id:
                    extra |= file_routes.get(dest, set())
        if extra:
            paths, methods, symbols = transcribed[ph.story_id]
            transcribed[ph.story_id] = (paths | extra, methods, symbols)
            jaxrs_only[ph.story_id] = jaxrs_only[ph.story_id] | extra
    uncovered: list[str] = []
    multi: list[str] = []
    claimed: dict[str, list[str]] = {ph.story_id: [] for ph in phases}
    for ep in http:
        f = _norm_path(str(ep.get("file") or "")) if ep.get("file") else ""
        sym = str(ep.get("symbol") or "")
        method = str(ep.get("http_method") or "").upper()
        route = str(ep.get("http_path") or "")
        key = f"{method} {route}".strip() if route else (f"{f}#{sym}" if sym else f)
        owners: list[str] = []
        if f and f in file_owner:
            owners.append(file_owner[f])
        for ph in phases:
            paths, methods, symbols = transcribed[ph.story_id]
            hit = False
            if sym and (sym in symbols or sym in ph.body):
                hit = True
            elif route and _path_covered(route, paths):
                if not method or method in methods:
                    hit = True
            if hit and ph.story_id not in owners:
                owners.append(ph.story_id)
        if not owners:
            uncovered.append(key)
            continue
        if len(owners) > 1:
            # Prefer the phase that named the HTTP method when several match.
            if method:
                method_owners = [
                    sid
                    for sid in owners
                    if method in transcribed[sid][1]
                ]
                if len(method_owners) == 1:
                    owners = method_owners
        if len(owners) > 1 and route:
            jaxrs_owners = [
                sid
                for sid in owners
                if _path_covered(route, jaxrs_only.get(sid, set()))
            ]
            if len(jaxrs_owners) == 1:
                owners = jaxrs_owners
        if len(owners) > 1:
            multi.append(f"{key}:{'+'.join(owners)}")
            continue
        claimed[owners[0]].append(key)
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


def assemble_bodies(root: Path) -> tuple[int, str]:
    spec_path = _READY / "assemble-m3-bodies-from-partition.py"
    proc = subprocess.run(
        [sys.executable, str(spec_path), str(root), "--write"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode, blob


def mint_wave(root: Path, parent: str, dry_run: bool) -> int:
    _die(
        "MINT",
        "mint-m3-wave.sh retired (165300Z / 2.4); holder session follows "
        "references/mint-m3-hermes.md — do not --parent from Cursor",
    )


def _parent_status(task_id: str) -> str:
    proc = subprocess.run(
        ["hermes", "kanban", "show", task_id, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return ""
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    task = data.get("task") if isinstance(data.get("task"), dict) else data
    if not isinstance(task, dict):
        return ""
    return str(task.get("status") or "").lower()


def ensure_open_wave_holder() -> str:
    """HKN-2 look-ahead: never --parent a done M2. Mint under a still-open holder."""
    title = "M3 WAVE HOLDER"
    proc = subprocess.run(
        [
            "hermes",
            "kanban",
            "create",
            "--json",
            "--assignee",
            "default",
            "--initial-status",
            "blocked",
            "--created-by",
            "handover-mint",
            title,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        _die("WAVE_HOLDER", f"hermes kanban create failed: {blob.strip()[:400]}")
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        _die("WAVE_HOLDER", f"create returned non-JSON: {blob.strip()[:400]}")
    tid = str(data.get("id") or "")
    if not tid:
        _die("WAVE_HOLDER", "create returned no id")
    print(f"OK: wave-holder {tid} status=blocked (HKN-2; do not --parent a done M2)", file=sys.stderr)
    return tid


def assert_parent_open(parent: str) -> None:
    status = _parent_status(parent)
    if status in {"done", "archived"}:
        _die(
            "PARENT_DONE",
            f"{parent} status={status} — PARK_AT_BIRTH children auto-promote "
            "(HKN-2). Pass --ensure-wave-holder instead of a done M2 id.",
        )
    if not status:
        _die(
            "PARENT_DONE",
            f"{parent} status unreadable — fail-closed (cannot prove parent is not done)",
        )


def run(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    tasks_md = find_tasks_md(root, args.tasks)
    text = tasks_md.read_text(encoding="utf-8")
    phases = parse_phases(text)
    transcribe_parents(text, phases)
    assert_foundational_no_service(phases)
    merge_import_parents(root, phases)
    assert_parents_resolved(phases)
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
        if args.parent or args.ensure_wave_holder:
            _die(
                "MINT",
                "mint-m3-wave.sh retired (165300Z / 2.4); holder session follows "
                "references/mint-m3-hermes.md — do not --parent from Cursor",
            )
        path_a_partition_on_disk(root)
        out = root / "evidence" / "briefs" / "partition.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote handover receipt {out} stories={len(phases)} pom_owner={pom_owner}")
        rc, assemble_blob = assemble_bodies(root)
        if rc != 0:
            tail = (assemble_blob or "").strip().replace("\n", " ")[:400]
            _die(
                "ASSEMBLE",
                f"assemble-m3-bodies-from-partition.py exited {rc}"
                + (f": {tail}" if tail else " (no child output)"),
            )
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
    ap.add_argument(
        "--ensure-wave-holder",
        action="store_true",
        help="create a still-open blocked wave-holder and mint under it (HKN-2)",
    )
    ap.add_argument("--print-receipt", action="store_true")
    args = ap.parse_args()
    if args.ensure_wave_holder and args.parent:
        print("FAIL: use --ensure-wave-holder or --parent, not both", file=sys.stderr)
        return 2
    if args.parent or args.ensure_wave_holder:
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
