#!/usr/bin/env python3
"""ADR-31 — project pre-verified evidence anchors for M1 PROFILE.

Architecture (same family as ADR-26 / G4):

  The seat must **select** an evidence anchor, not **discover** line numbers.
  Harness-owned facts (legacy file structure + findings IR incidents) are
  projected into DERIVED FACTS. Invented path:line:token pairs that are not
  in the projected set are **unrepresentable** at apply-time
  (F-anchor-membership) — not merely filtered at rubric time.

Anchor kinds (specimen-agnostic):
  - declaration — Java type declaration line (class/interface/enum/record)
  - annotation  — annotation lines immediately preceding the type decl
  - import      — import lines (capped)
  - finding     — kantra/IR incident line on the unit's legacy_path whose
                  token is verified to resolve on that line

Every projected anchor is verified with profile_roles.evidence_resolves
before it is offered. The falsifier F-evidence-resolves stays; membership
makes failure hard to express for honest seats.

Commands:
  profile_anchors.py project --root DIR [--legacy PATH] [--fqn FQN]
  profile_anchors.py member  --root DIR --path P --line N --token T [--fqn FQN]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SCHEMA = "profile-anchors/v1"

_TYPE_DECL = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|sealed|non-sealed|static|\s)+)"
    r"(?P<kind>class|interface|enum|record)\s+(?P<name>\w+)",
)
_ANNOTATION = re.compile(r"^\s*(?P<anno>@[A-Za-z_][\w.]*)")
_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?(?P<imp>[\w.*]+)\s*;")
_PACKAGE = re.compile(r"^\s*package\s+(?P<pkg>[\w.]+)\s*;")

# Cap projected anchors per unit so DERIVED FACTS stay tight (O-CTX).
_MAX_FINDING = 4
_MAX_IMPORT = 2
_MAX_ANNOTATION = 6
_MAX_TOTAL = 10


def resolve_legacy_root(root: Path, legacy: Optional[str] = None) -> Path:
    """Workspace: sibling `legacy/`. Fixture: sources under `root/src`."""
    if legacy:
        return Path(legacy).resolve()
    sibling = (root.parent / "legacy").resolve()
    if sibling.is_dir() and sibling != root.resolve():
        return sibling
    if (root / "src").is_dir():
        return root.resolve()
    return root.resolve()


def _read_lines(fp: Path) -> list[str]:
    try:
        return fp.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def is_generated_build_path(path: str) -> bool:
    """O-SCOPENOGEN / ADR-38 — never project cites into build outputs."""
    p = (path or "").replace("\\", "/").lower()
    if not p:
        return False
    return (
        "/target/" in f"/{p}"
        or p.startswith("target/")
        or "/build/" in f"/{p}"
        or p.startswith("build/")
    )


def snippet_at_path_line(
    root: Path,
    path: str,
    line: int,
    *,
    legacy: Optional[str] = None,
    legacy_root: Optional[Path] = None,
    before: int = 2,
    after: int = 2,
) -> Optional[str]:
    """ADR-38 — render source lines around path:line for M2/M3 projection.

    Returns a compact numbered block, or None if the cite is unresolvable /
    generated. Callers must omit the cite from the packet when None (no
    'allow read' escape — F-no-discovery).
    """
    lp = (path or "").replace("\\", "/").lstrip("./")
    if not lp or is_generated_build_path(lp):
        return None
    try:
        lineno = int(line)
    except (TypeError, ValueError):
        return None
    if lineno < 1:
        return None
    lr = legacy_root or resolve_legacy_root(root, legacy)
    fp = _resolve_unit_file(lr, lp)
    if fp is None:
        return None
    lines = _read_lines(fp)
    if not lines or lineno > len(lines):
        return None
    start = max(1, lineno - max(0, before))
    end = min(len(lines), lineno + max(0, after))
    out: list[str] = []
    for i in range(start, end + 1):
        out.append(f"L{i}:{lines[i - 1]}")
    return "\n".join(out)


def _looks_like_openapi_dto(legacy_path: str, fqn: str = "") -> bool:
    """OpenAPI *Dto types often exist only under target/generated-sources/openapi."""
    lp = (legacy_path or "").replace("\\", "/")
    base = Path(lp).name
    blob = f"{lp} {fqn}".lower()
    if not base.endswith("Dto.java"):
        return False
    return "/dto/" in f"/{lp.lower()}" or ".dto." in blob


def _openapi_dto_search_roots(legacy_root: Path) -> list[Path]:
    """Roots that may hold target/generated-sources/openapi.

    Outer-loop often passes ``…/legacy/src`` into profile-rubric while OpenAPI
    codegen writes under ``…/legacy/target/generated-sources/…`` (sibling of
    ``src``). Search the given root and its parent when the root is named
    ``src`` (O-PROFDTOANCHOR / O-PROFDTOLEGACYSRC).
    """
    roots: list[Path] = []
    if legacy_root.is_dir():
        roots.append(legacy_root)
    if legacy_root.name == "src":
        parent = legacy_root.parent
        if parent.is_dir() and parent not in roots:
            roots.append(parent)
    return roots


def _resolve_openapi_dto_file(legacy_root: Path, legacy_path: str) -> Optional[Path]:
    """O-PROFDTOANCHOR — resolve *Dto.java under generated-sources/openapi|swagger."""
    base = Path((legacy_path or "").replace("\\", "/")).name
    if not base.lower().endswith("dto.java"):
        return None
    for root in _openapi_dto_search_roots(legacy_root):
        for p in root.rglob(base):
            if not p.is_file():
                continue
            parts_l = [x.lower() for x in p.parts]
            if "generated-sources" not in parts_l:
                continue
            if "openapi" in parts_l or "swagger" in parts_l:
                return p
    return None


def _resolve_unit_file(
    legacy_root: Path, legacy_path: str, *, fqn: str = ""
) -> Optional[Path]:
    lp = (legacy_path or "").replace("\\", "/").lstrip("./")
    if not lp:
        return None
    candidates = [
        legacy_root / lp,
        legacy_root / lp[len("src/") :] if lp.startswith("src/") else None,
    ]
    for c in candidates:
        if c is not None and c.is_file():
            return c
    base = Path(lp).name
    if legacy_root.is_dir() and base:
        for p in legacy_root.rglob(base):
            if "target" in p.parts or "build" in p.parts:
                continue
            if p.is_file():
                return p
    # O-PROFDTOANCHOR: OpenAPI DTOs are build outputs but still profile units.
    if _looks_like_openapi_dto(lp, fqn):
        return _resolve_openapi_dto_file(legacy_root, lp)
    return None


def _token_on_line(body: str) -> Optional[str]:
    """Pick a stable substring token from a source line (generic Java)."""
    s = body.strip()
    if not s or s.startswith("//") or s.startswith("*") or s.startswith("/*"):
        return None
    m = _ANNOTATION.match(s)
    if m:
        return m.group("anno")
    m = _TYPE_DECL.match(s)
    if m:
        return m.group("name")
    m = _IMPORT.match(s)
    if m:
        imp = m.group("imp")
        # Prefer the simple type name for `import a.b.C` (not wildcards).
        if not imp.endswith(".*"):
            return imp.rsplit(".", 1)[-1]
        return imp
    m = _PACKAGE.match(s)
    if m:
        return m.group("pkg")
    # Fallback: first Java identifier ≥ 2 chars (skip keywords-only lines).
    ids = re.findall(r"\b[A-Za-z_][\w]{1,}\b", s)
    skip = {
        "public",
        "private",
        "protected",
        "static",
        "final",
        "abstract",
        "class",
        "interface",
        "enum",
        "record",
        "return",
        "new",
        "void",
        "int",
        "long",
        "boolean",
        "if",
        "else",
        "for",
        "while",
        "try",
        "catch",
        "throws",
        "extends",
        "implements",
        "import",
        "package",
    }
    for i in ids:
        if i not in skip:
            return i
    return None


def _verified(
    legacy_root: Path, path: str, line: int, token: str, kind: str, note: str = ""
) -> Optional[dict[str, Any]]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from profile_roles import evidence_resolves  # type: ignore

    ev = {"path": path, "line": int(line), "token": token}
    ok, _why = evidence_resolves(legacy_root, ev)
    if not ok:
        return None
    out: dict[str, Any] = {
        "path": path,
        "line": int(line),
        "token": token,
        "kind": kind,
    }
    if note:
        out["note"] = note
    return out


def _structural_anchors(
    legacy_root: Path,
    legacy_path: str,
    simple_name: str,
    *,
    fqn: str = "",
) -> list[dict[str, Any]]:
    fp = _resolve_unit_file(legacy_root, legacy_path, fqn=fqn)
    if fp is None:
        return []
    lines = _read_lines(fp)
    if not lines:
        return []
    path = legacy_path.replace("\\", "/").lstrip("./")
    decl_idx: Optional[int] = None
    for i, body in enumerate(lines):
        m = _TYPE_DECL.match(body)
        if m and (not simple_name or m.group("name") == simple_name or not simple_name):
            # Prefer the type whose name matches the unit simple name.
            if simple_name and m.group("name") != simple_name:
                continue
            decl_idx = i
            break
    if decl_idx is None:
        # Fallback: first type declaration in file.
        for i, body in enumerate(lines):
            if _TYPE_DECL.match(body):
                decl_idx = i
                break
    out: list[dict[str, Any]] = []
    if decl_idx is not None:
        body = lines[decl_idx]
        m = _TYPE_DECL.match(body)
        token = (m.group("name") if m else _token_on_line(body)) or simple_name
        if token:
            # Cite logical legacy_path (not target/…); O-PROFDTOANCHOR lets
            # evidence_resolves open generated-sources/openapi for *Dto.java.
            a = _verified(legacy_root, path, decl_idx + 1, token, "declaration")
            if a:
                out.append(a)
        # Annotations immediately above the declaration (contiguous).
        annos: list[dict[str, Any]] = []
        j = decl_idx - 1
        while j >= 0 and len(annos) < _MAX_ANNOTATION:
            raw = lines[j]
            if not raw.strip() or raw.strip().startswith("//"):
                j -= 1
                continue
            am = _ANNOTATION.match(raw)
            if not am:
                break
            a = _verified(
                legacy_root, path, j + 1, am.group("anno"), "annotation"
            )
            if a:
                annos.append(a)
            j -= 1
        out.extend(reversed(annos))
    # A few imports (often cite javax→jakarta / framework types).
    imports: list[dict[str, Any]] = []
    for i, body in enumerate(lines):
        if len(imports) >= _MAX_IMPORT:
            break
        im = _IMPORT.match(body)
        if not im:
            continue
        tok = _token_on_line(body)
        if not tok:
            continue
        a = _verified(legacy_root, path, i + 1, tok, "import")
        if a:
            imports.append(a)
    out.extend(imports)
    return out


def _finding_anchors(
    root: Path, legacy_root: Path, legacy_path: str, finding_ids: list[str]
) -> list[dict[str, Any]]:
    """Project IR incidents on this path whose line resolves to a token."""
    path = legacy_path.replace("\\", "/").lstrip("./")
    want = set(finding_ids or [])
    ir_path = root / "migration" / "findings.json"
    if not ir_path.is_file():
        # Fallback: rebuild attempt is out of scope here — empty is honest.
        return []
    try:
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for rule in ir.get("rules") or []:
        rid = rule.get("id") or ""
        if want and rid not in want:
            # Still allow incidents on this exact path even if unit.findings
            # is stale — path match is the bind key (ADR-24).
            pass
        for inc in rule.get("incidents") or []:
            if len(out) >= _MAX_FINDING:
                return out
            lp = (inc.get("legacy_path") or "").replace("\\", "/").lstrip("./")
            if lp != path:
                continue
            try:
                line = int(inc.get("line"))
            except (TypeError, ValueError):
                continue
            if line < 1:
                continue
            fp = _resolve_unit_file(legacy_root, path)
            if fp is None:
                continue
            lines = _read_lines(fp)
            if line > len(lines):
                continue
            tok = _token_on_line(lines[line - 1])
            if not tok:
                continue
            a = _verified(
                legacy_root,
                path,
                line,
                tok,
                "finding",
                note=rid or "finding",
            )
            if a:
                # Dedup by path:line:token
                key = (a["path"], a["line"], a["token"])
                if any(
                    (x["path"], x["line"], x["token"]) == key for x in out
                ):
                    continue
                out.append(a)
    return out


def anchors_for_unit(
    root: Path,
    unit: dict[str, Any],
    *,
    legacy: Optional[str] = None,
    legacy_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Compute the pre-verified anchor set for one profile unit."""
    lr = legacy_root or resolve_legacy_root(root, legacy)
    lp = (unit.get("legacy_path") or "").replace("\\", "/").lstrip("./")
    fqn = unit.get("legacy_fqn") or unit.get("key") or ""
    simple = fqn.rsplit(".", 1)[-1] if fqn else Path(lp).stem
    if not lp.endswith(".java"):
        return []
    structural = _structural_anchors(lr, lp, simple, fqn=fqn)
    findings = _finding_anchors(root, lr, lp, list(unit.get("findings") or []))
    # Prefer declaration + findings + annotations; cap total.
    merged: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def _add(a: dict[str, Any]) -> None:
        key = (a["path"], a["line"], a["token"])
        if key in seen:
            return
        seen.add(key)
        merged.append(a)

    for a in structural:
        if a.get("kind") == "declaration":
            _add(a)
    for a in findings:
        _add(a)
    for a in structural:
        if a.get("kind") != "declaration":
            _add(a)
    return merged[:_MAX_TOTAL]


