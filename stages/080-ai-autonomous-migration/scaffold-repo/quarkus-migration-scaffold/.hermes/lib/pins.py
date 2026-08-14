#!/usr/bin/env python3
"""Shared loader for .hermes/pins.yaml (no PyYAML dependency).

Minimal subset parser for our pins schema. Returns dict with
quarkus_platform / hermes_agent / spec_kit keys.
"""
from __future__ import annotations

import re
from pathlib import Path


def load_pins(root: Path) -> dict[str, dict[str, str]]:
    """Load pins from <root>/.hermes/pins.yaml."""
    path = root / ".hermes" / "pins.yaml"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m_sec = re.match(r"^  ([a-z_]+):\s*$", line)
        if m_sec:
            current = m_sec.group(1)
            out.setdefault(current, {})
            continue
        m_kv = re.match(r'^    ([a-z_]+):\s*"([^"]*)"\s*$', line)
        if m_kv and current:
            out[current][m_kv.group(1)] = m_kv.group(2)
            continue
        m_kv2 = re.match(r"^    ([a-z_]+):\s*([^#]+?)\s*$", line)
        if m_kv2 and current:
            out[current][m_kv2.group(1)] = m_kv2.group(2).strip().strip('"')
    return out


def quarkus_platform_gav(root: Path) -> str:
    pins = load_pins(root)
    qp = pins.get("quarkus_platform") or {}
    g = qp.get("group_id", "")
    a = qp.get("bom_artifact_id", "")
    v = qp.get("version", "")
    if not (g and a and v):
        raise ValueError("quarkus_platform incomplete in .hermes/pins.yaml")
    return f"{g}:{a}:{v}"


def quarkus_platform_props(root: Path) -> dict[str, str]:
    pins = load_pins(root)
    qp = pins.get("quarkus_platform") or {}
    return {
        "quarkus.platform.group-id": qp["group_id"],
        "quarkus.platform.artifact-id": qp["bom_artifact_id"],
        "quarkus.platform.version": qp["version"],
    }
