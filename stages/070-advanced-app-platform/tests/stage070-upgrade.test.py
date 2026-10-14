#!/usr/bin/env python3
"""Focused contract and adversarial tests for the integrated Stage 070 upgrade."""
import copy
import base64
import hashlib
import importlib.util
import json
import io
import re
import tarfile
import subprocess
import unittest
import tempfile
import os
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'gitops/stages/070-advanced-app-platform'
sys.path.insert(0, str(BASE / 'pipelines/gitlab'))


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
        role = yaml.safe_load((BASE / 'pipelines/project-enrollment/listener-role.yaml').read_text())
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


class CatalogEnvelope(unittest.TestCase):
    def test_rendered_annotations_remain_strings_for_numeric_gitlab_id(self):
        renderer = module('catalog_renderer', 'rhdh/jobs/catalog/render_catalog.py')
        body = renderer.render((BASE / 'rhdh/catalog/all.yaml').read_text(),
            revision='a' * 40, devspaces_url='https://devspaces.example.test',
            rhdh_url='https://rhdh.example.test', coolstore_url='https://inventory.example.test',
            sonarqube_url='https://sonar.example.test', maas_host='maas.example.test',
            maas_internal_ip='172.30.0.1', scm={
                'PLATFORM_CATALOG_REPO': 'https://gitlab.example.test/platform/demo.git',
                'GITLAB_HOST': 'gitlab.example.test', 'GITLAB_BASE_URL': 'https://gitlab.example.test',
                'GITLAB_WORKLOAD_GROUP': 'workloads', 'GITLAB_REGISTRATION_PROJECT_ID': 42,
                'agentic-quarkus-scaffold': 'https://gitlab.example.test/platform/app/-/tree/abc',
                'quarkus-migration-scaffold-v2': 'https://gitlab.example.test/platform/migration/-/tree/abc',
                'MTA_HUB_URL': 'https://mta.example.test',
            })
        entities = list(yaml.safe_load_all(body))
        component = next(e for e in entities if e and e.get('kind') == 'Component'
                         and e['metadata']['name'] == 'coolstore-inventory-service')
        self.assertEqual(component['metadata']['annotations'][
            'rhoai3.redhat.com/gitlab-registration-project-id'], '42')
        for entity in entities:
            if entity:
                for key, value in entity['metadata'].get('annotations', {}).items():
                    self.assertIsInstance(value, str, (entity['metadata']['name'], key))


