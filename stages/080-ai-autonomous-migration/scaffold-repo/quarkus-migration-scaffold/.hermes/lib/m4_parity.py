"""Measure M4 parity across recorded security modes; coverage gaps stay explicit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FLOOR = "check-mode-parity"
ACCEPTING = {"PROVISIONAL_ACCEPT", "SCOPED_ACCEPT", "ACCEPT"}


def runner_is_scoped(run) -> bool:
    """Whether this runner record is a card-scoped comparison, not a full mode.

    An empty ``scenario_filter`` is not a full comparison: a read-oracle-only
    run names no scenarios and still re-runs only the requested oracles."""
    if not isinstance(run, dict):
        return False
    if list(run.get("scenario_filter") or []):
        return True
    oracles = run.get("read_oracles") if isinstance(run.get("read_oracles"), dict) else {}
    requested = [str(e) for e in (oracles.get("requested") or []) if str(e)]
    rerun = [str(e) for e in (oracles.get("rerun") or []) if str(e)]
    if (requested or rerun) and not oracles.get("ran"):
        return True
    scenarios = run.get("scenarios") if isinstance(run.get("scenarios"), dict) else {}
    selected = int(scenarios.get("selected") or 0)
    declared = int(scenarios.get("declared") or 0)
    if requested and selected == 0:
        return True
    if declared and selected < declared:
        return True
    return False


def runner_is_full_mode(run) -> bool:
    """A complete unscoped compose of this mode, written by this runner."""
    if not isinstance(run, dict):
        return False
    if runner_is_scoped(run):
        return False
    return bool((run.get("receipt") or {}).get("composed_by_this_run"))


def runner_provenance_error(run, receipt) -> str:
    """Why this runner record is not the measurement of this receipt.

    A scoped accepted baseline remains a scoped baseline: a full-mode runner
    of artifact A cannot prove a candidate-B receipt (v10: snapshot_parity
    retained the older full-mode runner beside a newer scoped receipt, and
    measure() returned rc=0). Empty string means the pair is coherent, scoped
    or full; callers that need a complete unscoped compose still ask that
    separately.
    """
    if not isinstance(run, dict):
        return "no runner record"
    if not isinstance(receipt, dict):
        return "no receipt"
    run_mode = str(run.get("security_mode") or "disabled")
    rec_mode = str(receipt.get("security_mode") or "disabled")
    if run_mode != rec_mode:
        return "runner security mode disagrees with the receipt"
    rec_sha = str(receipt.get("receipt_sha256") or "")
    run_sha = str(run.get("receipt_sha256") or "")
    if rec_sha and run_sha and rec_sha != run_sha:
        return "runner receipt digest does not match the composed receipt"
    rec_bind = receipt.get("binding") if isinstance(receipt.get("binding"), dict) else {}
    run_bind = run.get("binding") if isinstance(run.get("binding"), dict) else {}
    rec_kind = str(rec_bind.get("mode") or "sealed")
    rec_cand = str(rec_bind.get("candidate_sha256") or "")
    run_cand = str(run_bind.get("candidate_sha256") or "")
    rec_card = str(rec_bind.get("card") or "")
    run_card = str(run_bind.get("card") or "")
    rec_art = ""
    if isinstance(receipt.get("artifact"), dict):
        rec_art = str(receipt["artifact"].get("sha256") or "")
    run_art = ""
    if isinstance(run.get("artifact"), dict):
        run_art = str(run["artifact"].get("sha256") or "")
    full = runner_is_full_mode(run)
    scoped = runner_is_scoped(run)
    if rec_kind == "candidate":
        if rec_cand and run_cand and rec_cand != run_cand:
            return "runner records a different candidate than the receipt"
        if rec_card and run_card and rec_card != run_card:
            return "runner records a different card than the receipt"
        if full and rec_cand and run_cand != rec_cand:
            return "candidate receipt is paired with a full-mode runner of another measurement"
        return ""
    if scoped:
        return "scoped runner is not a measurement of a sealed receipt"
    if rec_art and run_art and rec_art != run_art:
        return "runner artifact does not match the receipt"
    return ""


def measure(root: Path) -> dict:
    parity = root / "verification/parity"
    modes = ["disabled"]
    captures = root / "verification/source-oracles/scenarios-enabled"
    if (parity / "receipt-enabled.json").exists() or any(
        not p.name.startswith("_") for p in captures.glob("*.json")
    ):
        modes.append("enabled")
    rows, errors, bindings, artifacts = [], [], {}, {}
    for mode in modes:
        suffix = "" if mode == "disabled" else "-enabled"
        receipt = parity / ("receipt%s.json" % suffix)
        try:
            raw = receipt.read_bytes()
            doc = json.loads(raw)
            if not isinstance(doc, dict) or doc.get("schema") != "rhoai3.parity-receipt/v1":
                raise ValueError("not a parity receipt")
            if doc.get("security_mode", "disabled") != mode:
                raise ValueError("receipt security mode disagrees with its path")
            if doc.get("verdict") not in ("PASS", "FAIL", "INCONCLUSIVE"):
                raise ValueError("missing or unknown verdict")
            bindings[mode] = hashlib.sha256(raw).hexdigest()
            rows.append({"mode": mode, "verdict": doc["verdict"], "path": receipt.relative_to(root).as_posix()})
        except (OSError, ValueError) as exc:
            errors.append("%s: %s" % (mode, exc))
            continue
        if "enabled" in modes:
            try:
                run = json.loads((parity / ("_run%s.json" % suffix)).read_text())
                if not isinstance(run, dict) or run.get("security_mode") != mode or not run.get("ok"):
                    raise ValueError("no successful runner record for this mode")
                if not runner_is_full_mode(run):
                    raise ValueError("runner did not compose a full-mode comparison")
                why = runner_provenance_error(run, doc)
                if why:
                    raise ValueError(why)
                artifact = (run.get("artifact") or {}).get("sha256")
                if not artifact:
                    raise ValueError("runner records no packaged artifact digest")
                artifacts[mode] = artifact
            except (OSError, ValueError) as exc:
                errors.append("%s: %s" % (mode, exc))
    if len(set(artifacts.values())) > 1:
        errors.append("security modes were measured on different packaged artifacts")
    failed = [r for r in rows if r["verdict"] == "FAIL"]
    return {"rc": 2 if errors else (1 if failed else 0), "rows": rows, "errors": errors,
            "receipt_sha256_by_mode": bindings}


def verdict_issues(doc: dict, root: Path) -> list[str]:
    result = measure(root)
    issues = []
    if "enabled" in result["receipt_sha256_by_mode"]:
        if doc.get("parity_receipt_sha256_by_mode") != result["receipt_sha256_by_mode"]:
            issues.append("M4_MODE_PARITY_BINDING verdict does not bind the current receipts of both security modes")
    accepting = str(doc.get("verdict", "")).upper().replace("-", "_") in ACCEPTING
    if result["rc"] and accepting:
        floor = next((r for r in doc.get("floors", []) if isinstance(r, dict) and r.get("name") == FLOOR), {})
        if (FLOOR not in doc.get("failed_floors", []) or floor.get("rc") != result["rc"]
                or floor.get("idle") is not False):
            issues.append("M4_MODE_PARITY %s rc=%s must be a failed floor, not a coverage gap" % (FLOOR, result["rc"]))
        issues.append("ACCEPT_WITH_PARITY_FAILURE " + json.dumps(result, sort_keys=True))
    return issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    result = measure(parser.parse_args().root)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(result["rc"])
