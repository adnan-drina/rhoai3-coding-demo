#!/usr/bin/env python3
"""O-ACCEPTGEN / O-DEVDBURL — acceptance proof shape from migration.yaml.

Path was already parameterized; collection/service/endpointEnv/itemType
were Coolstore-hardcoded in sensors and the ship counter. Specimens set
acceptance.collection (and friends) here; Coolstore defaults apply only
when collection is omitted or remains ``products``.

Optional DB identity (R-83 P2 / O-DEVDBURL) — empty means sensors derive
from PROJECT_KEY (``${PROJECT_KEY}-postgres`` / ``${PROJECT_KEY}``):

    acceptance:
      dbService: myapp-postgres   # omit → ${PROJECT_KEY}-postgres
      dbName: myapp               # omit → ${PROJECT_KEY}

Bare-array specimens (Poll 81 / B1 — REST petclinic ``GET /petclinic/api/vets``
returns a top-level JSON array, not ``{vetList:[…]}``) set:

    acceptance:
      collection: _array
      getter: getAllVets
      service: ClinicService
      itemType: VetDto
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

# Sentinel: ship body must be a top-level JSON array (no collection key).
BARE_ARRAY = "_array"

# Coolstore-shaped defaults — used only when collection is products/absent.
_PRODUCTS_DEFAULTS = {
    "collection": "products",
    "service": "CatalogService",
    "endpointEnv": "CATALOG_ENDPOINT",
    "itemType": "Product",
    "idFields": ["itemId", "id", "item_id"],
    "mockClass": "MockCatalogService",
    "getter": "getProducts",
}


def _parse_simple(text: str) -> dict:
    data: dict = {}
    section = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^acceptance:\s*$", line):
            section = "acceptance"
            continue
        if re.match(r"^[a-zA-Z]", line) and not line.startswith(" "):
            section = None
            continue
        if section != "acceptance":
            continue
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "idFields":
            inner = val.strip("[]")
            data[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
            continue
        if val == "" or val == "|" or val == ">":
            continue
        data[key] = val.strip("\"'")
    return data


def is_bare_array(cfg: dict) -> bool:
    return str(cfg.get("collection") or "") == BARE_ARRAY


def load(path: str | Path = "migration.yaml") -> dict:
    p = Path(path)
    raw: dict = {}
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        if yaml is not None:
            doc = yaml.safe_load(text) or {}
            raw = dict(doc.get("acceptance") or {})
        else:
            raw = _parse_simple(text)
    collection = str(raw.get("collection") or _PRODUCTS_DEFAULTS["collection"])
    if collection == "products":
        base = dict(_PRODUCTS_DEFAULTS)
    elif collection == BARE_ARRAY:
        base = {
            "collection": BARE_ARRAY,
            "service": "",
            "endpointEnv": "",
            "itemType": "",
            "idFields": ["id"],
            "mockClass": "",
            "getter": "",
        }
    else:
        base = {
            "collection": collection,
            "service": "",
            "endpointEnv": "",
            "itemType": "",
            "idFields": ["id", "itemId"],
            "mockClass": "",
            "getter": "",
        }
    for key in ("path", "service", "endpointEnv", "itemType", "mockClass",
                "collection", "getter"):
        if raw.get(key) not in (None, ""):
            base[key] = str(raw[key])
    if isinstance(raw.get("idFields"), list) and raw["idFields"]:
        base["idFields"] = [str(x) for x in raw["idFields"]]
    if not base.get("getter"):
        base["getter"] = _getter(base["collection"], base)
    base.setdefault("path", "")
    # R-83 P2 / O-DEVDBURL — optional; empty → sensors use PROJECT_KEY defaults.
    base["dbService"] = str(raw["dbService"]) if raw.get("dbService") not in (None, "") else ""
    base["dbName"] = str(raw["dbName"]) if raw.get("dbName") not in (None, "") else ""
    return base


def _getter(collection: str, cfg: dict | None = None) -> str:
    cfg = cfg or {}
    if cfg.get("getter"):
        return str(cfg["getter"])
    if collection == BARE_ARRAY:
        return "getAll"
    if not collection:
        return "getProducts"
    return "get" + collection[0].upper() + collection[1:]


def proof_ere(cfg: dict) -> str:
    """Extended regex for grep -E — any collection proof token."""
    col = cfg["collection"]
    getter = _getter(col, cfg)
    parts: list[str] = [re.escape(getter) + r"\("]
    if col != BARE_ARRAY:
        parts.insert(0, re.escape(col) + r"\(")
    if cfg.get("service"):
        parts.append(re.escape(cfg["service"]))
    if cfg.get("endpointEnv"):
        parts.append(re.escape(cfg["endpointEnv"]))
    if cfg.get("itemType"):
        parts.append(r"List<.*" + re.escape(cfg["itemType"]))
        parts.append(r"Collection<.*" + re.escape(cfg["itemType"]))
    return "|".join(parts)


def return_ere(cfg: dict) -> str:
    col = cfg["collection"]
    getter = _getter(col, cfg)
    names = [getter]
    if col != BARE_ARRAY:
        names.append(col)
    alt = "|".join(re.escape(n) for n in names)
    return (
        r"return[[:space:]]+.*\b("
        + alt
        + r")\s*\(|return[[:space:]]+("
        + alt
        + r")\b"
    )


def export_shell(cfg: dict) -> str:
    label = "bare-array" if is_bare_array(cfg) else cfg["collection"]
    lines = [
        f"ACC_COLLECTION={shlex.quote(cfg['collection'])}",
        f"ACC_COLLECTION_LABEL={shlex.quote(label)}",
        f"ACC_BARE_ARRAY={'1' if is_bare_array(cfg) else '0'}",
        f"ACC_SERVICE={shlex.quote(cfg.get('service') or '')}",
        f"ACC_ENDPOINT_ENV={shlex.quote(cfg.get('endpointEnv') or '')}",
        f"ACC_ITEM_TYPE={shlex.quote(cfg.get('itemType') or '')}",
        f"ACC_MOCK_CLASS={shlex.quote(cfg.get('mockClass') or '')}",
        f"ACC_GETTER={shlex.quote(_getter(cfg['collection'], cfg))}",
        f"ACC_PROOF_RE={shlex.quote(proof_ere(cfg))}",
        f"ACC_RETURN_RE={shlex.quote(return_ere(cfg))}",
        f"ACC_ID_FIELDS={shlex.quote(','.join(cfg.get('idFields') or []))}",
        f"ACC_DB_SERVICE={shlex.quote(cfg.get('dbService') or '')}",
        f"ACC_DB_NAME={shlex.quote(cfg.get('dbName') or '')}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaml", default="migration.yaml")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--export-shell", action="store_true")
    args = ap.parse_args()
    cfg = load(args.yaml)
    if args.export_shell:
        sys.stdout.write(export_shell(cfg))
        return 0
    if args.json:
        json.dump(cfg, sys.stdout)
        sys.stdout.write("\n")
        return 0
    json.dump(cfg, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
