#!/usr/bin/env python3
"""O-ANALYZERPIN — stamp / read analyzer engine pins for findings JSON.

Sidecar files next to findings inventories:
  migration/mta-findings.engine
  migration/mta-findings-after.engine

Format (key=value lines):
  engine=kantra
  version=…
  mode=source-only
  bin=/path/to/kantra

migration.yaml ``analysis.engine`` is the contract default (kantra).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def engine_from_yaml(root: Path) -> str:
    myaml = root / "migration.yaml"
    if not myaml.is_file():
        return "kantra"
    try:
        text = myaml.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "kantra"
    # Prefer analysis: block engine
    m = re.search(
        r"(?ms)^analysis:\s*\n(?:^[ \t]+.*\n)*?[ \t]+engine:\s*['\"]?([A-Za-z0-9._-]+)",
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"(?m)^[ \t]+engine:\s*['\"]?([A-Za-z0-9._-]+)", text)
    return m.group(1).strip() if m else "kantra"


def pin_path(root: Path, kind: str) -> Path:
    if kind == "after":
        return root / "migration" / "mta-findings-after.engine"
    return root / "migration" / "mta-findings.engine"


def read_pin(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" not in ln or ln.strip().startswith("#"):
                continue
            k, _, v = ln.partition("=")
            out[k.strip()] = v.strip()
    except OSError:
        return {}
    return out


def stamp(
    root: Path,
    kind: str,
    *,
    engine: str | None = None,
    version: str = "",
    mode: str = "",
    bin_path: str = "",
    input_sha256: str = "",
) -> Path:
    eng = (engine or engine_from_yaml(root) or "kantra").strip()
    dest = pin_path(root, kind)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"engine={eng}",
        f"version={version}",
        f"mode={mode}",
        f"bin={bin_path}",
    ]
    if input_sha256:
        lines.append(f"input_sha256={input_sha256}")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def engines_match(root: Path) -> tuple[bool, str, str]:
    """Return (ok, before_engine, after_engine). Missing pins → ok (legacy)."""
    b = read_pin(pin_path(root, "before"))
    a = read_pin(pin_path(root, "after"))
    be = b.get("engine", "").strip()
    ae = a.get("engine", "").strip()
    if not be or not ae:
        return True, be, ae
    return be == ae, be, ae


def main() -> int:
    ap = argparse.ArgumentParser(description="O-ANALYZERPIN stamp/check")
    ap.add_argument("cmd", choices=("stamp", "check", "read"))
    ap.add_argument("--root", default=os.environ.get("FINDINGS_DELTA_ROOT", "."))
    ap.add_argument("--kind", choices=("before", "after"), default="before")
    ap.add_argument("--engine", default="")
    ap.add_argument("--version", default="")
    ap.add_argument("--mode", default="")
    ap.add_argument("--bin", dest="bin_path", default="")
    ap.add_argument("--input-sha256", default="")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.cmd == "stamp":
        p = stamp(
            root,
            args.kind,
            engine=args.engine or None,
            version=args.version,
            mode=args.mode,
            bin_path=args.bin_path,
            input_sha256=args.input_sha256,
        )
        print(f"ok:{p}")
        return 0
    if args.cmd == "read":
        pin = read_pin(pin_path(root, args.kind))
        print(pin.get("engine", "") or engine_from_yaml(root))
        return 0
    ok, be, ae = engines_match(root)
    if ok:
        print(f"ok:engine={be or ae or engine_from_yaml(root)}")
        return 0
    print(f"ENGINE-MISMATCH:before={be}:after={ae}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
