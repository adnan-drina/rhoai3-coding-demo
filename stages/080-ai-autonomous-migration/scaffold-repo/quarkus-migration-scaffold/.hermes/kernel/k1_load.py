#!/usr/bin/env python3
"""K1 loader — one unwrap. Read a body JSON file; optional digest sidecar.

Does not import hermes_cli.create_task. Does not freeze a Hermes card id.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_body(path: Path) -> dict[str, Any]:
    """Load one body object. Wrapper {body: {...}} is the only allowed unwrap."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("body"), dict):
        return data["body"]
    if isinstance(data, dict):
        return data
    raise ValueError("BODY_SCHEMA: body file must be a JSON object")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def sidecar_path(body_path: Path) -> Path:
    return body_path.with_suffix(body_path.suffix + ".sha256")


def stamp_sidecar(body_path: Path) -> str:
    digest = digest_file(body_path)
    sidecar_path(body_path).write_text(digest + "\n", encoding="utf-8")
    return digest


def read_sidecar(body_path: Path) -> str | None:
    sp = sidecar_path(body_path)
    if not sp.is_file():
        return None
    return sp.read_text(encoding="utf-8").strip().lower()
