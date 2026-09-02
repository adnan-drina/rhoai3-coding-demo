#!/usr/bin/env python3
"""K4 converter — typed partition → kanban_create payloads.

Does not mint. Does not import create_task. Does not read tasks.md for
write-sets. Optional --tasks only reports planning defects (all paths).

Writes each M3 story body to ``evidence/bodies/m3-<story_id>.json`` next
to ``evidence/partition.json`` so exit criteria that name
``--body evidence/bodies/m3-….json`` have a convert-authored file.
Does not put those paths in ``files_writable`` (Architect ``193642ZA``).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
_LIB = _KERNEL.parent / "lib"
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from k4_producers import KIND_DEFAULTS  # noqa: E402
from k4_schema import (  # noqa: E402
    IMPL,
    PATH_TOKEN_MARKERS,
    REMEDY,
    SHA256_RE,
    STAMP_ID,
    STAMP_SKILL,
    VERIFIER_ID,
    WRITER_ID,
)
from specimen_agnostic import stamp_dd3_extensions, writes_pom_xml  # noqa: E402

Issue = tuple[str, str, str]
DEST_POM_EXT_CMD = (
    "python3 .hermes/skills/migration/manage-quarkus-extensions/"
    "scripts/assert-dest-pom-extensions.py . --body "
    "evidence/bodies/m3-%s.json"
)
PATH_IN_PROSE = re.compile(r"(?:`)?((?:src|pom\.xml)[/.\w-]*)(?:`)?")
NEGATED_PROSE = re.compile(
    r"(?i)\b(?:do not|don't|dont|never|must not|not touch)\b"
)
HEALTH_AC = re.compile(
    r"(?i)/q/health|healthtest|smallrye-health|quarkus-smallrye-health"
    r"|\bhealth_probe\b"
)
POM_AC = re.compile(r"(?i)\bpom\.xml\b|quarkus:add-extension|\badd-extension\b")
SERVICE_JAVA = re.compile(r"(?i)(?:^|/)([^/]*Service\.java)$")
SKILLS_BY_KIND = KIND_DEFAULTS

DB_STORY_ID = "PROVISION_DATABASE"


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _story_id(story: dict[str, Any]) -> str:
    return str(story.get("story_id") or story.get("id") or "").strip()


def dest_file_named(story: dict[str, Any]) -> bool:
    """True when dest_file names at least one dest twin (str or list)."""
    raw = story.get("dest_file")
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, list):
        return any(str(x).strip() for x in raw)
    return False


def partition_write_union(stories: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for story in stories:
        for p in story.get("files_writable") or []:
            s = str(p).strip()
            if s:
                out.add(s)
    return out


def shared_service_java(stories: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Same *Service.java in two or more stories' files_writable."""
    owners: dict[str, list[str]] = {}
    for story in stories:
        sid = _story_id(story)
        for raw in story.get("files_writable") or []:
            match = SERVICE_JAVA.search(str(raw).replace("\\", "/"))
            if match:
                owners.setdefault(match.group(1), []).append(sid)
    return [
        (base, list(dict.fromkeys(sids)))
        for base, sids in owners.items()
        if len(set(sids)) >= 2
    ]


def prose_paths(text: str) -> list[str]:
    """Paths named as write claims. Negated prose is not a claim.

    dest-5 / dest-4: ``Do not touch src/test/`` was parsed as a write and
    the worker deleted the sentence to go green (Lead:k4-convert-path-in-prose-overmatches).
    """
    found: list[str] = []
    seen: set[str] = set()
    blob = text or ""
    for m in PATH_IN_PROSE.finditer(blob):
        line_start = blob.rfind("\n", 0, m.start()) + 1
        prefix = blob[line_start : m.start()]
        if NEGATED_PROSE.search(prefix):
            continue
        p = m.group(1).strip()
        if p and p not in seen:
            seen.add(p)
            found.append(p)
    return found


