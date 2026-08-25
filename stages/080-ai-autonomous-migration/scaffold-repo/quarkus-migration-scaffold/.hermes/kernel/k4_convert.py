#!/usr/bin/env python3
"""K4 converter — typed partition → kanban_create payloads.

Does not mint. Does not import create_task. Does not read tasks.md for
write-sets. Optional --tasks only reports planning defects (all paths).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k4_schema import (  # noqa: E402
    IMPL,
    PATH_TOKEN_MARKERS,
    REMEDY,
    SHA256_RE,
    VERIFIER_ID,
    WRITER_ID,
)

Issue = tuple[str, str, str]
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
SKILLS_BY_KIND = {
    "setup": [
        "author-destination-pom",
        "reference-rh-quarkus-pom",
        "manage-quarkus-extensions",
        "configure-quarkus-profiles",
    ],
    "us": ["spring-to-quarkus-patterns"],
    "polish": ["manage-quarkus-extensions"],
}


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _story_id(story: dict[str, Any]) -> str:
    return str(story.get("story_id") or story.get("id") or "").strip()


def partition_write_union(stories: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for story in stories:
        for p in story.get("files_writable") or []:
            s = str(p).strip()
            if s:
                out.add(s)
    return out


def shared_service_java(stories: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Same *Service.java in two or more stories = methods-in-shared-class."""
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
                _issue("K4_SKILLS", "%s skills empty (set skills[] or kind setup/us/polish)" % sid)
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
                "path": str(story.get("legacy_locus_path") or "evidence/locus.json"),
                "sha256": str(story.get("legacy_locus_sha256") or "pending"),
            },
        ],
        "identity": {"story_id": sid},
        "files_in_scope": list(fw),
        "files_writable": list(fw),
        "exit_criteria": exits,
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


def convert_partition(partition: dict[str, Any]) -> dict[str, Any]:
    type_sha = str(partition.get("type_inventory_sha256") or "")
    stories = [s for s in (partition.get("stories") or []) if isinstance(s, dict)]
    payloads: list[dict[str, Any]] = []
    for story in stories:
        sid = _story_id(story)
        part_parents = [str(p) for p in (story.get("parents") or [])]
        payloads.append(
            _payload(
                sid,
                title="M3 %s" % sid,
                assignee=IMPL,
                parents=part_parents,
                body=_m3_body(story, type_sha),
                skills=story_skills(story),
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
    return convert_partition(partition), []


def format_issues(issues: list[Issue]) -> str:
    lines = []
    for code, detail, remedy in issues:
        lines.append("%s: %s" % (code, detail))
        lines.append("  remedy: %s" % remedy)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
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
