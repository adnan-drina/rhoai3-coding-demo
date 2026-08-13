#!/usr/bin/env python3
"""AD-S — when HERMES_HOME is relocated, require both skills dirs on external_dirs.

Idle when HERMES_HOME unset or equals ~/.hermes.

Reads HERMES_CONFIG / HERMES_MANAGED_DIR / HERMES_HOME from the environment,
falling back to <root>/.hermes/home/config.yaml then ~/.hermes/config.yaml.

Usage:
  python3 check-external-dirs.py                 # assert against current dir
  python3 check-external-dirs.py /path/to/repo   # explicit workspace root
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

EXIT_CODES = """\
Exit codes:
  0  pass — skills.external_dirs lists both the project and the home skills
     dir; also printed when HERMES_HOME is unset or equals ~/.hermes (idle)
  1  BLOCK — HERMES_HOME is relocated and either no config.yaml was found, or
     external_dirs omits the project / home skills dir (FAIL: on stderr)
  2  usage error (bad/unknown arguments; emitted by argparse)
"""


def is_relocated() -> bool:
    hh = os.environ.get("HERMES_HOME")
    if not hh:
        return False
    try:
        return Path(hh).resolve() != (Path.home() / ".hermes").resolve()
    except Exception:
        return True


def config_paths(root: Path) -> list[Path]:
    out: list[Path] = []
    if os.environ.get("HERMES_CONFIG"):
        out.append(Path(os.environ["HERMES_CONFIG"]))
    if os.environ.get("HERMES_MANAGED_DIR"):
        out.append(Path(os.environ["HERMES_MANAGED_DIR"]) / "config.yaml")
    if os.environ.get("HERMES_HOME"):
        out.append(Path(os.environ["HERMES_HOME"]) / "config.yaml")
    out.append(root / ".hermes/home/config.yaml")
    out.append(Path.home() / ".hermes/config.yaml")
    return out


def parse_external_dirs(text: str) -> list[str]:
    dirs: list[str] = []
    in_block = False
    for raw in text.splitlines():
        ln = raw.split("#", 1)[0].rstrip()
        if re.search(r"external_dirs\s*:", ln):
            in_block = True
            rest = ln.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                for part in rest[1:-1].split(","):
                    part = part.strip().strip("\"'")
                    if part:
                        dirs.append(part)
                in_block = False
            continue
        if not in_block:
            continue
        m = re.match(r"^\s*-\s+(.+)$", ln)
        if m:
            dirs.append(m.group(1).strip().strip("\"'"))
            continue
        if ln.strip() and not ln.startswith(" ") and not ln.startswith("\t"):
            in_block = False
    return dirs


def expand(p: str, root: Path) -> Path:
    s = os.path.expandvars(os.path.expanduser(p))
    path = Path(s)
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    return path


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="workspace root to assert against (default: current directory)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not is_relocated():
        print("OK: HERMES_HOME not relocated — external_dirs assert idle")
        return 0

    cfg = next((c for c in config_paths(root) if c.is_file()), None)
    if cfg is None:
        print(
            "FAIL: HERMES_HOME relocated but no config.yaml found for "
            "skills.external_dirs assert (AD-S / no-compromise)",
            file=sys.stderr,
        )
        return 1

    dirs = parse_external_dirs(cfg.read_text(encoding="utf-8"))
    expanded = [expand(d, root) for d in dirs]
    need_project = (root / ".hermes/skills").resolve()
    need_home = (Path.home() / ".hermes/skills").resolve()

    missing = []
    if need_project not in expanded:
        missing.append(str(need_project))
    if need_home not in expanded:
        missing.append(str(need_home))
    if missing:
        print(
            f"FAIL: {cfg}: skills.external_dirs missing {missing} "
            f"(need project + Path.home skills when HERMES_HOME relocated)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: external_dirs lists project + home skills ({cfg})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
