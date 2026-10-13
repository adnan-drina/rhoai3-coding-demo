#!/usr/bin/env python3
"""Focused contract and adversarial tests for the integrated Stage 070 upgrade."""
import copy
import base64
import importlib.util
import json
import io
import tarfile
import subprocess
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform/base'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
    return loaded


scm = module('gitlab_reconcile', 'pipelines/gitlab/reconcile.py')
promotion = module('promotion', 'pipelines/project-pipeline/promote.py')
ai = module('mta_ai', 'mta/jobs/configure-ai.py')
bootstrap = module('scm_bootstrap', 'gitlab/bootstrap-scm.py')
oidc = module('gitlab_oidc', 'gitlab/bootstrap-oidc.py')
signing = module('signing_bootstrap', 'pipelines/signing/configure-signing.py')
reader = module('argo_reader', 'gitlab/configure-argocd-reader.py')


class Enrollment(unittest.TestCase):
    def setUp(self):
        self.sha = '1' * 40
        self.row = {'project_id': 42, 'initial_commit': self.sha, 'kind': 'migration'}
        self.project = {'id': 42, 'path': 'petclinic-vtest', 'namespace': {'id': 7}, 'default_branch': 'main'}
        self.commit = {'id': self.sha, 'parent_ids': []}

    def test_registered_first_commit(self):
        self.assertEqual(scm.validate_request(self.row, self.project, self.commit, 7), 'petclinic-vtest')

    def test_foreign_project_group_and_late_declaration_refused(self):
        for mutation in ('project', 'group', 'parent', 'zero', 'name', 'branch'):
            row, project, commit = copy.deepcopy((self.row, self.project, self.commit))
            if mutation == 'project': row['project_id'] = 43
            elif mutation == 'group': project['namespace']['id'] = 8
            elif mutation == 'parent': commit['parent_ids'] = ['2' * 40]
            elif mutation == 'zero': row['initial_commit'] = '0' * 40
            elif mutation == 'name': project['path'] = '../../outside'
            else: project['default_branch'] = 'foreign'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): scm.validate_request(row, project, commit, 7)

    def test_webhook_cannot_provision_or_select_another_project(self):
        resources = scm.trigger_resources('example', 'example-dev', 42, 'https://gitlab.example/rhoai-workloads/example.git', self.sha)
        role = next(r for r in resources if r['kind'] == 'Role')
        writes = [r for r in role['rules'] if 'create' in r['verbs']]
        self.assertEqual(writes, [{'apiGroups': ['tekton.dev'], 'resources': ['pipelineruns'], 'verbs': ['create']}])
        event = next(r for r in resources if r['kind'] == 'EventListener')
        interceptors = event['spec']['triggers'][0]['interceptors']
        self.assertEqual(interceptors[0]['ref']['name'], 'gitlab')
        condition = interceptors[1]['params'][0]['value']
        for term in ('body.project.id == 42', 'body.project.git_http_url', 'refs/heads/main', 'body.checkout_sha.matches', '0' * 40): self.assertIn(term, condition)
        self.assertNotIn('body.repository', condition)
        self.assertNotIn('head_commit', condition)

    def test_duplicate_delivery_has_the_same_run_identity(self):
        a = scm.pipeline_run('example', 'example-dev', 42, 'https://gitlab.example/group/example.git', self.sha)
        b = scm.pipeline_run('example', 'example-dev', 42, 'https://gitlab.example/group/example.git', self.sha)
        self.assertEqual(a['metadata']['name'], b['metadata']['name'])
        self.assertEqual(a['spec']['taskRunTemplate']['serviceAccountName'], 'app-builder')


