#!/usr/bin/env python3
"""AD-H §18 — assert phase-dispatch required_checks match the gate matrix.

Also --print <M3|M4|M5|factory> to emit the validator preflight checklist.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

# Canonical matrix (AD-H §18 / validation-release-gates.md)
EXPECTED: dict[str, list[str]] = {
    "M3": [
        "compile",
        "task_scoped_tests",
        # g2 when HARVEST — declared optional in dispatch via g2_if_harvest
        "g2_if_harvest",
    ],
    "M4": [
        "mvn_clean_verify",
        "unit_it_contract",
        "sonar",
        "boot_health",
        "g1_characterization",
        "g2_if_harvest",
    ],
    "M5": [
        "preflight",
        "regression_suite",
        "sonar",
        "mta_rescan",
        "g3_findings_delta",
        "acceptance_live",
        "g4_runtime_parity",
    ],
    "factory": [
        "compile",
        "unit_it_contract",
        "sonar",
        "security",
        "deploy_smoke",
        "must_not_contradict_m5_accept",
    ],
}


def load_dispatch(root: Path) -> dict:
    path = root / ".hermes" / "phase-dispatch.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Minimal fallback: only needed keys when PyYAML absent
    return _parse_required_checks_fallback(text)


def _parse_required_checks_fallback(text: str) -> dict:
    """Tiny YAML subset: phases.<Mn>.required_checks: list of - items."""
    phases: dict = {}
    cur_phase = None
    in_checks = False
    for raw in text.splitlines():
        ln = raw.split("#", 1)[0].rstrip()
        if not ln.strip():
            continue
        m_phase = None
        if ln.endswith(":") and not ln.startswith(" ") and not ln.startswith("\t"):
            # top-level key
            key = ln[:-1].strip()
            if key == "phases":
                cur_phase = None
                in_checks = False
            continue
        # "  M3:" under phases
        if ln.startswith("  ") and not ln.startswith("    ") and ln.strip().endswith(":"):
            name = ln.strip()[:-1]
            if name.startswith("M") or name == "factory":
                cur_phase = name
                phases.setdefault(cur_phase, {})
                in_checks = False
            continue
        if cur_phase and ln.strip() == "required_checks:":
            phases[cur_phase]["required_checks"] = []
            in_checks = True
            continue
        if cur_phase and in_checks and ln.strip().startswith("- "):
            phases[cur_phase]["required_checks"].append(ln.strip()[2:].strip())
            continue
        if cur_phase and in_checks and not ln.startswith("    ") and not ln.startswith("\t\t"):
            in_checks = False
    return {"phases": phases}


def main() -> int:
    ap = argparse.ArgumentParser(description="AD-H §18 phase gate matrix check")
    ap.add_argument("root", nargs="?", default=".", help="scaffold root")
    ap.add_argument("--print", dest="print_phase", metavar="PHASE", help="print checklist only")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    if args.print_phase:
        phase = args.print_phase.strip()
        checks = EXPECTED.get(phase)
        if not checks:
            print(f"FAIL: unknown phase {phase!r}; expected one of {sorted(EXPECTED)}", file=sys.stderr)
            return 1
        print(f"# AD-H §18 preflight checklist — {phase}")
        for c in checks:
            print(f"- [ ] {c}")
        print("- [ ] failure routing: INCONCLUSIVE → human queue (never ship)")
        print("- [ ] completion requires ACCEPT (not merely not-REFUSE)")
        if phase == "M4":
            print("- [ ] verdict token = PROVISIONAL_ACCEPT (not ACCEPT+footnote)")
            print("- [ ] g1_kill_ratio=pending_threshold (not PASS until pin)")
            print("- [ ] PROVISIONAL_ACCEPT must not ship")
        if phase == "M5":
            print("- [ ] verdict = ACCEPT (G-4); closes G-1 residue")
            print("- [ ] kill-ratio PASS (threshold pinned) or typed Operator waiver")
            print("- [ ] G-4 fail → reopen story; shared substrate → closure ∩ set")
        if phase == "factory":
            print("- [ ] must_not_contradict_m5_accept = M5 ACCEPT only (not provisional)")
        return 0

    try:
        data = load_dispatch(root)
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    phases = data.get("phases") or {}
    bad = 0
    for phase, expected in EXPECTED.items():
        if phase == "factory":
            # factory may live under phases.factory or top-level factory
            node = phases.get("factory") or data.get("factory") or {}
        else:
            node = phases.get(phase) or {}
        got = node.get("required_checks")
        if got is None:
            print(f"FAIL: phase {phase} missing required_checks (AD-H §18)", file=sys.stderr)
            bad = 1
            continue
        if not isinstance(got, list):
            print(f"FAIL: phase {phase} required_checks must be a list", file=sys.stderr)
            bad = 1
            continue
        got_set = {str(x) for x in got}
        missing = [c for c in expected if c not in got_set]
        if missing:
            print(
                f"FAIL: phase {phase} missing required_checks: {', '.join(missing)}",
                file=sys.stderr,
            )
            bad = 1
        else:
            print(f"OK: {phase} required_checks cover §18 matrix ({len(expected)} items)")

    if bad:
        print("Phase-matrix check FAILED.", file=sys.stderr)
        return 1
    print("OK: AD-H §18 phase-matrix present in phase-dispatch.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