def anchors_by_fqn(
    root: Path,
    *,
    legacy: Optional[str] = None,
    units: Optional[list[dict]] = None,
) -> dict[str, list[dict[str, Any]]]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import load, profile_units  # type: ignore

    model_units = units if units is not None else profile_units(load(root))
    lr = resolve_legacy_root(root, legacy)
    out: dict[str, list[dict[str, Any]]] = {}
    for u in model_units:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        out[fqn] = anchors_for_unit(root, u, legacy_root=lr)
    return out


def evidence_in_anchor_set(
    evidence: dict[str, Any], anchors: list[dict[str, Any]]
) -> bool:
    """F-anchor-membership — exact path:line:token ∈ projected set."""
    try:
        path = (evidence.get("path") or "").replace("\\", "/").lstrip("./")
        line = int(evidence.get("line"))
        token = (evidence.get("token") or "").strip()
    except (TypeError, ValueError):
        return False
    if not path or line < 1 or not token:
        return False
    for a in anchors:
        ap = (a.get("path") or "").replace("\\", "/").lstrip("./")
        if ap == path and int(a.get("line") or 0) == line and (a.get("token") or "").strip() == token:
            return True
    return False


def format_anchors_block(anchors: list[dict[str, Any]], indent: str = "    ") -> list[str]:
    if not anchors:
        return [
            f"{indent}anchors: NONE — file missing or unscannable; "
            f"cannot invent evidence"
        ]
    lines = [
        f"{indent}anchors (pre-verified — SELECT one; do not invent line/token):"
    ]
    for a in anchors:
        note = a.get("note") or a.get("kind") or ""
        lines.append(
            f"{indent}  L{a['line']}  {a['token']}  [{note}]"
        )
    return lines