def _touches_tests(paths: list[Any]) -> bool:
    for raw in paths:
        n = str(raw).replace("\\", "/").strip()
        if not n:
            continue
        padded = "/" + n.strip("/") + "/"
        if "/src/test/" in padded or n.startswith("src/test/"):
            return True
    return False


def _touches_main(paths: list[Any]) -> bool:
    for raw in paths:
        n = str(raw).replace("\\", "/").strip()
        if not n:
            continue
        padded = "/" + n.strip("/") + "/"
        if "/src/main/" in padded or n.startswith("src/main/"):
            return True
    return False


def _compile_or_test_exit(fw: list[str], kind: str = "") -> dict[str, str] | None:
    # Lead:test-compile-is-not-an-exit-criterion — compiling is not running.
    # Lead:setup-test-toolchain-claim-is-vacuous — test-compile on a tree
    # with no test sources always passes. Bootstrap either runs a real
    # smoke test or makes no Maven toolchain claim. mvn clean is forbidden
    # here: M4 snapshots surefire (batch 1).
    if _touches_tests(fw):
        return {"check": "test_suite_runs", "cmd": "mvn -q test"}
    k = (kind or "").strip().lower()
    if k in {"setup", "bootstrap"}:
        # Lead:setup-story-has-no-build-exit-criterion — a story that authors
        # pom.xml previously exited on nothing, so it shipped a pom whose tests
        # could not compile and the failure landed on the next story
        # (dest-6 us1_greeting; Operator E-20260825T200914ZO).
        #
        # `mvn -q test` is NOT the fix here: setup writes no test sources, so it
        # would pass vacuously — the same defect as the test-compile exit
        # Architect OBJECTed to restoring (E-20260825T201128ZA). The
        # non-vacuous claim a pom-authoring story CAN make is that the pom
        # declares a working test toolchain, which check-test-toolchain.py
        # verifies (quarkus-junit5 + rest-assured + assertj@version) and which
        # fails on dest-6's real pom.
        return {
            "check": "test_toolchain",
            "cmd": (
                "python3 .hermes/skills/gates/check-release-readiness/"
                "scripts/check-test-toolchain.py ."
            ),
        }
    if _touches_main(fw):
        return {"check": "compile", "cmd": "mvn -q compile"}
    return None


def acceptance_unsatisfiable(story: dict[str, Any]) -> list[str]:
    """Health / add-extension / proves paths not granted by files_writable."""
    fw = [str(p).replace("\\", "/").strip() for p in (story.get("files_writable") or []) if str(p).strip()]
    names = set(fw)
    names.update(Path(p).name for p in fw)
    blob_parts: list[str] = []
    proves: list[str] = []
    for key in ("acceptance_criteria", "acceptance", "ac"):
        raw = story.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            blob_parts.append(raw)
            continue
        blob_parts.append(json.dumps(raw, default=str))
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                for p in item.get("proves") or []:
                    if str(p).strip():
                        proves.append(str(p).replace("\\", "/").strip())
                blob_parts.append(
                    " ".join(str(item.get(k) or "") for k in ("cmd", "assert", "expect", "check"))
                )
    blob = "\n".join(blob_parts)
    missing: list[str] = []
    if HEALTH_AC.search(blob) or POM_AC.search(blob):
        if "pom.xml" not in names:
            missing.append("pom.xml")
    for rel in proves:
        if rel not in names and Path(rel).name not in names:
            missing.append(rel)
    seen: set[str] = set()
    out: list[str] = []
    for item in missing:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def story_skills(story: dict[str, Any]) -> list[str]:
    raw = story.get("skills")
    if isinstance(raw, list):
        named = [str(x).strip() for x in raw if str(x).strip()]
        if named:
            return named
    kind = str(story.get("kind") or "").strip().lower()
    return list(SKILLS_BY_KIND.get(kind) or [])


