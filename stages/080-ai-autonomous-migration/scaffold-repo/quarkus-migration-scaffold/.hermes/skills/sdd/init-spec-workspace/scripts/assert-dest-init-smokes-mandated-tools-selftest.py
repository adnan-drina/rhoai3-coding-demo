#!/usr/bin/env python3
"""Control: shim-only dest-init REFUSE; live GitOps dest-init must PASS after W1.

Architect ``20003309ZA``: walking parents for ``gitops/`` cannot succeed on a
dest pod (``/projects/modernized`` has no workshop tree). Shim-only REFUSE
runs everywhere. GitOps PASS is workshop-only; skip-by-name when absent,
do not FAIL.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
CHECKER = HERE.parent / "assert-dest-init-smokes-mandated-tools.py"


def gitops_from(start: Path) -> Path | None:
    """Workshop GitOps dest-init. Absent on a dest pod (no gitops/ above /projects)."""
    needle = (
        Path("gitops")
        / "stages/050-advanced-app-platform/base/devspaces"
        / "maas-api-key-provisioning.yaml"
    )
    for parent in start.parents:
        cand = parent / needle
        if cand.is_file():
            return cand
    return None


def _gitops() -> Path | None:
    return gitops_from(HERE)


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path)],
        text=True,
        capture_output=True,
    )


def _shim_only_must_refuse() -> int | None:
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
    return None


def main() -> int:
    err = _shim_only_must_refuse()
    if err is not None:
        return err
    with tempfile.TemporaryDirectory() as tmp:
        dest_shaped = Path(tmp) / "projects" / "modernized" / "scripts" / "selftest.py"
        dest_shaped.parent.mkdir(parents=True)
        dest_shaped.write_text("# dest pod has no gitops/ above modernized\n")
        if gitops_from(dest_shaped) is not None:
            return _fail("dest-shaped parents must not find workshop GitOps")
    gitops = _gitops()
    if gitops is None:
        print(
            "OK: dest-init specify smoke selftest "
            "(shim-only REFUSE; GitOps skipped — not in this tree)"
        )
        return 0
    proc = _run(gitops)
    blob = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return _fail("live dest-init must PASS after W1 smoke: %s" % blob)
    print("OK: dest-init specify smoke selftest (shim-only REFUSE; live PASS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
