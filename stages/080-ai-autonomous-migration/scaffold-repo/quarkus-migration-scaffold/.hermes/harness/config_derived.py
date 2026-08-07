#!/usr/bin/env python3
"""O-CONFIGDERIVED / F-config-derived — config values must match legacy or a declared transform.

Architecture (not a ship hack): every migrated properties key that has a
legacy counterpart must either (a) carry the legacy value (normalized), or
(b) be listed under migration.yaml ``configTransforms:`` as a declared
rename/value map. Undeclared drift REDs.

Scope (O-CONFIGDERIVEDPROD / W4-676): the fabrication class lives on
**unprofiled + %prod** keys (W4-631 specimen). ``%dev`` / ``%test`` Quarkus
local overrides (e.g. H2) are WARN-only — not undeclared drift of the
production contract.

Opus W4-675 amendment (accepted):
  - RED  — prod/unprofiled value differs from legacy with no declared transform
  - WARN — carried-verbatim secret in %prod, or %prod URL pointing at localhost;
           also %dev/%test divergences from legacy

Usage:
  python3 config_derived.py [--root DIR] [--legacy DIR] [--yaml PATH]
Exit 0 when no RED; 1 when refuse cases exist.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_KEY_MAP: dict[str, str] = {
    "spring.datasource.url": "quarkus.datasource.jdbc.url",
    "spring.datasource.username": "quarkus.datasource.username",
    "spring.datasource.password": "quarkus.datasource.password",
    "spring.datasource.driver-class-name": "quarkus.datasource.jdbc.driver",
    "server.servlet.context-path": "quarkus.http.root-path",
    "server.port": "quarkus.http.port",
}

_SECRET_BARE = re.compile(r"(?i)(password|secret|api[_-]?key|token|credential)$")
# Spring / legacy server.* keys must not be re-introduced into Quarkus
# application.properties as a "preserve token" greenwash (W4-676/677).
_FORBIDDEN_NS_RE = re.compile(r"(?i)^(?:%[^.]+\.)?(spring\.|server\.)")


def _strip_profile(key: str) -> tuple[str, str]:
    m = re.match(r"^%([^.]+)\.(.+)$", key.strip())
    if m:
        return m.group(1), m.group(2)
    return "", key.strip()


def _norm_val(v: str) -> str:
    """Normalize for compare — trailing slash on paths; strip whitespace."""
    s = (v or "").strip()
    if s.startswith("/") and len(s) > 1 and s.endswith("/"):
        return s.rstrip("/")
    return s


def _load_props(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _load_all_props(resources: Path) -> dict[str, str]:
    merged: dict[str, str] = {}
    if not resources.is_dir():
        return merged
    merged.update(_load_props(resources / "application.properties"))
    for p in sorted(resources.glob("application-*.properties")):
        merged.update(_load_props(p))
    return merged


def _parse_yaml_transforms(
    yaml_text: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse configTransforms: (not valueTransforms / preserve arrows).

    Returns (transforms, identity_errors). Identity valueMap entries are
    refused (O-CONFIGNOIDENT / W4-677 §3.2) — they only silence the differ.
    """
    out: dict[str, dict[str, Any]] = {}
    identity_errors: list[str] = []
    lines = yaml_text.splitlines()
    i = 0

    def _commit(frm: str, to: str, vmap: dict[str, str], reason: str) -> None:
        cleaned: dict[str, str] = {}
        for vk, vv in vmap.items():
            # Identity = textual silence (same after whitespace strip), NOT
            # path-normalization equivalence. `/petclinic/` → `/petclinic` is a
            # real transform that _norm_val collapses for drift compare only
            # (O-CONFIGNOIDENT / W4-680).
            if (vk or "").strip() == (vv or "").strip():
                identity_errors.append(
                    f"CONFIGDERIVED: identity valueMap {frm} {vk!r}->{vv!r} "
                    f"(O-CONFIGNOIDENT / F-config-transform)"
                )
            else:
                cleaned[vk] = vv
        # reason is required for honesty (W4-677 §3.1 / W4-680 §2) — empty is
        # not a RED (schema soft), but callers/instruments assert presence.
        out[frm] = {"to": to, "valueMap": cleaned, "reason": reason}

    while i < len(lines):
        if re.match(r"^configTransforms:\s*$", lines[i]):
            i += 1
            cur_from = ""
            cur_to = ""
            cur_reason = ""
            value_map: dict[str, str] = {}
            in_vmap = False
            while i < len(lines):
                ln = lines[i]
                if re.match(r"^[A-Za-z]", ln):
                    break
                m_from = re.match(r"^\s*-\s*from:\s*(\S+)\s*$", ln)
                m_to = re.match(r"^\s*to:\s*(\S+)\s*$", ln)
                m_reason = re.match(r"^\s*reason:\s*[\"']?(.*?)[\"']?\s*$", ln)
                m_vmap = re.match(r"^\s*valueMap:\s*$", ln)
                m_vpair = re.match(r"^\s+(\S+):\s*(.+?)\s*$", ln)
                if m_from:
                    if cur_from and cur_to:
                        _commit(cur_from, cur_to, value_map, cur_reason)
                    cur_from = m_from.group(1)
                    cur_to = ""
                    cur_reason = ""
                    value_map = {}
                    in_vmap = False
                elif m_to and cur_from:
                    cur_to = m_to.group(1)
                    in_vmap = False
                elif m_reason and cur_from and not in_vmap:
                    cur_reason = (m_reason.group(1) or "").strip()
                elif m_vmap and cur_from:
                    in_vmap = True
                elif in_vmap and m_vpair and not m_vpair.group(1).startswith("-"):
                    vk = m_vpair.group(1).strip().strip("'\"")
                    vv = m_vpair.group(2).strip().strip("'\"")
                    value_map[vk] = vv
                i += 1
            if cur_from and cur_to:
                _commit(cur_from, cur_to, value_map, cur_reason)
            continue
        i += 1
    return out, identity_errors