def validate_inputs(
    partition: Any, *, tasks_text: str | None = None
) -> list[Issue]:
    out: list[Issue] = []
    if not isinstance(partition, dict):
        return [_issue("K4_SCHEMA", "partition must be a JSON object")]
    sha = str(partition.get("type_inventory_sha256") or "")
    if not re.match(SHA256_RE, sha):
        out.append(
            _issue("K4_SCHEMA", "type_inventory_sha256 must be 64 lowercase hex")
        )
    stories = partition.get("stories")
    if not isinstance(stories, list) or not stories:
        out.append(_issue("K4_SCHEMA", "stories[] missing or empty"))
        return out
    objs = [s for s in stories if isinstance(s, dict)]
    if len(objs) != len(stories):
        out.append(_issue("K4_SCHEMA", "every stories[] entry must be an object"))
    known = {_story_id(s) for s in objs}
    for story in objs:
        sid = _story_id(story)
        if not sid:
            out.append(_issue("K4_SCHEMA", "story missing story_id"))
            continue
        fw = story.get("files_writable")
        if not isinstance(fw, list) or not [str(p).strip() for p in fw if str(p).strip()]:
            out.append(_issue("K4_SCOPE", "%s files_writable empty" % sid))
        else:
            for missing in acceptance_unsatisfiable(story):
                out.append(
                    _issue(
                        "K4_SCOPE",
                        "%s acceptance needs %s outside files_writable" % (sid, missing),
                    )
                )
        if not story_skills(story):
            out.append(
                _issue("K4_SKILLS", "%s skills empty (set skills[] or kind setup/us/polish/database)" % sid)
            )
        eps = story.get("endpoints") or []
        if isinstance(eps, list) and any(str(x).strip() for x in eps):
            if not str(story.get("legacy_source") or "").strip():
                out.append(
                    _issue(
                        "K4_LEGACY_SOURCE",
                        "%s HTTP story missing legacy_source" % sid,
                    )
                )
            if not dest_file_named(story):
                out.append(
                    _issue(
                        "K4_DEST_FILE",
                        "%s HTTP story missing dest_file" % sid,
                    )
                )
        parents = story.get("parents") or []
        if not isinstance(parents, list):
            out.append(_issue("K4_PARENT", "%s parents must be a list" % sid))
            continue
        for par in parents:
            if str(par) not in known:
                out.append(
                    _issue("K4_PARENT", "%s parent %s not a partition story" % (sid, par))
                )
    for base, sids in shared_service_java(objs):
        out.append(
            _issue(
                "K4_T0_3_SERVICE",
                "%s is writable on stories %s (methods in shared ClinicService)"
                % (base, ",".join(sids)),
            )
        )
    if tasks_text:
        for marker in PATH_TOKEN_MARKERS:
            if marker in tasks_text:
                out.append(
                    _issue("K4_PATH_TOKEN", "tasks.md asks for PATH_TOKEN scrape")
                )
                break
        union = partition_write_union(objs)
        extras = [p for p in prose_paths(tasks_text) if p not in union]
        if extras:
            out.append(
                _issue(
                    "K4_PLANNING_DEFECT",
                    "tasks.md paths absent from partition: %s" % ",".join(extras),
                )
            )
    if objs and not stamp_write_set(objs):
        out.append(
            _issue(
                "K4_SCOPE",
                "%s files_writable empty after OBJECT filter" % STAMP_ID,
            )
        )
    return out


