#!/usr/bin/env python3
"""AD-H §18 / §18.0 — verdict routing, PROVISIONAL_ACCEPT token, substrate reopen.

Looks under evidence/verdicts/*.json and evidence/preflight/*.json.
Idle (exit 0) when no verdict artifacts exist.

Usage:
  python3 check-verdict-routing.py .
  python3 check-verdict-routing.py /projects/modernized
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — every verdict artifact routes legally, or gate idle (no
     verdict/preflight artifacts)
  1  BLOCK — unreadable artifact, missing verdict, illegal verdict→routing
     pair, ship without full ACCEPT, PROVISIONAL_ACCEPT misuse, kill-ratio
     composition breach, or a failed shared-substrate reopen check
  2  usage / harness defect (bad or unknown argument)
"""

VALID_ROUTING = {
    "REFUSE": {
        "auto_fix",
        "retry",
        "fix_session",
        "requeue",
        "reopen_story",
        "blocked",
        "human",
        "human_queue",
    },
    "INCONCLUSIVE": {
        "human",
        "human_queue",
        "blocked",
        "steerer",
        "reopen_story",
    },
    "INCONCLUSIVE_FIXTURE": {
        "human",
        "human_queue",
        "blocked",
        "steerer",
        "reopen_story",
    },
    "ACCEPT": {"advance", "ship", "close", "none", ""},
    "PROVISIONAL_ACCEPT": {"advance", "none", ""},
}

SCRIPT_DIR = Path(__file__).resolve().parent
MINT_REL = (
    Path(".hermes")
    / "skills"
    / "harness"
    / "dispatch-phase"
    / "scripts"
    / "mint-remediation-card.py"
)


def mint_remediation_script(start: Path) -> Path:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        cand = cur / MINT_REL
        if cand.is_file():
            return cand
        if cur == cur.parent:
            raise SystemExit(
                f"cannot find {MINT_REL} (walk up to migration.yaml) (SR-2)"
            )
        cur = cur.parent


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def truthy(v: object) -> bool:
    return v in (True, "true", "yes", 1)


def normalize_verdict(v: str) -> str:
    return str(v or "").upper().replace("-", "_")


