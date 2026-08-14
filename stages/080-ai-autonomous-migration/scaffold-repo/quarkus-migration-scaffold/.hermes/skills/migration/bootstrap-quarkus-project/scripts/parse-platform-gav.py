#!/usr/bin/env python3
"""Parse Red Hat Quarkus platform GAV from .hermes/pins.yaml."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow import from .hermes/lib when invoked as a script
_ROOT_CANDIDATES = [
    Path(__file__).resolve().parents[4],  # …/scaffold/.hermes/skills/migration/bootstrap…/scripts
]
# scripts → bootstrap → migration → skills → .hermes → scaffold = parents[5]?
# path: scaffold/.hermes/skills/migration/bootstrap-quarkus-project/scripts/parse-platform-gav.py
# parents[0]=scripts [1]=bootstrap [2]=migration [3]=skills [4]=.hermes [5]=scaffold
_SCAFFOLD = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_SCAFFOLD / ".hermes" / "lib"))
from pins import quarkus_platform_gav  # noqa: E402


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("Parse Red Hat Quarkus platform GAV from .hermes/pins.yaml.")
        print("usage: parse-platform-gav.py [<scaffold-root>]")
        return 0
    root = Path(sys.argv[1] if len(sys.argv) > 1 else _SCAFFOLD).resolve()
    # Accept legacy path arg pointing at old `.hermes/pins.yaml` — treat as root parent search
    if root.is_file() and root.name.endswith(".md"):
        # walk up for .hermes/pins.yaml
        cur = root.parent
        while cur != cur.parent:
            if (cur / ".hermes" / "pins.yaml").is_file():
                root = cur
                break
            cur = cur.parent
    try:
        print(quarkus_platform_gav(root))
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
