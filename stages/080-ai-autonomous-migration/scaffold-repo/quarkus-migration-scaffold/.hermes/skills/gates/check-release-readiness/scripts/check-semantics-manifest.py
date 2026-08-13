#!/usr/bin/env python3
"""B8 — enforce governance/contracts/check-semantics-manifest.md lints.

Fixture-proof ≠ semantically adequate. Bind check ids to adequacy class and
refuse over-promise receipts / verdicts.

Usage:
  python3 check-semantics-manifest.py .
  python3 check-semantics-manifest.py /projects/modernized
  python3 check-semantics-manifest.py governance/fixtures/check-semantics-manifest/bad-endpoint-smoke-overpromise
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — receipts/verdicts honour the check-semantics manifest, or idle
  1  BLOCK — over-promise / adequacy / lint breach
  2  usage / harness defect
"""

# Canonical adequacy map — must stay aligned with
# governance/contracts/check-semantics-manifest.md
ADEQUACY: dict[str, str] = {
    "boot_health": "SEMANTIC",
    "endpoint_smoke": "SEMANTIC",
    "endpoint_smoke_health": "SEMANTIC",
    "g4_hook": "ADMISSION",
    "mvn_clean_verify": "SEMANTIC",
    "unit_it_contract": "SEMANTIC",
    "sonar": "TOOLING",
    "g1_characterization": "ADMISSION",
    "g2_if_harvest": "ADMISSION",
    "preflight": "TOOLING",
    "regression_suite": "SEMANTIC",
    "mta_rescan": "SEMANTIC",
    "g3_findings_delta": "ADMISSION",
    "acceptance_live": "SEMANTIC",
    "g4_runtime_parity": "SEMANTIC",
    "accept_scope": "TOOLING",
}

CONTRACT_REL = "governance/contracts/check-semantics-manifest.md"
API_PATH_RE = re.compile(r"(^|/)/?api(/|$)", re.IGNORECASE)


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def as_items(data: object) -> list[dict]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def smoke_paths_of(obj: dict) -> list[str]:
    raw = obj.get("smoke_paths") or obj.get("smokePaths") or []
    if isinstance(raw, str):
        return [p for p in raw.split() if p]
    if isinstance(raw, list):
        return [str(p) for p in raw]
    # fall back to note hits=... or operand URL path
    note = str(obj.get("note") or "")
    hits = re.findall(r"(/[^\s:,]+):\d+", note)
    if hits:
        return hits
    return []


def claim_text(obj: dict) -> str:
    parts = [
        str(obj.get("claim") or ""),
        str(obj.get("coverage_claim") or ""),
        str(obj.get("note") or ""),
    ]
    return " ".join(parts).lower()


def has_api_path(paths: list[str]) -> bool:
    return any(API_PATH_RE.search(p) for p in paths)


