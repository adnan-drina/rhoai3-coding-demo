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


def standard_constraints(story_id: str, operand_class: str, body: dict | None = None) -> list[str]:
    """Standard applicable set — F7 short imperatives (no archaeology prose).

    Provenance of *why* a constraint was injected lives on the F2 injection
    receipt, not in the constraint text the worker must act on.
    """
    body = body or {}
    # F7: ≤1 line each; no Pre-v12 / tip-bank / v13 specimen archaeology.
    forbid = (
        "FORBIDDEN: do not use @IfBuildProfile. Use %profile config or "
        "build-time alternatives (skill_view references/di-config.md)."
    )
    write_set = (
        "WRITE-SET: write only files_writable. Readable deps are not write "
        "authority; silent OOS writes = FAIL."
    )
    coverage = (
        "COVERAGE-GAP: orphan type / missing owner → typed needs_input. "
        "Never OOS-invent types or owners."
    )
    residue = (
        "RESIDUE: unfinished in-scope Spring/javax residue → typed "
        "needs_input, not kanban_complete."
    )
    out = [forbid, write_set, coverage, residue]
    oc = operand_class.lower().replace("-", "_")
    writable = [
        str(p.get("dest") or p.get("path") or p) if isinstance(p, dict) else str(p)
        for p in (
            body.get("files_writable")
            or body.get("write_set")
            or body.get("files_in_scope")
            or []
        )
    ]
    has_app_props = any(
        "application" in p.lower() and p.lower().endswith(".properties") for p in writable
    )
    profile_hint = "profile" in oc or (oc == "config" and has_app_props)
    if profile_hint:
        out.insert(
            1,
            "PROFILE: use %mysql/%postgresql (or matching) in "
            "application-*.properties — never @IfBuildProfile/@Profile on beans.",
        )
    if oc in {"build_config", "pom"}:
        out = [c for c in out if not c.startswith("RESIDUE:")]
        out.append(
            "BUILD_CONFIG: edit only declared config operands; no src_code "
            "without typed needs_input / Lead rescope."
        )
        out.append(
            "FOUNDATION: assert build_resolves/config_profile_load — never "
            "quarkus_compile; do not invent Application.java."
        )
    rest_hint = oc in {"src_code", "rest", "api"} or "controller" in oc
    if rest_hint:
        out.append(
            "CORS: do not implement @CrossOrigin or CORS filters. Platform/infra "
            "only — typed needs_input if blocked."
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
            f"(Architect E-20260811T200911Z / .hermes/skills/sdd/check-spec-readiness/references/body-integrity.md)",
            file=sys.stderr,
        )
        return 1

    injected = standard_constraints(sid, oc, body)
    body["constraints"] = injected
    if "body" in raw and isinstance(raw["body"], dict):
        raw["body"] = body
        out_doc = raw
    else:
        out_doc = body
    body_path.write_text(json.dumps(out_doc, indent=2) + "\n", encoding="utf-8")
    # F2 — every --inject leaves an auditable receipt (not silent nursing).
    try:
        from injection_receipt import write_injection_receipt
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from injection_receipt import write_injection_receipt
    receipt = write_injection_receipt(
        root,
        script="assert-mint-constraints-complete.py",
        target=body_path,
        fields=["constraints"],
        source=(
            f"standard_constraints(story_id={sid or '?'}, "
            f"operand_class={oc}) — F3 class/write-set signals"
        ),
        summary=f"injected standard constraints n={len(injected)}",
        extra={"n": len(injected), "operand_class": oc},
    )
    print(
        f"OK: injected standard constraints n={len(injected)} story={sid or '?'} "
        f"operand_class={oc} → {body_path}"
    )
    print(f"OK: injection receipt → {receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
