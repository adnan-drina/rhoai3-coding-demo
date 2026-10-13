#!/usr/bin/env python3
"""Kustomize delivery, derived configuration and GitLab upgrade regressions."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


bootstrap = module('gitlab_bootstrap', 'gitops/stages/070-advanced-app-platform/base/gitlab/bootstrap.py')
renderer = module('chart_renderer', 'scripts/platform/render-stage070-charts.py')


class NativeDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resources = list(yaml.safe_load_all(subprocess.check_output(
            ['kustomize', 'build', str(BASE)], text=True)))

    def test_plain_kustomize_has_no_runtime_chart_or_gitlab_operator(self):
        for document in self.resources:
            self.assertNotIn(document['kind'], ('HelmRelease', 'HelmChart', 'GitLab'))
            self.assertNotIn('helm.sh/hook', document['metadata'].get('annotations', {}))
            self.assertNotEqual(document['metadata']['name'], 'gitlab-controller-manager')
        app = yaml.safe_load((ROOT / 'gitops/argocd/app-of-apps/070-advanced-app-platform.yaml').read_text())
        self.assertNotIn('helm', app['spec']['source'])
        self.assertNotIn('--enable-helm', (ROOT / 'stages/070-advanced-app-platform/deploy.sh').read_text())

    def test_native_order_preserves_credentials_and_migrations(self):
        rows = {(d['kind'], d['metadata']['name']): d for d in self.resources
                if d['metadata'].get('namespace') == 'gitlab-system'}
        expected = {'gitlab-gitlab-upgrade-check': 4, 'gitlab-shared-secrets': 5,
                    'gitlab-bootstrap': 6, 'gitlab-migrations': 9, 'gitlab-record-release': 12}
        for name, wave in expected.items():
            job = rows['Job', name]
            self.assertEqual(job['metadata']['annotations']['argocd.argoproj.io/hook'], 'Sync')
            self.assertEqual(job['metadata']['annotations']['argocd.argoproj.io/sync-wave'], str(wave))
        self.assertEqual(rows['Deployment', 'gitlab-postgresql']['metadata']['annotations']['argocd.argoproj.io/sync-wave'], '7')
        self.assertEqual(rows['StatefulSet', 'gitlab-gitaly']['metadata']['annotations']['argocd.argoproj.io/sync-wave'], '8')
        self.assertEqual(rows['Deployment', 'gitlab-webservice-default']['metadata']['annotations']['argocd.argoproj.io/sync-wave'], '10')
        # Applying the new target must never overwrite the previous installed version.
        self.assertNotIn(('ConfigMap', 'gitlab-gitlab-chart-info'), rows)

    def test_derived_keys_only_have_narrow_argo_ignores(self):
        templates = next(d for d in self.resources if d['kind'] == 'ConfigMap'
                         and d['metadata']['name'] == 'gitlab-runtime-templates')
        app = yaml.safe_load((ROOT / 'gitops/argocd/app-of-apps/070-advanced-app-platform.yaml').read_text())
        for name, data in json.loads(templates['data']['templates.json']).items():
            derived = {'/data/' + key.replace('~', '~0').replace('/', '~1') for key, text in data.items()
                       if 'example.invalid' in text or 'pending-' in text}
            ignore = next(d for d in app['spec']['ignoreDifferences']
                          if d.get('name') == name and d.get('namespace') == 'gitlab-system')
            self.assertEqual(set(ignore['jsonPointers']), derived)
            self.assertNotIn('/data', ignore['jsonPointers'])

    def test_images_are_immutable_and_application_has_no_api_token(self):
        for document in self.resources:
            if document['metadata'].get('namespace') not in ('gitlab-system', 'sonarqube'):
                continue
            if document['kind'] not in ('Deployment', 'StatefulSet', 'Job', 'CronJob'):
                continue
            pod = (document['spec']['jobTemplate']['spec']['template']['spec'] if document['kind'] == 'CronJob'
                   else document['spec']['template']['spec'])
            for container in (pod.get('containers') or []) + (pod.get('initContainers') or []):
                # Existing Sonar configuration jobs are outside the converted chart.
                if document['metadata']['name'] == 'sonarqube' or document['metadata']['name'].startswith('gitlab'):
                    self.assertIn('@sha256:', container['image'])
            if document['metadata']['name'] in ('gitlab-webservice-default', 'gitlab-sidekiq-all-in-1-v2', 'gitlab-gitaly', 'gitlab-toolbox'):
                self.assertFalse(pod['automountServiceAccountToken'])
            self.assertNotIn('pending-', json.dumps(pod))
            self.assertNotIn('example.invalid', json.dumps(pod))

    def test_future_chart_credentials_are_refused_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'credential'):
            renderer.gitlab_documents([{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'unexpected'},
                                       'data': {'password': 'must-not-be-committed'}}], {})


class BootstrapLifecycle(unittest.TestCase):
    def setUp(self):
        self.target = {'gitlabVersion': 'v19.4.2', 'gitlabChartVersion': '10.4.2'}

    def test_initial_install_and_same_release_retry(self):
        self.assertEqual(bootstrap.upgrade_action(self.target, None, None, False), 'initialize')
        self.assertEqual(bootstrap.upgrade_action(self.target, None, self.target, True), 'resume')

    def test_missing_or_foreign_installation_metadata_never_infers_success(self):
        with self.assertRaises(RuntimeError):
            bootstrap.upgrade_action(self.target, None, None, True)
        with self.assertRaises(RuntimeError):
            bootstrap.upgrade_action(self.target, None, {'gitlabVersion': 'v19.3.0'}, True)
        for bad in ({}, {'gitlabVersion': 'unknown', 'gitlabChartVersion': '10.4.2'}, {'gitlabVersion': 'v19.4.2'},
                    {'gitlabVersion': 19, 'gitlabChartVersion': '10.4.2'}):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                bootstrap.upgrade_action(self.target, bad, None, True)

    def test_upgrade_still_requires_the_upstream_check(self):
        previous = {'gitlabVersion': 'v19.2.6', 'gitlabChartVersion': '10.2.8'}
        self.assertEqual(bootstrap.upgrade_action(self.target, previous, None, True), 'check')
        with self.assertRaisesRegex(RuntimeError, 'downgrade'):
            bootstrap.upgrade_action(self.target, {'gitlabVersion': 'v19.5.1', 'gitlabChartVersion': '10.5.1'}, None, True)

    def test_runtime_configuration_comes_from_route_and_claims(self):
        templates = {'gitlab-webservice': {'gitlab.yml.erb': 'gitlab.example.invalid pending-uploads',
                                          'pages_redirect_uri': 'pages.apps.example.invalid'}}
        actual = bootstrap.runtime_data(templates, 'gitlab-gitlab-system.apps.test', 'apps.test',
                                        {'uploads': ('owned-upload-bucket', 'not-rendered-access-key', 'not-rendered-secret')})
        self.assertEqual(actual['gitlab-webservice']['gitlab.yml.erb'], 'gitlab-gitlab-system.apps.test owned-upload-bucket')
        self.assertEqual(actual['gitlab-webservice']['pages_redirect_uri'], 'pages.apps.test')
        self.assertNotIn('not-rendered-secret', str(actual))
        with self.assertRaises(RuntimeError):
            bootstrap.runtime_data(templates, 'gitlab-gitlab-system.apps.test', 'apps.test', {})


if __name__ == '__main__':
    unittest.main()