class IntegratedContract(unittest.TestCase):
    def test_mta_consumers_use_the_governed_model_id(self):
        tackle = yaml.safe_load((BASE / 'mta/mta-instance/tackle.yaml').read_text())
        gateway = next(row for row in yaml.safe_load_all((BASE / 'mta/jobs/configure-ai.yaml').read_text())
                       if row['kind'] == 'Gateway')
        alias = 'publishers/internal-models/models/qwen3-8-27b'
        self.assertEqual(tackle['spec']['kai_llm_model'], alias)
        self.assertEqual(gateway['spec']['model']['name'], alias)

    def test_argo_reader_keeps_existing_policy_and_is_idempotent(self):
        current = 'g, system:cluster-admins, role:admin\np, role:other, applications, get, other/*, allow\n'
        updated = reader.policy(current)
        self.assertTrue(updated.startswith(current))
        self.assertEqual(reader.policy(updated), updated)
        self.assertEqual([r for r in updated.splitlines() if 'rhdh' in r], reader.RULES)
        self.assertTrue(all(', get,' in r or r.startswith('g, ') for r in reader.RULES))

    def test_argo_plugins_follow_110_oci_packaging(self):
        plugins = yaml.safe_load(yaml.safe_load((BASE / 'rhdh/rhdh-instance/dynamic-plugins-configmap.yaml').read_text())['data']['dynamic-plugins.yaml'])['plugins']
        packages = [p['package'] for p in plugins if 'argocd' in p['package'] or 'argo-cd' in p['package']]
        self.assertEqual(len(packages), 2)
        self.assertTrue(all(p.startswith('oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/') and '@sha256:' in p for p in packages))

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

    def test_sonarqube_database_guard_names_the_rendered_deployment(self):
        guard = re.search(r'oc get deployment (\S+) -n sonarqube', (ROOT / 'stages/070-advanced-app-platform/deploy.sh').read_text()).group(1)
        rendered = [d['metadata']['name'] for d in yaml.safe_load_all((BASE / 'sonarqube/postgresql.yaml').read_text())
                    if d and d['kind'] == 'Deployment']
        self.assertEqual(rendered, [guard])

    def test_coolstore_namespace_precedes_its_delivery_bindings(self):
        namespace = next(d for d in yaml.safe_load_all((BASE / 'namespaces/namespaces.yaml').read_text())
                         if d and d['metadata']['name'] == 'coolstore-dev')
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
                'https://gitlab-gitlab-system.example.test/rhoai-platform/rhoai3-coding-demo.git', 'a' * 40, 'synthetic-token')
            argv = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any('merge-base' in args and '--is-ancestor' in args for args in argv))
            self.assertIn(['push', '--atomic', 'origin', 'a' * 40 + ':refs/heads/main'], [a[-4:] for a in argv])
            self.assertNotIn('synthetic-token', json.dumps(argv))
            self.assertFalse(any('--force' in a or '--force-with-lease' in a for a in argv))
        with self.assertRaises(ValueError):
            bootstrap.sync_platform_revision('https://outside.test/repo.git', 'https://gitlab.example.test/rhoai-platform/rhoai3-coding-demo.git', 'a' * 40, 'synthetic')
        with self.assertRaises(ValueError):
            bootstrap.sync_platform_revision('https://github.com/adnan-drina/rhoai3-coding-demo.git',
                'https://gitlab-gitlab-system.example.test/rhoai-workloads/rhoai3-coding-demo.git', 'a' * 40, 'synthetic')

    def test_membership_requires_the_same_oidc_subject(self):
        self.assertTrue(bootstrap.check_oidc_identity({'identities': [{'provider': 'openid_connect', 'extern_uid': 'reviewed-subject'}]}, 'reviewed-subject'))
        self.assertFalse(bootstrap.check_oidc_identity({'identities': []}, 'reviewed-subject'))
        with self.assertRaises(RuntimeError):
            bootstrap.check_oidc_identity({'identities': [{'provider': 'openid_connect', 'extern_uid': 'foreign'}]}, 'reviewed-subject')

    def test_personas_create_valid_gitlab_names_with_the_original_subject(self):
        from unittest.mock import Mock
        for name, expected in bootstrap.PERSONA_USERNAMES.items():
            persona = {'username': name, 'id': 'verified-subject', 'email': name+'@example.invalid'}
            api = Mock(return_value={'id': 3, 'username': expected})
            account = bootstrap.ensure_persona(api, lambda path, query: [], persona)
            self.assertEqual(account['username'], expected)
            data = api.call_args.args[2]
            self.assertEqual(data['extern_uid'], persona['id'])
            self.assertEqual(data['provider'], 'openid_connect')
            self.assertFalse(expected.startswith(('ai-', 'ai_', 'duo-', 'duo_')))
            api.reset_mock()
            linked = {**account, 'identities': [{'provider': 'openid_connect', 'extern_uid': persona['id']}]}
            self.assertEqual(bootstrap.ensure_persona(api, lambda path, query: [linked], persona), linked)
            api.assert_not_called()
            linked['identities'][0]['extern_uid'] = 'foreign-subject'
            with self.assertRaises(RuntimeError): bootstrap.ensure_persona(api, lambda path, query: [linked], persona)
            api.assert_not_called()

    def test_native_git_url_import_enabled_without_local_network_access(self):
        settings = {'signup_enabled': True, 'import_sources': [], 'auto_devops_enabled': True,
                    'allow_local_requests_from_web_hooks_and_services': False}
        def api(method, path, payload):
            if path == 'application/settings':
                self.assertEqual(method, 'PUT')
                settings.update(payload)
                return settings
            if path == 'projects' and payload.get('import_url'):
                if 'git' not in settings['import_sources']: raise PermissionError('Importer disabled')
                return {'id': 42}
            raise AssertionError('unexpected API call')
        payload = {'import_url': 'https://github.com/adnan-drina/coolstore-inventory-service.git'}
        with self.assertRaises(PermissionError): api('POST', 'projects', payload)
        bootstrap.configure_imports(api)
        self.assertEqual(api('POST', 'projects', payload)['id'], 42)
        self.assertFalse(settings['signup_enabled'])
        self.assertFalse(settings['auto_devops_enabled'])
        self.assertEqual(settings['import_sources'], ['git'])
        self.assertFalse(settings['allow_local_requests_from_web_hooks_and_services'])

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

    def test_large_inventory_keeps_small_publication_and_the_actual_size_bound(self):
        contents = {'devfile.yaml': b'schemaVersion: 2.2.2\n', 'AGENTS.md': b'reviewed\n',
                    'large-existing.txt': b'x' * 8_000_000}
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for path, data in contents.items():
                item = tarfile.TarInfo('platform-ref/stages/golden/' + path)
                item.size = len(data); archive.addfile(item, io.BytesIO(data))
        files = bootstrap.golden_files(stream.getvalue(), 'stages/golden')
        current = {path: {'id': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
                          'mode': '100644'} for path, data in contents.items()}
        self.assertEqual(bootstrap.golden_actions(files, current), [])
        files['AGENTS.md'] = (b'new reviewed instruction\n', False)
        self.assertEqual([a['file_path'] for a in bootstrap.golden_actions(files, current)], ['AGENTS.md'])
        with self.assertRaises(RuntimeError): bootstrap.golden_actions(files, {})

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
        for name, wave in [('mta/jobs/configure-ai.yaml', '11'),
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




class GatewayAndPolicy(unittest.TestCase):
    def test_native_agents_do_not_require_solution_server_or_drop_auth(self):
        spec = yaml.safe_load((BASE / 'mta/mta-instance/tackle.yaml').read_text())['spec']
        self.assertTrue(spec['agentic_enabled'])
        self.assertFalse(spec['agentic_steer_enabled'])
        self.assertFalse(spec['kai_solution_server_enabled'])
        # The vendor kai.yml retains its common DB and PVC while the proxy is
        # enabled. Disabling both is a separate lifecycle decision.
        self.assertTrue(spec['kai_llm_proxy_enabled'])
        self.assertTrue(spec['feature_auth_required'])
        self.assertTrue(spec['idp_primary'])

    def test_deferred_operand_absence_is_not_an_api_error_or_readiness(self):
        import re
        library = (ROOT / 'scripts/shared/validate-lib.sh').read_text()
        check_function = re.search(r'(?ms)^check\(\) \{.*?^\}', library).group()
        validator = (ROOT / 'stages/070-advanced-app-platform/validate.sh').read_text()
        check_line = next(s for s in validator.splitlines() if s.startswith("check 'Deferred Solution Server"))
        for stdout, status, failures in [('', 0, 0), ('deployment.apps/kai-api', 0, 1), ('', 1, 1)]:
            script = 'set -euo pipefail\nGREEN= RED= NC=\nVALIDATE_PASS=0\nVALIDATE_FAIL=0\n'
            script += check_function + '\noc() { printf "%s" "$TEST_RESULT"; return "$TEST_STATUS"; }\n'
            script += check_line + '\nprintf "FAILURES=%s\\n" "$VALIDATE_FAIL"\n'
            result = subprocess.run(['bash'], input=script, env=dict(os.environ, TEST_RESULT=stdout, TEST_STATUS=str(status)),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('FAILURES=' + str(failures), result.stdout)

    def test_native_gateway_apply_precedes_endpoint_bootstrap(self):
        resources = list(yaml.safe_load_all((BASE / 'mta/jobs/configure-ai.yaml').read_text()))
        gateway = next(row for row in resources if row['kind'] == 'Gateway')
        hook = next(row for row in resources if row['kind'] == 'Job')
        wave = lambda row: int(row['metadata']['annotations']['argocd.argoproj.io/sync-wave'])
        self.assertGreater(wave(hook), wave(gateway))

    def test_live_endpoint_checks_refuse_extra_path_segments(self):
        import re, shlex
        library = (ROOT / 'scripts/shared/validate-lib.sh').read_text()
        check_function = re.search(r'(?ms)^check\(\) \{.*?^\}', library).group()
        contains_function = next(x for x in library.splitlines() if x.startswith('contains()'))
        validator = (ROOT / 'stages/070-advanced-app-platform/validate.sh').read_text()
        section = validator[validator.index('MTA_MAAS_ORIGIN='):validator.index("log_step 'Signing service")]
        fake = """oc() {
  if [[ "$2" == gateway.gateway.networking.k8s.io ]]; then
    printf '%s' '{"spec":{"listeners":[{"hostname":"maas.example.test"}]}}'
  elif [[ "$2" == gateways.konveyor.io ]]; then
    printf '%s' "$TEST_NATIVE_ENDPOINT"
  else
    printf '%s' "$TEST_PROXY_BASE"
  fi
}
"""
        origin = 'https://maas.example.test'
        for native, proxy, failures in [(origin, origin+'/v1', 0),
                                         (origin+'/v1', origin+'/v1', 1),
                                         (origin+'/v1/v1', origin+'/v1', 1),
                                         (origin, origin+'/v1/extra', 1)]:
            script = 'set -euo pipefail\nGREEN= RED= NC=\nVALIDATE_PASS=0\nVALIDATE_FAIL=0\nPYTHON='+shlex.quote(sys.executable)+'\n'
            script += check_function+'\n'+contains_function+'\n'+fake+section
            script += '\nprintf "FAILURES=%s\\n" "$VALIDATE_FAIL"\n'
            result = subprocess.run(['bash'], input=script, env=dict(os.environ, TEST_NATIVE_ENDPOINT=native, TEST_PROXY_BASE=proxy),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('FAILURES='+str(failures), result.stdout, result.stdout)

    def test_native_gateway_origin_is_distinct_from_lightspeed_api_base(self):
        from unittest.mock import patch
        calls = []
        def fake_oc(*args, **kwargs):
            calls.append(args)
            if args[:2] == ('get', 'gateway.gateway.networking.k8s.io'):
                return {'spec': {'listeners': [{'hostname': 'maas.example.test'}]}}
            if args[:2] == ('get', 'secret'):
                return {'data': {'MAAS_KEY_ID': base64.b64encode(b'test-key-id').decode(),
                                 'OPENAI_API_KEY': base64.b64encode(b'test-only').decode()}}
        owner = {'username': 'system:serviceaccount:openshift-mta:mta-maas-provisioner',
                 'subscription': 'mta-migration-ai', 'status': 'active'}
        with patch.object(ai, 'oc', side_effect=fake_oc), \
             patch.object(ai.Path, 'read_text', return_value='test-service-account-token'), \
             patch.object(ai.urllib.request, 'urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value = io.BytesIO(json.dumps(owner).encode())
            ai.main()
        patches = {call[1]: json.loads(call[-1])['spec'] for call in calls if call[0] == 'patch' and call[1] in ('tackle', 'gateways.konveyor.io')}
        self.assertEqual(patches['tackle']['kai_llm_baseurl'], 'https://maas.example.test/v1')
        endpoint = patches['gateways.konveyor.io']['endpoint']
        # Pinned vendor gateway_controller.go adds /v1/models to the origin.
        self.assertEqual(endpoint + '/v1/models', 'https://maas.example.test/v1/models')
        resources = list(yaml.safe_load_all((BASE / 'mta/jobs/configure-ai.yaml').read_text()))
        gateway = next(row for row in resources if row['kind'] == 'Gateway')
        self.assertEqual(gateway['spec']['endpoint'], 'https://maas.pending.invalid')
        self.assertFalse(any(call[0] == 'apply' for call in calls), 'Existing key must be reused')

    def test_maas_host_from_current_gateway_not_listener_name(self):
        gateway = yaml.safe_load((ROOT / 'gitops/stages/040-governed-models-as-a-service/gateway-governance/gateway/gateway.yaml').read_text())
        self.assertEqual(ai.gateway_host(gateway), 'maas.placeholder.example.com')
        for listeners in ([], [{'name':'https','hostname':'qwen3-8-maas.example'}], [{'hostname':'maas.one.example'},{'hostname':'maas.two.example'}]):
            with self.assertRaises(ValueError): ai.gateway_host({'spec':{'listeners':listeners}})

    def test_shared_operator_namespace_keeps_automatic(self):
        for name in ('pipelines-subscription.yaml','rhtas-subscription.yaml'):
            sub=yaml.safe_load((BASE/'pipelines/operators'/name).read_text())
            self.assertEqual(sub['spec']['installPlanApproval'],'Automatic')


class InitialInstall(unittest.TestCase):
    def test_mta_configurator_can_read_only_the_objects_it_patches(self):
        rows=list(yaml.safe_load_all((BASE/'mta/jobs/configure-ai.yaml').read_text()))
        role=next(r for r in rows if r['kind']=='Role' and r['metadata']['namespace']=='openshift-mta')
        for resource,name in (('tackles','mta'),('gateways','maas-qwen')):
            rule=next(r for r in role['rules'] if resource in r['resources'])
            self.assertEqual(set(rule['verbs']),{'get','patch'})
            self.assertEqual(rule['resourceNames'],[name])
        link=yaml.safe_load((BASE/'mta/mta-instance/consolelink.yaml').read_text())
        sso=list(yaml.safe_load_all((BASE/'mta/jobs/configure-mta-platform-sso.yaml').read_text()))
        job=next(r for r in sso if r['kind']=='Job')
        self.assertLess(int(link['metadata']['annotations']['argocd.argoproj.io/sync-wave']),int(job['metadata']['annotations']['argocd.argoproj.io/sync-wave']))

    def test_reused_keycloak_served_import_api(self):
        realm = yaml.safe_load((BASE / 'identity/rhbk-instance/realm-platform.yaml').read_text())
        self.assertEqual(realm['apiVersion'], 'k8s.keycloak.org/v2alpha1')
        self.assertEqual(realm['spec']['keycloakCRName'], 'keycloak')

    def test_native_tasks_follow_operator_install(self):
        for path in (BASE / 'pipelines/project-pipeline').glob('*.yaml'):
            for resource in yaml.safe_load_all(path.read_text()):
                if isinstance(resource, dict) and resource.get('kind') in ('Task', 'Pipeline'):
                    with self.subTest(resource=resource['metadata']['name']):
                        self.assertGreaterEqual(int(resource['metadata'].get('annotations', {}).get('argocd.argoproj.io/sync-wave', '0')), 20)


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


class WorkspaceAnnotationRepair(unittest.TestCase):
    def run_repair(self, state, fail_get=False):
        rows=list(yaml.safe_load_all((BASE/'devspaces/repair-devworkspace-sync-options.yaml').read_text()))
        job=next(r for r in rows if r['kind']=='Job')
        script=job['spec']['template']['spec']['containers'][0]['command'][-1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); statefile=root/'state.json';statefile.write_text(json.dumps(state))
            fake=root/'oc'
            fake.write_text('#!'+sys.executable+'\n'+r"""
import json,os,sys
from pathlib import Path
p=Path(os.environ['FAKE_OC_STATE']);s=json.loads(p.read_text());a=sys.argv[1:]
ns=a[a.index('-n')+1];row=s['rows'].get(ns)
if a[0]=='get':
    if os.environ.get('FAIL_GET')=='true':raise SystemExit(42)
    if row is None:raise SystemExit(0 if '--ignore-not-found' in a else 1)
    if '-o' not in a:print(a[2])
    elif 'metadata.uid' in a[a.index('-o')+1]:print(row['uid'],end='')
    else:print(row.get('annotation',''),end='')
elif a[0]=='annotate':
    s['writes'].append(ns)
    if any(v.endswith('sync-options-') for v in a):row.pop('annotation',None)
    else:
        value=next(v.split('=',1)[1] for v in a if v.startswith('argocd.argoproj.io/sync-options='))
        row['annotation']=value
    p.write_text(json.dumps(s))
else:raise SystemExit('Unexpected mutation or command')
""")
            fake.chmod(0o755)
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],FAKE_OC_STATE=str(statefile),FAIL_GET='true' if fail_get else 'false')
            result=subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True)
            return result,json.loads(statefile.read_text())

    def test_current_workspace_annotation_is_not_deleted(self):
        state={'rows':{ns:{'uid':ns,'annotation':'SkipDryRunOnMissingResource=true','started':False} for ns in ('wksp-ai-developer','wksp-ai-admin')},'writes':[]}
        result,after=self.run_repair(state)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(after,state)

    def test_legacy_annotation_reconciles_without_lifecycle_change(self):
        state={'rows':{'wksp-ai-developer':{'uid':'a','annotation':'Force=true,Replace=true','started':False},'wksp-ai-admin':{'uid':'b','started':False}},'writes':[]}
        result,after=self.run_repair(state)
        self.assertEqual(result.returncode,0,result.stderr)
        for ns,row in after['rows'].items():
            self.assertEqual(row['annotation'],'SkipDryRunOnMissingResource=true')
            self.assertFalse(row['started'])
            self.assertEqual(row['uid'],state['rows'][ns]['uid'])
        self.assertEqual(len(after['writes']),2)
        result,again=self.run_repair(after)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(again,after)

    def test_absence_is_distinct_from_read_failure(self):
        state={'rows':{},'writes':[]}
        result,after=self.run_repair(state)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(after,state)
        result,after=self.run_repair(state,fail_get=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(after,state)

if __name__ == '__main__': unittest.main()
