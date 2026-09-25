"""Which board protocol a run uses, and whether its execution may run.

The outcome board (stages/080-ai-autonomous-migration/OUTCOME-BOARD-CONTRACT.md)
applies to NEW runs only. A run selects it once, before publication, from a
record the run itself cannot rewrite:

  governed run (run control in the initial commit)
      the platform's read-only contract: ``board_protocol`` and
      ``outcome_board.execution``;
  legacy / local run
      ``run-defaults.json`` ``configuration.board_protocol``, bound by the
      destination's initial commit through run_declaration when a factory
      declaration exists, and ``.hermes/pins.json``
      ``pins.planner.outcome_board.execution``.

Absent means the serial loop (``serial-loop/v1``) and ``disabled``. The golden
ships neither key, so every existing and every next-golden run is unchanged.

Execution modes:

  disabled       nothing executes under the outcome protocol (default).
  qualification  local, disposable fixtures only: honoured only when there
                 is no factory run declaration and no run control. A real run
                 can never enter it. Every check runs, against the cooperative
                 store; ``claimed_control`` stays false.
  enabled        requires a PROTECTED authority store (another UID owns it and
                 the caller cannot write it). No such principal exists in the
                 current workspace architecture, so this refuses
                 AUTHORITY_UNPROTECTED (architect F1).

Mixed state -- outcome records beside serial-loop records, or the reverse --
refuses on every path (A13).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SERIAL = "serial-loop/v1"
OUTCOME = "outcome-board/v1"
PROTOCOLS = (SERIAL, OUTCOME)

DISABLED = "disabled"
QUALIFICATION = "qualification"
ENABLED = "enabled"
MODES = (DISABLED, QUALIFICATION, ENABLED)

STORE_DIR = Path("verification") / "outcome-board"
STORE_FILE = STORE_DIR / "authority.sqlite3"
DEFAULTS = Path("run-defaults.json")
DECLARATION = Path("run-budget.json")
PINS = Path(".hermes") / "pins.json"
LOOP_ISSUED = Path("verification") / "loop" / "issued.json"
MINT_RECEIPTS = Path("evidence") / "receipts" / "k4" / "mints.json"

# Refusal codes, each with the one remedy it names.
REMEDY = {
    "PROTOCOL_UNKNOWN": "board_protocol must be serial-loop/v1 or outcome-board/v1; recreate the run from the factory.",
    "PROTOCOL_UNBOUND": "The protocol record is not the one the run was created with (run declaration refused); a run never switches protocol.",
    "PROTOCOL_MIXED": "Outcome-board and serial-loop records coexist. Neither reader may act; abandon or restore the run explicitly.",
    "PROTOCOL_NOT_OUTCOME": "This path belongs to the outcome-board protocol and this run uses the serial loop.",
    "OUTCOME_EXECUTION_DISABLED": "Outcome-board execution is disabled (the default). Nothing is published or executed.",
    "OUTCOME_QUALIFICATION_REFUSED": "qualification mode is honoured only on a disposable fixture with no factory run declaration and no run control.",
    "AUTHORITY_UNPROTECTED": "enabled execution needs a protected authority store (another UID owns it; the caller cannot write it). None exists in this architecture (F1).",
    "EXECUTION_MODE_UNKNOWN": "outcome_board.execution must be disabled, qualification or enabled.",
}


@dataclass
class Selection:
    protocol: str
    execution: str
    source: str
    governed: bool
    declaration: str
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def outcome(self) -> bool:
        return self.protocol == OUTCOME

    def as_dict(self) -> dict[str, Any]:
        return {"protocol": self.protocol, "execution": self.execution, "source": self.source,
                "governed": self.governed, "declaration": self.declaration,
                "errors": [list(e) for e in self.errors]}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _declaration_code(root: Path) -> str:
    if not (root / DECLARATION).is_file():
        return "RUN_DECLARATION_MISSING"
    try:
        from planner import run_declaration
        return run_declaration.load(root).code
    except Exception as exc:  # a declaration we cannot read binds nothing
        return "RUN_DECLARATION_UNVERIFIABLE:%s" % type(exc).__name__


def select_protocol(root: Path) -> Selection:
    """The run's protocol and execution mode, with the record they came from."""
    root = Path(root)
    governed = False
    try:
        from planner import run_control
        governed = run_control.in_use(root)
    except Exception:
        governed = False
    if governed:
        from planner import run_control
        doc, gaps = run_control.contract(root)
        if gaps:
            return Selection(SERIAL, DISABLED, "run-control", True, "governed",
                             [("PROTOCOL_UNBOUND", gaps[0])])
        protocol = str(doc.get("board_protocol") or SERIAL)
        board = doc.get("outcome_board") if isinstance(doc.get("outcome_board"), dict) else {}
        execution = str(board.get("execution") or DISABLED)
        sel = Selection(protocol, execution, "run-control", True, "governed")
    else:
        code = _declaration_code(root)
        defaults = _read_json(root / DEFAULTS)
        conf = defaults.get("configuration") if isinstance(defaults, dict) else None
        protocol = str((conf or {}).get("board_protocol") or SERIAL) if isinstance(conf, dict) else SERIAL
        pins = _read_json(root / PINS)
        planner = (((pins or {}).get("pins") or {}).get("planner") or {}) if isinstance(pins, dict) else {}
        board = planner.get("outcome_board") if isinstance(planner, dict) and isinstance(planner.get("outcome_board"), dict) else {}
        execution = str(board.get("execution") or DISABLED)
        sel = Selection(protocol, execution, "run-defaults+pins", False, code)
        if code not in ("RUN_DECLARATION_MISSING", "OK", "LEGACY"):
            sel.errors.append(("PROTOCOL_UNBOUND", "run declaration %s" % code))
    if sel.protocol not in PROTOCOLS:
        sel.errors.append(("PROTOCOL_UNKNOWN", "board_protocol %r" % sel.protocol))
    if sel.execution not in MODES:
        sel.errors.append(("EXECUTION_MODE_UNKNOWN", "execution %r" % sel.execution))
    return sel


