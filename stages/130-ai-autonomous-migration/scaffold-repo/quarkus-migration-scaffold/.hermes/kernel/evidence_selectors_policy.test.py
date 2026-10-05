#!/usr/bin/env python3
"""F2 / release-plan item 5: the evidence selectors through the ACTUAL tool policy.

Owner run 89 (architect diagnosis): a 308K kanban_show result spilled to a file whose preview recommended
execute_code, which the harness refuses; the inline-Python alternative was refused too. c9ab129d added
bounded selectors and names them in the K2 refusal. Here, on a loop card of the implementer profile:

  1. the refusal of inline Python is taken from kernel/pre_tool_call.sh itself, and the selector commands
     it recommends are built from ITS text (placeholders filled with this card's real spill file, field
     and obligation id) -- not from a list written in this test;
  2. each of those exact commands passes the same hook (no block of any kind);
  3. each is then executed as the worker would run it, and retrieves what it promises: one field of a
     one-line ~300K spill with honest truncation metadata, the assigned scenario's evidence (mode,
     source and destination body paths, candidate binding, differing subtree, state prerequisites), and
     a bounded card view;
  4. inline Python and execute_code stay refused on that card.

This shows the retrieval path is allowed and works. It does not show, and is not claimed to show, that
the model stops looping.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/kernel/evidence_selectors_policy.test.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
HERMES = KERNEL.parent
HOOK = KERNEL / "pre_tool_call.sh"
TASK = "t_loopcard"
SPILL_REL = ".hermes/home/profiles/implementer/cache/spillover/chatcmpl-tool-ad9ae7cbbcd2a84f.txt"
ITEM = "parity:4a43e638d94c08fb"


def hook(cmd: str, root: Path, env: dict, tool: str = "terminal", extra_input: dict | None = None) -> dict:
    e = dict(os.environ, K2_ALLOW_ROOT=str(root), **env)
    payload = {"tool_name": tool, "tool_input": dict({"command": cmd}, **(extra_input or {})), "cwd": str(root)}
    p = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload), text=True, capture_output=True, env=e, check=False)
    return json.loads((p.stdout or "").strip() or "{}")


class EvidenceSelectorsUnderK2(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix="k2-selectors-")
        root = self.root = Path(self.td.name).resolve() / "modernized"
        (root / ".hermes").mkdir(parents=True)
        for name in ("skills", "lib", "kernel", "planning"):
            if (HERMES / name).exists():
                (root / ".hermes" / name).symlink_to(HERMES / name)
        files = {
            # the issued loop card (the inline-Python rule applies to it)
            "verification/loop/issued.json": {"schema": "rhoai3.loop-issued/v1", "task_id": TASK, "cluster": "c:215b"},
            # the enabled corpus: the read was captured AFTER an unselected delete (the v29 Owner shape)
            "verification/scenarios-enabled/corpus.json": {"scenarios": [
                {"id": "sc:auth-allowed-delete-visits-1", "method": "DELETE", "path": "/api/visits/1", "reset_before": True},
                {"id": "sc:auth-allowed-read-api-owners", "method": "GET", "path": "/api/owners", "reset_before": False}]},
            "verification/source-oracles/scenarios-enabled/sc_auth-allowed-read-api-owners.json": {},
            "verification/parity/scenarios-enabled/sc_auth-allowed-read-api-owners.json": {
                "verdict": "FAIL", "binding": {"mode": "candidate", "candidate_sha256": "c" * 64}},
            "evidence/planning/worklist.json": {"candidate_sha256": "c" * 64, "items": [{
                "id": ITEM, "kind": "parity", "source": "parity", "security_mode": "enabled",
                "scenario": "sc:auth-allowed-read-api-owners", "path": "src/main/java/p/OwnerRestController.java",
                "advice": {"body_diff": {"differences": [{"path": "$[*].pets[*].visits", "kind": "length",
                                                          "observed": 2, "expected": 1}]}}}], "clusters": []},
        }
        for rel, doc in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(json.dumps(doc), encoding="utf-8")
        for rel in ("verification/source-oracles/scenarios-enabled/bodies/sc_auth-allowed-read-api-owners/response.body",
                    "verification/parity/scenarios-enabled/_bodies/sc_auth-allowed-read-api-owners/response.body"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("[]", encoding="utf-8")
        # the saved large-show shape, one line, ~300K: a short body, 86 machine comments, a large worker context
        self.show = {"task": {"id": TASK, "title": "M3 BEHAVIOR -- Owner", "body": "Owner behaviour card. " * 20},
                     "comments": [{"id": i, "body": "[native-control] " + json.dumps({"kind": "accept-evaluated", "n": i,
                                                                                        "pad": "x" * 1800})} for i in range(86)],
                     "worker_context": "y" * 74000}
        spill = root / SPILL_REL
        spill.parent.mkdir(parents=True, exist_ok=True)
        spill.write_text(json.dumps(self.show), encoding="utf-8")
        assert "\n" not in spill.read_text() and len(spill.read_text()) > 200000
        self.env = {"HERMES_PROFILE": "implementer", "HERMES_KANBAN_TASK": TASK, "K2_BOUND_GATE_EXIT": "0"}

    def tearDown(self):
        self.td.cleanup()

    def recommended(self) -> list[str]:
        """The selector commands the hook's own refusal names, placeholders filled for this card."""
        r = hook('python3 -c "import json; print(json.load(open(\'%s\'))[\'task\'][\'body\'])"' % SPILL_REL, self.root, self.env)
        self.assertEqual(r.get("action"), "block", r)
        msg = r.get("message") or ""
        self.assertIn("inline python refused on a loop card", msg)
        m = re.search(r"(python3 \S+/brief\.py --root \.) --card", msg)
        self.assertTrue(m, msg)
        base = m.group(1)
        opts = re.findall(r"(--card|--item <id>|--spill <file> --field <path>)", msg)
        self.assertEqual(opts, ["--card", "--item <id>", "--spill <file> --field <path>"], msg)
        fill = {"<id>": ITEM, "<file>": SPILL_REL, "<path>": "task.body"}
        out = []
        for o in opts:
            for k, v in fill.items():
                o = o.replace(k, v)
            out.append("%s %s" % (base, o))
        return out

    def execute(self, cmd: str) -> str:
        p = subprocess.run(["bash", "-c", cmd], cwd=str(self.root), text=True, capture_output=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **self.env), check=False)
        self.assertEqual(p.returncode, 0, (cmd, p.stdout[-2000:], p.stderr[-2000:]))
        return p.stdout

    def test_the_recommended_selectors_pass_the_hook_and_retrieve_the_evidence(self):
        cmds = self.recommended()
        for c in cmds:
            r = hook(c, self.root, self.env)
            self.assertNotEqual(r.get("action"), "block", (c, r))
        card, item, spill = cmds
        # one field of the spill, whole and marked not truncated
        got = json.loads(self.execute(spill))
        self.assertEqual((got["value"], got["truncated"], got["total_chars"]),
                         (self.show["task"]["body"], False, len(self.show["task"]["body"])))
        # a large field of the same spill is bounded and says so (the same selector, another field)
        big_cmd = spill.replace("--field task.body", "--field comments --limit 3000")
        self.assertNotEqual(hook(big_cmd, self.root, self.env).get("action"), "block")
        big = json.loads(self.execute(big_cmd))
        self.assertEqual((big["truncated"], big["length"], big["shown_chars"]), (True, 86, 3000))
        self.assertGreater(big["total_chars"], 150000)
        # the assigned scenario's evidence in its mode: both bodies, binding, difference, prerequisites
        ev = self.execute(item)
        for must in ("(enabled mode)",
                     "verification/source-oracles/scenarios-enabled/bodies/sc_auth-allowed-read-api-owners/response.body",
                     "verification/parity/scenarios-enabled/_bodies/sc_auth-allowed-read-api-owners/response.body",
                     "bound to candidate cccccccccccc", "differs at $[*].pets[*].visits: length",
                     "sc:auth-allowed-delete-visits-1 DELETE /api/visits/1"):
            self.assertIn(must, ev)
        # the bounded card view runs under the same policy (no native board in this fixture: it says so briefly)
        view = self.execute(card)
        self.assertLess(len(view), 3000)
        self.assertIn("no native card here", view)          # the board-backed view is brief.test.py's card_view case

    def test_inline_python_and_execute_code_stay_refused(self):
        for cmd in ("python3 -c \"print(open('%s').read()[:100])\"" % SPILL_REL,
                    "python3 - <<'PY'\nimport json\nprint(json.load(open('%s'))['task'])\nPY" % SPILL_REL):
            r = hook(cmd, self.root, self.env)
            self.assertEqual(r.get("action"), "block", (cmd, r))
            self.assertIn("inline python", r.get("message") or "")
        r = hook("", self.root, self.env, tool="execute_code", extra_input={"code": "print(1)"})
        self.assertEqual(r.get("action"), "block", r)


if __name__ == "__main__":
    unittest.main(verbosity=1)
