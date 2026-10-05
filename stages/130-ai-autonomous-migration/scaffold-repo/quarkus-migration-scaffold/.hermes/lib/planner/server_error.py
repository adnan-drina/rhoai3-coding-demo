"""A destination's 5xx, taken from the destination's own log (H5b).

A parity difference ``status 500 vs 204`` carries only what the destination
ANSWERED, and on the platform's error page that is an error id and nothing
else. The exception is in the destination's log, and only during the
verification that produced the verdict: the runner that started the
destination is the one place that has both the log and the request's window
in it. So the runner extracts the exception block for a 5xx verdict and puts a
BOUNDED excerpt on the verdict (``server_error``); the planner turns it into
advice whose locus hints are the product files the stack names.

Nothing here knows a specimen. The block is matched by the error id the body
carried (a UUID, the platform's shape) when there is one, else it is the last
ERROR/stack block appended to the log while the request ran. A frame belongs
to the product when its class resolves to a file of this tree -- through the
destination model, the frozen structure model, or the derived source path --
and to the platform otherwise. Full stacks never enter a canonical record: the
block is retained beside the verdict as evidence and digested on it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from planner.canonical import load_json, sha256_bytes, write_canonical

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
FRAME_RE = re.compile(r"^\s*at\s+(?:[\w.]+/)?(?P<cls>[\w$.]+)\.(?P<method>[\w$<>]+)\((?P<file>[^:)]*)(?::(?P<line>\d+))?\)")
# a qualified class whose simple name ENDS in the throwable suffix: the logger
# category "QuarkusErrorHandler" is not an exception
EXCEPTION_RE = re.compile(r"(?P<cls>(?:[A-Za-z_$][\w$]*\.)+[A-Z][\w$]*?(?:Exception|Error|Throwable|Failure))(?![\w$])(?::\s?(?P<msg>.*))?")
CAUSED_RE = re.compile(r"^\s*Caused by:\s*(?P<rest>.*)$")
# a log line that starts a record: a timestamp and/or a level token
HEADER_RE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[.,]?\d*\s+)?(?:\[[^\]]*\]\s*)?(ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL|SEVERE)\b")
ERROR_LEVEL_RE = re.compile(r"\b(ERROR|SEVERE|FATAL)\b")
# a line that continues a record when the log carries no headers at all
CONTINUATION_RE = re.compile(r"^(?:\s+at\s|\s*Caused by:|\s*Suppressed:|\s*\.\.\.\s*\d+\s+(?:more|common frames omitted)|\s|$)")
STATUS_DIFF_RE = re.compile(r"(?:^|;\s*)status (?P<have>\d{3}) vs (?P<want>\d{3})\b")

FRAMES_SHOWN = 5
CAUSES_SHOWN = 3
EXCERPT_LINES = 12
LINE_CAP = 240
MESSAGE_CAP = 300
RETAINED_CAP = 64 * 1024
RETAINED_DIR = "_server-errors"   # beside the verdicts; "_" keeps it out of the record partition


def server_error_status(reason: str) -> tuple[int, int] | None:
    """(observed, expected) when the verdict's status difference is a 5xx the
    source did not answer; None for anything else (a 4xx, a matching status,
    a 5xx the source answered too)."""
    m = STATUS_DIFF_RE.search(str(reason or ""))
    if not m:
        return None
    have, want = int(m.group("have")), int(m.group("want"))
    if have >= 500 and want < 500:
        return have, want
    return None


def log_blocks(text: str) -> list[str]:
    """The log cut into records. A record starts at a header line (timestamp
    and/or level) when the log has any; a log with none is cut at every line
    that is not a continuation (a frame, a cause, an indented line)."""
    lines = str(text or "").splitlines()
    if not lines:
        return []
    headed = any(HEADER_RE.match(ln) for ln in lines)
    starts = (lambda ln: bool(HEADER_RE.match(ln))) if headed else (lambda ln: not CONTINUATION_RE.match(ln))
    blocks: list[list[str]] = []
    for ln in lines:
        if starts(ln) or not blocks:
            blocks.append([ln])
        else:
            blocks[-1].append(ln)
    return ["\n".join(b) for b in blocks]


def _is_stack_block(block: str) -> bool:
    head = block.split("\n", 1)[0]
    return bool(ERROR_LEVEL_RE.search(head)) or any(FRAME_RE.match(ln) for ln in block.split("\n")[1:4])


def find_error_block(log_text: str, error_ids: list[str], window_text: str | None) -> tuple[str, str]:
    """(the block, how it was matched). ``error_id`` when a block carries one
    of the ids the body named -- looked for in the request's window first and
    in the whole log after; ``window`` when the id is absent and the last
    ERROR/stack block appended while the request ran is taken instead; ("",
    "") when neither exists (no window, or nothing was logged in it)."""
    ids = [str(i) for i in (error_ids or []) if str(i)]
    scopes = [t for t in (window_text, log_text) if t]
    for eid in ids:
        for scope in scopes:
            for block in log_blocks(scope):
                if eid in block:
                    return block, "error_id"
    if window_text:
        for block in reversed(log_blocks(window_text)):
            if _is_stack_block(block):
                return block, "window"
    return "", ""


def _exception_of(line: str) -> tuple[str, str]:
    m = EXCEPTION_RE.search(line)
    if not m:
        return "", ""
    return m.group("cls"), str(m.group("msg") or "").strip()[:MESSAGE_CAP]


def frame_class(cls: str) -> str:
    """The top-level type a frame's class names: inner classes, lambdas and
    generated subclasses (``$``) are declared in the outer type's file."""
    return str(cls or "").split("$", 1)[0]


