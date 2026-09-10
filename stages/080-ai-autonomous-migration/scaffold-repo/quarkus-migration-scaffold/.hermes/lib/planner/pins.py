"""Read `.hermes/pins.json` for planner-relevant pins, the activation gate,
and the pilot seal; enumerate tool-pin gaps against producer receipts.

A pin is either pinned (``version`` present and ``status`` absent or
``pinned``) or unpinned (``status: unpinned``). The planner never chooses
a version; an unpinned mandatory tool is a fail-closed boundary recorded
by the producer, the ledger, admission, and K4.

Activation (SAD §12) has three values:

- ``not-activated``  M2 unavailable; admission never ADMITS; K4 emits nothing.
- ``pilot``          one Operator-authorized run: ``pins.planner.pilot`` names
                     ``run_id``, ``authorized_by`` and the exact
                     ``evidence_bundle_sha256`` it covers. Admission ADMITS
                     only that bundle; K4 re-checks independently.
- ``activated``      normal operation after the §12 gate.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from planner.canonical import is_sha256, load_json
from planner.paths import PINS

ACTIVATED = "activated"
PILOT = "pilot"
NOT_ACTIVATED = "not-activated"

# producer name → pins.json key. Mandatory producers must be pinned for any
# admission (no optional producers in v3).
MANDATORY_TOOL_PINS = {"jdk-model": "structure_extractor", "mta": "mta_cli"}
OPTIONAL_TOOL_PINS: dict[str, str] = {}
USED_STATUSES = ("ok", "partial")


def load_pins(root: Path) -> dict[str, Any]:
    path = Path(root) / PINS
    doc = load_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("pins"), dict):
        raise ValueError("%s: expected {pins: {...}}" % path)
    return doc["pins"]


def pin(pins: dict[str, Any], key: str) -> dict[str, Any]:
    raw = pins.get(key)
    return raw if isinstance(raw, dict) else {}


def pin_status(pins: dict[str, Any], key: str) -> str:
    """'pinned' | 'unpinned' | 'missing'."""
    p = pin(pins, key)
    if not p:
        return "missing"
    status = str(p.get("status") or "").strip().lower()
    if status == "unpinned":
        return "unpinned"
    if p.get("version"):
        return "pinned"
    return "unpinned"


def pinned_version(pins: dict[str, Any], key: str) -> str | None:
    if pin_status(pins, key) != "pinned":
        return None
    return str(pin(pins, key).get("version"))


def planner_activation(pins: dict[str, Any]) -> str:
    """Activation gate (SAD §12). Absent block means not activated."""
    p = pin(pins, "planner")
    value = str(p.get("activation") or NOT_ACTIVATED).strip().lower()
    if value == ACTIVATED:
        return ACTIVATED
    if value == PILOT:
        return PILOT
    return NOT_ACTIVATED


def pilot_seal(pins: dict[str, Any]) -> dict[str, Any]:
    seal = pin(pins, "planner").get("pilot")
    return seal if isinstance(seal, dict) else {}


def pilot_authorization(pins: dict[str, Any]) -> dict[str, Any]:
    """Who authorized this pilot run and how it was recorded."""
    auth = pilot_seal(pins).get("authorization")
    return auth if isinstance(auth, dict) else {}


def pilot_bind_gaps(pins: dict[str, Any]) -> list[str]:
    """Why the pilot seal may NOT be bound to the bundle on disk mechanically.

    Empty list = the platform recorded a named authorization for this run
    (dest-init, from the DevWorkspace its named creator started) and the seal
    is not bound yet, so the binding is a derivation, not a decision: the only
    value written is the canonical digest of the bundle that exists.

    A seal that is already bound, one with no named authorizer, and one whose
    authorization did not come from the platform are all refused here; so is
    an `activated` or `not-activated` planner, which needs no binding.
    """
    if planner_activation(pins) != PILOT:
        return ["planner activation is %r, not pilot" % planner_activation(pins)]
    seal = pilot_seal(pins)
    gaps: list[str] = []
    if not str(seal.get("run_id") or "").strip():
        gaps.append("pins.planner.pilot.run_id missing")
    if not str(seal.get("authorized_by") or "").strip():
        gaps.append("pins.planner.pilot.authorized_by missing")
    auth = pilot_authorization(pins)
    if str(auth.get("source") or "") != "devworkspace":
        gaps.append("pins.planner.pilot.authorization.source is %r, not 'devworkspace' (only the platform may record an authorization the harness binds)" % auth.get("source"))
    if not str(auth.get("creator") or "").strip():
        gaps.append("pins.planner.pilot.authorization.creator missing (the workspace creator)")
    if str(seal.get("evidence_bundle_sha256") or "").strip():
        gaps.append("pins.planner.pilot.evidence_bundle_sha256 is already bound; a bound seal is never rewritten")
    return gaps


def bundle_fitness_gaps(bundle: dict[str, Any]) -> list[str]:
    """Why this evidence bundle is not fit to be authorized.

    The facts a human was nominally checking before signing a pilot seal, made
    mechanical so they are re-checked on every run: every producer the bundle
    names ran ok, the MTA canary fired, entry points exist, obligations exist.
    Admission re-checks all of this independently; binding an unfit bundle is
    refused here so an authorization never covers one.
    """
    gaps: list[str] = []
    producers = bundle.get("producers") if isinstance(bundle.get("producers"), dict) else {}
    if not producers:
        gaps.append("bundle names no producers")
    for name, rec in sorted(producers.items()):
        status = str((rec or {}).get("status") or "missing") if isinstance(rec, dict) else str(rec)
        if status not in USED_STATUSES:
            gaps.append("producer %s status is %r" % (name, status))
    mta = producers.get("mta") if isinstance(producers.get("mta"), dict) else {}
    if not (mta.get("canary") or {}).get("fired"):
        gaps.append("the MTA canary did not fire; the effective ruleset is unproven")
    if not (bundle.get("entry_points") or []):
        gaps.append("bundle has no entry point")
    if not (bundle.get("obligations") or []):
        gaps.append("bundle has no obligation; an empty plan is not a silent success")
    return gaps


def activation_gaps(pins: dict[str, Any], bundle_digest: str) -> list[str]:
    """Why this bundle may not be admitted under the current activation.

    Empty list = admissible (activated, or a pilot seal bound to exactly
    this evidence bundle). Everything else is a fail-closed reason.
    """
    mode = planner_activation(pins)
    if mode == ACTIVATED:
        return []
    if mode == PILOT:
        seal = pilot_seal(pins)
        gaps: list[str] = []
        if not str(seal.get("run_id") or "").strip():
            gaps.append("PLANNER_PILOT_SEAL: pins.planner.pilot.run_id missing")
        if not str(seal.get("authorized_by") or "").strip():
            gaps.append("PLANNER_PILOT_SEAL: pins.planner.pilot.authorized_by missing (named Operator GO)")
        sealed = str(seal.get("evidence_bundle_sha256") or "")
        if not is_sha256(sealed):
            gaps.append("PLANNER_PILOT_SEAL: pins.planner.pilot.evidence_bundle_sha256 is not a sha256")
        elif sealed != bundle_digest:
            gaps.append("PLANNER_PILOT_SEAL: pilot seal covers bundle %s, this bundle is %s" % (sealed[:16], str(bundle_digest)[:16]))
        return gaps
    return ["PLANNER_NOT_ACTIVATED: pins.planner.activation is %r (SOLUTION-ARCHITECTURE §12)" % mode]


def activation_record(pins: dict[str, Any]) -> dict[str, Any]:
    mode = planner_activation(pins)
    seal = pilot_seal(pins) if mode == PILOT else {}
    return {
        "mode": mode,
        "pilot_run_id": str(seal.get("run_id") or "") if mode == PILOT else "",
        "authorized_by": str(seal.get("authorized_by") or "") if mode == PILOT else "",
    }


def pin_gaps(pins: dict[str, Any], producers: dict[str, Any]) -> list[dict[str, str]]:
    """Tool-pin gaps between `.hermes/pins.json` and the producer receipts.

    Rows are ledger-entry shaped {class, subject, detail}. Classes:
    TOOL_UNPINNED (pins.json has no version), TOOL_PIN_MISMATCH (receipt
    disagrees with the pin: pin_status, version, artifact digest).
    """
    gaps: list[dict[str, str]] = []

    def gap(cls: str, subject: str, detail: str) -> None:
        gaps.append({"class": cls, "subject": subject, "detail": detail})

    for producer, key, mandatory in sorted(
        [(p, k, True) for p, k in MANDATORY_TOOL_PINS.items()] + [(p, k, False) for p, k in OPTIONAL_TOOL_PINS.items()]
    ):
        rec = producers.get(producer) if isinstance(producers.get(producer), dict) else {}
        status = str(rec.get("status") or "missing")
        tool = rec.get("tool") if isinstance(rec.get("tool"), dict) else {}
        if not mandatory and status not in USED_STATUSES:
            continue  # optional output not used; the ledger notes it
        ps = pin_status(pins, key)
        if ps != "pinned":
            gap("TOOL_UNPINNED", key, "%s producer requires pins.%s with a version; it is %s (do not invent one; name it in an ADR)" % (producer, key, ps))
            continue
        want_version = pinned_version(pins, key) or ""
        got_status = str(tool.get("pin_status") or "")
        if got_status != "pinned":
            gap("TOOL_PIN_MISMATCH", key, "%s receipt records pin_status %r; pins.%s is pinned at %s" % (producer, got_status, key, want_version))
        got_version = str(tool.get("version") or "")
        if got_version != want_version:
            gap("TOOL_PIN_MISMATCH", key, "%s receipt ran version %r; pins.%s is %r" % (producer, got_version, key, want_version))
        want_sha = str(pin(pins, key).get("artifact_sha256") or "")
        got_sha = str(tool.get("artifact_sha256") or "")
        if want_sha and got_sha != want_sha:
            gap("TOOL_PIN_MISMATCH", key, "%s receipt artifact %s != pinned artifact %s" % (producer, got_sha[:16] or "(none)", want_sha[:16]))
    return gaps


def digestable_pins(pins: dict[str, Any]) -> dict[str, Any]:
    """Pins that the admission receipt seals (tool/product/runtime pins)."""
    keys = (
        "hermes_agent",
        "quarkus_platform",
        "compiler_plugin",
        "surefire_plugin",
        "assertj_core",
        "mapstruct",
        "structure_extractor",
        "mta_cli",
        "planner",
    )
    out: dict[str, Any] = {}
    for key in keys:
        if key in pins:
            out[key] = pins[key]
    return out