def validate_result(result: Any) -> list[Issue]:
    out: list[Issue] = []
    if not isinstance(result, dict):
        return [_issue("K4_CREATED_CARDS", "result must be an object")]
    payloads = result.get("payloads")
    created = (result.get("manifest") or {}).get("created_cards")
    if not isinstance(payloads, list) or not payloads:
        out.append(_issue("K4_CREATED_CARDS", "payloads empty"))
        return out
    if not isinstance(created, list) or not created:
        out.append(_issue("K4_CREATED_CARDS", "created_cards empty or missing"))
        return out
    ids: list[str] = []
    for i, payload in enumerate(payloads):
        if not isinstance(payload, dict):
            out.append(_issue("K4_SCHEMA", "payloads[%d] must be an object" % i))
            continue
        lid = str(payload.get("logical_id") or "").strip()
        if not lid:
            out.append(_issue("K4_SCHEMA", "payloads[%d] missing logical_id" % i))
            continue
        ids.append(lid)
        who = str(payload.get("assignee") or "")
        if lid in {WRITER_ID, VERIFIER_ID}:
            out.append(
                _issue("K4_FACTORY", "%s dest factory card is retired" % lid)
            )
            continue
        if who != IMPL:
            out.append(_issue("K4_ASSIGNEE", "%s assignee=%s" % (lid, who)))
        parents = [str(p) for p in (payload.get("parents") or [])]
        if WRITER_ID in parents or VERIFIER_ID in parents:
            out.append(
                _issue(
                    "K4_PARENT",
                    "%s must not parent to dest factory cards" % lid,
                )
            )
        skills = payload.get("skills") or []
        if not isinstance(skills, list) or not [
            str(s).strip() for s in skills if str(s).strip()
        ]:
            out.append(_issue("K4_SKILLS", "%s skills empty" % lid))
    if created != ids:
        out.append(
            _issue(
                "K4_CREATED_CARDS",
                "created_cards must equal payload logical_id order",
            )
        )
    return out


def _m3_body(story: dict[str, Any], type_sha: str) -> dict[str, Any]:
    sid = _story_id(story)
    fw = [str(p) for p in (story.get("files_writable") or []) if str(p).strip()]
    kind = str(story.get("kind") or "").strip().lower()
    if not kind and sid.lower() == "setup":
        kind = "setup"
    exits: list[dict[str, str]] = [
        {
            "check": "skills",
            "assert": (
                "consult each skill pinned on this card; unused pins are "
                "legal (skills_unused). AD-002E is a false consult — "
                "claiming a skill that was not loaded. Do not silence a "
                "missing pin."
            ),
        },
        {
            "check": "terminator",
            "assert": (
                "kanban_block is a legal outcome when a bound gate exits "
                "non-zero or when acceptance cannot be satisfied inside "
                "files_writable; do not kanban_complete around a red gate "
                "or an unsatisfiable acceptance. If the named owner of a "
                "missing file is already done, kanban_block (terminal). "
                "Native kanban edit cannot re-open for work. Do not "
                "dependency_wait (kind=dependency) on a done parent — that "
                "routes to todo and the dispatcher promotes a wasted retry"
            ),
        },
    ]
    maven = _compile_or_test_exit(fw, kind)
    if maven:
        exits.append(maven)
    if any(
        str(p).replace("\\", "/").rstrip("/").endswith("pom.xml") for p in fw
    ):
        exits.append(
            {
                "check": "dest_pom_extensions",
                "cmd": DEST_POM_EXT_CMD % sid,
            }
        )
    identity: dict[str, Any] = {"story_id": sid}
    src = str(story.get("legacy_source") or "").strip()
    if src:
        identity["legacy_source"] = src
    for key in (
        "operand_class",
        "endpoints",
        "dest_file",
        "kind",
        "extensions_declared",
        "extensions",
        "acceptance_criteria",
    ):
        if key not in story:
            continue
        val = story[key]
        if val in (None, "", []):
            continue
        identity[key] = val
    locus_path = str(
        story.get("legacy_locus_path") or "evidence/entry-point-inventory.json"
    )
    return {
        "task_id": sid,
        "role": IMPL,
        "phase": "M3",
        "refs": [
            {
                "key": "type-inventory",
                "path": "evidence/type-inventory.json",
                "sha256": type_sha,
            },
            {
                "key": "brief_identity_ack",
                "path": "evidence/acks/brief-identity.ack",
                "sha256": "pending",
            },
            {
                "key": "legacy_locus",
                "path": locus_path,
                "sha256": str(story.get("legacy_locus_sha256") or "pending"),
            },
        ],
        "identity": identity,
        "files_in_scope": list(fw),
        "files_writable": list(fw),
        "exit_criteria": exits,
    }


