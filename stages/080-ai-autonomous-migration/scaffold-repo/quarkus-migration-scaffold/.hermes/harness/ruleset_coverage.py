#!/usr/bin/env python3
"""O-RULESETLOG — derive MTA ruleset coverage from mta-findings.json.

Surfaces which rulesets loaded, which fired, which were empty (evaluated,
nothing found), and which were unevaluated (skipped>0, fired=0). The last
class is the finding-maker: openjdk21-with-openjdk17-only targets shows
skipped=16,fired=0 and must not read as "clean".

Usage:
  python3 ruleset_coverage.py --findings PATH [--yaml PATH] [--write PATH] [--log]
  Exit 0 always when findings parse; 2 on usage / unreadable JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_targets(yaml_text: str) -> list[str]:
    """Extract analysis.targets list — no PyYAML dependency."""
    in_analysis = False
    for line in yaml_text.splitlines():
        if re.match(r"^analysis:\s*$", line):
            in_analysis = True
            continue
        if in_analysis and re.match(r"^[A-Za-z]", line):
            break
        if not in_analysis:
            continue
        m = re.match(r"^\s*targets:\s*\[(.*)\]\s*$", line)
        if m:
            return [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]
    return []


def _viol_count(rs: dict) -> int:
    viol = rs.get("violations")
    if isinstance(viol, dict):
        return len(viol)
    if isinstance(viol, list):
        return len(viol)
    return 0


def _skipped_count(rs: dict) -> int:
    sk = rs.get("skipped")
    if isinstance(sk, list):
        return len(sk)
    if isinstance(sk, dict):
        return len(sk)
    return 0


def _incident_count(rs: dict) -> int:
    viol = rs.get("violations")
    if not isinstance(viol, dict):
        return 0
    n = 0
    for body in viol.values():
        if isinstance(body, dict):
            inc = body.get("incidents")
            if isinstance(inc, list):
                n += len(inc)
            else:
                n += 1
        else:
            n += 1
    return n


def summarize(findings: list, targets: list[str], *, mode: str = "", custom: str = "") -> dict:
    fired: list[tuple[int, str]] = []
    unevaluated: list[tuple[int, str]] = []
    empty_names: list[str] = []
    rules_fired = 0
    rules_filtered = 0
    incidents = 0
    for rs in findings:
        if not isinstance(rs, dict):
            continue
        name = str(rs.get("name") or "?")
        nfire = _viol_count(rs)
        nsk = _skipped_count(rs)
        rules_filtered += nsk
        incidents += _incident_count(rs)
        rules_fired += nfire
        if nfire > 0:
            fired.append((nfire, name))
        elif nsk > 0:
            unevaluated.append((nsk, name))
        else:
            empty_names.append(name)
    fired.sort(key=lambda x: (-x[0], x[1]))
    unevaluated.sort(key=lambda x: (-x[0], x[1]))
    return {
        "targets": list(targets),
        "mode": mode,
        "custom": custom,
        "loaded": len(findings),
        "evaluated": len(fired),
        "empty": len(empty_names),
        "unevaluated": len(unevaluated),
        "rules_fired": rules_fired,
        "rules_filtered": rules_filtered,
        "incidents": incidents,
        "fired": fired,
        "unevaluated_list": unevaluated,
        "empty_names": sorted(empty_names),
    }


def render_md(s: dict) -> str:
    lines = [
        "# Ruleset coverage (O-RULESETLOG)",
        "",
        "Derived from `migration/mta-findings.json` at M1 ANALYZE. "
        "Unevaluated = skipped>0 and fired=0 (rules never asked).",
        "",
        f"- targets: `{', '.join(s['targets']) or '(none)'}`",
        f"- mode: `{s.get('mode') or '(unset)'}`",
        f"- custom rules: `{s.get('custom') or '(none)'}`",
        f"- rulesets: loaded={s['loaded']} evaluated={s['evaluated']} "
        f"empty={s['empty']} unevaluated={s['unevaluated']}",
        f"- rules: fired={s['rules_fired']} filtered={s['rules_filtered']} "
        f"incidents={s['incidents']}",
        "",
        "## Fired",
        "",
    ]
    if s["fired"]:
        for n, name in s["fired"]:
            lines.append(f"- {name}: {n}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Unevaluated (skipped>0, fired=0)", ""])
    if s["unevaluated_list"]:
        for n, name in s["unevaluated_list"]:
            lines.append(f"- {name}: skipped={n}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Empty (skipped=0, fired=0)", ""])
    if s["empty_names"]:
        for name in s["empty_names"]:
            lines.append(f"- {name}")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def render_log_lines(s: dict, *, uneval_top: int = 6) -> list[str]:
    tgt = " ".join(s["targets"]) if s["targets"] else "(none)"
    custom = s.get("custom") or "(none)"
    mode = s.get("mode") or "(unset)"
    fired_bits = " · ".join(f"{name} {n}" for n, name in s["fired"][:8]) or "(none)"
    uneval_bits = (
        " · ".join(f"{name} {n}" for n, name in s["unevaluated_list"][:uneval_top])
        or "(none)"
    )
    if len(s["unevaluated_list"]) > uneval_top:
        uneval_bits += " · …"
    return [
        f"O-RULESETLOG targets=[{tgt}] mode={mode} custom={custom}",
        (
            f"O-RULESETLOG rulesets: loaded={s['loaded']} evaluated={s['evaluated']} "
            f"empty={s['empty']} · rules: fired={s['rules_fired']} "
            f"filtered={s['rules_filtered']} · incidents={s['incidents']}"
        ),
        f"O-RULESETLOG fired:  {fired_bits}",
        f"O-RULESETLOG unevaluated (skipped>0, fired=0): {uneval_bits}",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="O-RULESETLOG ruleset coverage")
    ap.add_argument("--findings", required=True, help="mta-findings.json / output.json")
    ap.add_argument("--yaml", default="", help="migration.yaml for analysis.targets")
    ap.add_argument("--write", default="", help="write markdown coverage file")
    ap.add_argument("--log", action="store_true", help="print O-RULESETLOG log lines")
    ap.add_argument("--mode", default="", help="analysis.mode for log line")
    ap.add_argument("--custom", default="", help="custom rules path for log line")
    ap.add_argument("--uneval-top", type=int, default=6)
    args = ap.parse_args()

    fpath = Path(args.findings)
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"O-RULESETLOG RED: cannot read findings: {e}", file=sys.stderr)
        return 2
    if not isinstance(data, list):
        print("O-RULESETLOG RED: findings root must be a list", file=sys.stderr)
        return 2

    targets: list[str] = []
    mode = args.mode
    if args.yaml:
        ypath = Path(args.yaml)
        if ypath.is_file():
            ytext = ypath.read_text(encoding="utf-8", errors="replace")
            targets = parse_targets(ytext)
            if not mode:
                mm = re.search(
                    r"^analysis:.*?^\s*mode:\s*(\S+)",
                    ytext,
                    re.M | re.S,
                )
                if mm:
                    mode = mm.group(1).strip().strip("'\"")

    summary = summarize(
        data, targets, mode=mode, custom=args.custom or ""
    )
    md = render_md(summary)
    if args.write:
        out = Path(args.write)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    if args.log:
        for line in render_log_lines(summary, uneval_top=args.uneval_top):
            print(line)
    elif not args.write:
        print(md, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
