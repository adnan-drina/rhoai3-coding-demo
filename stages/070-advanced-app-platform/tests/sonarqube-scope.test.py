"""Exercise project token creation, reuse and exact workspace mounting."""
import base64
import io
import urllib.error
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('sonar_scope', ROOT / 'gitops/stages/070-advanced-app-platform/070-pipelines/gitlab/reconcile.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def b64(s): return base64.b64encode(s.encode()).decode()


class Scope(unittest.TestCase):
    def setUp(self):
        self.control = {'data': {'host': b64('http://sonar.test'), 'token': b64('control-secret')}}
        self.stored = None
        self.tokens = []
        self.writes = []
        self.calls = []
        self.projects = set()
        self.client = Mock()
        def request(method, path, data=None):
            self.calls.append((method, path, data))
            if path == 'projects/create':
                if data['project'] in self.projects:
                    raise urllib.error.HTTPError(path, 400, 'Bad Request', {}, io.BytesIO(b'{"errors":[{"msg":"Could not create Project with key: \\"example\\". A similar key already exists: \\"example\\""}]}'))
                self.projects.add(data['project']); return {'project': {'key': data['project']}}
            if path == 'user_tokens/search': return {'userTokens': self.tokens}
            if path == 'authentication/validate': return {'valid': True}
            if path == 'user_tokens/generate':
                self.tokens = [{'name':data['name'], 'type':data['type'], 'project': {'key':data['projectKey']}}]
                return {**data, 'token': 'project-only-secret'}
            raise AssertionError(path)
        self.client.request.side_effect = request
        def oc(*args, document=None):
            if args[0] == 'create':
                self.writes.append(document)
                self.stored = {**document, 'data': {k: b64(v) for k, v in document['stringData'].items()}}
                return self.stored
            if args[4] == 'app-platform-build': return self.control
            if self.stored is None: raise subprocess.CalledProcessError(1, args, stderr='(NotFound)')
            return self.stored
        self.patches = [patch.object(m, 'Sonar', return_value=self.client), patch.object(m, 'oc', side_effect=oc)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def ensure(self): return m.ensure_project_scanner('example', 'example-dev', 42)

    def test_creation_is_project_scoped_and_restart_preserves_it(self):
        first = self.ensure()
        self.assertIn(('POST', 'user_tokens/generate', {'name': 'gitlab-project-42', 'type': 'PROJECT_ANALYSIS_TOKEN', 'projectKey': 'example'}), self.calls)
        self.assertEqual(first['data']['token'], b64('project-only-secret'))
        self.assertEqual(self.ensure(), first)
        self.assertEqual(len(self.writes), 1)

    def test_lost_secret_never_rotates_an_existing_token(self):
        self.tokens = [{'name': 'gitlab-project-42', 'type': 'PROJECT_ANALYSIS_TOKEN', 'project': {'key': 'example'}}]
        with self.assertRaisesRegex(ValueError, 'without its Secret'): self.ensure()
        self.assertFalse(self.writes)
        self.assertFalse(any(c[1] == 'user_tokens/generate' for c in self.calls))

    def test_the_provisioner_creates_the_project_or_accepts_its_existing_key(self):
        self.projects = {'example'}
        self.ensure()
        self.assertIn(('POST', 'projects/create', {'project': 'example', 'name': 'example', 'visibility': 'private'}), self.calls)
        self.assertFalse(any(c[1].startswith('projects/search') for c in self.calls))

    def test_foreign_or_user_token_cannot_be_reused(self):
        self.ensure()
        for change in ({'type': 'USER_TOKEN'}, {'project': {'key': 'foreign'}}):
            self.tokens = [{'name': 'gitlab-project-42', 'type': 'PROJECT_ANALYSIS_TOKEN', 'project': {'key': 'example'}, **change}]
            with self.assertRaises(ValueError): self.ensure()
        self.assertEqual(len(self.writes), 1)

    def test_top_level_project_key_does_not_substitute_for_server_metadata(self):
        self.ensure()
        self.tokens = [{'name': 'gitlab-project-42', 'type': 'PROJECT_ANALYSIS_TOKEN', 'projectKey': 'example'}]
        with self.assertRaises(ValueError): self.ensure()

    def test_missing_control_and_malformed_binding_fail_closed(self):
        self.control['data'].pop('token')
        with self.assertRaises(ValueError): self.ensure()
        self.assertFalse(self.writes)
        self.control['data']['token'] = b64('control-secret')
        self.ensure()
        self.stored['metadata']['annotations'][m.SONAR_KEY] = 'foreign'
        with self.assertRaises(ValueError): self.ensure()

    def test_workspace_mount_is_for_one_persona_and_exact_workspace(self):
        self.ensure()
        with patch.object(m, 'apply') as write:
            m.mount_project_scanner('example', 'example-dev', {'kind': 'application', 'requester': 'user:default/ai-developer'}, 42)
        secret = write.call_args.args[0]
        self.assertEqual(secret['metadata']['namespace'], 'wksp-ai-developer')
        self.assertEqual(secret['metadata']['annotations']['controller.devfile.io/mount-to-devworkspace-include'], 'example')
        self.assertEqual(secret['data']['SONAR_TOKEN'], b64('project-only-secret'))
        self.assertNotIn(b64('control-secret'), str(secret))

    def test_global_token_cannot_be_mirrored(self):
        self.ensure()
        self.stored['metadata']['annotations'][m.SONAR_TYPE] = 'USER_TOKEN'
        with patch.object(m, 'apply') as write, self.assertRaises(ValueError):
            m.mount_project_scanner('example', 'example-dev', {'kind': 'application', 'requester': 'user:default/ai-developer'}, 42)
        write.assert_not_called()


if __name__ == '__main__': unittest.main()
