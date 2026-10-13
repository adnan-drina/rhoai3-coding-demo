"""Execute checkout and enrollment boundaries; no cluster, GitLab or image build."""
import base64
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scm = load('enrollment', BASE / 'pipelines/gitlab/reconcile.py')
lifecycle = load('lifecycle', ROOT / 'scripts/demo/gitlab-project-lifecycle.py')


class Checkout(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repo = self.root / 'repository'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        (repo / 'proof.txt').write_text('first version\n')
        subprocess.run(['git', '-C', str(repo), 'add', 'proof.txt'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'first'], check=True)
        self.sha = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        (repo / 'proof.txt').write_text('second version\n')
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qam', 'second'], check=True)
        self.url = 'https://gitlab-gitlab-system.example.test/rhoai-workloads/test.git'
        auth = self.root / 'auth'
        auth.mkdir()
        (auth / '.git-credentials').write_text('https://test:synthetic@gitlab-gitlab-system.example.test\n')
        self.env = dict(os.environ, REPO_URL=self.url, REVISION=self.sha, AUTH_DIR=str(auth),
                        COMMIT_RESULT=str(self.root / 'result'), GIT_TERMINAL_PROMPT='0',
                        GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='url.file://' + str(repo) + '.insteadOf',
                        GIT_CONFIG_VALUE_0=self.url)
        task = yaml.safe_load((BASE / 'pipelines/project-pipeline/task-git-clone.yaml').read_text())
        self.script = task['spec']['steps'][0]['script']

    def run_task(self, **changes):
        work = self.root / ('checkout-' + str(len(list(self.root.glob('checkout-*')))))
        work.mkdir()
        result = subprocess.run(['/bin/sh', '-c', self.script], cwd=work, env={**self.env, **changes}, capture_output=True, text=True)
        return result, work

    def test_exact_commit_not_latest_branch(self):
        result, work = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((work / 'proof.txt').read_text(), 'first version\n')
        self.assertEqual((self.root / 'result').read_text(), self.sha)
        self.assertNotIn('synthetic', result.stdout + result.stderr)

    def test_shared_workspace_ownership_does_not_weaken_commit_binding(self):
        result, work = self.run_task(GIT_TEST_ASSUME_DIFFERENT_OWNER='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'result').read_text(), self.sha)
        self.assertEqual((work / 'proof.txt').read_text(), 'first version\n')

    def test_mutable_and_foreign_revision_refused_before_git(self):
        for changes in ({'REVISION': 'main'}, {'REVISION': 'g' * 40}, {'REPO_URL': 'https://outside.test/test.git'}):
            result, work = self.run_task(**changes)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((work / '.git').exists())
            self.assertFalse((self.root / 'result').exists())


class Enrollment(unittest.TestCase):
    def setUp(self):
        self.sha = '1' * 40
        self.row = {'project_id': 42, 'initial_commit': self.sha, 'kind': 'application'}
        self.project = {'id': 42, 'path': 'example', 'namespace': {'id': 7}, 'default_branch': 'main',
                        'http_url_to_repo': 'https://gitlab.example.test/rhoai-workloads/example.git'}
        self.commit = {'id': self.sha, 'parent_ids': []}
        self.config = {'GITLAB_WORKLOAD_GROUP_ID': '7', 'GITLAB_HOST': 'gitlab.example.test',
                       'PLATFORM_REPO_URL': 'https://gitlab.example.test/rhoai-platform/demo.git', 'PLATFORM_REVISION': '2' * 40}
        self.created = {}
        self.scanner = {'host': 'aG9zdA==', 'token': 'dG9rZW4='}
        self.api = unittest.mock.Mock()
        self.api.request.side_effect = lambda method, path, data=None: [] if method == 'GET' else {}
        self.patches = [patch.object(scm, 'oc', side_effect=self.oc), patch.object(scm, 'apply'),
                        patch.object(scm, 'ensure_delivery'), patch.object(scm, 'Sonar')]
        self.mocks = [p.start() for p in self.patches]
        self.mocks[3].return_value.request.side_effect = lambda method, path, data=None: ({'components': [{'key': 'example'}]} if path.startswith('projects/search') else {'userTokens': [{'name':'gitlab-project-42','type':'PROJECT_ANALYSIS_TOKEN','project':{'key':'example'}}]} if path == 'user_tokens/search' else {'valid': True})
        for p in self.patches: self.addCleanup(p.stop)

    def oc(self, *args, document=None):
        if args[0] == 'create':
            key = (document['kind'].lower(), document['metadata']['name'])
            if key in self.created: raise subprocess.CalledProcessError(1, args, stderr='(AlreadyExists)')
            self.created[key] = document
            return document
        kind, name = args[1:3]
        if name == 'sonarqube-credentials': return {'data': self.scanner, 'metadata': {'annotations': {scm.SONAR_KEY: 'example', scm.SONAR_TYPE: 'PROJECT_ANALYSIS_TOKEN', scm.SONAR_NAME: 'gitlab-project-42'}}}
        if kind == 'pipeline': return {'metadata': {'name': name}}
        if kind == 'route': return {'spec': {'host': 'listener.example.test'}}
        if name == 'gitlab-read-source': return {'data': {}}
        if name == 'gitlab-webhook': return {'data': {'token': base64.b64encode(b'synthetic').decode()}}
        key = (kind, name)
        if key in self.created: return self.created[key]
        raise subprocess.CalledProcessError(1, args, stderr='(NotFound)')

    def enroll(self):
        with patch.dict(os.environ, POD_NAMESPACE='example-dev'):
            scm.bootstrap_project(self.api, self.row, self.project, self.commit, self.config)

    def test_initial_build_is_once_and_bound(self):
        self.enroll()
        self.enroll()
        runs = [d for (kind, _), d in self.created.items() if kind == 'pipelinerun']
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['metadata']['name'], 'gitlab-42-' + self.sha)
        self.assertEqual(runs[0]['spec']['taskRunSpecs'], [{'pipelineTaskName': 'build-and-push', 'serviceAccountName': 'image-builder'}])
        receipt = self.created['configmap', 'initial-build-receipt']
        self.assertTrue(receipt['immutable'])
        self.assertEqual(receipt['data']['source_commit'], self.sha)

    def test_missing_scanner_token_never_seeds(self):
        self.scanner = {'host': 'aG9zdA=='}
        with self.assertRaises(ValueError): self.enroll()
        self.assertFalse(any(k[0] == 'pipelinerun' for k in self.created))
        self.assertNotIn(('configmap', 'initial-build-receipt'), self.created)

    def test_archived_project_has_no_cluster_mutation(self):
        self.project['archived'] = True
        with self.assertRaises(ValueError): self.enroll()
        self.mocks[0].assert_not_called()
        self.mocks[1].assert_not_called()


class Lifecycle(unittest.TestCase):
    def test_foreign_registration_refused(self):
        row = {'project_id': 42, 'repo_url': 'https://gitlab.example.test/rhoai-workloads/example.git', 'initial_commit': 'a' * 40}
        project = {'id': 42, 'path': 'example', 'http_url_to_repo': row['repo_url']}
        lifecycle.check_registration('example', row, project)
        for changes in ({'id': 43}, {'path': 'foreign'}, {'http_url_to_repo': 'https://outside.test/a.git'}):
            with self.assertRaises(ValueError): lifecycle.check_registration('example', row, {**project, **changes})

    def test_registration_survives_project_namespace_deletion(self):
        row={'project_id':42,'repo_url':'https://gitlab.example.test/rhoai-workloads/example.git','initial_commit':'a'*40,'kind':'migration'}
        error=subprocess.CalledProcessError(1,['oc'],stderr='(NotFound)')
        saved={'data':{'retirement.json':json.dumps({'name':'example','namespace':'example-dev','registration':row})}}
        with patch.object(lifecycle,'oc',side_effect=[error,saved]):
            self.assertEqual(lifecycle.registration('example'),('example-dev',row))
        saved['data']['retirement.json']=json.dumps({'name':'foreign','namespace':'example-dev','registration':row})
        with patch.object(lifecycle,'oc',side_effect=[error,saved]),self.assertRaises(ValueError):
            lifecycle.registration('example')
        with patch.object(lifecycle,'oc',side_effect=subprocess.CalledProcessError(1,['oc'],stderr='Forbidden')) as query,self.assertRaises(subprocess.CalledProcessError):
            lifecycle.registration('example')
        self.assertEqual(query.call_count,1)

    def test_retire_never_deletes_stage_owned_import(self):
        with self.assertRaises(ValueError): lifecycle.check_action('retire', 'coolstore-inventory-service', {'kind': 'imported-application'})
        lifecycle.check_action('reset-coolstore', 'coolstore-inventory-service', {'kind': 'imported-application'})
        with self.assertRaises(ValueError): lifecycle.check_action('reset-coolstore', 'migration', {'kind': 'migration'})
        lifecycle.check_action('retire', 'example', {'kind': 'migration'})


if __name__ == '__main__': unittest.main()
