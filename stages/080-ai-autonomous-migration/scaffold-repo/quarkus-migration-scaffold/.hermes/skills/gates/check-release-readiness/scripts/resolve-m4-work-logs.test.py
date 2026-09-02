#!/usr/bin/env python3
"""Land-time tests for resolve-m4-work-logs (Operator 105656ZO)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOLVE = HERE / "resolve-m4-work-logs.py"


class ResolveM4WorkLogs(unittest.TestCase):
    def _run(self, env: dict[str, str], extra_files: dict[str, str] | None = None):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        home = tmp / "home"
        logs = home / "kanban" / "logs"
        logs.mkdir(parents=True)
        for name, body in (extra_files or {}).items():
            (logs / name).write_text(body, encoding="utf-8")
        merged = {
            **os.environ,
            "HERMES_HOME": str(home),
            **env,
        }
        for key in (
            "FENCE_EVASION_LOG",
            "FENCE_EVASION_LOGS",
            "HERMES_KANBAN_TASK",
            "HERMES_KANBAN_SHOW",
        ):
            if key not in env:
                merged.pop(key, None)
        return subprocess.run(
            [sys.executable, str(RESOLVE)],
            capture_output=True,
            text=True,
            env=merged,
            cwd=str(tmp),
        ), logs

    def test_missing_everything_refuses(self):
        proc, _ = self._run({})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REFUSE silent skip", proc.stderr)

    def test_single_log_without_task_is_land_time(self):
        tmp = Path(tempfile.mkdtemp())
        log = tmp / "benign.log"
        log.write_text("echo ok\n", encoding="utf-8")
        proc, _ = self._run({"FENCE_EVASION_LOG": str(log)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), str(log))

    def test_task_without_parents_refuses_own_log(self):
        show = Path(tempfile.mkdtemp()) / "show.py"
        show.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "tid = [a for a in sys.argv[1:] if not a.startswith('-')][0]\n"
            "print(json.dumps({'id': tid, 'parents': []}))\n",
            encoding="utf-8",
        )
        show.chmod(0o755)
        proc, logs = self._run(
            {
                "HERMES_KANBAN_TASK": "t_m4",
                "HERMES_KANBAN_SHOW": str(show),
            },
            extra_files={"t_m4.log": "verdict only\n"},
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("no parent work cards", proc.stderr)
        self.assertTrue((logs / "t_m4.log").is_file())

    def test_walk_parents_excludes_self(self):
        graph = {
            "t_m4": ["t_m3b", "t_m3a"],
            "t_m3b": ["t_m2", "t_m3a"],
            "t_m3a": ["t_m2"],
            "t_m2": ["t_m1"],
            "t_m1": [],
        }
        show = Path(tempfile.mkdtemp()) / "show.py"
        show.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "GRAPH = %s\n"
            "tid = [a for a in sys.argv[1:] if not a.startswith('-')][0]\n"
            "print(json.dumps({'id': tid, 'parents': GRAPH[tid]}))\n"
            % json.dumps(graph),
            encoding="utf-8",
        )
        show.chmod(0o755)
        files = {
            "t_m4.log": "verdict\n",
            "t_m3a.log": "story a\n",
            "t_m3b.log": "story b\n",
            "t_m2.log": "plan\n",
            "t_m1.log": "analyze\n",
        }
        proc, logs = self._run(
            {
                "HERMES_KANBAN_TASK": "t_m4",
                "HERMES_KANBAN_SHOW": str(show),
            },
            extra_files=files,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = [Path(p).name for p in proc.stdout.splitlines() if p.strip()]
        self.assertEqual(
            set(got),
            {"t_m3b.log", "t_m3a.log", "t_m2.log", "t_m1.log"},
        )
        self.assertNotIn("t_m4.log", got)
        self.assertIn(str(logs / "t_m1.log"), proc.stderr)

    def test_explicit_list_drops_self_and_requires_the_rest(self):
        tmp = Path(tempfile.mkdtemp())
        home = tmp / "home"
        logs = home / "kanban" / "logs"
        logs.mkdir(parents=True)
        (logs / "t_m4.log").write_text("verdict\n", encoding="utf-8")
        (logs / "work.log").write_text("ok\n", encoding="utf-8")
        env = {
            **os.environ,
            "HERMES_HOME": str(home),
            "HERMES_KANBAN_TASK": "t_m4",
            "FENCE_EVASION_LOGS": "%s:%s" % (logs / "t_m4.log", logs / "work.log"),
        }
        env.pop("FENCE_EVASION_LOG", None)
        env.pop("HERMES_KANBAN_SHOW", None)
        proc = subprocess.run(
            [sys.executable, str(RESOLVE)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = [p.strip() for p in proc.stdout.splitlines() if p.strip()]
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].endswith("work.log"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
