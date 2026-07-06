#!/usr/bin/env python3
"""Block risky OpenShift commands unless the project cluster guard matches."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


COMMAND_KEYS = {"cmd", "command", "shellCommand", "shell_command"}
MUTATING_OC = re.compile(
    r"\b(?:oc|kubectl)\s+"
    r"(?:apply|create|delete|patch|replace|scale|adm|annotate|label|rollout|edit|expose|set)\b"
)
MUTATING_SCRIPT = re.compile(
    r"(?:^|\s)(?:\./)?(?:"
    r"scripts/bootstrap\.sh|"
    r"scripts/resume-gpu-demo\.sh|"
    r"[^\s;]*deploy\.sh|"
    r"[^\s;]*upload-to-minio\.sh|"
    r"[^\s;]*run-guidellm-load-test\.sh"
    r")\b"
)
DRY_RUN = re.compile(r"--dry-run(?:=|\s)")
INLINE_EXPECTED = re.compile(r"\b(RHOAI_EXPECTED_API_SERVER|RHOAI_EXPECTED_CLUSTER)=([^\s;]+)")
INLINE_ALLOW = re.compile(r"\bRHOAI_ALLOW_UNGUARDED_CLUSTER=(true|1|yes)\b", re.I)


def command_values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in COMMAND_KEYS and isinstance(item, str):
                yield item
            else:
                yield from command_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from command_values(item)


def read_command_text() -> str:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return ""
    text = "\n".join(command_values(payload))
    if text.lstrip().startswith("*** Begin Patch"):
        return ""
    return text


def read_guard_from_env_file(repo_root: Path) -> dict[str, str]:
    result = {}
    env_file = repo_root / ".env"
    if not env_file.exists():
        return result

    for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {
            "RHOAI_EXPECTED_API_SERVER",
            "RHOAI_EXPECTED_CLUSTER",
            "RHOAI_ALLOW_UNGUARDED_CLUSTER",
            "KUBECONFIG",
        }:
            continue
        result[key] = value.strip().strip('"').strip("'")
    return result


def current_api_server(kubeconfig: str = "") -> str:
    env = os.environ.copy()
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig
    try:
        completed = subprocess.run(
            ["oc", "whoami", "--show-server"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            env=env,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def block(message: str) -> None:
    payload = {
        "continue": False,
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }
    print(json.dumps(payload))
    print(message, file=sys.stderr)
    sys.exit(2)


def main() -> int:
    command_text = read_command_text()
    if not command_text:
        return 0

    mutating = bool(MUTATING_OC.search(command_text) or MUTATING_SCRIPT.search(command_text))
    if MUTATING_OC.search(command_text) and DRY_RUN.search(command_text):
        mutating = False
    if not mutating:
        return 0

    repo_root = Path.cwd()
    try:
        repo_root = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], text=True, timeout=3
            ).strip()
        )
    except Exception:
        pass

    file_guard = read_guard_from_env_file(repo_root)
    inline_expected = ""
    inline_match = INLINE_EXPECTED.search(command_text)
    if inline_match:
        inline_expected = inline_match.group(2).strip('"').strip("'")

    expected = (
        inline_expected
        or os.environ.get("RHOAI_EXPECTED_API_SERVER")
        or os.environ.get("RHOAI_EXPECTED_CLUSTER")
        or file_guard.get("RHOAI_EXPECTED_API_SERVER")
        or file_guard.get("RHOAI_EXPECTED_CLUSTER")
        or ""
    )
    allow_unguarded = (
        INLINE_ALLOW.search(command_text)
        or os.environ.get("RHOAI_ALLOW_UNGUARDED_CLUSTER", "").lower() in {"true", "1", "yes"}
        or file_guard.get("RHOAI_ALLOW_UNGUARDED_CLUSTER", "").lower() in {"true", "1", "yes"}
    )

    if not expected and not allow_unguarded:
        block(
            "Blocked OpenShift mutation: set RHOAI_EXPECTED_API_SERVER in this project's .env "
            "before running deployment, bootstrap, or resource-management commands."
        )

    server = current_api_server(file_guard.get("KUBECONFIG", ""))
    if expected and not server:
        block("Blocked OpenShift mutation: unable to verify current oc API server.")
    if expected and expected not in server:
        block(
            "Blocked OpenShift mutation: current oc API server does not match "
            "RHOAI_EXPECTED_API_SERVER for this project."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
