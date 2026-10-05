"""Which board protocol a run uses, and whether its execution may run.

The outcome board (stages/130-ai-autonomous-migration/OUTCOME-BOARD-CONTRACT.md)
applies to NEW runs only. A run selects it ONCE, at creation, and the selection
has one source of truth per run shape:

  governed run (run control declared in the destination's initial commit)
      REQUEST   ``board_protocol`` in the factory-stamped ``run-budget.json`` of
                the initial commit (the app-migration template's boardProtocol
                parameter; default serial-loop/v1). Immutable: it is read from
                the initial commit, never from the working tree.
      SELECTION the platform's read-only contract (``board_protocol`` and
                ``outcome_board.execution``), written by the migration-run
                provisioner from that same scaffolding commit.
      The two must agree. A run that requested nothing and whose contract
      selects nothing keeps serial-loop/v1: every run created before the
      request existed (v12-v17) is unchanged.
  legacy / local run (no run control)
      ``run-defaults.json`` ``configuration.board_protocol``, bound by the
      destination's initial commit through run_declaration when a factory
      declaration exists, and ``.hermes/pins.json``
      ``pins.planner.outcome_board.execution``.

A governed run never falls back silently. Each disagreement is a typed refusal
and routes to the outcome-board paths (which refuse) rather than to the serial
loop:

  PROTOCOL_UNBOUND      outcome requested, the contract selects nothing (or
                        the contract is missing/malformed)
  PROTOCOL_DOWNGRADED   outcome requested, the contract selects the serial loop
  PROTOCOL_UNREQUESTED  the contract selects outcome (or enables its
                        execution) and the run never requested it
  PROTOCOL_MISMATCH     the run requested one outcome-board version and the
                        contract selects the other
  PROTOCOL_UNKNOWN      a value outside serial-loop/v1, outcome-board/v1 and
                        outcome-board/v2

Two outcome-board versions (same outcomes, different control model):

  outcome-board/v1   protected-authority control (architect F1): every
                     deciding record in a separate principal's store.
                     Kept for the runs that selected it; no new run
                     requests it.
  outcome-board/v2   native cooperative control (architect review
                     2026-09-27, user confirmation): Hermes Kanban owns the
                     lifecycle -- tasks, runs, dependencies, review and
                     rework -- and the domain checks guard the native
                     actions (planner/native_control.py). The worker's
                     local user can alter the board and its records; no
                     tamper resistance against worker code is claimed.

Execution modes:

  disabled       nothing executes under the outcome protocol (default).
  qualification  local, disposable fixtures only: honoured only when there
                 is no factory run declaration and no run control. A real run
                 can never enter it. Every check runs, against the cooperative
                 in-process store; ``claimed_control`` stays false.
  enabled        v2: requires the platform's explicit measurement-trust
                 decision (``outcome_board.measurement_trust``); the control
                 model is the protocol's own (native cooperative).
                 v1: requires the PROTECTED authority service
                 (planner/outcome_authority.py, architect F1): a separate
                 principal answering on the fixed socket, whose store the
                 caller cannot reach by path and whose code identity is the
                 image's pinned stamp; AND an explicit platform decision on
                 measurement trust (``outcome_board.measurement_trust``).
                 Otherwise AUTHORITY_UNPROTECTED / MEASUREMENT_TRUST_UNDECIDED.

Mixed state -- outcome records beside serial-loop records, or the reverse, or
a cooperative in-tree store beside the protected service -- refuses on every
path (A13).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SERIAL = "serial-loop/v1"
OUTCOME = "outcome-board/v1"
NATIVE = "outcome-board/v2"
OUTCOMES = (OUTCOME, NATIVE)
PROTOCOLS = (SERIAL, OUTCOME, NATIVE)

DISABLED = "disabled"
QUALIFICATION = "qualification"
ENABLED = "enabled"
MODES = (DISABLED, QUALIFICATION, ENABLED)

# The one measurement-trust value the platform may declare today: heavy
# receipts (build, tests, parity, MTA) stay worker-produced; the authority
# measures tree identity, scope and baseline ancestry itself. Declaring it is
# the architect's explicit acceptance of that limit (OUTCOME-BOARD-CONTRACT 8a).
MEASUREMENT_TRUSTS = ("cooperative-receipts",)

STORE_DIR = Path("verification") / "outcome-board"
STORE_FILE = STORE_DIR / "authority.sqlite3"
DEFAULTS = Path("run-defaults.json")
DECLARATION = Path("run-budget.json")
PINS = Path(".hermes") / "pins.json"
LOOP_ISSUED = Path("verification") / "loop" / "issued.json"
MINT_RECEIPTS = Path("evidence") / "receipts" / "k4" / "mints.json"

# The protected authority's fixed endpoint (devfile sidecar). Never taken from
# the environment or from a worker-writable file on a governed run.
AUTHORITY_SOCKET = Path("/run/outcome-authority/authority.sock")
AUTHORITY_SCHEMA = "rhoai3.outcome-authority/v1"
IMAGE_STAMP = Path("/opt/rhoai3/080.pins")
STAMP_KEY = "outcome_authority.code_sha256"

# Refusal codes, each with the one remedy it names.
REMEDY = {
    "PROTOCOL_UNKNOWN": "board_protocol must be serial-loop/v1, outcome-board/v1 or outcome-board/v2; recreate the run from the factory.",
    "PROTOCOL_MISMATCH": "The run requested one outcome-board version and the platform record selects the other. A run never switches control model; reprovision the run control or recreate the run.",
    "PROTOCOL_UNBOUND": "The run requested an outcome board but the platform record does not select it (or the record is missing). A run never switches protocol; reprovision the run control from the scaffolding event or recreate the run.",
    "PROTOCOL_DOWNGRADED": "The run requested an outcome board and the platform record selects the serial loop. Nothing falls back; recreate the run or reprovision its run control.",
    "PROTOCOL_UNREQUESTED": "The platform record selects (or enables) the outcome board for a run that never requested it. Nothing runs; correct the run control.",
    "PROTOCOL_MIXED": "Outcome-board and serial-loop records coexist. Neither reader may act; abandon or restore the run explicitly.",
    "PROTOCOL_NOT_OUTCOME": "This path belongs to the outcome-board protocol and this run uses the serial loop.",
    "OUTCOME_EXECUTION_DISABLED": "Outcome-board execution is disabled (the default). Nothing is published or executed.",
    "OUTCOME_QUALIFICATION_REFUSED": "qualification mode is honoured only on a disposable fixture with no factory run declaration and no run control.",
    "AUTHORITY_UNPROTECTED": "enabled execution needs the protected authority service: another principal on the fixed socket, a store the caller cannot reach, and the image-pinned code identity (F1).",
    "MEASUREMENT_TRUST_UNDECIDED": "enabled execution needs the platform's explicit measurement-trust decision (outcome_board.measurement_trust) in the run control.",
    "EXECUTION_MODE_UNKNOWN": "outcome_board.execution must be disabled, qualification or enabled.",
}

SELECTION_REFUSALS = ("PROTOCOL_UNKNOWN", "PROTOCOL_UNBOUND", "PROTOCOL_DOWNGRADED", "PROTOCOL_UNREQUESTED",
                      "PROTOCOL_MISMATCH", "EXECUTION_MODE_UNKNOWN")


@dataclass
class Selection:
    protocol: str
    execution: str
    source: str
    governed: bool
    declaration: str
    errors: list[tuple[str, str]] = field(default_factory=list)
    requested: str | None = None          # the run's own request (governed: the initial commit)
    selected: str | None = None           # what the platform record selects (governed)
    measurement_trust: str = ""
    authority_socket: str = ""            # qualification fixtures only; enabled uses AUTHORITY_SOCKET

    @property
    def outcome(self) -> bool:
        """Either outcome-board version: outcomes are tasks, not loop steps."""
        return self.protocol in OUTCOMES

    @property
    def native(self) -> bool:
        """outcome-board/v2: native cooperative control (no authority service)."""
        return self.protocol == NATIVE

    def as_dict(self) -> dict[str, Any]:
        return {"protocol": self.protocol, "execution": self.execution, "source": self.source,
                "governed": self.governed, "declaration": self.declaration, "requested": self.requested,
                "selected": self.selected, "measurement_trust": self.measurement_trust,
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


def _governed(root: Path) -> Selection:
    """The governed selection: the run's request (initial commit) against the
    platform's record. One rule, used by every reader (K2, K4, reconciler,
    Stage 050 hook producer, preflight)."""
    from planner import run_control
    decl = run_control.declared(root) or {}
    has_request = bool(decl.get("board_protocol_requested"))
    raw = decl.get("board_protocol") if has_request else None
    requested = raw if isinstance(raw, str) else (None if raw is None else repr(raw))
    doc, gaps = run_control.contract(root)
    board = doc.get("outcome_board") if isinstance(doc.get("outcome_board"), dict) else {}
    selected = doc.get("board_protocol") if "board_protocol" in doc else None
    execution = str(board.get("execution") or DISABLED)
    trust = str(board.get("measurement_trust") or "")
    wants_outcome = requested in OUTCOMES
    sel = Selection(SERIAL, execution, "run-control", True, "governed", requested=requested,
                    selected=selected if isinstance(selected, str) or selected is None else repr(selected),
                    measurement_trust=trust)
    if gaps:
        # a missing or malformed platform record: the serial gates refuse it on
        # their own (run_gaps); an outcome request must not reach them
        sel.protocol = requested if wants_outcome else SERIAL
        sel.errors.append(("PROTOCOL_UNBOUND", gaps[0]))
        return sel
    if has_request and requested not in PROTOCOLS:
        sel.protocol = OUTCOME
        sel.errors.append(("PROTOCOL_UNKNOWN", "the initial commit's %s requests board_protocol %s" % (DECLARATION, requested)))
        return sel
    if selected is not None and selected not in PROTOCOLS:
        sel.protocol = OUTCOME
        sel.errors.append(("PROTOCOL_UNKNOWN", "the run control selects board_protocol %r" % (selected,)))
        return sel
    if wants_outcome:
        sel.protocol = str(requested)
        if selected is None:
            sel.errors.append(("PROTOCOL_UNBOUND", "the run requested %s in its initial commit and the run control "
                                                   "selects no board protocol" % requested))
        elif selected == SERIAL:
            sel.errors.append(("PROTOCOL_DOWNGRADED", "the run requested %s and the run control selects %s" % (requested, SERIAL)))
        elif selected != requested:
            sel.errors.append(("PROTOCOL_MISMATCH", "the run requested %s and the run control selects %s" % (requested, selected)))
        return sel
    # requested serial, or requested nothing (a run created before the request existed)
    if selected in OUTCOMES:
        sel.protocol = str(selected)
        sel.errors.append(("PROTOCOL_UNREQUESTED", "the run control selects %s and the run requested %s"
                                                   % (selected, requested or "nothing")))
        return sel
    if board and execution != DISABLED:
        sel.protocol = OUTCOME
        sel.errors.append(("PROTOCOL_UNREQUESTED", "the run control sets outcome_board.execution=%s for a %s run"
                                                   % (execution, SERIAL)))
        return sel
    try:
        conf = (_read_json(root / DEFAULTS) or {}).get("configuration") or {}
    except AttributeError:
        conf = {}
    if isinstance(conf, dict) and conf.get("board_protocol") not in (None, SERIAL):
        # the shared golden defaults may not select a protocol behind a governed run
        sel.protocol = OUTCOME
        sel.errors.append(("PROTOCOL_UNREQUESTED", "%s names board_protocol %r; a governed run's protocol is its "
                                                   "request and the run control" % (DEFAULTS, conf.get("board_protocol"))))
    return sel


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
        sel = _governed(root)
    else:
        code = _declaration_code(root)
        defaults = _read_json(root / DEFAULTS)
        conf = defaults.get("configuration") if isinstance(defaults, dict) else None
        protocol = str((conf or {}).get("board_protocol") or SERIAL) if isinstance(conf, dict) else SERIAL
        pins = _read_json(root / PINS)
        planner = (((pins or {}).get("pins") or {}).get("planner") or {}) if isinstance(pins, dict) else {}
        board = planner.get("outcome_board") if isinstance(planner, dict) and isinstance(planner.get("outcome_board"), dict) else {}
        execution = str(board.get("execution") or DISABLED)
        sel = Selection(protocol, execution, "run-defaults+pins", False, code,
                        measurement_trust=str(board.get("measurement_trust") or ""),
                        authority_socket=str(board.get("authority_socket") or ""))
        if code not in ("RUN_DECLARATION_MISSING", "OK"):
            sel.errors.append(("PROTOCOL_UNBOUND", "run declaration %s" % code))
        if sel.protocol not in PROTOCOLS:
            sel.errors.append(("PROTOCOL_UNKNOWN", "board_protocol %r" % sel.protocol))
    if sel.execution not in MODES:
        sel.errors.append(("EXECUTION_MODE_UNKNOWN", "execution %r" % sel.execution))
    return sel


# ---------------------------------------------------------------------------
# the protected authority (architect F1)
# ---------------------------------------------------------------------------

def authority_endpoint(sel: Selection) -> str:
    """Where the authority for this selection lives: '' = in-process
    (cooperative; qualification fixtures), else a unix socket path. Enabled
    execution always uses the fixed AUTHORITY_SOCKET; a qualification fixture
    may name a local test socket in its pins."""
    if sel.native:
        return ""   # native cooperative control has no authority service
    if sel.execution == ENABLED:
        return str(AUTHORITY_SOCKET)
    if sel.execution == QUALIFICATION and not sel.governed and sel.authority_socket:
        return sel.authority_socket
    return ""


def image_stamp(stamp: Path | None = None) -> str:
    try:
        lines = Path(stamp or IMAGE_STAMP).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return next((l.split("=", 1)[1].strip() for l in lines if l.startswith(STAMP_KEY + "=")), "")


def _unreachable(path: str) -> str:
    """'' when this process can neither stat nor open ``path``; else why not."""
    if not path or not os.path.isabs(path):
        return "the service names no absolute store path"
    try:
        os.stat(path)
    except (FileNotFoundError, PermissionError, NotADirectoryError):
        return ""
    except OSError as exc:
        return "stat(%s) answered %s" % (path, type(exc).__name__)
    return "%s is reachable from this process" % path


def protection_facts(hello: dict[str, Any], root: Path, *, uid: int, stamp: str, pinned: str) -> tuple[bool, str]:
    """The decision behind authority_protected, over facts already gathered."""
    if hello.get("schema") != AUTHORITY_SCHEMA:
        return False, "the socket answered %r, not %s" % (hello.get("schema"), AUTHORITY_SCHEMA)
    if os.path.realpath(str(hello.get("root") or "")) != os.path.realpath(str(root)):
        return False, "the service serves %r, not %s" % (hello.get("root"), root)
    if int(hello.get("uid", -1)) == uid:
        return False, "the service runs as the calling uid %d" % uid
    for key in ("store_dir", "store_path"):
        why = _unreachable(str(hello.get(key) or ""))
        if why:
            return False, "store not protected: %s" % why
    if (Path(root) / STORE_FILE).exists():
        return False, "a cooperative in-tree store %s shadows the service" % STORE_FILE
    code = str(hello.get("code_sha256") or "")
    if not stamp:
        return False, "the image stamp %s names no %s" % (IMAGE_STAMP, STAMP_KEY)
    if code != stamp:
        return False, "the service code %s is not the image-pinned %s" % (code[:12], stamp[:12])
    if pinned and pinned != code:
        return False, "the harness pins authority code %s, the service runs %s" % (pinned[:12], code[:12])
    return True, "service uid %s, store %s unreachable, code %s" % (hello.get("uid"), hello.get("store_dir"), code[:12])


def authority_protected(root: Path, sel: Selection | None = None, *, socket_path: str = "",
                        stamp: Path | None = None) -> tuple[bool, str]:
    """True only when the authority for this root is the protected service:
    it answers on the socket with its identity, runs as ANOTHER uid, reports
    a store path this process cannot stat or open, no cooperative store sits in
    the tree, and its code identity is the image's pinned stamp (and the
    harness pin when one is present). Peer credentials are never consulted:
    they are forgeable from a user namespace. Inside the service process
    itself the answer is the service's own startup check."""
    from planner import outcome_store
    if outcome_store.service_binding() is not None:
        return True, "this process is the authority service"
    path = socket_path or str(AUTHORITY_SOCKET)
    try:
        from planner.outcome_authority import AuthorityError, hello
        info = hello(path)
    except Exception as exc:  # AuthorityError, OSError, ImportError: nothing protected answers
        return False, "no authority service answers on %s (%s)" % (path, exc)
    pins = _read_json(Path(root) / PINS) or {}
    pinned = str((((pins.get("pins") or {}) if isinstance(pins, dict) else {}).get("outcome_authority") or {}).get("code_sha256") or "")
    return protection_facts(info, Path(root), uid=os.getuid(), stamp=image_stamp(stamp), pinned=pinned)


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
    if not sel.native:
        ok, why = authority_protected(root, sel)
        if not ok:
            return [("AUTHORITY_UNPROTECTED", why)]
    if sel.measurement_trust not in MEASUREMENT_TRUSTS:
        return [("MEASUREMENT_TRUST_UNDECIDED", "outcome_board.measurement_trust is %r; one of %s must be declared"
                 % (sel.measurement_trust, ", ".join(MEASUREMENT_TRUSTS)))]
    return []