def authority_protected(root: Path) -> tuple[bool, str]:
    """True only when the store directory is owned by ANOTHER uid and this
    process cannot write it: the minimum for a writer the worker cannot
    replace. In the current workspace every process shares one UID, so this
    is (False, reason)."""
    d = Path(root) / STORE_DIR
    try:
        st = d.stat()
    except OSError:
        return False, "%s does not exist" % STORE_DIR
    if st.st_uid == os.getuid():
        return False, "%s is owned by the calling uid %d (worker-writable)" % (STORE_DIR, os.getuid())
    if os.access(d, os.W_OK):
        return False, "%s is writable by the calling process" % STORE_DIR
    return True, "%s owned by uid %d, not writable by uid %d" % (STORE_DIR, st.st_uid, os.getuid())


def execution_gate(root: Path, sel: Selection | None = None) -> list[tuple[str, str]]:
    """[] when outcome-board execution may run on this root; typed refusals otherwise."""
    sel = sel or select_protocol(root)
    if sel.errors:
        return list(sel.errors)
    if not sel.outcome:
        return [("PROTOCOL_NOT_OUTCOME", "protocol %s" % sel.protocol)]
    mixed = mixed_state(root, sel)
    if mixed:
        return mixed
    if sel.execution == DISABLED:
        return [("OUTCOME_EXECUTION_DISABLED", "outcome_board.execution=%s (%s)" % (sel.execution, sel.source))]
    if sel.execution == QUALIFICATION:
        if sel.governed or sel.declaration != "RUN_DECLARATION_MISSING":
            return [("OUTCOME_QUALIFICATION_REFUSED", "governed=%s declaration=%s" % (sel.governed, sel.declaration))]
        return []
    ok, why = authority_protected(root)
    if not ok:
        return [("AUTHORITY_UNPROTECTED", why)]
    return []


def serial_records(root: Path) -> list[str]:
    """Serial-loop execution records present on this root."""
    out: list[str] = []
    issued = _read_json(Path(root) / LOOP_ISSUED)
    if isinstance(issued, dict) and str(issued.get("idempotency_key") or "").startswith("k4:"):
        out.append(str(LOOP_ISSUED))
    mints = _read_json(Path(root) / MINT_RECEIPTS)
    if isinstance(mints, dict):
        for m in mints.get("mints") or []:
            for row in (m or {}).get("created") or []:
                if str((row or {}).get("idempotency_key") or "").startswith("k4:"):
                    out.append(str(MINT_RECEIPTS))
                    return out
    return out


def mixed_state(root: Path, sel: Selection | None = None) -> list[tuple[str, str]]:
    sel = sel or select_protocol(root)
    store = (Path(root) / STORE_FILE).exists()
    if sel.outcome:
        serial = serial_records(root)
        if serial:
            return [("PROTOCOL_MIXED", "outcome-board run carries serial-loop records %s" % ", ".join(serial))]
        return []
    if store:
        return [("PROTOCOL_MIXED", "serial-loop run carries an outcome-board store %s" % STORE_FILE)]
    return []


def describe(issues: list[tuple[str, str]]) -> str:
    return "\n".join("%s: %s\n  remedy: %s" % (c, d, REMEDY.get(c, "")) for c, d in issues)
