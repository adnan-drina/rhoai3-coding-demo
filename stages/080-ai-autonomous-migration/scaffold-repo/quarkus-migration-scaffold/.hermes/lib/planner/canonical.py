"""Canonical JSON and content digests for the five planner artifacts.

Canonical form: UTF-8, ``sort_keys=True``, ``separators=(",", ":")``,
``ensure_ascii=True``, one trailing newline. A digest is the SHA-256 of
those bytes. Two runs that agree on content agree byte-for-byte.

Excluded from any digested authority (SAD §6): hostnames, timestamps,
tool-internal IDs, LLM text. Producers keep such observations under an
``observations`` key that ``strip_observations`` removes before hashing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OBSERVATION_KEYS = frozenset({"observations", "observed_at", "hostname", "pid"})
SHA256_HEX = 64


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def canonical_text(obj: Any) -> str:
    return canonical_bytes(obj).decode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(obj: Any) -> str:
    """Digest of the canonical form after stripping observations."""
    return sha256_bytes(canonical_bytes(strip_observations(obj)))


def strip_observations(obj: Any) -> Any:
    """Return a copy without observation-only keys at any depth."""
    if isinstance(obj, dict):
        return {
            k: strip_observations(v)
            for k, v in obj.items()
            if k not in OBSERVATION_KEYS
        }
    if isinstance(obj, list):
        return [strip_observations(v) for v in obj]
    return obj


def sort_unique(items: Any) -> list:
    """Deterministic list: sorted, duplicates removed, stable for scalars."""
    out = sorted({str(x) for x in (items or []) if str(x).strip()})
    return out


def write_canonical(path: Path, obj: Any) -> str:
    """Write canonical bytes and return their digest (of the stripped form)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(obj))
    return digest(obj)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != SHA256_HEX:
        return False
    return all(c in "0123456789abcdef" for c in value)
