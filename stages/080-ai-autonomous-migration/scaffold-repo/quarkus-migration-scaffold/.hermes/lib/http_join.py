#!/usr/bin/env python3
"""HTTP join — inventory HTTP denominator + story.endpoints ∩ inventory rows.

Split from specimen_agnostic.py / check-partition-coverage.py (TR-3). Not a skill.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from inventory_io import inventory_http_expected


def endpoint_tokens(ep: str) -> set[str]:
    """Transcribed story.endpoints tokens (path-only or METHOD path). Not mint."""
    s = " ".join(str(ep).split())
    out = {s} if s else set()
    parts = s.split(" ", 1)
    if len(parts) == 2 and parts[1].strip():
        out.add(parts[1].strip())
    return out


def row_tokens(row: dict) -> set[str]:
    method = str(row.get("http_method") or "").strip().upper()
    path = str(row.get("http_path") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    out: set[str] = set()
    if path:
        out.add(path)
        if method:
            out.add(f"{method} {path}")
    if symbol:
        out.add(symbol)
    return {x for x in out if x}


def story_claims_http(story: dict, row: dict) -> bool:
    wanted: set[str] = set()
    for ep in story.get("endpoints") or []:
        wanted |= endpoint_tokens(str(ep))
    return bool(wanted & row_tokens(row))