def launch_gaps(root: Path) -> tuple[Selection, list[tuple[str, str]]]:
    """What a launch (autostart, run-preflight) must refuse on. A serial run
    passes unless it carries outcome records; an outcome-board run passes only
    when its execution gate is open. Nothing here ever launches the serial loop
    for a run that requested the outcome board."""
    sel = select_protocol(root)
    if sel.errors:
        return sel, list(sel.errors)
    if not sel.outcome:
        return sel, mixed_state(root, sel)
    return sel, execution_gate(root, sel)


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
        if store and sel.native:
            return [("PROTOCOL_MIXED", "a native-control (%s) run carries an outcome-board/v1 authority store %s" % (NATIVE, STORE_FILE))]
        if store and authority_endpoint(sel):
            return [("PROTOCOL_MIXED", "a cooperative in-tree store %s sits beside the authority service" % STORE_FILE)]
        return []
    if store:
        return [("PROTOCOL_MIXED", "serial-loop run carries an outcome-board store %s" % STORE_FILE)]
    return []


def store_present(root: Path, sel: Selection | None = None) -> bool:
    """Has anything been published under the outcome protocol on this root?
    In-process: the in-tree store exists. Service: the service says so. An
    unreachable service answers True so that callers fail closed on it rather
    than falling back to the serial road."""
    sel = sel or select_protocol(root)
    if sel.native:
        # native control keeps no store; whether a TASK is a published node is
        # read from the board by native_control (the hooks ask per task)
        return False
    ep = authority_endpoint(sel)
    if not ep:
        return (Path(root) / STORE_FILE).exists()
    try:
        from planner.outcome_authority import call
        return bool(call(ep, "status", {}).get("published"))
    except Exception:
        return True


def describe(issues: list[tuple[str, str]]) -> str:
    return "\n".join("%s: %s\n  remedy: %s" % (c, d, REMEDY.get(c, "")) for c, d in issues)


def main(argv: list[str] | None = None) -> int:
    """python3 -m planner.outcome_protocol --root PATH [launch-check]"""
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="outcome_protocol")
    ap.add_argument("--root", required=True)
    ap.add_argument("action", nargs="?", default="launch-check", choices=("launch-check", "show"))
    ns = ap.parse_args(argv)
    sel, gaps = launch_gaps(Path(ns.root))
    print(json.dumps(dict(sel.as_dict(), launch_gaps=[list(g) for g in gaps]), sort_keys=True))
    if ns.action == "launch-check" and gaps:
        print("REFUSE %s" % describe(gaps).splitlines()[0], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
