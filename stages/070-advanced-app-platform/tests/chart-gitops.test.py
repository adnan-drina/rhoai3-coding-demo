#!/usr/bin/env python3
"""Kustomize delivery, derived configuration and GitLab upgrade regressions."""
import importlib.util
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'
sys.path.insert(0, str(BASE / 'pipelines/gitlab'))


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

    def test_offline_render_uses_served_stable_apis(self):
        expected={'CronJob':'batch/v1','PodDisruptionBudget':'policy/v1','HorizontalPodAutoscaler':'autoscaling/v2'}
        seen=set()
        for path in (BASE/'gitlab/generated').glob('*.yaml'):
            row=yaml.safe_load(path.read_text())
            if row.get('kind') in expected:
                seen.add(row['kind'])
                self.assertEqual(row['apiVersion'],expected[row['kind']])
                if row['kind']=='HorizontalPodAutoscaler':
                    metric=row['spec']['metrics'][0]['resource']
                    self.assertIn('target',metric)
                    self.assertNotIn('targetAverageUtilization',metric)
        self.assertEqual(seen,set(expected))
    def test_sonarqube_version_label_is_not_the_image_digest(self):
        row=next(r for r in self.resources if r['kind']=='StatefulSet' and r['metadata']['name']=='sonarqube')
        self.assertEqual(row['metadata']['labels']['app.kubernetes.io/version'],'26.9.0.129388-community')
        self.assertEqual(row['spec']['template']['spec']['containers'][0]['image'],
                         'docker.io/library/sonarqube@sha256:c0f1160bccfa435db4168c2d7df69af3c3ea7bfeb87395613014048fb33a68c1')

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

    def test_derived_config_is_separate_from_canonical_chart(self):
        templates = next(d for d in self.resources if d['kind'] == 'ConfigMap'
                         and d['metadata']['name'] == 'gitlab-runtime-templates')
        app = yaml.safe_load((ROOT / 'gitops/argocd/app-of-apps/070-advanced-app-platform.yaml').read_text())
        static = {r['metadata']['name']: r for r in self.resources if r['kind'] == 'ConfigMap'}
        for name, data in json.loads(templates['data']['templates.json']).items():
            if name != 'gitlab-runtime-buckets':
                self.assertEqual(static[name]['data'], data)
                self.assertNotIn(name+'-runtime', static)
            self.assertFalse(any(r.get('kind')=='ConfigMap' and r.get('name')==name
                                 for r in app['spec']['ignoreDifferences']))
        for row in self.resources:
            if row['kind'] not in ('Deployment','StatefulSet','Job','CronJob'): continue
            pod = (row['spec']['jobTemplate']['spec']['template']['spec'] if row['kind']=='CronJob'
                   else row['spec']['template']['spec'])
            for volume in pod.get('volumes',[]):
                if volume.get('configMap',{}).get('name','').endswith('-runtime'):
                    source=volume['configMap']['name'][:-8]
                    self.assertIn(source, json.loads(templates['data']['templates.json']))

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
    def test_backup_policy_uses_bound_account_identity_not_a_guessed_email(self):
        claim={'spec':{'objectBucketName':'obc-gitlab-system-gitlab-backups'}}
        obj={'spec':{'endpoint':{'bucketName':'owned'},'additionalState':{'arn':'arn:aws:iam::'+'a'*24+':root'}}}
        with patch.object(bootstrap,'oc',return_value=obj) as read:
            self.assertEqual(bootstrap.backup_principal(claim,'owned'),obj['spec']['additionalState']['arn'])
            read.assert_called_once_with('get','objectbucket','obc-gitlab-system-gitlab-backups','-o','json')
            with self.assertRaises(RuntimeError):bootstrap.backup_principal(claim,'foreign')
        with patch.object(bootstrap,'oc') as read:
            with self.assertRaises(RuntimeError):bootstrap.backup_principal({'spec':{'objectBucketName':'foreign'}},'owned')
            read.assert_not_called()
        obj['spec']['additionalState']['arn']='*'
        with patch.object(bootstrap,'oc',return_value=obj):
            with self.assertRaises(RuntimeError):bootstrap.backup_principal(claim,'owned')

    def setUp(self):
        self.target = {'gitlabVersion': 'v19.4.2', 'gitlabChartVersion': '10.4.2'}

    def test_derived_secret_values_are_not_command_arguments(self):
        with patch.object(bootstrap,'optional',return_value={'data':{}}),patch.object(bootstrap,'oc') as command:
            bootstrap.secret('gitlab-storage-uploads',{'connection':'synthetic-sensitive-value'},derived=True)
        argv=command.call_args.args
        self.assertNotIn('synthetic-sensitive-value',str(argv))
        self.assertIn('--patch-file=/dev/stdin',argv)
        self.assertEqual(command.call_args.kwargs,{'document':{'stringData':{'connection':'synthetic-sensitive-value'}}})

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
