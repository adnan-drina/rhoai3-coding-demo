#!/usr/bin/env python3
"""Execute the actual Task scripts with fake providers; no cluster or build."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "gitops/stages/070-advanced-app-platform"
TASKS = BASE / "pipelines/project-pipeline"
SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
PREFIX = "image-registry.openshift-image-registry.svc:5000/example-dev/"


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        for name in ("bin", "sa", "auth", "source"):
            (self.work / name).mkdir()
        (self.work / "sa/namespace").write_text("example-dev")
        (self.work / "sa/token").write_text("initial-test-token")
        (self.work / "uid_map").write_text("0 123456 65536\n")
        self.log = self.work / "calls.jsonl"
        self.env = dict(os.environ, PATH=str(self.work / "bin") + ":" + os.environ["PATH"],
                        TEST_WORK=str(self.work), CALL_LOG=str(self.log),
                        DIGEST_RESULT=str(self.work / "digest"), IMAGE_RESULT=str(self.work / "image"),
                        TARGET_IMAGE=PREFIX + "example:" + SHA, IMAGE_NAME="example")
        self.provider("buildah", '''
import json, os, pathlib, sys
args = sys.argv[1:]
command = next(x for x in args if not x.startswith('--'))
row = {'command': command, 'args': args}
if command == 'login':
    row['token'] = sys.stdin.read()
    pathlib.Path(args[args.index('--authfile') + 1]).write_text('test auth')
    if os.environ.get('FAIL_LOGIN'): sys.exit(11)
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(row) + '\\n')
if command == 'bud':
    pathlib.Path(os.environ['TEST_WORK'], 'sa/token').write_text('rotated-test-token')
    if os.environ.get('FAIL_BUILD'): sys.exit(9)
if command == 'push':
    if os.environ.get('FAIL_PUSH'): sys.exit(10)
    pathlib.Path(args[args.index('--digestfile') + 1]).write_text(os.environ.get('RETURN_DIGEST', 'sha256:' + 'b' * 64))
''')
        self.provider("oc", '''
import json, os, sys
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps({'args': sys.argv[1:]}) + '\\n')
if 'configmap' in sys.argv:
    if os.environ.get('POLICY_ERROR'): sys.exit(1)
    print(os.environ.get('MODE', 'internal'), end='')
elif 'imagestream' in sys.argv and os.environ.get('STREAM_MISSING'):
    sys.exit(1)
''')

    def provider(self, name, body):
        path = self.work / "bin" / name
        path.write_text("#!/usr/bin/python3\n" + body)
        path.chmod(0o755)

    def run_task(self, name, **env):
        task = yaml.safe_load((TASKS / name).read_text())
        script = task["spec"]["steps"][0]["script"]
        # Only runtime mount/result paths are redirected. The control flow is
        # the shipped script, including the authentication and digest checks.
        script = script.replace("/var/run/secrets/kubernetes.io/serviceaccount", str(self.work / "sa"))
        script = script.replace("/run/registry-auth", str(self.work / "auth"))
        script = script.replace("/proc/self/uid_map", str(self.work / "uid_map"))
        script = script.replace("$(results.registry.path)", str(self.work / "registry"))
        return subprocess.run(["bash", "-c", script], cwd=self.work / "source",
                              env=dict(self.env, **env), text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_push_settles_to_digest_and_refreshes_identity(self):
        result = self.run_task("task-build-image.yaml")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual([c["command"] for c in calls], ["login", "bud", "login", "push"])
        self.assertEqual(calls[0]["token"], "initial-test-token")
        self.assertEqual(calls[2]["token"], "rotated-test-token")
        self.assertEqual((self.work / "image").read_text(), PREFIX + "example@" + DIGEST)
        self.assertFalse((self.work / "auth/auth.json").exists())
        self.assertNotIn("test-token", result.stdout + result.stderr)
        for c in calls:
            self.assertIn("--tls-verify=true", c["args"])
            self.assertNotIn("initial-test-token", c["args"])

    def test_build_failure_does_not_push_or_emit_image(self):
        result = self.run_task("task-build-image.yaml", FAIL_BUILD="yes")
        self.assertEqual(result.returncode, 9)
        self.assertEqual([c["command"] for c in self.calls()], ["login", "bud"])
        self.assertFalse((self.work / "image").exists())
        self.assertFalse((self.work / "auth/auth.json").exists())

    def test_host_or_insufficient_user_mapping_refuses_before_login(self):
        for mapping in ("0 0 4294967295\n", "0 123456 1\n", "", "1000 123456 65536\n"):
            with self.subTest(mapping=mapping):
                (self.work / "uid_map").write_text(mapping)
                result = self.run_task("task-build-image.yaml")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.calls(), [])
        (self.work / "uid_map").unlink()
        self.assertNotEqual(self.run_task("task-build-image.yaml").returncode,0)
        self.assertEqual(self.calls(),[])

    def test_push_failure_does_not_emit_image(self):
        result = self.run_task("task-build-image.yaml", FAIL_PUSH="yes")
        self.assertEqual(result.returncode, 10)
        self.assertFalse((self.work / "image").exists())
        self.assertFalse((self.work / "auth/auth.json").exists())

    def test_failed_login_never_builds_and_cleans_auth(self):
        result = self.run_task("task-build-image.yaml", FAIL_LOGIN="yes")
        self.assertEqual(result.returncode, 11)
        self.assertFalse((self.work / "image").exists())
        self.assertFalse((self.work / "auth/auth.json").exists())

    def test_promotion_refuses_foreign_artifact_before_provider_access(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("registry_promotion", TASKS / "promote.py")
        promotion = importlib.util.module_from_spec(spec); spec.loader.exec_module(promotion)
        runtime = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "example"},
                   "spec": {"template": {"spec": {"containers": [{"name": "example", "image": "bootstrap:tag"}]}}}}
        for image in (PREFIX + "example:latest", PREFIX + "other@" + DIGEST,
                      "quay.io/example/example@" + DIGEST):
            with self.subTest(image=image), self.assertRaises(ValueError):
                promotion.validate_runtime([runtime], "example", "example-dev", image)
        self.assertNotIn("oc apply", (TASKS / "promote.py").read_text())

    def test_registry_storage_gate_refuses_empty_and_ephemeral_storage(self):
        # Run the actual preflight's Python predicate, not a second definition.
        deploy = (ROOT / "stages/070-advanced-app-platform/deploy.sh").read_text()
        start = deploy.index('cluster -o json | python3 -c \'') + len('cluster -o json | python3 -c \'')
        predicate = deploy[start:deploy.index("\n'", start)]
        for storage, expected in (({}, 1), ({"emptyDir": {}}, 1), (None, 1),
                                  ({"s3": {"bucket": "test-registry"}}, 0), ({"pvc": {"claim": "registry"}}, 0)):
            result = subprocess.run(["/usr/bin/python3", "-c", predicate],
                                    input=json.dumps({"spec": {"storage": storage}}), text=True, capture_output=True)
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_missing_or_malformed_digest_refuses(self):
        for value in ("", "sha256:no", "b" * 64):
            with self.subTest(value=value):
                result = self.run_task("task-build-image.yaml", RETURN_DIGEST=value)
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.work / "image").exists())

    def test_foreign_registry_namespace_and_mutable_tag_refuse_before_login(self):
        for image in ("quay.io/example/app:" + SHA, PREFIX.replace("example-dev", "other-dev") + "app:" + SHA,
                      PREFIX + "app:latest", PREFIX + "app:main", PREFIX + "app:$(touch injected)"):
            with self.subTest(image=image):
                result = self.run_task("task-build-image.yaml", TARGET_IMAGE=image)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])

    def test_registry_policy_and_stream_are_required(self):
        for bad in ({"POLICY_ERROR": "yes"}, {"MODE": ""}, {"MODE": "external"}, {"STREAM_MISSING": "yes"},
                    {"IMAGE_NAME": "app;echo hacked"}):
            with self.subTest(bad=bad):
                result = self.run_task("task-resolve-image-registry.yaml", **bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.work / "registry").exists())
        result = self.run_task("task-resolve-image-registry.yaml")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / "registry").read_text(), PREFIX.rstrip("/"))

    def test_pipeline_consumes_pushed_digest_and_checked_out_commit(self):
        spec = yaml.safe_load((TASKS / "pipeline.yaml").read_text())["spec"]
        tasks = {t["name"]: t for t in spec["tasks"]}
        build = dict((p["name"], p["value"]) for p in tasks["build-and-push"]["params"])
        deploy = dict((p["name"], p["value"]) for p in tasks["deploy"]["params"])
        self.assertIn("$(tasks.clone-source.results.COMMIT)", build["IMAGE"])
        self.assertEqual(deploy["IMAGE"], "$(tasks.build-and-push.results.IMAGE_URL)")
        self.assertNotIn("tag-latest", tasks)
        self.assertNotIn("dockerconfig", [w["name"] for w in spec["workspaces"]])
        build_task = yaml.safe_load((TASKS / "task-build-image.yaml").read_text())["spec"]
        volumes = {v["name"]: v for v in build_task["volumes"]}
        self.assertEqual(volumes["registry-auth"]["emptyDir"]["medium"], "Memory")
        self.assertNotIn("persistentVolumeClaim", volumes["registry-auth"])

    def test_stage_render_has_one_declared_output_and_no_quay_distribution(self):
        result = subprocess.run(["kustomize", "build", str(BASE / "pipelines/project-enrollment")], capture_output=True, text=True, check=True)
        objects = list(yaml.safe_load_all(result.stdout))
        outputs = [o for o in objects if o["kind"] == "ImageStream" and o["metadata"].get("namespace") == "unassigned-dev"]
        self.assertEqual([o["metadata"]["name"] for o in outputs], ["unassigned"])
        binding = next(o for o in objects if o["kind"] == "RoleBinding" and o["metadata"]["name"] == "pipeline-image-builder")
        self.assertEqual(binding["metadata"]["namespace"], "unassigned-dev")
        self.assertEqual(binding["subjects"], [{"kind": "ServiceAccount", "name": "image-builder", "namespace": "unassigned-dev"}])
        for path in (BASE / "pipelines").rglob("*.yaml"):
            self.assertNotIn("quay-push-secret", path.read_text())
        self.assertNotIn("patch-coolstore-image", result.stdout)


if __name__ == "__main__":
    unittest.main()
