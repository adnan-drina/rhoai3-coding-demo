#!/usr/bin/env python3
"""Partition gaps coverage used to miss: stale AC HTTP vs endpoints, implicit pom.

Lead:us1-acceptance-names-a-stale-route — dest-6 M2 corrected ``endpoints``
to ``GET /greeting`` and left AC prose at ``/api/greeting``. Coverage read
the field; nothing read the text (Operator E-20260825T205101ZO).

Lead:dependency-wait-on-a-done-parent-is-unresolvable — ``mvn -q test``
names no file, so batch-3 unsatisfiable-acceptance could not see that the
pom (and its test toolchain) is an implicit parent obligation.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def _load_invented():
    path = _SCRIPTS / "assert-partition-invented-routes.py"
    spec = importlib.util.spec_from_file_location("invented_routes_mod", path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: cannot load assert-partition-invented-routes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_inv = _load_invented()


def _cmd_runs_tests(cmd: str) -> bool:
    c = " ".join(str(cmd or "").split())
    if not c or "test-compile" in c:
        return False
    return bool(re.search(r"(?:^|\s)(?:mvn|\./mvnw)(?:\s|$).*\b(?:test|verify)\b", c))


def _story_id(story: dict) -> str:
    return str(story.get("story_id") or story.get("id") or "").strip()


def _writable(story: dict) -> list[str]:
    out: list[str] = []
    for key in ("files_writable", "files", "files_in_scope"):
        raw = story.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.replace("\\", "/").strip())
    return out


def _owns_pom(story: dict) -> bool:
    names = {Path(p).name for p in _writable(story)}
    return "pom.xml" in names


def _ac_blob(story: dict) -> str:
    parts: list[str] = []
    for key in ("acceptance_criteria", "acceptance", "ac", "exit_criteria", "done_when"):
        raw = story.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            parts.append(raw)
            continue
        parts.append(json.dumps(raw, default=str))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    parts.append(
                        " ".join(
                            str(item.get(k) or "")
                            for k in ("cmd", "assert", "expect", "check")
                        )
                    )
    return "\n".join(parts)


def _runs_tests(story: dict) -> bool:
    if _cmd_runs_tests(_ac_blob(story)):
        return True
    for rel in _writable(story):
        padded = "/" + rel.strip("/") + "/"
        if "/src/test/" in padded or rel.startswith("src/test/"):
            return True
    return False


def _has_test_toolchain_claim(story: dict) -> bool:
    return "check-test-toolchain" in _ac_blob(story)


def stale_ac_http_gaps(stories: list[dict]) -> list[str]:
    """AC HTTP tokens that are not in the endpoints field.

    Empty endpoints with AC HTTP is invented-routes, not this gap.
    """
    gaps: list[str] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        eps = story.get("endpoints") or []
        if not isinstance(eps, list) or not [str(x).strip() for x in eps if str(x).strip()]:
            continue
        sid = _story_id(story) or "?"
        ep_paths = set()
        for ep in eps:
            ep_paths |= _inv.routes_in(str(ep))
        ac_parts: list[str] = []
        for key in ("acceptance_criteria", "acceptance", "ac"):
            raw = story.get(key)
            if raw is None:
                continue
            ac_parts.append(raw if isinstance(raw, str) else json.dumps(raw, default=str))
        ac_paths = _inv.routes_in(" ".join(ac_parts))
        for path in sorted(ac_paths - ep_paths):
            gaps.append(f"stale_ac:{sid}:{path}")
    return gaps


def implicit_pom_gaps(stories: list[dict]) -> list[str]:
    """``mvn -q test`` / src/test without pom.xml in this write-set.

    Legal when a parent owns pom.xml AND that parent claims the test
    toolchain (check-test-toolchain). A compile-only parent is the dest-6
    setup→us1 shape: the wait is unresolvable once setup is done.
    """
    by_id = {_story_id(s): s for s in stories if isinstance(s, dict) and _story_id(s)}
    gaps: list[str] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        sid = _story_id(story)
        if not sid or not _runs_tests(story) or _owns_pom(story):
            continue
        parents = story.get("parents") or []
        if not isinstance(parents, list):
            parents = []
        seen: set[str] = set()
        stack = [str(p) for p in parents]
        pom_parents: list[str] = []
        while stack:
            par = stack.pop()
            if not par or par in seen:
                continue
            seen.add(par)
            parent = by_id.get(par)
            if not isinstance(parent, dict):
                continue
            if _owns_pom(parent):
                pom_parents.append(par)
            stack.extend(str(x) for x in (parent.get("parents") or []) if x)
        if not pom_parents:
            gaps.append(f"implicit_pom:{sid}")
            continue
        for par in pom_parents:
            parent = by_id.get(par) or {}
            if not _has_test_toolchain_claim(parent):
                gaps.append(f"implicit_pom_parent_vacuous:{sid}:{par}")
    return gaps


def extra_story_gaps(stories: list[dict]) -> list[str]:
    return stale_ac_http_gaps(stories) + implicit_pom_gaps(stories)
