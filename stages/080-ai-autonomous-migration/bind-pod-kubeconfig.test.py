#!/usr/bin/env python3
"""Behavioral regressions for destfile worker kubeconfig replacement.

The factory postStart must bind ~/.kube/config to THIS pod's projected
ServiceAccount token as a replacement Config. oc login merges users and
contexts into an existing file; a stubbed failing oc login previously left
the leftover identity in place and still printed success. These cases execute
the shipped destfile fragment; they are not a live isolation qualification.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parents[1] / (
    "gitops/stages/050-advanced-app-platform/base/rhdh/templates/"
    "app-migration/skeleton/devfile.yaml"
)
START = "# rhoai3-bind-pod-kubeconfig:start"
END = "# rhoai3-bind-pod-kubeconfig:end"
OLD_KUBECONFIG = textwrap.dedent(
    """\
    apiVersion: v1
    kind: Config
    clusters:
    - cluster:
        server: https://old.example:6443
      name: old-cluster
    contexts:
    - context:
        cluster: old-cluster
        user: workspace-legacy-sa
      name: old-context
    current-context: old-context
    users:
    - name: workspace-legacy-sa
      user:
        token: leftover-legacy-token
    """
)


def shipped_fragment() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise AssertionError("destfile is missing bind-pod-kubeconfig markers")
    return textwrap.dedent(text.split(START, 1)[1].split(END, 1)[0])


class BindPodKubeconfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.sa = self.root / "sa"
        self.kube = self.home / ".kube"
        self.kube.mkdir(parents=True)
        self.sa.mkdir()
        (self.sa / "ca.crt").write_text("fixture-ca\n")
        (self.sa / "namespace").write_text("wksp-ai-developer\n")
        (self.sa / "token").write_text("current-pod-token\n")
        self.oc_log = self.root / "oc.log"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        oc = bin_dir / "oc"
        oc.write_text(
            "#!/bin/sh\n"
            "printf 'oc %%s\\n' \"$*\" >> \"%s\"\n"
            "exit 1\n" % self.oc_log
        )
        oc.chmod(0o755)
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "SA_DIR": str(self.sa),
            "KUBERNETES_SERVICE_HOST": "kubernetes.default.svc",
            "KUBERNETES_SERVICE_PORT": "443",
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "TMPDIR": str(self.root / "tmp"),
        }
        (self.root / "tmp").mkdir()
        self.env.pop("KUBECONFIG", None)

    def write_old(self, path: Path | None = None) -> Path:
        target = path or (self.kube / "config")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(OLD_KUBECONFIG)
        return target

    def run_bind(self, extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
            for key, value in list(env.items()):
                if value is None:
                    env.pop(key)
        script = "set +e\n" + shipped_fragment()
        return subprocess.run(
            ["bash", "-s"],
            input=script,
            env=env,
            text=True,
            capture_output=True,
            cwd=str(self.root),
        )

    def test_existing_old_kubeconfig_is_replaced_not_merged(self):
        self.write_old()
        result = self.run_bind()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        body = (self.kube / "config").read_text()
        self.assertNotIn("leftover-legacy-token", body)
        self.assertNotIn("workspace-legacy-sa", body)
        self.assertNotIn("old-context", body)
        self.assertIn("current-pod", body)
        self.assertIn("tokenFile: %s" % (self.sa / "token"), body)
        self.assertIn("kubeconfig bound to this pod ServiceAccount token", result.stdout)
        self.assertFalse(self.oc_log.exists())

    def test_stubbed_failing_oc_login_cannot_keep_old_identity(self):
        self.write_old()
        result = self.run_bind()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.oc_log.exists(), "shipped bind must not call oc login")
        self.assertNotIn("leftover-legacy-token", (self.kube / "config").read_text())

    def test_missing_token_blocks_without_success_or_old_identity(self):
        self.write_old()
        (self.sa / "token").unlink()
        result = self.run_bind()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing projected ServiceAccount token", result.stderr)
        self.assertNotIn("kubeconfig bound to this pod ServiceAccount token", result.stdout)
        self.assertFalse((self.kube / "config").exists())

    def test_failed_initialization_blocks_without_success_or_old_identity(self):
        self.write_old()
        result = self.run_bind(extra_env={"KUBERNETES_SERVICE_HOST": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing in-cluster API address", result.stderr)
        self.assertNotIn("kubeconfig bound to this pod ServiceAccount token", result.stdout)
        self.assertFalse((self.kube / "config").exists())

    def test_successful_replacement_writes_only_current_pod_context(self):
        extra = self.home / "other-kubeconfig"
        extra.write_text(OLD_KUBECONFIG)
        self.write_old()
        result = self.run_bind(extra_env={"KUBECONFIG": str(extra)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        body = extra.read_text()
        self.assertEqual(body.count("name: current-pod"), 2)
        self.assertIn("namespace: wksp-ai-developer", body)
        self.assertNotIn("leftover-legacy-token", body)
        self.assertFalse((self.kube / "config").exists())
        mode = stat.S_IMODE(extra.stat().st_mode)
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