def project_text_for_units(
    root: Path,
    units: list[dict[str, Any]],
    *,
    legacy: Optional[str] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return fqn → anchors for the units about to be projected."""
    lr = resolve_legacy_root(root, legacy)
    out: dict[str, list[dict[str, Any]]] = {}
    for u in units:
        fqn = u.get("legacy_fqn") or u.get("key") or "?"
        out[fqn] = anchors_for_unit(root, u, legacy_root=lr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-31 profile evidence anchors")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("project")
    p.add_argument("--root", default=".")
    p.add_argument("--legacy", default="")
    p.add_argument("--fqn", default="")
    m = sub.add_parser("member")
    m.add_argument("--root", default=".")
    m.add_argument("--legacy", default="")
    m.add_argument("--fqn", required=True)
    m.add_argument("--path", required=True)
    m.add_argument("--line", type=int, required=True)
    m.add_argument("--token", required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    legacy = args.legacy or None
    if args.cmd == "project":
        mapping = anchors_by_fqn(root, legacy=legacy)
        if args.fqn:
            mapping = {args.fqn: mapping.get(args.fqn) or []}
        print(json.dumps({"schema": SCHEMA, "units": mapping}, indent=2))
        return 0
    if args.cmd == "member":
        mapping = anchors_by_fqn(root, legacy=legacy)
        anchors = mapping.get(args.fqn) or []
        ev = {"path": args.path, "line": args.line, "token": args.token}
        ok = evidence_in_anchor_set(ev, anchors)
        print("MEMBER" if ok else "NOT_MEMBER", args.fqn, f"{args.path}:{args.line}:{args.token}")
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