def check_composition(label: str, obj: dict, root: Path) -> int:
    """AD-H §18.0 PROVISIONAL_ACCEPT + kill-ratio + shared-substrate reopen."""
    bad = 0
    phase = str(obj.get("phase") or "").upper()
    verdict = normalize_verdict(obj.get("verdict") or obj.get("gate_verdict") or "")
    kind = str(obj.get("accept_kind") or obj.get("acceptKind") or "").lower()
    ship = truthy(obj.get("ship")) or str(obj.get("status") or "").lower() in {
        "shipped",
        "released",
        "merged_main",
    }
    kill = str(obj.get("g1_kill_ratio") or obj.get("g1KillRatio") or "").lower()
    pinned = truthy(obj.get("g1_kill_ratio_threshold_pinned"))
    waiver = truthy(obj.get("g1_kill_ratio_waiver")) or (
        isinstance(obj.get("operator_waiver"), dict)
        and truthy(obj["operator_waiver"].get("g1_kill_ratio"))
    )
    if "g1_kill_ratio_waiver" in obj or (
        isinstance(obj.get("operator_waiver"), dict)
        and "g1_kill_ratio" in obj["operator_waiver"]
    ):
        waiver = True
    routing = str(obj.get("routing") or obj.get("failure_class") or "").lower().replace(
        "-", "_"
    )
    prior = normalize_verdict(
        obj.get("prior_verdict") or obj.get("prior_accept_kind") or ""
    )
    if prior == "PROVISIONAL":
        prior = "PROVISIONAL_ACCEPT"
    gate = str(obj.get("gate") or obj.get("failed_gate") or "").lower()
    implicated = obj.get("implicated_substrate") or obj.get("implicatedSubstrate")

    if phase == "M4" and verdict == "ACCEPT":
        print(
            f"FAIL: {label}: M4 must emit verdict=PROVISIONAL_ACCEPT "
            f"(not ACCEPT+accept_kind; AD-H §18.0)",
            file=sys.stderr,
        )
        bad = 1

    if verdict == "PROVISIONAL_ACCEPT":
        if phase and phase != "M4":
            print(
                f"FAIL: {label}: PROVISIONAL_ACCEPT only valid at M4 (got {phase})",
                file=sys.stderr,
            )
            bad = 1
        if ship:
            print(
                f"FAIL: {label}: PROVISIONAL_ACCEPT must never ship (AD-H §18.0)",
                file=sys.stderr,
            )
            bad = 1
        if kind and kind not in {"provisional", ""}:
            print(
                f"FAIL: {label}: accept_kind mirror must be provisional when set",
                file=sys.stderr,
            )
            bad = 1
        if kill == "pass" and not pinned:
            print(
                f"FAIL: {label}: g1_kill_ratio=PASS forbidden until threshold pinned "
                f"(AD-H §18.0 option A)",
                file=sys.stderr,
            )
            bad = 1
        if kill and kill not in {"pending_threshold", "pass"}:
            print(f"FAIL: {label}: unknown g1_kill_ratio={kill!r}", file=sys.stderr)
            bad = 1

    if verdict == "ACCEPT" and phase == "M5":
        if kind == "provisional":
            print(
                f"FAIL: {label}: M5 must not record provisional ACCEPT",
                file=sys.stderr,
            )
            bad = 1
        if kind and kind not in {"full", ""}:
            print(
                f"FAIL: {label}: M5 ACCEPT accept_kind must be full when set",
                file=sys.stderr,
            )
            bad = 1
        # Prefer explicit full; bare ACCEPT at M5 is allowed as full token
        if waiver:
            print(
                f"FAIL: {label}: g1_kill_ratio_waiver / operator_waiver cannot "
                f"author ACCEPT (B-4/C-3(a))",
                file=sys.stderr,
            )
            bad = 1
        if kill == "pass" and not pinned:
            print(
                f"FAIL: {label}: g1_kill_ratio=PASS without threshold pin (AD-H §18.0)",
                file=sys.stderr,
            )
            bad = 1
        if kill != "pass" or not pinned:
            print(
                f"FAIL: {label}: M5 ACCEPT needs g1_kill_ratio PASS and "
                f"threshold pin — if G-1 cannot be computed the verdict is "
                f"not ACCEPT (B-4)",
                file=sys.stderr,
            )
            bad = 1

    # Single-unit reopen after provisional
    if (
        phase == "M5"
        and verdict in {"REFUSE", "INCONCLUSIVE"}
        and prior in {"PROVISIONAL_ACCEPT", "PROVISIONAL"}
        and not implicated
    ):
        if routing not in {"reopen_story", "blocked", "human", "human_queue", "steerer"}:
            print(
                f"FAIL: {label}: M5 fail after PROVISIONAL_ACCEPT requires "
                f"routing=reopen_story|blocked (got {routing!r}; AD-H §18.0)",
                file=sys.stderr,
            )
            bad = 1

    # Shared-substrate reopen (§18.0 ¶4)
    if (
        phase == "M5"
        and verdict in {"REFUSE", "INCONCLUSIVE"}
        and isinstance(implicated, list)
        and implicated
    ):
        cmap = root / "evidence/slices/closure-map.json"
        if not cmap.is_file():
            if verdict != "INCONCLUSIVE" and routing not in {"blocked", "human", "human_queue"}:
                print(
                    f"FAIL: {label}: missing closure map with implicated_substrate "
                    f"→ must be INCONCLUSIVE/blocked (AD-H §18.0 ¶4)",
                    file=sys.stderr,
                )
                bad = 1
        else:
            # write temp verdict for --check
            import tempfile

            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
                json.dump(obj, fh)
                tmp = fh.name
            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT_DIR / "compute-substrate-reopen.py"),
                        str(root),
                        "--check",
                        tmp,
                    ],
                    capture_output=True,
                    text=True,
                )
            finally:
                Path(tmp).unlink(missing_ok=True)
            if proc.returncode != 0:
                sys.stderr.write(proc.stderr or proc.stdout or "substrate reopen check failed\n")
                bad = 1
            else:
                print(proc.stdout.strip() or "OK: substrate reopen")
            if routing not in {
                "reopen_story",
                "blocked",
                "human",
                "human_queue",
                "steerer",
            }:
                print(
                    f"FAIL: {label}: shared-substrate fail needs "
                    f"routing=reopen_story|blocked (got {routing!r})",
                    file=sys.stderr,
                )
                bad = 1

    return bad


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
        help="product root containing evidence/verdicts + evidence/preflight (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files: list[Path] = []
    for d in (root / "evidence/verdicts", root / "evidence/preflight"):
        if d.is_dir():
            files.extend(sorted(d.glob("*.json")))
    if not files:
        print("OK: no verdict/preflight artifacts — routing lint idle")
        return 0

    bad = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(root))
        try:
            items = load_items(path)
        except Exception as e:
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            bad = 1
            continue
        for i, obj in enumerate(items):
            if not isinstance(obj, dict):
                continue
            verdict = normalize_verdict(obj.get("verdict") or obj.get("gate_verdict") or "")
            if not verdict and str(obj.get("phase") or "").upper() == "FACTORY":
                continue
            if not verdict:
                if "verdict" not in obj and "gate_verdict" not in obj:
                    continue
            checked += 1
            label = rel if len(items) == 1 else f"{rel}[{i}]"
            routing = str(obj.get("routing") or obj.get("failure_class") or "").lower().replace(
                "-", "_"
            )
            ship = truthy(obj.get("ship")) or str(obj.get("status") or "").lower() in {
                "shipped",
                "released",
                "merged_main",
            }

            if not verdict:
                print(f"FAIL: {label}: missing verdict", file=sys.stderr)
                bad = 1
                continue

            if verdict in {"INCONCLUSIVE", "INCONCLUSIVE_FIXTURE"} and ship:
                print(
                    f"FAIL: {label}: {verdict} must never ship (AD-H §18 / B-5)",
                    file=sys.stderr,
                )
                bad = 1
            if verdict == "ACCEPT" and "INCONCLUSIVE_FIXTURE" in json.dumps(obj):
                print(
                    f"FAIL: {label}: ACCEPT embeds INCONCLUSIVE_FIXTURE "
                    f"(B-5: a fixture run cannot score ACCEPT)",
                    file=sys.stderr,
                )
                bad = 1

            if ship and verdict not in {"ACCEPT"}:
                print(
                    f"FAIL: {label}: ship requires ACCEPT (full), got {verdict}",
                    file=sys.stderr,
                )
                bad = 1

            if verdict in VALID_ROUTING and routing:
                allowed = VALID_ROUTING[verdict]
                if verdict not in {"ACCEPT", "PROVISIONAL_ACCEPT"} and routing not in allowed:
                    print(
                        f"FAIL: {label}: verdict={verdict} routing={routing!r} "
                        f"not in {sorted(allowed)} (AD-H §18)",
                        file=sys.stderr,
                    )
                    bad = 1
                if verdict == "PROVISIONAL_ACCEPT" and routing not in allowed:
                    print(
                        f"FAIL: {label}: PROVISIONAL_ACCEPT routing={routing!r} "
                        f"not in {sorted(allowed)}",
                        file=sys.stderr,
                    )
                    bad = 1

            if str(obj.get("failure_class") or "").lower() == "block_wave" and routing in {
                "auto_fix",
                "retry",
                "fix_session",
            }:
                print(f"FAIL: {label}: wave block must not auto_fix", file=sys.stderr)
                bad = 1

            bad |= check_composition(label, obj, root)

            if verdict == "REFUSE":
                try:
                    mint_py = mint_remediation_script(SCRIPT_DIR)
                except SystemExit as exc:
                    print(f"FAIL: {label}: C-3(a) {exc}", file=sys.stderr)
                    bad = 1
                    continue
                mint = subprocess.run(
                    [
                        sys.executable,
                        str(mint_py),
                        str(root),
                        "--verdict-file",
                        str(path),
                        "--index",
                        str(i),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if mint.returncode != 0:
                    err = (mint.stderr or mint.stdout or "").strip()
                    print(
                        f"FAIL: {label}: C-3(a) remediation receipt failed: {err}",
                        file=sys.stderr,
                    )
                    bad = 1

    if bad:
        print(f"Verdict-routing checks FAILED ({checked} artifact(s)).", file=sys.stderr)
        return 1
    print(f"OK: verdict-routing checks passed ({checked} artifact(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
