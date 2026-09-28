#!/usr/bin/env python3
"""Judge one MTA CLI `analyze` invocation before its findings are used.

    judge-analyzer-exit.py --rc N --report-dir DIR --console FILE \
        --started FILE --cli-version "version: 8.2.1" --input-root PATH \
        [--canary-id ID]

Prints one JSON verdict on stdout (recorded in the findings' execution
evidence and the producer receipt) and exits 0 when the findings may be
used, 1 when they may not (incidents UNKNOWN; the caller must fail).

A clean exit (rc 0) is usable when `<report-dir>/output.json` was written by
this invocation (newer than the `--started` marker) and parses.

A nonzero exit is usable ONLY as the narrow compatibility exception
MTA-8.2.1-DEPENDENCIES-JSON-MARSHAL. The pinned MTA CLI 8.2.1, asked for JSON
output (`--json-output`, a boolean), writes output.json from output.yaml and
then fails to convert dependencies.yaml to JSON when indirect dependencies
carry nested `baseDep.extras` ("json: unsupported type: map[interface {}]
interface {}"), so every analysis of a Maven project exits 1 after the
analysis completed. All of these must hold, or the exit is a failure:

  - the measured CLI version is exactly 8.2.1 (the version the defect was
    identified on; any other or unmeasured version is refused);
  - analysis.log records the analyzer's completion (`msg="finished running
    analysis"`, the marker the pinned binary writes) and no provider failed
    to start (`msg="unable to init provider"`);
  - the analyzer's console reports "Analysis complete!", carries the exact
    marshal failure, and every error line on it is that failure (any other
    error refuses). Measured on the pinned image 2026-09-28: four error lines
    ("failed to marshal dependencies file to json", "failed to create json
    output file", "analysis failed", cobra's "Error: "), each ending in the
    marshal message;
  - the failure is in the dependencies conversion: dependencies.yaml was
    written and no dependencies.json was;
  - output.json was produced by this invocation (absent before it, modified
    after the `--started` marker), parses as a non-empty list of rulesets, and
    every file incident names a file under this invocation's input root;
  - output.json agrees with output.yaml: the same rulesets in the same order,
    and per ruleset the same violation and insight rule and incident counts;
  - the canary (`--canary-id`, migration.yaml analysis.canary_rule_id) fired
    in output.json; without a declared canary the exception is refused.

The analyzer's exit status is never rewritten: the verdict carries it as
`analyzer_exit_status`, with the exception's id and reason when it applies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

EXCEPTION_ID = "MTA-8.2.1-DEPENDENCIES-JSON-MARSHAL"
EXCEPTION_VERSION = "8.2.1"
MARSHAL_FAILURE = "json: unsupported type: map[interface {}]interface {}"
COMPLETION_MARKER = 'msg="finished running analysis"'
CONSOLE_COMPLETION = "Analysis complete!"
PROVIDER_FAILURE = 'msg="unable to init provider"'
# what counts as an error line on the analyzer console (logrus levels and cobra's "Error: ")
ERROR_LINE = re.compile(r"(?i)(level=(error|fatal|panic)\b|^\s*(error|fatal|panic)\b|\berror:)")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def yaml_ruleset_counts(text: str) -> list[tuple]:
    """Per ruleset (name, violation rules, violation incidents, insight rules,
    insight incidents) from the analyzer's output.yaml, read by its fixed
    layout (the pinned image has no YAML library): a ruleset opens at column 0
    with `- name:`, sections sit at indent 2, rule ids at indent 4 and incident
    items (`- uri:`) at indent 6. Deeper lines (messages, code snippets,
    block scalars) never start at those indents."""
    out: list[list] = []
    section = ""
    for ln in text.splitlines():
        if ln.startswith("- name:"):
            out.append([_unquote(ln[len("- name:"):]), 0, 0, 0, 0])
            section = ""
            continue
        if not out:
            continue
        m = re.match(r"^  ([A-Za-z]+):", ln)
        if m:
            section = m.group(1)
            continue
        if section not in ("violations", "insights"):
            continue
        base = 1 if section == "violations" else 3
        if re.match(r"^    [^ -]", ln) and ln.rstrip().endswith(":"):
            out[-1][base] += 1
        elif ln.startswith("      - uri:"):
            out[-1][base + 1] += 1
    return [tuple(r) for r in out]


def json_ruleset_counts(doc: list) -> list[tuple]:
    rows = []
    for rs in doc:
        v = rs.get("violations") if isinstance(rs.get("violations"), dict) else {}
        i = rs.get("insights") if isinstance(rs.get("insights"), dict) else {}
        rows.append((str(rs.get("name") or ""),
                     len(v), sum(len(x.get("incidents") or []) for x in v.values() if isinstance(x, dict)),
                     len(i), sum(len(x.get("incidents") or []) for x in i.values() if isinstance(x, dict))))
    return rows


def _version(measured: str) -> str:
    m = re.search(r"\d+(?:\.\d+)+", measured or "")
    return m.group(0) if m else ""


def judge(args: argparse.Namespace) -> tuple[bool, dict]:
    report = Path(args.report_dir)
    out_json = report / "output.json"
    started = Path(args.started)
    verdict: dict = {
        "analyzer_exit_status": args.rc,
        "cli_version_measured": args.cli_version,
        "output_json": str(out_json),
        "output_json_sha256": "",
        "compatibility_exception": None,
    }

    def refuse(why: str) -> tuple[bool, dict]:
        verdict["accepted"] = False
        verdict["refusal"] = why
        return False, verdict

    if not started.is_file():
        return refuse("no start marker %s: this invocation cannot be told apart from an earlier one" % started)
    if args.output_existed:
        return refuse("output.json existed before this invocation (stale artifact)")
    if not out_json.is_file() or out_json.stat().st_size == 0:
        return refuse("the analyzer exited %d and wrote no output.json" % args.rc)
    if out_json.stat().st_mtime_ns < started.stat().st_mtime_ns:
        return refuse("output.json predates this invocation (stale artifact)")
    try:
        doc = json.loads(out_json.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return refuse("output.json does not parse (truncated or corrupt): %s" % exc)
    if not isinstance(doc, list) or not doc or not all(isinstance(r, dict) and r.get("name") for r in doc):
        return refuse("output.json is not a non-empty list of named rulesets")
    verdict["output_json_sha256"] = _sha256(out_json)
    verdict["rulesets"] = len(doc)
    if args.rc == 0:
        verdict["accepted"] = True
        verdict["basis"] = "clean-exit"
        return True, verdict

    # --- nonzero exit: the compatibility exception, or a failure ---
    version = _version(args.cli_version)
    if version != EXCEPTION_VERSION:
        return refuse("the analyzer exited %d on CLI version %r; the %s exception is bound to %s only"
                      % (args.rc, version or "unmeasured", EXCEPTION_ID, EXCEPTION_VERSION))
    log = report / "analysis.log"
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    if COMPLETION_MARKER not in log_text:
        return refuse("the analyzer exited %d and analysis.log does not record a completed analysis (%s)"
                      % (args.rc, COMPLETION_MARKER))
    if PROVIDER_FAILURE in log_text:
        return refuse("the analyzer exited %d and analysis.log records a provider that failed to start" % args.rc)
    console = Path(args.console)
    con_text = console.read_text(encoding="utf-8", errors="replace") if console.is_file() else ""
    if CONSOLE_COMPLETION not in con_text:
        return refuse("the analyzer exited %d and its console does not report %r" % (args.rc, CONSOLE_COMPLETION))
    if MARSHAL_FAILURE not in con_text:
        return refuse("the analyzer exited %d without the known dependency-JSON marshal failure" % args.rc)
    others = [ln.strip() for ln in con_text.splitlines() if ERROR_LINE.search(ln) and MARSHAL_FAILURE not in ln]
    if others:
        return refuse("the analyzer exited %d with another error besides the known marshal failure: %s"
                      % (args.rc, others[0][:300]))
    deps_yaml, deps_json = report / "dependencies.yaml", report / "dependencies.json"
    if not deps_yaml.is_file() or deps_yaml.stat().st_size == 0:
        return refuse("the marshal failure is not in the dependencies conversion (no dependencies.yaml)")
    if deps_json.is_file() and deps_json.stat().st_size > 0:
        return refuse("dependencies.json was written, so the marshal failure is not the dependencies conversion")
    root = str(Path(args.input_root))
    uris = [str(inc.get("uri") or "") for rs in doc for sec in ("violations", "insights")
            for v in ((rs.get(sec) or {}).values() if isinstance(rs.get(sec), dict) else [])
            if isinstance(v, dict) for inc in (v.get("incidents") or []) if isinstance(inc, dict)]
    files = [u for u in uris if u.startswith("file://")]
    foreign = [u for u in files if not (u[len("file://"):] + "/").startswith(root.rstrip("/") + "/")]
    if not files or foreign:
        return refuse("output.json is not bound to this invocation's input %s: %s"
                      % (root, (foreign[0] if foreign else "no file incidents")))
    out_yaml = report / "output.yaml"
    if not out_yaml.is_file():
        return refuse("no output.yaml to check output.json against")
    y = yaml_ruleset_counts(out_yaml.read_text(encoding="utf-8", errors="replace"))
    j = json_ruleset_counts(doc)
    if len(y) != len(j):
        return refuse("output.json has %d rulesets, output.yaml %d" % (len(j), len(y)))
    for a, b in zip(j, y):
        if a != b:
            return refuse("output.json and output.yaml disagree for ruleset %s: json %s, yaml %s" % (a[0], a[1:], b[1:]))
    if not args.canary_id:
        return refuse("no canary rule is declared, so the %s exception cannot prove the ruleset ran" % EXCEPTION_ID)
    fired = any(isinstance(rs.get(sec), dict) and isinstance(rs[sec].get(args.canary_id), dict)
                and rs[sec][args.canary_id].get("incidents")
                for rs in doc for sec in ("violations", "insights"))
    if not fired:
        return refuse("the canary %s did not fire in output.json" % args.canary_id)
    verdict["accepted"] = True
    verdict["basis"] = "compatibility-exception"
    verdict["compatibility_exception"] = {
        "id": EXCEPTION_ID,
        "cli_version": version,
        "analyzer_exit_status": args.rc,
        "reason": "MTA CLI %s completed the analysis and wrote output.json, then failed converting dependencies.yaml "
                  "to JSON (%s); the findings were checked against output.yaml and the canary" % (version, MARSHAL_FAILURE),
        "rulesets": len(doc),
        "violation_incidents": sum(r[2] for r in j),
        "insight_incidents": sum(r[4] for r in j),
        "canary": args.canary_id,
    }
    return True, verdict


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rc", type=int, required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--console", required=True)
    ap.add_argument("--started", required=True)
    ap.add_argument("--cli-version", default="")
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--canary-id", default="")
    ap.add_argument("--output-existed", action="store_true", help="output.json was present before the analyzer ran")
    args = ap.parse_args(argv)
    ok, verdict = judge(args)
    print(json.dumps(verdict, sort_keys=True))
    if not ok:
        print("FAIL: MTA_ANALYZER_FAILED %s; incidents are UNKNOWN" % verdict["refusal"], file=sys.stderr)
        return 1
    if verdict.get("compatibility_exception"):
        print("WARN: %s accepted: the analyzer exited %d after a completed analysis; the exit status is recorded"
              % (EXCEPTION_ID, args.rc), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
