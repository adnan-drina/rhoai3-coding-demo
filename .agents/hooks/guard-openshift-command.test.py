"""Offline tests for the cluster command guard: the Cursor matcher and the guard's own verb detection."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("guard", HERE / "guard-openshift-command.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
MATCHER = re.compile(json.loads((HERE.parents[1] / ".cursor/hooks.json").read_text())
                     ["hooks"]["beforeShellExecution"][0]["matcher"])

MUTATING = [
    "oc patch application x -n openshift-gitops --type merge -p '{}'",
    "oc --request-timeout=10s patch application x",
    "oc -n demo-sandbox delete pod x",
    "kubectl --context prod --namespace a apply -f x.yaml",
    "cd repo && /usr/local/bin/oc scale deploy x --replicas=0",
    "oc --kubeconfig /tmp/k -n a annotate ns a x=y",
]
READ_ONLY = [
    "oc get pods -A",
    "oc -n demo-sandbox get pods",
    "oc --request-timeout=10s logs deploy/x",
    "oc whoami --show-server",
    "echo patch the doc about oc usage",
    "kubectl -n a describe pod delete-me",
]


class Guard(unittest.TestCase):
    def test_mutating_commands_with_global_options_are_detected(self):
        for command in MUTATING:
            self.assertTrue(guard.mutating_oc(command), command)
            self.assertTrue(MATCHER.search(command), "Cursor matcher misses: " + command)

    def test_read_only_commands_pass(self):
        for command in READ_ONLY:
            self.assertFalse(guard.mutating_oc(command), command)


if __name__ == "__main__":
    unittest.main()