def product_file_resolver(root: Path | None) -> Callable[[str], str]:
    """class fqn -> the file of THIS tree that declares it, or "".

    Read from the destination model when it can be had (the compiled sources'
    own paths), else from the frozen structure model (the same relative path
    convention), else derived from the name when that file exists in the tree.
    A class none of these know is the platform's."""
    by_fqn: dict[str, str] = {}
    if root is not None:
        try:
            from planner.dest_model import DestModelUnavailable, dest_model

            model = dest_model(Path(root))
            prefix = str(model.get("source_root") or "src/main/java").rstrip("/") + "/"
            for t in model.get("types") or []:
                if isinstance(t, dict) and t.get("fqn") and t.get("path"):
                    by_fqn.setdefault(str(t["fqn"]), prefix + str(t["path"]))
        except Exception:  # noqa: BLE001  (no JDK, no tool, no sources: the other two sources answer)
            pass
        try:
            from planner.worklist import structure_type_path, structure_types

            for t in structure_types(Path(root)):
                if t.get("fqn"):
                    p = structure_type_path(Path(root), t)
                    if p:
                        by_fqn.setdefault(str(t["fqn"]), p)
        except Exception:  # noqa: BLE001
            pass

    def resolve(cls: str) -> str:
        outer = frame_class(cls)
        if not outer:
            return ""
        hit = by_fqn.get(outer, "")
        if hit:
            return hit
        if root is not None:
            derived = "src/main/java/%s.java" % outer.replace(".", "/")
            if (Path(root) / derived).is_file():
                return derived
        return ""

    return resolve


def describe_block(block: str, resolve: Callable[[str], str], error_id: str = "") -> dict[str, Any]:
    """The bounded description of one exception block: the exception and its
    message, the cause chain (bounded), the first frames that belong to THIS
    product (resolved to files), an excerpt, and the digest of the whole."""
    lines = block.split("\n")
    head_lines = []
    for ln in lines:
        if FRAME_RE.match(ln):
            break
        head_lines.append(ln)
    exception, message = "", ""
    for ln in head_lines:
        exception, message = _exception_of(ln)
        if exception:
            break
    causes: list[dict[str, str]] = []
    for ln in lines:
        m = CAUSED_RE.match(ln)
        if m:
            cls, msg = _exception_of(m.group("rest"))
            if cls and len(causes) < CAUSES_SHOWN:
                causes.append({"exception": cls, "message": msg})
    frames: list[dict[str, Any]] = []
    platform_skipped = 0
    for ln in lines:
        fm = FRAME_RE.match(ln)
        if not fm:
            continue
        path = resolve(fm.group("cls"))
        if not path:
            platform_skipped += 1
            continue
        if len(frames) < FRAMES_SHOWN:
            frames.append({"class": fm.group("cls"), "method": fm.group("method"), "file": path,
                           "line": int(fm.group("line")) if fm.group("line") else 0})
    eid = error_id or next(iter(UUID_RE.findall(block)), "")
    excerpt = [ln[:LINE_CAP] for ln in lines[:EXCERPT_LINES]]
    return {"error_id": eid, "exception": exception, "message": message, "causes": causes, "frames": frames,
            "platform_frames_skipped": platform_skipped, "excerpt": excerpt, "lines": len(lines),
            "stack_sha256": sha256_bytes(block.encode("utf-8"))}


def annotate_record(root: Path, record: Path, log: Path, window: tuple[int, int] | None,
                    resolve: Callable[[str], str] | None = None) -> dict[str, Any] | None:
    """Put the destination's exception on a 5xx verdict, bounded.

    ``window`` is the byte span of ``log`` that was appended while this
    comparison ran (the request's window). Returns the row written, or None
    when the record is not a FAIL, its status difference is not a 5xx the
    source did not answer, or the log is not there. A verdict whose block
    cannot be found still records the search (``matched`` ""), so the advice
    can say the log holds no exception for it rather than nothing."""
    root, record, log = Path(root), Path(record), Path(log)
    if not record.is_file() or not log.is_file():
        return None
    try:
        doc = load_json(record)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or str(doc.get("verdict") or "") != "FAIL":
        return None
    status = server_error_status(str(doc.get("reason") or ""))
    if status is None:
        return None
    observed = doc.get("observed") if isinstance(doc.get("observed"), dict) else {}
    ids = UUID_RE.findall(str(observed.get("body_sample") or ""))
    raw = log.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    window_text = None
    if window and window[1] > window[0] >= 0:
        window_text = raw[window[0]:window[1]].decode("utf-8", errors="replace")
    block, how = find_error_block(text, ids, window_text)
    resolve = resolve or product_file_resolver(root)
    row: dict[str, Any] = {"status": status[0], "expected_status": status[1], "matched": how,
                           "log": _rel(root, log), "window": list(window) if window else []}
    if block:
        matched_id = next((i for i in ids if i in block), "")
        row.update(describe_block(block, resolve, matched_id))
        keep = record.parent / RETAINED_DIR / (record.stem + ".log")
        keep.parent.mkdir(parents=True, exist_ok=True)
        data = block.encode("utf-8")
        keep.write_bytes(data[:RETAINED_CAP])
        row["retained"] = _rel(root, keep)
        row["retained_truncated"] = len(data) > RETAINED_CAP
    else:
        row.update({"error_id": ids[0] if ids else "", "exception": "", "message": "", "causes": [], "frames": [],
                    "note": ("the destination log holds no exception block for this request (%s)"
                             % ("error id %s not logged" % ids[0] if ids else "no error id in the body, nothing at ERROR in the window"))})
    doc["server_error"] = row
    write_canonical(record, doc)
    return row


def _rel(root: Path, p: Path) -> str:
    try:
        return p.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()
