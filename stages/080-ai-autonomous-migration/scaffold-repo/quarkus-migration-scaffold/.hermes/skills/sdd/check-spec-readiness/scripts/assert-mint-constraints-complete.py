#!/usr/bin/env python3
"""Mint-completeness: refuse empty/absent constraints unless tagged constraint-free.

Architect E-20260811T200911Z Class A (BIND mint-completeness). Distinct from
constraints-preservation (preserve≠invent baseline). Fresh/re-mints must carry
the standard applicable constraint set for the story class.

Usage:
  # Check only
  python3 assert-mint-constraints-complete.py . --body evidence/bodies/m3-s-003.json

  # Inject standard set when absent/empty, then check
  python3 assert-mint-constraints-complete.py . --body evidence/bodies/m3-s-003.json --inject
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA_TAG = "constraint_free"


def load_body(path: Path) -> tuple[dict, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("body"), dict):
        return raw, raw["body"]
    return raw, raw


def story_id_of(body: dict, path: Path) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    sid = str(ident.get("story_id") or body.get("story_id") or "")
    if sid:
        return sid
    name = path.name
    if name.startswith("m3-s-") and name.endswith(".json"):
        return "S-" + name[len("m3-s-") : -len(".json")].upper()
    return ""


def operand_class_of(body: dict) -> str:
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    return str(ident.get("operand_class") or body.get("operand_class") or "src_code")


def standard_constraints(story_id: str, operand_class: str) -> list[str]:
    """Standard applicable set (Architect E-20260811T200911Z / Operator E-200426Z)."""
    forbid = (
        "FORBIDDEN API: do not use @IfBuildProfile (any profile). Required path: "
        "%profile config / build-time alternatives per skill_view references/di-config.md "
        "(Pre-v12 R5 / Architect E-20260811T102405Z). Silent adoption after quoting this "
        "forbid = execute-as-defined FAIL/abort."
    )
    write_set = (
        "WRITE-SET (AR-4.4): write only files_writable / destination write-set. Readable "
        "deps and OOS paths are not write authority. Silent OOS writes = FAIL/abort."
    )
    coverage = (
        "COVERAGE-GAP: orphan model/interface / missing dependency owner ⇒ typed "
        "needs_input BLOCK (escalate Lead) — NEVER OOS-invent types or owners."
    )
    residue = (
        "RESIDUE: do not leave Spring/javax migration residue in files_writable that the "
        "story claims to migrate; unfinished in-scope residue ⇒ typed needs_input, not "
        "kanban_complete."
    )
    out = [forbid, write_set, coverage, residue]
    # S-009 / profile-gated properties: emphasize %profile required path
    if story_id.upper() in {"S-009", "009"} or "profile" in operand_class.lower():
        out.insert(
            1,
            "REQUIRED PATH (profile locality): use %mysql / %postgresql (or matching) "
            "Quarkus profile config in application-*.properties — never @IfBuildProfile / "
            "@Profile on beans for this story's writable set (Operator E-20260811T200426Z).",
        )
    if operand_class == "build_config":
        # build_config still gets forbid+write+coverage; residue less about java
        out = [c for c in out if not c.startswith("RESIDUE:")]
        out.append(
            "BUILD_CONFIG: edit only declared properties/config operands; do not expand "
            "into src_code without typed needs_input / Lead rescope."
        )
    # Tip-bank B2 (Operator E-20260813T111910Z / v13 s-008): CORS is infra,
    # not a REST story operand. HARD forbid at mint — never mid-run amend tip.
    sid_u = story_id.upper().replace("S-", "").lstrip("0") or story_id.upper()
    rest_hint = (
        operand_class in {"src_code", "rest", "api"}
        or "REST" in story_id.upper()
        or sid_u in {"8", "008"}
        or "controller" in operand_class.lower()
    )
    if rest_hint:
        out.append(
            "CORS_OUT_OF_SCOPE (HARD / tip-bank B2): do NOT implement @CrossOrigin, "
            "CORS filters, or CORS essays. CORS is platform/infra — write REST "
            "resources first; typed needs_input if blocked, never thrash on CORS."
        )
    return out


def constraints_list(body: dict) -> list:
    raw = body.get("constraints")
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def is_constraint_free(body: dict) -> bool:
    tags = body.get("tags") or body.get("mint_tags") or []
    if isinstance(tags, list) and SCHEMA_TAG in tags:
        return True
    if body.get("constraint_free") is True:
        return True
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    return bool(ident.get("constraint_free"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--body", required=True)
    ap.add_argument(
        "--inject",
        action="store_true",
        help="When constraints absent/empty, inject standard applicable set and write body",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    body_path = Path(args.body)
    if not body_path.is_file():
        body_path = root / args.body
    if not body_path.is_file():
        print(f"FAIL: body missing {args.body}", file=sys.stderr)
        return 1

    raw, body = load_body(body_path)
    if is_constraint_free(body):
        print(f"OK: {body_path.name} tagged constraint-free — mint-completeness idle")
        return 0

    items = constraints_list(body)
    nonempty = [x for x in items if (isinstance(x, str) and x.strip()) or isinstance(x, dict)]
    if nonempty:
        print(f"OK: mint-completeness constraints present (n={len(nonempty)}) → {body_path.name}")
        return 0

    sid = story_id_of(body, body_path)
    oc = operand_class_of(body) or "src_code"
    if not args.inject:
        print(
            f"FAIL: MINT_COMPLETENESS: {body_path.name} constraints absent/empty "
            f"(story={sid or '?'} operand_class={oc}). Inject standard set "
            f"(--inject) or tag constraint_free. "
            f"(Architect E-20260811T200911Z / governance/contracts/mint-completeness-constraints.md)",
            file=sys.stderr,
        )
        return 1

    injected = standard_constraints(sid, oc)
    body["constraints"] = injected
    if "body" in raw and isinstance(raw["body"], dict):
        raw["body"] = body
        out_doc = raw
    else:
        out_doc = body
    body_path.write_text(json.dumps(out_doc, indent=2) + "\n", encoding="utf-8")
    print(
        f"OK: injected standard constraints n={len(injected)} story={sid or '?'} "
        f"operand_class={oc} → {body_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
