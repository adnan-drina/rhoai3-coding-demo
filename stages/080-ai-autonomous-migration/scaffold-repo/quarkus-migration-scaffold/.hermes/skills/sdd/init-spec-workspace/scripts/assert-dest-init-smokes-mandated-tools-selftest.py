#!/usr/bin/env python3
"""Control: shim-only dest-init REFUSE; live GitOps dest-init must PASS after W1."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
CHECKER = HERE.parent / "assert-dest-init-smokes-mandated-tools.py"


def _gitops() -> Path | None:
    needle = (
        Path("gitops")
        / "stages/050-advanced-app-platform/base/devspaces"
        / "maas-api-key-provisioning.yaml"
    )
    for parent in HERE.parents:
        cand = parent / needle
        if cand.is_file():
            return cand
    return None


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path)],
        text=True,
        capture_output=True,
    )


def main() -> int:
    shim_only = (
        "specify_helper = os.path.join(project, 'specify-from-project.sh')\n"
        "with open(specify_wrap, 'w') as fh:\n"
        "    fh.write('exec bash helper --root project \"$@\"\\n')\n"
        "print('specify PATH shim: ' + specify_wrap)\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(shim_only)
        tmp = Path(fh.name)
    try:
        proc = _run(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return _fail("shim-only dest-init must REFUSE: %s" % blob)
    if "SPECIFY_REAL" not in blob and "specify init" not in blob:
        return _fail("shim-only must name SPECIFY_REAL or specify init gap: %s" % blob)
    gitops = _gitops()
    if gitops is None:
        return _fail("GitOps dest-init missing above %s" % HERE)
    proc = _run(gitops)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("live dest-init must PASS after W1 smoke: %s" % blob)
    print("OK: dest-init specify smoke selftest (shim-only REFUSE; live PASS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
