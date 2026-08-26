#!/usr/bin/env python3
"""K4 mint — K4 payloads → serial hermes kanban create.

Does not import create_task. Does not kanban swarm. Does not kanban
decompose. Does not kanban daemon --force. Default is dry-run argv.
--exec shells the pin CLI (terminal seat). Model kanban_create has no
max_retries field; M3 stories require CLI --max-retries 1.
Refuses a card whose pinned skills contain no producer for its primary
artifact (k4_producers.py; dest-8 M2+M4 are the negative fixture).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k4_convert import convert_file, format_issues, validate_result  # noqa: E402
from k4_producers import card_from_payload, producer_issues  # noqa: E402
from k4_schema import IMPL, REMEDY, VERIFIER_ID, WRITER_ID  # noqa: E402

Issue = tuple[str, str, str]
TASK_ID_RE = re.compile(r"^t_[A-Za-z0-9]+$")
FORBIDDEN = ("swarm", "decompose", "daemon", "create_task")
DEFAULT_WORKSPACE_ROOT = "/projects/modernized"
DEFAULT_MAX_RUNTIME = "2h"

Runner = Callable[[list[str]], tuple[int, str, str]]


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def _fail(issues: list[Issue]) -> None:
    raise ValueError(format_issues(issues))


def parse_created_id(stdout: str) -> str:
    text = (stdout or "").strip()
    if not text:
        _fail([_issue("K4_MINT_ID", "create --json stdout empty")])
    blob: Any = None
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                blob = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                blob = None
    if not isinstance(blob, dict):
        _fail([_issue("K4_MINT_ID", "create --json is not an object")])
    for key in ("task_id", "id"):
        raw = blob.get(key)
        if raw:
            tid = str(raw).strip()
            if TASK_ID_RE.match(tid):
                return tid
    nested = blob.get("task")
    if isinstance(nested, dict):
        for key in ("task_id", "id"):
            raw = nested.get(key)
            if raw:
                tid = str(raw).strip()
                if TASK_ID_RE.match(tid):
                    return tid
    _fail([_issue("K4_MINT_ID", "create --json missing t_* task_id")])
    raise AssertionError("unreachable")


def resolve_parents(payload: dict[str, Any], mapping: dict[str, str]) -> list[str]:
    out: list[str] = []
    for raw in payload.get("parents") or []:
        parent = str(raw).strip()
        if not parent:
            continue
        if parent in mapping:
            out.append(mapping[parent])
            continue
        if TASK_ID_RE.match(parent):
            out.append(parent)
            continue
        _fail(
            [
                _issue(
                    "K4_MINT_PARENT",
                    "%s parent %s is not minted and is not t_*"
                    % (payload.get("logical_id"), parent),
                )
            ]
        )
    return out


def workspace_flag() -> str:
    root = (
        os.environ.get("K4_WORKSPACE")
        or os.environ.get("MODERNIZED_ROOT")
        or DEFAULT_WORKSPACE_ROOT
    ).rstrip("/")
    return "dir:" + root


def max_runtime_flag() -> str:
    return (os.environ.get("K4_MAX_RUNTIME") or DEFAULT_MAX_RUNTIME).strip() or DEFAULT_MAX_RUNTIME


def assert_native_create(argv: list[str]) -> None:
    if len(argv) < 4 or argv[1:3] != ["kanban", "create"]:
        _fail([_issue("K4_MINT_CREATE", "argv is not hermes kanban create")])
    lowered = [a.lower() for a in argv]
    for token in FORBIDDEN:
        if token in lowered:
            _fail([_issue("K4_MINT_CREATE", "argv contains %s" % token)])
    if "--force" in argv:
        _fail([_issue("K4_MINT_CREATE", "argv contains --force")])


def argv_for_payload(
    payload: dict[str, Any],
    mapping: dict[str, str],
    *,
    hermes: str = "hermes",
) -> list[str]:
    if not isinstance(payload, dict):
        _fail([_issue("K4_SCHEMA", "payload must be an object")])
    lid = str(payload.get("logical_id") or "").strip()
    title = str(payload.get("title") or "")
    assignee = str(payload.get("assignee") or "")
    if lid in {WRITER_ID, VERIFIER_ID}:
        _fail([_issue("K4_FACTORY", "%s dest factory card is retired" % lid)])
    expected = "M3 %s" % lid
    if not lid or title != expected:
        _fail([_issue("K4_MINT_TITLE", "%s title %r != %r" % (lid, title, expected))])
    if assignee != IMPL:
        _fail([_issue("K4_ASSIGNEE", "%s assignee=%s" % (lid, assignee))])
    if payload.get("max_retries") != 1:
        _fail(
            [
                _issue(
                    "K4_MINT_RETRIES",
                    "%s max_retries %s" % (lid, payload.get("max_retries")),
                )
            ]
        )
    parents = resolve_parents(payload, mapping)
    m2 = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if m2 and TASK_ID_RE.match(m2) and m2 not in parents:
        parents = [m2] + parents
    argv = [hermes, "kanban", "create", title]
    body = str(payload.get("body") or "")
    argv.extend(["--body", body])
    argv.extend(["--assignee", assignee])
    for parent in parents:
        argv.extend(["--parent", parent])
    key = str(payload.get("idempotency_key") or "").strip()
    if not key:
        _fail([_issue("K4_SCHEMA", "%s missing idempotency_key" % lid)])
    argv.extend(["--idempotency-key", key])
    argv.extend(["--max-runtime", max_runtime_flag()])
    argv.extend(["--max-retries", "1"])
    argv.extend(["--workspace", workspace_flag()])
    skills = [str(s).strip() for s in (payload.get("skills") or []) if str(s).strip()]
    if not skills:
        _fail([_issue("K4_MINT_SKILLS", "%s skills empty" % lid)])
    prod = producer_issues(card_from_payload(payload))
    if prod:
        _fail(prod)
    for name in skills:
        argv.extend(["--skill", name])
    argv.append("--json")
    assert_native_create(argv)
    return argv


def mint_payloads(
    payloads: list[dict[str, Any]],
    *,
    runner: Runner,
    hermes: str = "hermes",
) -> dict[str, Any]:
    wrapped = {
        "payloads": payloads,
        "manifest": {"created_cards": [str(p.get("logical_id") or "") for p in payloads]},
        "claimed_control": False,
    }
    issues = validate_result(wrapped)
    if issues:
        _fail(issues)
    mapping: dict[str, str] = {}
    created: list[dict[str, Any]] = []
    for payload in payloads:
        argv = argv_for_payload(payload, mapping, hermes=hermes)
        code, out, err = runner(argv)
        if code != 0:
            _fail(
                [
                    _issue(
                        "K4_MINT_ID",
                        "create exit %s stderr=%s" % (code, (err or "").strip()[:200]),
                    )
                ]
            )
        tid = parse_created_id(out)
        lid = str(payload["logical_id"])
        mapping[lid] = tid
        created.append({"logical_id": lid, "task_id": tid, "argv": list(argv)})
    native_ids = [row["task_id"] for row in created]
    if not native_ids or any(not TASK_ID_RE.match(tid) for tid in native_ids):
        _fail([_issue("K4_MINT_ID", "created_cards empty or not t_* after mint")])
    return {
        "created": created,
        "created_cards": native_ids,
        "by_logical_id": mapping,
        "attribution": (
            "CLI k4_mint.py --exec; task ids are real "
            "(Architect 144916ZA: empty created_cards after a mint is OBJECT)"
        ),
        "claimed_control": False,
    }


def subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    payloads_path: Path | None = None
    partition_path: Path | None = None
    out_path: Path | None = None
    hermes = os.environ.get("HERMES_BIN", "hermes")
    execute = False
    i = 0
    while i < len(args):
        if args[i] == "--payloads" and i + 1 < len(args):
            payloads_path = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--partition" and i + 1 < len(args):
            partition_path = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--out" and i + 1 < len(args):
            out_path = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--hermes" and i + 1 < len(args):
            hermes = args[i + 1]
            i += 2
            continue
        if args[i] == "--exec":
            execute = True
            i += 1
            continue
        print("FAIL: unknown arg %s" % args[i], file=sys.stderr)
        return 1
    if (payloads_path is None) == (partition_path is None):
        print("FAIL: pass exactly one of --payloads PATH or --partition PATH", file=sys.stderr)
        return 1
    if partition_path is not None:
        result, issues = convert_file(partition_path)
        if issues or result is None:
            print(format_issues(issues), file=sys.stderr)
            print("K4 convert FAILED.", file=sys.stderr)
            return 1
        payloads = result["payloads"]
    else:
        try:
            blob = json.loads(payloads_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print("FAIL: %s" % exc, file=sys.stderr)
            return 1
        if isinstance(blob, dict) and isinstance(blob.get("payloads"), list):
            payloads = blob["payloads"]
        elif isinstance(blob, list):
            payloads = blob
        else:
            print("FAIL: --payloads must be convert JSON or a payload list", file=sys.stderr)
            return 1
    if execute:
        try:
            minted = mint_payloads(payloads, runner=subprocess_runner, hermes=hermes)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            print("K4 mint FAILED.", file=sys.stderr)
            return 1
        text = json.dumps(minted, indent=2, sort_keys=True) + "\n"
        if out_path is not None:
            out_path.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        print("OK: K4 mint (%d card(s))." % len(minted["created"]), file=sys.stderr)
        return 0
    try:
        mapping: dict[str, str] = {}
        dry: list[dict[str, Any]] = []
        wrapped = {
            "payloads": payloads,
            "manifest": {
                "created_cards": [str(p.get("logical_id") or "") for p in payloads]
            },
            "claimed_control": False,
        }
        issues = validate_result(wrapped)
        if issues:
            _fail(issues)
        for i, payload in enumerate(payloads):
            argv_list = argv_for_payload(payload, mapping, hermes=hermes)
            lid = str(payload["logical_id"])
            fake = "t_dry%04d" % (i + 1)
            mapping[lid] = fake
            dry.append({"logical_id": lid, "argv": argv_list})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        print("K4 mint FAILED.", file=sys.stderr)
        return 1
    text = json.dumps({"argv": dry, "claimed_control": False}, indent=2, sort_keys=True) + "\n"
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("OK: K4 mint dry-run (%d argv)." % len(dry), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