STAMP_OBJECT_PREFIXES = ("evidence/", ".hermes/", ".specify/", "target/")
STAMP_OBJECT_EXACT = frozenset({".env"})


def _rel_path(raw: Any) -> str:
    rel = str(raw).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def stamp_write_set(stories: list[dict[str, Any]]) -> list[str]:
    """Union of M3 product writes. OBJECT evidence/.hermes/.specify/target/.env."""
    out: list[str] = []
    seen: set[str] = set()
    for story in stories:
        for raw in story.get("files_writable") or []:
            rel = _rel_path(raw)
            if not rel or rel in seen:
                continue
            if rel in STAMP_OBJECT_EXACT or rel.endswith("/.env"):
                continue
            if any(rel == p[:-1] or rel.startswith(p) for p in STAMP_OBJECT_PREFIXES):
                continue
            seen.add(rel)
            out.append(rel)
    return out


def _stamp_body(stories: list[dict[str, Any]], type_sha: str) -> dict[str, Any]:
    fw = stamp_write_set(stories)
    return {
        "task_id": STAMP_ID,
        "role": IMPL,
        "phase": "M3",
        "refs": [
            {
                "key": "type-inventory",
                "path": "evidence/type-inventory.json",
                "sha256": type_sha,
            }
        ],
        "identity": {"story_id": STAMP_ID},
        "files_in_scope": list(fw),
        "files_writable": list(fw),
        "exit_criteria": [
            {
                "check": "skills",
                "assert": (
                    "consult each skill pinned on this card; unused pins are "
                    "legal (skills_unused). AD-002E is a false consult — "
                    "claiming a skill that was not loaded. Do not silence a "
                    "missing pin."
                ),
            },
            {
                "check": "terminator",
                "assert": (
                    "kanban_complete only after assert-retrievable-tree "
                    "--check-only PASS. kanban_block if src/ or pom.xml stay "
                    "untracked. Do not git config. Do not dest-push. Do not "
                    "restore this commit to M4."
                ),
            },
            {
                "check": "retrievable_tree",
                "cmd": (
                    "python3 .hermes/skills/gates/assert-retrievable-tree/"
                    "scripts/assert-retrievable-tree.py --check-only "
                    "/projects/modernized"
                ),
            },
        ],
    }


def _payload(
    logical_id: str,
    *,
    title: str,
    assignee: str,
    parents: list[str],
    body: dict[str, Any],
    skills: list[str] | None = None,
    max_retries: int | None = None,
    type_sha: str = "",
) -> dict[str, Any]:
    stem = (type_sha or "none")[:12]
    out = {
        "logical_id": logical_id,
        "title": title,
        "assignee": assignee,
        "skills": list(skills or []),
        "parents": list(parents),
        "body": json.dumps(body, sort_keys=True, separators=(",", ":")),
        "idempotency_key": "k4:%s:%s" % (logical_id, stem),
    }
    if max_retries is not None:
        # Operator 105355ZO: story cards inherit M2 `--max-retries 1`
        # (null falls through to failure_limit 2 and masks Gate K).
        out["max_retries"] = max_retries
    return out


