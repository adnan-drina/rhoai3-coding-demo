#!/usr/bin/env python3
"""K1 validator — every BODY_* in one pass. Each refuse names a remedy.

Loader + validator ≤400 lines is a land-time checkpoint (AD-019), not a proof.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_KERNEL = Path(__file__).resolve().parent
if str(_KERNEL) not in sys.path:
    sys.path.insert(0, str(_KERNEL))

from k1_load import digest_file, load_body, read_sidecar
from k1_schema import (
    HERMES_ID_RE,
    INLINE_MARKERS,
    PENDING_SHA,
    PHASES,
    REACHABILITY_PHASES,
    REF_KEYS,
    REMEDY,
    REQUIRED_TOP,
    SHA256_RE,
    TYPE_INVENTORY_KEY,
)

Issue = tuple[str, str, str]


def _issue(code: str, detail: str) -> Issue:
    return (code, detail, REMEDY[code])


def validate_body(body: Any, *, root: Path | None = None) -> list[Issue]:
    """Return every violation. Never returns at the first fail."""
    out: list[Issue] = []
    if not isinstance(body, dict):
        return [_issue("BODY_SCHEMA", "body must be a JSON object")]

    if "generated" in body or (
        isinstance(body.get("identity"), dict) and "generated" in body["identity"]
    ):
        out.append(
            _issue(
                "BODY_GENERATED",
                "stored generated flag present",
            )
        )

    missing = [k for k in REQUIRED_TOP if k not in body]
    if missing:
        out.append(_issue("BODY_SCHEMA", "missing keys: %s" % ",".join(missing)))

    tid = body.get("task_id")
    if isinstance(tid, str) and re.match(HERMES_ID_RE, tid):
        out.append(_issue("BODY_HERMES_ID", "task_id looks like a Hermes card id: %s" % tid))
    elif tid is not None and (not isinstance(tid, str) or not tid.strip()):
        out.append(_issue("BODY_SCHEMA", "task_id must be a non-empty logical story_id"))

    role = body.get("role")
    if "role" in body and (not isinstance(role, str) or not role.strip()):
        out.append(_issue("BODY_SCHEMA", "role must be a non-empty string"))

    phase = str(body.get("phase") or "").upper()
    if "phase" in body and phase not in PHASES:
        out.append(_issue("BODY_SCHEMA", "phase %r is not in %s" % (body.get("phase"), sorted(PHASES))))

    refs = body.get("refs")
    if "refs" in body and not isinstance(refs, list):
        out.append(_issue("BODY_SCHEMA", "refs must be a list"))
        refs = []
    seen_keys: set[str] = set()
    if isinstance(refs, list):
        for i, ref in enumerate(refs):
            if not isinstance(ref, dict):
                out.append(_issue("BODY_SCHEMA", "refs[%d] must be an object" % i))
                continue
            for rk in REF_KEYS:
                if rk not in ref:
                    out.append(_issue("BODY_SCHEMA", "refs[%d] missing %s" % (i, rk)))
            key = str(ref.get("key") or "")
            path_s = str(ref.get("path") or "")
            sha = str(ref.get("sha256") or "")
            if key:
                seen_keys.add(key)
            exp = sha.lower()
            if sha and exp != PENDING_SHA and not re.match(SHA256_RE, exp):
                out.append(
                    _issue("BODY_REF_SHA256", "refs[%d] key=%s sha256 %r" % (i, key, sha))
                )
            if exp == PENDING_SHA and key == TYPE_INVENTORY_KEY:
                out.append(
                    _issue(
                        "BODY_REF_SHA256",
                        "type-inventory may not be pending; stamp a real digest",
                    )
                )
            if root is not None and path_s and exp and re.match(SHA256_RE, exp):
                fp = Path(path_s) if Path(path_s).is_absolute() else (root / path_s)
                if not fp.is_file():
                    out.append(
                        _issue("BODY_REF_DIGEST", "refs[%d] path %s is not a file" % (i, path_s))
                    )
                else:
                    got = digest_file(fp)
                    if got != exp:
                        out.append(
                            _issue(
                                "BODY_REF_DIGEST",
                                "refs[%d] key=%s digest mismatch" % (i, key),
                            )
                        )

    if phase in REACHABILITY_PHASES and TYPE_INVENTORY_KEY not in seen_keys:
        out.append(
            _issue(
                "BODY_REF_MISSING",
                "phase=%s consumes reachability but refs[] has no key=%s" % (phase, TYPE_INVENTORY_KEY),
            )
        )

    slim = {
        k: v
        for k, v in body.items()
        if k not in ("files_in_scope", "filesInScope", "files_writable", "exit_criteria")
    }
    raw = json.dumps(slim, sort_keys=True)
    if len(raw) > 12000 or re.search(INLINE_MARKERS, raw):
        out.append(_issue("BODY_INLINE", "body looks like it inlines derived content"))

    if phase == "M3":
        scope = body.get("files_in_scope") or body.get("filesInScope")
        writable = body.get("files_writable")
        if not isinstance(scope, list) or not scope:
            out.append(_issue("BODY_SCOPE", "M3 files_in_scope is missing or empty"))
        if not isinstance(writable, list) or not writable:
            out.append(_issue("BODY_SCOPE", "M3 files_writable is missing or empty"))

    if phase in {"M3", "M4", "M5"}:
        exits = body.get("exit_criteria") or body.get("done_when")
        if not isinstance(exits, list) or not exits:
            out.append(_issue("BODY_EXIT", "phase=%s needs non-empty exit_criteria[]" % phase))
        else:
            for i, item in enumerate(exits):
                if not isinstance(item, dict) or not item.get("check"):
                    out.append(
                        _issue("BODY_EXIT", "exit_criteria[%d] needs check" % i)
                    )
                    continue
                if not (item.get("cmd") or item.get("assert")):
                    out.append(
                        _issue("BODY_EXIT", "exit_criteria[%d] needs cmd or assert" % i)
                    )

    return out


def validate_file(path: Path, *, root: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    try:
        body = load_body(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [_issue("BODY_SCHEMA", str(exc))]
    issues.extend(validate_body(body, root=root))
    side = read_sidecar(path)
    if side is not None:
        got = digest_file(path)
        if side != got:
            issues.append(
                _issue("BODY_REF_DIGEST", "sidecar sha256 does not match body file")
            )
    return issues


def format_issues(issues: list[Issue]) -> str:
    lines = []
    for code, detail, remedy in issues:
        lines.append("%s: %s" % (code, detail))
        lines.append("  remedy: %s" % remedy)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root: Path | None = None
    bodies: list[Path] = []
    i = 0
    while i < len(args):
        if args[i] == "--root" and i + 1 < len(args):
            root = Path(args[i + 1])
            i += 2
            continue
        if args[i] in ("--body", "--only") and i + 1 < len(args):
            bodies.append(Path(args[i + 1]))
            i += 2
            continue
        if args[i].startswith("-"):
            print("FAIL: unknown flag %s" % args[i], file=sys.stderr)
            return 1
        bodies.append(Path(args[i]))
        i += 1
    if not bodies:
        print("FAIL: pass --body PATH", file=sys.stderr)
        return 1
    bad = 0
    n = 0
    for p in bodies:
        n += 1
        body_path = p if p.is_absolute() else ((root / p) if root is not None else p)
        issues = validate_file(body_path, root=root)
        if issues:
            bad = 1
            print(format_issues(issues), file=sys.stderr)
    if bad:
        print("K1 body checks FAILED (%d file(s))." % n, file=sys.stderr)
        return 1
    print("OK: K1 body checks passed (%d file(s))." % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
