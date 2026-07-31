#!/usr/bin/env python3
"""O-ACCEPTGEN — acceptance proof shape from migration.yaml.

Path was already parameterized; collection/service/endpointEnv/itemType
were Coolstore-hardcoded in sensors and the ship counter. Specimens set
acceptance.collection (and friends) here; Coolstore defaults apply only
when collection is omitted or remains ``products``.
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

# Coolstore-shaped defaults — used only when collection is products/absent.
_PRODUCTS_DEFAULTS = {
    "collection": "products",
    "service": "CatalogService",
    "endpointEnv": "CATALOG_ENDPOINT",
    "itemType": "Product",
    "idFields": ["itemId", "id", "item_id"],
    "mockClass": "MockCatalogService",
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
            # inline list: [a, b] or leave for yaml path
            inner = val.strip("[]")
            data[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
            continue
        if val == "" or val == "|" or val == ">":
            continue
        data[key] = val.strip("\"'")
    return data


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
    else:
        base = {
            "collection": collection,
            "service": "",
            "endpointEnv": "",
            "itemType": "",
            "idFields": ["id", "itemId"],
            "mockClass": "",
        }
    for key in ("path", "service", "endpointEnv", "itemType", "mockClass", "collection"):
        if raw.get(key) not in (None, ""):
            base[key] = str(raw[key])
    if isinstance(raw.get("idFields"), list) and raw["idFields"]:
        base["idFields"] = [str(x) for x in raw["idFields"]]
    base.setdefault("path", "")
    return base


def _getter(collection: str) -> str:
    if not collection:
        return "getProducts"
    return "get" + collection[0].upper() + collection[1:]


def proof_ere(cfg: dict) -> str:
    """Extended regex for grep -E — any catalog/collection proof token."""
    col = cfg["collection"]
    getter = _getter(col)
    parts = [re.escape(col) + r"\(", re.escape(getter) + r"\("]
    if cfg.get("service"):
        parts.append(re.escape(cfg["service"]))
    if cfg.get("endpointEnv"):
        parts.append(re.escape(cfg["endpointEnv"]))
    if cfg.get("itemType"):
        parts.append(r"List<.*" + re.escape(cfg["itemType"]))
    return "|".join(parts)


def return_ere(cfg: dict) -> str:
    col = cfg["collection"]
    getter = _getter(col)
    return (
        r"return[[:space:]]+.*\b("
        + re.escape(col)
        + r"|"
        + re.escape(getter)
        + r")\s*\(|return[[:space:]]+"
        + re.escape(col)
        + r"\b"
    )


def export_shell(cfg: dict) -> str:
    lines = [
        f"ACC_COLLECTION={shlex.quote(cfg['collection'])}",
        f"ACC_SERVICE={shlex.quote(cfg.get('service') or '')}",
        f"ACC_ENDPOINT_ENV={shlex.quote(cfg.get('endpointEnv') or '')}",
        f"ACC_ITEM_TYPE={shlex.quote(cfg.get('itemType') or '')}",
        f"ACC_MOCK_CLASS={shlex.quote(cfg.get('mockClass') or '')}",
        f"ACC_GETTER={shlex.quote(_getter(cfg['collection']))}",
        f"ACC_PROOF_RE={shlex.quote(proof_ere(cfg))}",
        f"ACC_RETURN_RE={shlex.quote(return_ere(cfg))}",
        f"ACC_ID_FIELDS={shlex.quote(','.join(cfg.get('idFields') or []))}",
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
