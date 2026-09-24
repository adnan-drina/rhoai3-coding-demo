#!/usr/bin/env python3
"""Render the worker config.yaml exactly as the Stage 050 producer builds it.

Extracts the Python heredoc from
gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml
(HERMESEOF block) up to the end of the ``cfg = {...}`` literal and executes
only that prefix with placeholder environment values. The model-profile
table is read from the committed
gitops/stages/050-advanced-app-platform/base/devspaces/model-profiles.json
(the producer's platform-table path is redirected to it). Nothing is written to
the managed dir, no hooks are installed, no network is touched.

Usage: render_worker_config.py <repo-root> <out.json> [base_url] [api_key]
The JSON keeps ``${env:...}`` references exactly as the producer emits them.
"""
import json
import os
import sys
import textwrap
from pathlib import Path

PRODUCER = "gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml"
PROFILES = "gitops/stages/050-advanced-app-platform/base/devspaces/model-profiles.json"
PINNED_PROFILE = "/etc/rhoai3/run-control/profile.json"
PLATFORM_PROFILE = "/etc/rhoai3/model-profiles/model-profiles.json"
START = "<<'HERMESEOF'"
STOP = 'if os.environ.get("HERMES_MINIMAX") == "1":'


def render(repo_root: Path, base_url: str = "http://127.0.0.1:1/v1", api_key: str = "sk-fake-0000") -> dict:
    lines = (repo_root / PRODUCER).read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if START in l) + 1
    stop = next(i for i in range(start, len(lines)) if lines[i].strip() == STOP)
    src = textwrap.dedent("\n".join(lines[start:stop]))
    # The producer loads the model-profile table from the run's pinned copy or
    # the platform ConfigMap mount. Point both at the committed source file
    # (gitops .../devspaces/model-profiles.json); refuse if the producer no
    # longer reads them, so a producer change cannot silently bypass the table.
    for literal in (PINNED_PROFILE, PLATFORM_PROFILE):
        if src.count(repr(literal).replace("'", '"')) != 1:
            raise SystemExit(f"render: producer no longer reads {literal}")
    src = src.replace('"%s"' % PINNED_PROFILE, repr(str(repo_root / "nonexistent-pinned-profile.json")))
    src = src.replace('"%s"' % PLATFORM_PROFILE, repr(str(repo_root / PROFILES)))
    env = {
        "HERMES_MANAGED_DIR": "/nonexistent/managed",
        "HERMES_SKILLS_DIR": "/nonexistent/skills",
        "HERMES_GLOBAL_SKILLS_DIR": "/nonexistent/global-skills",
        "MAAS_API_BASE_URL": base_url,
        "MAAS_API_KEY": api_key,
    }
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        scope: dict = {}
        exec(compile(src, PRODUCER + ":HERMESEOF", "exec"), scope)
        return scope["cfg"]
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    cfg = render(root, *sys.argv[3:5])
    out.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out} ({len(cfg)} top-level keys)")
