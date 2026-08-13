#!/usr/bin/env python3
"""AD-H §G.1 / AR-3.6 — refuse probe-only trees as G-1 acceptance operand.

Exit 0 when at least one *Test.java / *IT.java exists outside com.demo.harness.
Exit 1 (REFUSE) when tests are absent or only under the harness probe package.
Tooling smoke may still target harness under G1_OPERAND=tooling_smoke (not
acceptance).

*IT.java is included (Quarkus integration-test convention); paired with AR-2.8
family coverage.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HARNESS_PREFIX = "com/demo/harness/"


def test_paths(root: Path) -> list[Path]:
    test_root = root / "src" / "test" / "java"
    if not test_root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(test_root.rglob("*.java")):
        name = p.name
        if name.endswith("Test.java") or name.endswith("IT.java"):
            out.append(p)
    return out


def is_harness(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root / "src" / "test" / "java").as_posix()
    except ValueError:
        return False
    return rel.startswith(HARNESS_PREFIX)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument(
        "--allow-tooling-smoke",
        action="store_true",
        help="Permit harness-only when G1_OPERAND=tooling_smoke (non-acceptance)",
    )
    sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
    from output_format import add_format_arg, emit_result  # noqa: E402

    add_format_arg(ap)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    operand = os.environ.get("G1_OPERAND", "acceptance").strip().lower()

    tests = test_paths(root)
    if not tests:
        emit_result(
            args.format,
            {"check": "g1-acceptance-operand", "ok": False, "reason": "empty"},
            "FAIL: AR-3.6 no *Test.java — G-1 acceptance operand empty",
            ok=False,
        )
        return 1

    product = [p for p in tests if not is_harness(p, root)]
    harness = [p for p in tests if is_harness(p, root)]

    if not product:
        if args.allow_tooling_smoke or operand == "tooling_smoke":
            emit_result(
                args.format,
                {
                    "check": "g1-acceptance-operand",
                    "ok": True,
                    "mode": "tooling_smoke",
                    "harness": len(harness),
                },
                "OK: harness-only tests under G1_OPERAND=tooling_smoke "
                "(NOT acceptance evidence)",
                ok=True,
            )
            return 0
        emit_result(
            args.format,
            {
                "check": "g1-acceptance-operand",
                "ok": False,
                "reason": "probe_only",
                "harness": len(harness),
            },
            "FAIL: AR-3.6 probe-only tests (com.demo.harness.*) — "
            "REFUSE as G-1 acceptance operand",
            ok=False,
        )
        for p in harness[:20]:
            print(f"  probe_test: {p.relative_to(root)}", file=sys.stderr)
        return 1

    emit_result(
        args.format,
        {
            "check": "g1-acceptance-operand",
            "ok": True,
            "product": len(product),
            "harness": len(harness),
        },
        f"OK: G-1 acceptance operand has {len(product)} product test(s) "
        f"(harness smoke={len(harness)})",
        ok=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
