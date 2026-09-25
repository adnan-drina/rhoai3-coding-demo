"""Which call paths report usage, and which does Hermes record? Real kanban worker, token mode, producer config."""
import json, os, sqlite3, sys, tempfile, time
from pathlib import Path
import yaml
sys.path.insert(0, "/Users/adrina/Sandbox/rhoai3-coding-demo/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/tests/rhoai3_b3b4")
from fake_openai_server import FakeProvider
home = Path(tempfile.mkdtemp(prefix="usage-")); os.environ["HERMES_HOME"] = str(home); os.environ["HOME"] = str(home / "u"); (home / "u").mkdir()
for k in [k for k in os.environ if k.endswith("_API_KEY")]: os.environ.pop(k)
repo = home / "repo"; repo.mkdir()
led = home / "state" / "tokens.log"
os.environ.update(RHOAI3_ACCOUNTING_MODE="token", RHOAI3_TOKEN_BUDGET="51000000/3600", RHOAI3_TOKEN_RESERVATION="262144", RHOAI3_REQUEST_LEDGER=str(led), HERMES_KANBAN_CRASH_GRACE_SECONDS="0")
cfg = json.load(open("/Users/adrina/Sandbox/rhoai3-coding-demo/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/tests/rhoai3_b3b4/worker_config.json"))
cfg["terminal"]["cwd"] = str(repo); cfg["skills"]["external_dirs"] = []
partial = '{"path": "a.txt", "content": "par'
script = [("tool", "terminal", {"command": "echo a"}, {"prompt_tokens": 180000, "completion_tokens": 100}),
          ("text", "## Goal\nsummary", {"prompt_tokens": 20000, "completion_tokens": 1500}),
          ("truncated_tool", "write_file", partial),
          ("http", 429, {"Retry-After": "1"}, {"error": {"message": "slow", "type": "x"}}),
          ("tool", "kanban_complete", {"summary": "done"}, {"prompt_tokens": 5000, "completion_tokens": 200}),
          ("text", "done", {"prompt_tokens": 5100, "completion_tokens": 50})]
with FakeProvider(script) as fp:
    os.environ["MAAS_API_BASE_URL"] = fp.base_url; os.environ["MAAS_API_KEY"] = "sk-fake-0000000000"
    prof = home / "profiles" / "implementer"; prof.mkdir(parents=True)
    (prof / "config.yaml").write_text(yaml.safe_dump(cfg)); (home / "config.yaml").write_text(yaml.safe_dump(cfg))
    from hermes_cli import kanban_db as kb
    kb.init_db(); conn = kb.connect()
    tid = kb.create_task(conn, title="usage", body="x", assignee="implementer", workspace_kind="dir", workspace_path=str(repo))
    kb.dispatch_once(conn); pid = kb.get_task(conn, tid).worker_pid
    while True:
        w, st = os.waitpid(pid, os.WNOHANG)
        if w: break
        time.sleep(0.2)
    print("task", kb.get_task(conn, tid).status)
    reqs = fp.chat_requests()
    for i, r in enumerate(reqs):
        kind = "main" if r.get("tools") else "aux"
        print("REQ", i, kind, "stream", r.get("stream"), "include_usage", (r.get("stream_options") or {}).get("include_usage"), "usage_sent", r.get("_usage_sent"))
    sent_total = sum((u["prompt_tokens"] + u["completion_tokens"]) for u in (r.get("_usage_sent") for r in reqs) if u)
print("provider-reported total (all responses with usage):", sent_total)
for line in led.read_text().splitlines(): print("LEDGER", line[:120])
for db in home.rglob("state.db"):
    c = sqlite3.connect(db); c.row_factory = sqlite3.Row
    try:
        rows = c.execute("SELECT model, task, api_call_count, input_tokens, output_tokens FROM session_model_usage").fetchall()
        print("STATE", db, [dict(r) for r in rows])
    except Exception as e:
        print("STATE", db, e)
