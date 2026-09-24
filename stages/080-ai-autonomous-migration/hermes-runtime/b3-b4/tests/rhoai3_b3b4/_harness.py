"""Shared harness: the real Stage 050 worker config, a real kanban worker, a fake provider.

``worker_config.json`` is rendered from the Stage 050 producer by
``b3-b4/render_worker_config.py`` (repo-relative:
gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml,
HERMESEOF block). It keeps the producer's ``${env:MAAS_API_BASE_URL}`` /
``${env:MAAS_API_KEY}`` references; tests point them at the loopback fake.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
WORKER_CONFIG = json.loads((HERE / "worker_config.json").read_text())

# The Qwen3.8-27B non-thinking row exactly as the producer declares it
# (providers.qwen38.extra_body), plus the model block's output cap.
NONTHINKING_ROW = {
    "chat_template_kwargs": {"enable_thinking": False},
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5,
    "repetition_penalty": 1.0,
}
MODEL_ID = "qwen3-8-27b-int4"
OUTPUT_CAP = 8192
# model-profiles.json quota.max_output_tokens: the largest output any request
# may carry (main-path truncation retries reach it; auxiliary slots declare it).
AUX_OUTPUT_CAP = 32768


def worker_config(repo: Path | None = None) -> dict:
    cfg = copy.deepcopy(WORKER_CONFIG)
    if repo is not None:
        cfg["terminal"]["cwd"] = str(repo)
    # Test HERMES_HOME has no managed skills tree.
    cfg["skills"]["external_dirs"] = []
    return cfg


def clean_env(monkeypatch, provider) -> None:
    for key in [k for k in os.environ if k.endswith("_API_KEY")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MAAS_API_BASE_URL", provider.base_url)
    monkeypatch.setenv("MAAS_API_KEY", "sk-fake-0000000000")
    monkeypatch.setenv("HERMES_KANBAN_CRASH_GRACE_SECONDS", "0")


def write_home(cfg: dict, profile: str | None = "implementer") -> Path:
    home = Path(os.environ["HERMES_HOME"])
    (home / "config.yaml").write_text(yaml.safe_dump(cfg))
    if profile:
        pdir = home / "profiles" / profile
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "config.yaml").write_text(yaml.safe_dump(cfg))
    return home


def run_cli_query(query: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """`hermes chat -q <query> -Q` in a subprocess, same interpreter/tree as the test."""
    return subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "chat", "-q", query, "-Q"],
        env=dict(os.environ), cwd=os.environ["HERMES_HOME"],
        capture_output=True, text=True, timeout=timeout,
    )


def wait_exit(pid: int, timeout: float = 300) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        wpid, status = os.waitpid(pid, os.WNOHANG)
        if wpid:
            return status
        time.sleep(0.2)
    os.kill(pid, 9)
    raise AssertionError(f"worker pid {pid} did not exit within {timeout}s")


def dispatch_and_reap(kb, conn, tid) -> int:
    res = kb.dispatch_once(conn)
    assert [s[0] for s in res.spawned] == [tid], f"expected {tid} to be spawned, got {res}"
    pid = kb.get_task(conn, tid).worker_pid
    status = wait_exit(pid)
    kb._record_worker_exit(pid, status)
    return os.waitstatus_to_exitcode(status)


def events(conn, tid):
    return [(r["kind"], json.loads(r["payload"]) if r["payload"] else {})
            for r in conn.execute(
                "SELECT kind, payload FROM task_events WHERE task_id = ? ORDER BY id", (tid,))]


def runs(conn, tid):
    return [dict(r) for r in conn.execute(
        "SELECT id, status, outcome, error, metadata FROM task_runs WHERE task_id = ? ORDER BY id", (tid,))]


def agent_requests(provider):
    """Main-agent chat requests (auxiliary calls carry no tools)."""
    return [r for r in provider.chat_requests() if r.get("tools")]


def wire_fields(body: dict) -> dict:
    """The JSON body minus conversation content and recorder bookkeeping."""
    return {k: v for k, v in body.items() if k not in ("messages", "tools") and not k.startswith("_")}


def profile_mismatches(body: dict) -> list[str]:
    """Differences between a request body and the declared non-thinking row."""
    out = []
    for key, want in NONTHINKING_ROW.items():
        if key not in body:
            out.append(f"{key}: missing")
        elif body[key] != want:
            out.append(f"{key}: expected {want!r}, got {body[key]!r}")
    if "extra_body" in body:
        out.append("extra_body: arrived nested instead of merged into the body")
    return out