def _legacy_lookup(legacy: dict[str, str], bare: str) -> str | None:
    if bare in legacy:
        return legacy[bare]
    for k, v in legacy.items():
        _p, b = _strip_profile(k)
        if b == bare:
            return v
    return None


def check(
    *,
    root: Path,
    legacy_root: Path,
    yaml_path: Path,
) -> tuple[list[str], list[str]]:
    reds: list[str] = []
    warns: list[str] = []
    dest_res = root / "src" / "main" / "resources"
    leg_res = legacy_root / "src" / "main" / "resources"
    if not leg_res.is_dir():
        return reds, warns
    dest = _load_all_props(dest_res)
    legacy = _load_all_props(leg_res)
    if not dest or not legacy:
        return reds, warns

    key_map = dict(DEFAULT_KEY_MAP)
    value_maps: dict[str, dict[str, str]] = {}
    if yaml_path.is_file():
        declared, ident_errs = _parse_yaml_transforms(
            yaml_path.read_text(encoding="utf-8", errors="replace")
        )
        reds.extend(ident_errs)
        for frm, meta in declared.items():
            if frm.startswith("__"):
                continue
            to = str(meta.get("to") or "").strip()
            if to:
                key_map[frm] = to
                vm = meta.get("valueMap") or {}
                if isinstance(vm, dict) and vm:
                    value_maps[frm] = {
                        str(k): str(v)
                        for k, v in vm.items()
                        if not str(k).startswith("__IDENT__")
                    }

    rev = {v: k for k, v in key_map.items()}

    # O-CONFIGNOSPRING: refuse Spring keys reintroduced into Quarkus props
    for dest_key in sorted(dest):
        if _FORBIDDEN_NS_RE.match(dest_key):
            reds.append(
                f"CONFIGDERIVED: {dest_key} uses forbidden spring.*/server.* namespace in Quarkus resources — "
                f"declare configTransforms: / keep quarkus.* only "
                f"(O-CONFIGNOSPRING / F-config-transform)"
            )

    for dest_key, dest_val in sorted(dest.items()):
        if _FORBIDDEN_NS_RE.match(dest_key):
            continue
        prof, dest_bare = _strip_profile(dest_key)
        legacy_bare = rev.get(dest_bare)
        if not legacy_bare:
            if dest_bare in legacy or any(
                _strip_profile(k)[1] == dest_bare for k in legacy
            ):
                legacy_bare = dest_bare
            else:
                continue
        leg_val = _legacy_lookup(legacy, legacy_bare)
        if leg_val is None:
            continue
        allowed = {_norm_val(leg_val)}
        vm = value_maps.get(legacy_bare) or {}
        for k, v in vm.items():
            allowed.add(_norm_val(v))
            allowed.add(_norm_val(k))
        if leg_val in vm:
            allowed.add(_norm_val(vm[leg_val]))
        dest_n = _norm_val(dest_val)
        if dest_n == _norm_val(leg_val) or dest_n in allowed:
            if prof == "prod":
                bare_leaf = dest_bare.split(".")[-1]
                if _SECRET_BARE.search(bare_leaf) or _SECRET_BARE.search(dest_bare):
                    warns.append(
                        f"CONFIGDERIVED WARN: {dest_key} carries a secret value in %prod "
                        f"(inherited hygiene — not fabrication; O-CONFIGDERIVED)"
                    )
                if "localhost" in dest_val.lower() or "127.0.0.1" in dest_val:
                    warns.append(
                        f"CONFIGDERIVED WARN: {dest_key}={dest_val!r} points at localhost "
                        f"in %prod (inherited hygiene; O-CONFIGDERIVED)"
                    )
            continue

        msg = (
            f"CONFIGDERIVED: {dest_key}={dest_val!r} ≠ legacy {legacy_bare}={leg_val!r} "
            f"with no declared value transform (O-CONFIGDERIVED / F-config-derived)"
        )
        # O-CONFIGDERIVEDPROD: only unprofiled + %prod are RED; dev/test WARN.
        if prof in ("dev", "test"):
            warns.append(msg.replace("CONFIGDERIVED:", "CONFIGDERIVED WARN (dev/test):", 1))
        else:
            reds.append(msg)
    return reds, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument("--legacy", default="", help="Legacy app root")
    ap.add_argument("--yaml", default="migration.yaml", type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    if args.legacy:
        legacy = Path(args.legacy).resolve()
    else:
        candidates = [
            Path("/projects/legacy"),
            root.parent / "legacy",
            root / "legacy",
        ]
        legacy = next((c for c in candidates if c.is_dir()), candidates[0])
    yaml_path = args.yaml if args.yaml.is_absolute() else root / args.yaml
    reds, warns = check(root=root, legacy_root=legacy, yaml_path=yaml_path)
    for w in warns:
        print(w)
    for p in reds:
        print(p)
    if reds:
        print(f"CONFIGDERIVED RED: {len(reds)} undeclared drift(s)", file=sys.stderr)
        return 1
    if warns:
        print(
            f"CONFIGDERIVED GREEN with {len(warns)} WARN(s)",
            file=sys.stderr,
        )
    else:
        print("CONFIGDERIVED GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
