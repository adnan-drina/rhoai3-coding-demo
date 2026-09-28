"""Shared dest-root and hermes-lib bootstrap for paved-road-m5 CLIs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


def root_parser(description: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--root", required=True, type=Path)
    return ap


def dump(doc: dict) -> None:
    print(json.dumps(doc, indent=2, sort_keys=True))