def dd3_union_gaps(result: dict[str, Any]) -> list[str]:
    """REFUSE when the sole pom writer lacks identity.extensions_apply."""
    gaps: list[str] = []
    writers: list[tuple[str, dict[str, Any]]] = []
    others: list[tuple[str, dict[str, Any]]] = []
    for payload in result.get("payloads") or []:
        if not isinstance(payload, dict):
            continue
        lid = str(payload.get("logical_id") or "").strip()
        if not lid or lid == STAMP_ID:
            continue
        try:
            body = json.loads(str(payload.get("body") or "{}"))
        except json.JSONDecodeError:
            gaps.append("K4_DD3 %s body unreadable" % (lid or "?"))
            continue
        if not isinstance(body, dict):
            continue
        if writes_pom_xml(body):
            writers.append((lid, body))
        else:
            others.append((lid, body))
    if len(writers) != 1:
        gaps.append(
            "K4_DD3 expected 1 pom.xml writer, got %d"
            % len(writers)
        )
        return gaps
    lid, body = writers[0]
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    apply = ident.get("extensions_apply") if isinstance(ident, dict) else None
    if not isinstance(apply, list) or not apply:
        gaps.append(
            "K4_DD3 %s missing identity.extensions_apply union" % lid
        )
    for other_id, other in others:
        oident = other.get("identity") if isinstance(other.get("identity"), dict) else {}
        if isinstance(oident, dict) and "extensions_apply" in oident:
            gaps.append(
                "K4_DD3 %s must not carry extensions_apply" % other_id
            )
    return gaps


def harvest_database_needed(root: Path | None) -> bool:
    if root is None:
        return False
    path = root / "evidence" / "required-extensions.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    db = data.get("database")
    if not isinstance(db, dict) or "needed" not in db:
        return False
    needed = db.get("needed")
    if isinstance(needed, bool):
        return needed
    if isinstance(needed, str):
        return needed.strip().lower() in {"true", "1", "yes"}
    return bool(needed)


def ensure_database_story(
    stories: list[dict[str, Any]], root: Path | None
) -> list[dict[str, Any]]:
    """Mint postgres provisioning only when the harvest says needed."""
    if not harvest_database_needed(root):
        return stories
    if any(_story_id(s) == DB_STORY_ID for s in stories):
        return stories
    extra: dict[str, Any] = {
        "story_id": DB_STORY_ID,
        "kind": "database",
        "parents": [],
        "skills": ["form-entity-persistence"],
        "files_writable": ["k8s/postgres.yaml", "k8s/app.yaml"],
        "acceptance_criteria": [
            "Copy k8s-templates/postgres.yaml to k8s/postgres.yaml",
            "Merge k8s-templates/app-datasource-env.yaml into k8s/app.yaml",
        ],
    }
    return list(stories) + [extra]


def _m1_root(start: Path | None) -> Path | None:
    if start is None:
        return None
    cur = start if start.is_dir() else start.parent
    for cand in [cur, *cur.parents]:
        if (cand / "evidence" / "required-extensions.json").is_file():
            return cand
    return None


def _write_root(partition_path: Path | None) -> Path | None:
    """Dest root only when the partition lives at evidence/partition.json.

    Do not walk the repo looking for required-extensions.json — that would
    write bodies into the workshop destfile from kernel fixtures.
    """
    if partition_path is None:
        return None
    parent = partition_path.resolve().parent
    if parent.name == "evidence":
        return parent.parent
    return None


def m3_body_relpath(story_id: str) -> str:
    return "evidence/bodies/m3-%s.json" % story_id