class RuntimeArtifact(unittest.TestCase):
    def setUp(self):
        self.image = 'image-registry.openshift-image-registry.svc:5000/example-dev/example@sha256:' + 'a' * 64
        self.artifact = {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'example'}, 'spec': {'template': {'spec': {'containers': [{'name': 'example', 'image': 'bootstrap:tag'}]}}}}

    def test_main_image_is_pinned_and_runtime_has_no_api_token(self):
        result = promotion.validate_runtime([self.artifact], 'example', 'example-dev', self.image)
        pod = result[0]['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(pod['serviceAccountName'], 'app-runtime')
        self.assertEqual(pod['containers'][0]['image'], self.image)
        self.assertEqual(self.artifact['spec']['template']['spec']['containers'][0]['image'], 'bootstrap:tag')

    def test_foreign_images_and_mutable_tags_refused(self):
        for image in (self.image.replace('example-dev', 'other-dev'), self.image.replace('/example@', '/other@'), self.image.split('@')[0] + ':latest', 'quay.io/example/example@sha256:' + 'a' * 64):
            with self.subTest(image=image), self.assertRaises(ValueError): promotion.validate_runtime([self.artifact], 'example', 'example-dev', image)

    def test_host_privileges_and_foreign_secret_refused(self):
        for mutation in ('host', 'privileged', 'account', 'volume', 'secret', 'kind', 'namespace'):
            obj = copy.deepcopy(self.artifact); pod = obj['spec']['template']['spec']
            if mutation == 'host': pod['hostNetwork'] = True
            elif mutation == 'privileged': pod['containers'][0]['securityContext'] = {'privileged': True}
            elif mutation == 'account': pod['serviceAccountName'] = 'project-provisioner'
            elif mutation == 'volume': pod['volumes'] = [{'name': 'host', 'hostPath': {'path': '/'}}]
            elif mutation == 'secret': pod['containers'][0]['env'] = [{'name': 'PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'another-project-secret', 'key': 'password'}}}]
            elif mutation == 'kind': obj['kind'] = 'RoleBinding'
            else: obj['metadata']['namespace'] = 'outside'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): promotion.validate_runtime([obj], 'example', 'example-dev', self.image)


class IntegratedContract(unittest.TestCase):
    def test_argo_reader_keeps_existing_policy_and_is_idempotent(self):
        current = 'g, system:cluster-admins, role:admin\np, role:other, applications, get, other/*, allow\n'
        updated = reader.policy(current)
        self.assertTrue(updated.startswith(current))
        self.assertEqual(reader.policy(updated), updated)
        self.assertEqual([r for r in updated.splitlines() if 'rhdh' in r], reader.RULES)
        self.assertTrue(all(', get,' in r or r.startswith('g, ') for r in reader.RULES))

    def test_tekton_frontend_is_wired_and_migration_requires_hub(self):
        plugins = yaml.safe_load(yaml.safe_load((BASE / 'rhdh/rhdh-instance/dynamic-plugins-configmap.yaml').read_text())['data']['dynamic-plugins.yaml'])['plugins']
        tekton = next(p for p in plugins if 'plugin-tekton@sha256:' in p['package'])
        point = tekton['pluginConfig']['dynamicPlugins']['frontend']['backstage-community.plugin-tekton']['mountPoints'][0]
        self.assertEqual((point['mountPoint'], point['importName']), ('entity.page.ci/cards', 'TektonCI'))
        steps = yaml.safe_load((BASE / 'rhdh/templates/app-migration/template.yaml').read_text())['spec']['steps']
        ids = [s['id'] for s in steps]
        self.assertLess(ids.index('require-mta-hub'), ids.index('publish'))
        guard = steps[ids.index('require-mta-hub')]
        self.assertIn('mta-hub-url', guard['if'])
        self.assertEqual(guard['input']['url'], './refusals/FACTORY_MTA_HUB_MISSING')

    def test_coolstore_namespace_precedes_its_delivery_bindings(self):
        namespace = yaml.safe_load((BASE / 'coolstore/namespace.yaml').read_text())
        binding = yaml.safe_load((BASE / 'pipelines/project-pipeline/rbac-image-builder.yaml').read_text())
        self.assertLess(int(namespace['metadata']['annotations']['argocd.argoproj.io/sync-wave']),
                        int(binding['metadata']['annotations']['argocd.argoproj.io/sync-wave']))

    def test_archive_is_complete_and_rejects_links_before_publication(self):
        def archive(files, link=False):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                for path, content in files.items():
                    item = tarfile.TarInfo('platform-ref/stages/golden/' + path)
                    item.size = len(content)
                    tar.addfile(item, io.BytesIO(content))
                if link:
                    item = tarfile.TarInfo('platform-ref/stages/golden/redirect')
                    item.type = tarfile.SYMTYPE; item.linkname = '/outside'
                    tar.addfile(item)
            return stream.getvalue()
        files = {'devfile.yaml': b'schemaVersion: 2.2.2\n', 'AGENTS.md': b'reviewed\n'}
        self.assertEqual(set(bootstrap.golden_files(archive(files), 'stages/golden')), set(files))
        for contents in (archive({'devfile.yaml': b'incomplete'}), archive(files, link=True), archive({**files, '../foreign': b'bad'})):
            with self.assertRaises((RuntimeError, ValueError)):
                bootstrap.golden_files(contents, 'stages/golden')

    def test_platform_mirror_push_is_normal_and_does_not_expose_credentials(self):
        from unittest.mock import patch
        with patch.object(bootstrap.subprocess, 'run') as run:
            bootstrap.sync_platform_revision('https://github.com/adnan-drina/rhoai3-coding-demo.git',
                'https://gitlab.example.test/rhoai-platform/rhoai3-coding-demo.git', 'a' * 40, 'synthetic-token')
            argv = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any('merge-base' in args and '--is-ancestor' in args for args in argv))
            self.assertIn(['push', '--atomic', 'origin', 'a' * 40 + ':refs/heads/main'], [a[-4:] for a in argv])
            self.assertNotIn('synthetic-token', json.dumps(argv))
            self.assertFalse(any('--force' in a or '--force-with-lease' in a for a in argv))
        with self.assertRaises(ValueError):
            bootstrap.sync_platform_revision('https://outside.test/repo.git', 'https://gitlab.example.test/rhoai-platform/rhoai3-coding-demo.git', 'a' * 40, 'synthetic')

    def test_membership_requires_the_same_oidc_subject(self):
        self.assertTrue(bootstrap.check_oidc_identity({'identities': [{'provider': 'openid_connect', 'extern_uid': 'reviewed-subject'}]}, 'reviewed-subject'))
        self.assertFalse(bootstrap.check_oidc_identity({'identities': []}, 'reviewed-subject'))
        with self.assertRaises(RuntimeError):
            bootstrap.check_oidc_identity({'identities': [{'provider': 'openid_connect', 'extern_uid': 'foreign'}]}, 'reviewed-subject')

    def test_import_retry_uses_the_reviewed_file_commit(self):
        contents = 'reviewed runtime\n'
        row = {'encoding': 'base64', 'content': base64.b64encode(contents.encode()).decode(),
               'last_commit_id': 'b' * 40}
        self.assertEqual(bootstrap.imported_runtime_commit(row, contents), 'b' * 40)
        for bad in ({**row, 'content': base64.b64encode(b'foreign runtime').decode()},
                    {**row, 'last_commit_id': 'main'}, {**row, 'encoding': 'text'}):
            with self.assertRaises(RuntimeError): bootstrap.imported_runtime_commit(bad, contents)

    def test_golden_is_one_normal_commit_and_reconcile_is_noop(self):
        files = {'a.txt': (b'new\n', False), 'run.sh': (b'#!/bin/sh\n', True)}
        actions = bootstrap.golden_actions(files, {'a.txt': {'id': 'foreign', 'mode': '100644'},
                                                  'obsolete': {'id': 'old', 'mode': '100644'}})
        self.assertEqual([a['action'] for a in actions], ['update', 'create', 'delete'])
        self.assertTrue(actions[1]['execute_filemode'])
        import hashlib
        current = {p: {'id': hashlib.sha1(b'blob ' + str(len(c)).encode() + b'\0' + c).hexdigest(),
                       'mode': '100755' if executable else '100644'} for p, (c, executable) in files.items()}
        self.assertEqual(bootstrap.golden_actions(files, current), [])
        for path in ('../foreign', '.git/config', '.hermes/_park/old', 'run-chaos-matrix.py'):
            with self.assertRaises(ValueError): bootstrap.golden_actions({path: (b'bad', False)}, {})

    def test_gitlab_sso_and_signing_share_the_verified_platform_issuer(self):
        issuer = 'https://sso.example.test/realms/platform'
        provider = oidc.provider(issuer, 'gitlab.example.test', 'synthetic-client-secret')['args']
        self.assertEqual(provider['issuer'], issuer)
        self.assertEqual(provider['uid_field'], 'sub')
        self.assertEqual(provider['client_options']['redirect_uri'],
                         'https://gitlab.example.test/users/auth/openid_connect/callback')
        self.assertEqual(signing.issuer_configuration('sso.example.test')[0]['issuer'], issuer)
        for host in ('bad/path', ''):
            with self.assertRaises(ValueError): oidc.provider(issuer, host, 'synthetic')

    def test_credentials_are_ready_during_sync_not_after_it(self):
        for name, wave in [('mta/jobs/configure-ai.yaml', '10'),
                           ('mta/jobs/configure-mta-platform-sso.yaml', '10'),
                           ('rhdh/jobs/configure-rhdh.yaml', '18')]:
            docs = list(yaml.safe_load_all((BASE / name).read_text()))
            job = next(d for d in docs if d['kind'] == 'Job')
            annotations = job['metadata']['annotations']
            self.assertEqual(annotations['argocd.argoproj.io/hook'], 'Sync')
            self.assertEqual(annotations['argocd.argoproj.io/sync-wave'], wave)

    def test_noobaa_claims_and_disabled_duplicate_components(self):
        claims = list(yaml.safe_load_all((BASE / 'gitlab/buckets.yaml').read_text()))
        self.assertEqual(len(claims), 6)
        for claim in claims:
            self.assertEqual(claim['spec']['storageClassName'], 'openshift-storage.noobaa.io')
            self.assertEqual(claim['metadata']['annotations']['argocd.argoproj.io/sync-options'], 'Prune=false')
        values = yaml.safe_load((BASE / 'gitlab/values.yaml').read_text())
        for field in ('postgresql', 'redis', 'prometheus', 'gitlab-runner'): self.assertFalse(values[field]['install'])
        self.assertFalse(values['global']['registry']['enabled'])
        self.assertFalse(values['global']['minio']['enabled'])
        self.assertFalse(values['nginx-ingress']['enabled'])
        rendered_identity = subprocess.check_output(['kustomize', 'build', str(BASE / 'identity')], text=True)
        kinds = [d['kind'] for d in yaml.safe_load_all(rendered_identity)]
        self.assertNotIn('Keycloak', kinds); self.assertNotIn('Subscription', kinds)

    def test_key_unknown_and_foreign_states_are_not_rotation(self):
        principal, sub = 'owner', 'mta-migration-ai'
        self.assertTrue(ai.active_key({'username': principal, 'subscription': sub, 'status': 'active'}, principal, sub))
        self.assertFalse(ai.active_key({'username': principal, 'subscription': sub, 'status': 'expired'}, principal, sub))
        for row in ({}, {'username': 'foreign', 'subscription': sub, 'status': 'active'}, {'username': principal, 'subscription': sub, 'status': 'unknown'}):
            with self.assertRaises(ValueError): ai.active_key(row, principal, sub)

    def test_no_old_shared_push_or_direct_apply_path(self):
        pipeline = yaml.safe_load((BASE / 'pipelines/project-pipeline/pipeline.yaml').read_text())
        deploy = next(t for t in pipeline['spec']['tasks'] if t['name'] == 'deploy')
        self.assertEqual(deploy['taskRef']['name'], 'promote-gitlab-runtime')
        self.assertFalse((BASE / 'pipelines/build/triggers.yaml').exists())
        self.assertFalse((BASE / 'devspaces/workspace-git-credentials.yaml').exists())
        self.assertNotIn('oc apply', (BASE / 'pipelines/project-pipeline/promote.py').read_text())
        self.assertNotIn('oc delete pod', (BASE / 'devspaces/workspace-sonar-credentials.yaml').read_text())




class HookRuntime(unittest.TestCase):
    def test_python36_subprocess_contract(self):
        # The exact pinned ose-cli image runs Python 3.6. Newer keyword aliases
        # failed the real first-sync hook before its first API read.
        import ast
        scripts = [BASE / p for p in (
            'gitlab/configure-argocd-reader.py', 'gitlab/bootstrap.py',
            'gitlab/bootstrap-oidc.py', 'gitlab/bootstrap-scm.py',
            'pipelines/gitlab/reconcile.py', 'pipelines/project-pipeline/promote.py',
            'pipelines/signing/configure-signing.py', 'mta/jobs/configure-ai.py')]
        for script in scripts:
            tree = ast.parse(script.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess':
                        with self.subTest(script=script.name, line=node.lineno):
                            self.assertFalse({'text', 'capture_output'} & {k.arg for k in node.keywords})

if __name__ == '__main__': unittest.main()