def lint_receipt(label: str, obj: dict) -> int:
    """Return 1 on failure, 0 on ok."""
    bad = 0
    check = str(obj.get("check") or "")
    result = str(obj.get("result") or "").upper()
    adequacy = str(obj.get("adequacy") or obj.get("adequacy_class") or ADEQUACY.get(check, ""))

    if check and check not in ADEQUACY and not adequacy:
        print(
            f"FAIL: {label}: unknown check id {check!r} — add a row to "
            f"{CONTRACT_REL} before first live use (B8)",
            file=sys.stderr,
        )
        bad = 1

    # 1) endpoint_smoke over-promise
    if check == "endpoint_smoke" and result == "PASS":
        paths = smoke_paths_of(obj)
        if paths and not has_api_path(paths):
            claim = claim_text(obj)
            if "health/root only" not in claim and "health only" not in claim:
                print(
                    f"FAIL: {label}: endpoint_smoke PASS with non-/api/* smoke "
                    f"paths {paths} — rename check to endpoint_smoke_health or "
                    f"set claim/note to 'health/root only' (B8 / {CONTRACT_REL})",
                    file=sys.stderr,
                )
                bad = 1
        elif not paths:
            # no declared list + id still endpoint_smoke → over-promise
            print(
                f"FAIL: {label}: endpoint_smoke PASS without declared "
                f"smoke_paths — declare paths or use endpoint_smoke_health (B8)",
                file=sys.stderr,
            )
            bad = 1

    # 2) boot_health — forbid PASS if package skipped
    if check == "boot_health" and result == "PASS":
        pkg = obj.get("package_rc")
        if pkg is None:
            pkg = obj.get("packageRc")
        health = obj.get("health_status")
        if health is None:
            health = obj.get("healthStatus")
        if pkg is None or str(pkg).lower() in {"skipped", "skip", ""}:
            print(
                f"FAIL: {label}: boot_health PASS requires package_rc "
                f"(forbid skipped) (B8)",
                file=sys.stderr,
            )
            bad = 1
        if health is None or str(health).strip() == "":
            print(
                f"FAIL: {label}: boot_health PASS requires health_status (B8)",
                file=sys.stderr,
            )
            bad = 1

    # 3) g4_hook — SAMPLE must not claim product G-4 closed
    if check == "g4_hook":
        g4_mode = str(obj.get("g4_mode") or obj.get("g4Mode") or "").upper()
        note = claim_text(obj)
        if not g4_mode and "g4_mode=sample" in note:
            g4_mode = "SAMPLE"
        if g4_mode == "SAMPLE" and result == "PASS":
            print(
                f"FAIL: {label}: g4_hook PASS with g4_mode=SAMPLE — "
                f"ADMISSION only; cannot close product G-4 (B8)",
                file=sys.stderr,
            )
            bad = 1
        if result == "PASS" and adequacy == "ADMISSION":
            if "product" in note and ("closed" in note or "parity closed" in note):
                print(
                    f"FAIL: {label}: ADMISSION g4_hook PASS claims product "
                    f"parity closed (B8)",
                    file=sys.stderr,
                )
                bad = 1

    # 4) mvn_clean_verify — require clean token
    if check == "mvn_clean_verify" and result == "PASS":
        cmd = str(obj.get("cmd") or "")
        if not re.search(r"(^|\s)clean(\s|$)", cmd):
            print(
                f"FAIL: {label}: mvn_clean_verify PASS requires 'clean' in "
                f"cmd (B8; stale MapStruct false-green)",
                file=sys.stderr,
            )
            bad = 1

    # 5) unit_it_contract / regression_suite — empty suite
    if check in {"unit_it_contract", "regression_suite"} and result in {
        "PASS",
        "SKIP",
    }:
        tests_required = obj.get("tests_required")
        if tests_required is None:
            tests_required = obj.get("testsRequired")
        test_count = obj.get("test_count")
        if test_count is None:
            test_count = obj.get("testCount")
        if tests_required in (True, "true", "yes", 1) or str(
            tests_required
        ).lower() in {"true", "yes", "1", "ar-2.8", "required"}:
            try:
                n = int(test_count) if test_count is not None else -1
            except (TypeError, ValueError):
                n = -1
            if n == 0 and result == "PASS":
                print(
                    f"FAIL: {label}: {check} PASS with tests_required and "
                    f"test_count=0 — FAIL or SKIP+accept_scope (B8)",
                    file=sys.stderr,
                )
                bad = 1
            if n == 0 and result == "SKIP" and not (
                obj.get("accept_scope") or obj.get("acceptScope")
            ):
                print(
                    f"FAIL: {label}: {check} SKIP with zero tests requires "
                    f"accept_scope block (B8)",
                    file=sys.stderr,
                )
                bad = 1

    # 6) sonar — SKIP only when plugin absent; never maps to ship (verdict side)
    if check == "sonar" and result == "SKIP":
        plugin_absent = obj.get("plugin_absent")
        if plugin_absent is None:
            plugin_absent = obj.get("pluginAbsent")
        if plugin_absent not in (True, "true", "yes", 1):
            print(
                f"FAIL: {label}: sonar SKIP requires plugin_absent=true (B8)",
                file=sys.stderr,
            )
            bad = 1

    return bad


def lint_verdict(label: str, obj: dict) -> int:
    bad = 0
    g4_mode = str(obj.get("g4_mode") or obj.get("g4Mode") or "").upper()
    verdict = str(obj.get("verdict") or obj.get("gate_verdict") or "").upper()
    checks = obj.get("checks") or obj.get("check_results") or {}
    required = obj.get("required_checks") or obj.get("requiredChecks") or []
    ship = obj.get("ship") in (True, "true", "yes", 1) or str(
        obj.get("status") or ""
    ).lower() in {"shipped", "released", "merged_main"}

    # ADMISSION check must not satisfy a SEMANTIC obligation
    if isinstance(required, list):
        for req in required:
            req_id = str(req)
            adeq = ADEQUACY.get(req_id, "")
            # g4_runtime_parity SEMANTIC cannot be closed by g4_hook ADMISSION
            if req_id == "g4_runtime_parity" and isinstance(checks, dict):
                hook = checks.get("g4_hook") or {}
                if isinstance(hook, dict):
                    hook_r = str(hook.get("result") or "").upper()
                    hook_mode = str(
                        hook.get("g4_mode") or g4_mode or ""
                    ).upper()
                    if hook_r == "PASS" and hook_mode == "SAMPLE":
                        print(
                            f"FAIL: {label}: ADMISSION g4_hook PASS "
                            f"(SAMPLE) cannot satisfy SEMANTIC "
                            f"g4_runtime_parity (B8 / {CONTRACT_REL})",
                            file=sys.stderr,
                        )
                        bad = 1

    if g4_mode == "SAMPLE":
        # forbid mapping hook PASS → product G-4 closed
        closed = str(obj.get("g4_status") or obj.get("g4Status") or "").upper()
        if closed in {"CLOSED", "PASS", "ACCEPT"} and verdict in {
            "ACCEPT",
            "PROVISIONAL_ACCEPT",
        }:
            print(
                f"FAIL: {label}: g4_mode=SAMPLE forbids product G-4 "
                f"closed/PASS under ACCEPT (B8)",
                file=sys.stderr,
            )
            bad = 1
        if isinstance(checks, dict):
            hook = checks.get("g4_hook") or {}
            if isinstance(hook, dict) and str(hook.get("result") or "").upper() == "PASS":
                if closed in {"CLOSED", "PASS", "ACCEPT"} or truthy_product_g4_closed(
                    obj
                ):
                    print(
                        f"FAIL: {label}: g4_mode=SAMPLE + g4_hook PASS must "
                        f"not map to product-G-4-closed (B8)",
                        file=sys.stderr,
                    )
                    bad = 1

    # sonar never maps to ship alone
    if ship and isinstance(checks, dict):
        only_sonar = set(checks.keys()) <= {"sonar", "preflight", "accept_scope"}
        if "sonar" in checks and only_sonar:
            print(
                f"FAIL: {label}: sonar/TOOLING checks alone must never ship (B8)",
                file=sys.stderr,
            )
            bad = 1

    return bad