def write_m3_bodies(
    root: Path,
    stories: list[dict[str, Any]],
    story_bodies: list[dict[str, Any]],
) -> None:
    dest = root / "evidence" / "bodies"
    dest.mkdir(parents=True, exist_ok=True)
    for story, body in zip(stories, story_bodies):
        sid = _story_id(story)
        if not sid:
            continue
        path = dest / ("m3-%s.json" % sid)
        path.write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def convert_partition(
    partition: dict[str, Any], *, root: Path | None = None, write_root: Path | None = None
) -> dict[str, Any]:
    type_sha = str(partition.get("type_inventory_sha256") or "")
    stories = ensure_database_story(
        [s for s in (partition.get("stories") or []) if isinstance(s, dict)],
        root,
    )
    payloads: list[dict[str, Any]] = []
    story_bodies = [_m3_body(story, type_sha) for story in stories]
    if story_bodies:
        stamp_dd3_extensions(story_bodies, root=root)
    dest = write_root if write_root is not None else None
    if dest is not None:
        write_m3_bodies(dest, stories, story_bodies)
    for story, body in zip(stories, story_bodies):
        sid = _story_id(story)
        part_parents = [str(p) for p in (story.get("parents") or [])]
        payloads.append(
            _payload(
                sid,
                title="M3 %s" % sid,
                assignee=IMPL,
                parents=part_parents,
                body=body,
                skills=story_skills(story),
                max_retries=1,
                type_sha=type_sha,
            )
        )
    story_ids = [_story_id(s) for s in stories if _story_id(s)]
    fw = stamp_write_set(stories)
    if not fw:
        raise ValueError(
            format_issues(
                [
                    _issue(
                        "K4_SCOPE",
                        "%s files_writable empty after OBJECT filter" % STAMP_ID,
                    )
                ]
            )
        )
    payloads.append(
        _payload(
            STAMP_ID,
            title="M3 %s" % STAMP_ID,
            assignee=IMPL,
            parents=story_ids,
            body=_stamp_body(stories, type_sha),
            skills=[STAMP_SKILL],
            max_retries=1,
            type_sha=type_sha,
        )
    )
    result = {
        "payloads": payloads,
        "manifest": {"created_cards": [str(p["logical_id"]) for p in payloads]},
        "claimed_control": False,
    }
    issues = validate_result(result)
    if issues:
        raise ValueError(format_issues(issues))
    return result


def convert_file(
    partition_path: Path, *, tasks_path: Path | None = None
) -> tuple[dict[str, Any] | None, list[Issue]]:
    try:
        partition = json.loads(partition_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [_issue("K4_SCHEMA", str(exc))]
    tasks_text = None
    if tasks_path is not None:
        try:
            tasks_text = tasks_path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, [_issue("K4_SCHEMA", str(exc))]
    issues = validate_inputs(partition, tasks_text=tasks_text)
    if issues:
        return None, issues
    return (
        convert_partition(
            partition,
            root=_m1_root(partition_path),
            write_root=_write_root(partition_path),
        ),
        [],
    )


def format_issues(issues: list[Issue]) -> str:
    lines = []
    for code, detail, remedy in issues:
        lines.append("%s: %s" % (code, detail))
        lines.append("  remedy: %s" % remedy)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write(
            "k4_convert.py --partition PATH [--tasks PATH] [--out PATH]\n"
            "Convert typed partition.json to kanban_create payloads. Does not mint.\n"
            "--partition PATH  evidence/partition.json\n"
            "--tasks PATH      optional tasks.md (planning defects only; not write-sets)\n"
            "--out PATH        write payloads JSON (stdout if omitted)\n"
        )
        return 0 if args else 2
    partition: Path | None = None
    tasks: Path | None = None
    out: Path | None = None
    i = 0
    while i < len(args):
        if args[i] == "--partition" and i + 1 < len(args):
            partition = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--tasks" and i + 1 < len(args):
            tasks = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--out" and i + 1 < len(args):
            out = Path(args[i + 1])
            i += 2
            continue
        if args[i] in {"-h", "--help"}:
            sys.stdout.write(
                "k4_convert.py --partition PATH [--tasks PATH] [--out PATH]\n"
                "Convert typed partition.json to kanban_create payloads. Does not mint.\n"
            )
            return 0
        print("FAIL: unknown arg %s" % args[i], file=sys.stderr)
        return 1
    if partition is None:
        print("FAIL: pass --partition PATH", file=sys.stderr)
        return 1
    result, issues = convert_file(partition, tasks_path=tasks)
    if issues or result is None:
        print(format_issues(issues), file=sys.stderr)
        print("K4 convert FAILED.", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if out is not None:
        out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("OK: K4 convert (%d payload(s))." % len(result["payloads"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
