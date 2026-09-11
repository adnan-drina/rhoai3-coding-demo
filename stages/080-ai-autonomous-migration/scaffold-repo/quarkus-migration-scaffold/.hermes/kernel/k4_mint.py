#!/usr/bin/env python3
"""K4 mint — the loop's next card → one hermes kanban create.

Refuses before emitting any command unless admission-receipt.json is
ADMITTED and sealed (k4_convert.convert_admitted). Every card, including
M4 VERIFY, carries a receipt-bound idempotency key
(k4:<cluster>:<attempt>:<receipt16>), so a repeated mint is a no-op and a
card from another receipt or attempt is foreign.

Does not import create_task. Does not kanban swarm / decompose / link /
daemon --force. Default is dry-run argv. --exec shells the pin CLI
(terminal seat). --verify-board compares the live board to the DAG after
--exec (K3 live comparator) and refuses on any mismatch.
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
_LIB = _KERNEL.parent / "lib"
for p in (_KERNEL, _LIB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from k4_convert import convert_admitted, format_issues, validate_result  # noqa: E402
from k4_producers import card_from_payload, producer_issues  # noqa: E402
from k4_schema import IMPL, KEY_PREFIX, REMEDY, VERIFIER_ID, WRITER_ID  # noqa: E402
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.live_board import collect_board, compare_board, expected_from_loop, mint_map_from_receipts  # noqa: E402
from planner.paths import LOOP_CARDS, LOOP_ISSUED, LOOP_STEPS  # noqa: E402

Issue = tuple[str, str, str]
TASK_ID_RE = re.compile(r"^t_[A-Za-z0-9]+$")
FORBIDDEN = ("swarm", "decompose", "daemon", "create_task", "link")
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
        if raw and TASK_ID_RE.match(str(raw).strip()):
            return str(raw).strip()
    nested = blob.get("task")
    if isinstance(nested, dict):
        for key in ("task_id", "id"):
            raw = nested.get(key)
            if raw and TASK_ID_RE.match(str(raw).strip()):
                return str(raw).strip()
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
        _fail([_issue("K4_MINT_PARENT", "%s parent %s is not minted and is not t_*" % (payload.get("logical_id"), parent))])
    return out


def workspace_flag() -> str:
    if "K4_WORKSPACE" in os.environ:
        raw = os.environ.get("K4_WORKSPACE")
    elif "MODERNIZED_ROOT" in os.environ:
        raw = os.environ.get("MODERNIZED_ROOT")
    else:
        raw = DEFAULT_WORKSPACE_ROOT
    root = (raw or "").strip().rstrip("/")
    if not root or not root.startswith("/"):
        _fail([_issue("K4_MINT_WORKSPACE", "workspace root %r is empty or not absolute (scratch OBJECT)" % root)])
    referent = DEFAULT_WORKSPACE_ROOT.rstrip("/")
    if root != referent and not root.startswith(referent + "/"):
        _fail([_issue("K4_MINT_WORKSPACE", "workspace root %s is outside %s (scratch OBJECT)" % (root, referent))])
    return "dir:" + root


def max_runtime_flag() -> str:
    return (os.environ.get("K4_MAX_RUNTIME") or DEFAULT_MAX_RUNTIME).strip() or DEFAULT_MAX_RUNTIME


def assert_native_create(argv: list[str]) -> None:
    if len(argv) < 4 or argv[1:3] != ["kanban", "create"]:
        _fail([_issue("K4_MINT_CREATE", "argv is not hermes kanban create")])
    lowered = [a.lower() for a in argv[3:]]
    for token in FORBIDDEN:
        if token in lowered:
            _fail([_issue("K4_MINT_CREATE", "argv contains %s" % token)])
    if "--force" in argv:
        _fail([_issue("K4_MINT_CREATE", "argv contains --force")])


def argv_for_payload(payload: dict[str, Any], mapping: dict[str, str], *, hermes: str = "hermes", receipt_digest: str = "") -> list[str]:
    if not isinstance(payload, dict):
        _fail([_issue("K4_SCHEMA", "payload must be an object")])
    lid = str(payload.get("logical_id") or "").strip()
    title = str(payload.get("title") or "")
    assignee = str(payload.get("assignee") or "")
    kind = str(payload.get("kind") or "")
    if lid in {WRITER_ID, VERIFIER_ID}:
        _fail([_issue("K4_FACTORY", "%s dest factory card is retired" % lid)])
    # Titles are readable ("M3 build pom.xml (14 items, attempt 1)"); the
    # cluster id lives in the body and the idempotency key, never in the title.
    ok_title = (title == "M4 VERIFY") if kind == "close" else (title.startswith("M3 ") and ", attempt " in title)
    if not lid or not ok_title:
        _fail([_issue("K4_MINT_TITLE", "%s title %r is not a loop-card title" % (lid, title))])
    if assignee != IMPL:
        _fail([_issue("K4_ASSIGNEE", "%s assignee=%s" % (lid, assignee))])
    if payload.get("max_retries") != 1:
        _fail([_issue("K4_MINT_RETRIES", "%s max_retries %s" % (lid, payload.get("max_retries")))])
    key = str(payload.get("idempotency_key") or "").strip()
    attempt = payload.get("attempt")
    if not key.startswith(KEY_PREFIX + lid + ":") or key == "m4-verify" or not isinstance(attempt, int) or attempt < 1 or (receipt_digest and key != "%s%s:%d:%s" % (KEY_PREFIX, lid, attempt, receipt_digest[:16])):
        _fail([_issue("K4_MINT_KEY", "%s idempotency_key %r attempt %r" % (lid, key, attempt))])
    parents = resolve_parents(payload, mapping)
    m2 = control_card("m2")
    if m2 and TASK_ID_RE.match(m2) and m2 not in parents:
        parents = [m2] + parents
    argv = [hermes, "kanban", "create", title]
    argv.extend(["--body", str(payload.get("body") or "")])
    argv.extend(["--assignee", assignee])
    for parent in parents:
        argv.extend(["--parent", parent])
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


def mint_payloads(result: dict[str, Any], *, runner: Runner, hermes: str = "hermes") -> dict[str, Any]:
    payloads = result["payloads"]
    issues = validate_result(result)
    if issues:
        _fail(issues)
    receipt_digest = str(result.get("receipt_sha256") or "")
    # Translate every argv BEFORE running any: a refusal emits zero commands.
    plan: list[tuple[dict[str, Any], list[str]]] = []
    mapping: dict[str, str] = {}
    for i, payload in enumerate(payloads):
        fake = "t_pending%04d" % (i + 1)
        argv = argv_for_payload(payload, mapping, hermes=hermes, receipt_digest=receipt_digest)
        mapping[str(payload["logical_id"])] = fake
        plan.append((payload, argv))
    mapping = {}
    created: list[dict[str, Any]] = []
    for payload, _ in plan:
        argv = argv_for_payload(payload, mapping, hermes=hermes, receipt_digest=receipt_digest)
        code, out, err = runner(argv)
        if code != 0:
            _fail([_issue("K4_MINT_ID", "create exit %s stderr=%s" % (code, (err or "").strip()[:200]))])
        tid = parse_created_id(out)
        lid = str(payload["logical_id"])
        mapping[lid] = tid
        created.append({"logical_id": lid, "task_id": tid, "idempotency_key": payload["idempotency_key"], "argv": list(argv)})
    native_ids = [row["task_id"] for row in created]
    if not native_ids or any(not TASK_ID_RE.match(tid) for tid in native_ids):
        _fail([_issue("K4_MINT_ID", "created_cards empty or not t_* after mint")])
    return {
        "created": created,
        "created_cards": native_ids,
        "by_logical_id": mapping,
        "receipt_sha256": receipt_digest,
        "attribution": "CLI k4_mint.py --exec; task ids are real (empty created_cards after a mint is OBJECT)",
        "claimed_control": False,
    }


MINT_RECEIPTS = Path("evidence") / "receipts" / "k4" / "mints.json"
_CARDS_ROOT: Path | None = None


def register_control_cards(root: Path) -> dict[str, str]:
    """verification/loop/cards.json: the M2 (and M1) control cards, registered
    once from HERMES_KANBAN_TASK on the M2 card. Execution cards never enter
    this registry; K3 exempts only what is registered here."""
    global _CARDS_ROOT
    _CARDS_ROOT = Path(root)
    path = Path(root) / LOOP_CARDS
    doc = load_json(path) if path.is_file() else {"schema": "rhoai3.loop-cards/v1", "control": {}}
    changed = False
    env = (os.environ.get("HERMES_KANBAN_TASK") or "").strip()
    if env and TASK_ID_RE.match(env) and not doc["control"].get("m2"):
        doc["control"]["m2"] = env
        changed = True
    # dest-init's own record of the cards it minted (M1 always, M2 under an
    # activated/pilot planner): registered here so K3 never reports them as
    # foreign and no worker needs --exempt (pilot v5 measured that workaround).
    status_p = Path(root) / ".hermes" / "AUTOSTART-STATUS"
    if status_p.is_file():
        try:
            status = load_json(status_p)
        except Exception:
            status = {}
        for name, key in (("m1", "m1_id"), ("m2", "m2_id")):
            tid = str((status or {}).get(key) or "").strip()
            if tid and TASK_ID_RE.match(tid) and not doc["control"].get(name):
                doc["control"][name] = tid
                changed = True
    if changed:
        write_canonical(path, doc)
    return dict(doc.get("control") or {})


def control_card(name: str) -> str:
    if _CARDS_ROOT is None:
        return ""
    path = _CARDS_ROOT / LOOP_CARDS
    doc = load_json(path) if path.is_file() else {}
    return str((doc.get("control") or {}).get(name) or "")


def load_mint_receipts(root: Path) -> list[dict[str, Any]]:
    p = Path(root) / MINT_RECEIPTS
    if not p.is_file():
        return []
    doc = load_json(p)
    return list(doc.get("mints") or []) if isinstance(doc, dict) else []


def write_mint_receipt(root: Path, minted: dict[str, Any]) -> Path:
    """Append the task-id → key mapping captured from the real create
    responses. K3 matches cards on a board that does not expose
    idempotency keys only through these; anything else is foreign."""
    path = Path(root) / MINT_RECEIPTS
    mints = load_mint_receipts(root)
    mints.append({
        "schema": "rhoai3.k4-mint-receipt/v1",
        "receipt_sha256": minted.get("receipt_sha256"),
        "created": [{"logical_id": r["logical_id"], "task_id": r["task_id"], "idempotency_key": r["idempotency_key"]} for r in minted.get("created") or []],
    })
    write_canonical(path, {"schema": "rhoai3.k4-mint-receipts/v1", "mints": mints, "claimed_control": False})
    return path


def record_issued_task(root: Path, minted: dict[str, Any]) -> None:
    """Bind the minted t_* to the issued card so advance.py can require it."""
    path = Path(root) / LOOP_ISSUED
    if not path.is_file():
        return
    doc = load_json(path)
    for row in minted.get("created") or []:
        if row.get("idempotency_key") == doc.get("idempotency_key"):
            doc["task_id"] = row["task_id"]
            write_canonical(path, doc)


def verify_board(root: Path, result: dict[str, Any], *, runner: Runner, hermes: str = "hermes", exempt: list[str]) -> dict[str, Any]:
    """Post-mint K3 live comparison; raises K4_BOARD on mismatch."""
    try:
        enriched = collect_board(runner, hermes)
    except ValueError as exc:
        _fail([_issue("K4_BOARD", str(exc))])
    mint_map = mint_map_from_receipts(load_mint_receipts(root))
    steps = load_json(root / LOOP_STEPS) if (root / LOOP_STEPS).is_file() else None
    open_card = result["payloads"][0] if result.get("payloads") else None
    expected = expected_from_loop(steps, open_card, mint_map)
    verdict = compare_board(expected, enriched, exempt_ids=exempt, mint_map=mint_map)
    verdict["receipt_sha256"] = str(result.get("receipt_sha256") or "")
    write_canonical(root / "evidence" / "receipts" / "k3" / "live-board.json", verdict)
    if verdict["verdict"] != "EQUAL":
        _fail([_issue("K4_BOARD", "missing=%s foreign=%s edges=%s" % (verdict["missing_keys"], verdict["foreign_cards"], verdict["edge_gaps"]))])
    return verdict


def subprocess_runner(argv: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write(
            "k4_mint.py --root PATH [--out PATH] [--exec] [--verify-board] [--exempt t_x]... [--hermes BIN]\n"
            "Translate the ADMITTED DAG into serial hermes kanban create. Default is dry-run argv.\n"
            "Zero commands unless admission-receipt.json is ADMITTED and sealed.\n"
        )
        return 0 if args else 2
    root: Path | None = None
    out_path: Path | None = None
    hermes = os.environ.get("HERMES_BIN", "hermes")
    execute = False
    verify = False
    exempt: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--root" and i + 1 < len(args):
            root = Path(args[i + 1])
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
        if args[i] == "--exempt" and i + 1 < len(args):
            exempt.append(args[i + 1])
            i += 2
            continue
        if args[i] == "--exec":
            execute = True
            i += 1
            continue
        if args[i] == "--verify-board":
            verify = True
            i += 1
            continue
        print("FAIL: unknown arg %s" % args[i], file=sys.stderr)
        return 1
    if root is None:
        print("FAIL: pass --root PATH", file=sys.stderr)
        return 1
    root = root.resolve()
    control = register_control_cards(root)
    result, issues = convert_admitted(root)
    if issues or result is None:
        print(format_issues(issues), file=sys.stderr)
        print("K4 mint REFUSED before emitting any command (0 creates).", file=sys.stderr)
        return 1
    exempt.extend(v for v in control.values() if v)
    if execute:
        try:
            minted = mint_payloads(result, runner=subprocess_runner, hermes=hermes)
            write_mint_receipt(root, minted)
            record_issued_task(root, minted)
            if verify:
                minted["board"] = verify_board(root, result, runner=subprocess_runner, hermes=hermes, exempt=exempt)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            print("K4 mint FAILED.", file=sys.stderr)
            return 1
        text = json.dumps(minted, indent=2, sort_keys=True) + "\n"
        if out_path is not None:
            out_path.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        print("OK: K4 mint (%d card(s), receipt %s)." % (len(minted["created"]), result["receipt_sha256"][:16]), file=sys.stderr)
        return 0
    try:
        mapping: dict[str, str] = {}
        dry: list[dict[str, Any]] = []
        for i, payload in enumerate(result["payloads"]):
            argv_list = argv_for_payload(payload, mapping, hermes=hermes, receipt_digest=result["receipt_sha256"])
            lid = str(payload["logical_id"])
            mapping[lid] = "t_dry%04d" % (i + 1)
            dry.append({"logical_id": lid, "argv": argv_list})
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        print("K4 mint FAILED.", file=sys.stderr)
        return 1
    text = json.dumps({"argv": dry, "receipt_sha256": result["receipt_sha256"], "claimed_control": False}, indent=2, sort_keys=True) + "\n"
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    print("OK: K4 mint dry-run (%d argv, receipt %s)." % (len(dry), result["receipt_sha256"][:16]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