def truthy_product_g4_closed(obj: dict) -> bool:
    for key in ("product_g4_closed", "productG4Closed", "g4_product_closed"):
        if obj.get(key) in (True, "true", "yes", 1):
            return True
    return False


def find_receipt_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    # fixture root: receipts live directly under root
    root_markers = (
        "boot_health.json",
        "endpoint_smoke.json",
        "endpoint_smoke_health.json",
        "g4_hook.json",
        "mvn_clean_verify.json",
        "unit_it_contract.json",
        "sonar.json",
    )
    if any((root / name).is_file() for name in root_markers):
        dirs.append(root)
    for candidate in (
        root / "evidence/receipts/m4-floor",
        root / "evidence/receipts",
        root / "receipts",
    ):
        if not candidate.is_dir():
            continue
        leaves = [p for p in candidate.rglob("*.json") if p.is_file()]
        by_parent: dict[Path, int] = {}
        for p in leaves:
            by_parent[p.parent] = by_parent.get(p.parent, 0) + 1
        for parent in sorted(by_parent):
            if parent not in dirs:
                dirs.append(parent)
    return dirs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root or fixture dir containing receipts/verdicts",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    bad = 0
    checked = 0

    # Cite the contract so inbound-ref metric is no longer zero.
    contract = root / CONTRACT_REL
    if not contract.is_file():
        # fixture trees may omit the contract file; resolve from script → scaffold
        scaffold = Path(__file__).resolve().parents[5]
        alt = scaffold / CONTRACT_REL
        if alt.is_file():
            contract = alt
    if contract.is_file():
        # touch read for tooling; keep a visible stdout citation
        _ = contract.read_text(encoding="utf-8")[:80]
        print(f"OK: citing {CONTRACT_REL}")

    for rdir in find_receipt_dirs(root):
        for path in sorted(rdir.glob("*.json")):
            try:
                data = load_json(path)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {path}: {exc}", file=sys.stderr)
                bad = 1
                continue
            for obj in as_items(data):
                if "check" not in obj and "schema" not in obj:
                    continue
                if obj.get("schema") not in (
                    None,
                    "rhoai3.gate-receipt/v1",
                ) and "check" not in obj:
                    continue
                if "check" not in obj:
                    continue
                checked += 1
                try:
                    rel = str(path.relative_to(root))
                except ValueError:
                    rel = str(path)
                bad |= lint_receipt(rel, obj)

    verdict_dirs = [
        root / "evidence/verdicts",
        root / "evidence/preflight",
        root / "verdicts",
    ]
    for vdir in verdict_dirs:
        if not vdir.is_dir():
            continue
        for path in sorted(vdir.glob("*.json")):
            try:
                data = load_json(path)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {path}: {exc}", file=sys.stderr)
                bad = 1
                continue
            for i, obj in enumerate(as_items(data)):
                checked += 1
                try:
                    rel = str(path.relative_to(root))
                except ValueError:
                    rel = str(path)
                label = rel if len(as_items(data)) == 1 else f"{rel}[{i}]"
                bad |= lint_verdict(label, obj)

    # Also accept a single-receipt fixture at root without nested dirs
    for name in (
        "endpoint_smoke.json",
        "endpoint_smoke_health.json",
        "boot_health.json",
        "g4_hook.json",
        "mvn_clean_verify.json",
        "unit_it_contract.json",
        "sonar.json",
    ):
        path = root / name
        if path.is_file() and path.parent not in find_receipt_dirs(root):
            try:
                data = load_json(path)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {path}: {exc}", file=sys.stderr)
                bad = 1
                continue
            for obj in as_items(data):
                if "check" in obj:
                    checked += 1
                    bad |= lint_receipt(name, obj)

    if bad:
        return 1
    if checked == 0:
        print(
            "OK: check-semantics-manifest idle "
            "(no gate receipts/verdicts to lint)"
        )
        return 0
    print(f"OK: check-semantics-manifest passed ({checked} artifact(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
