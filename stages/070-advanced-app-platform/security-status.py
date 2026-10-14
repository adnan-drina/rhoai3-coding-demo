"""Read-only live checks for the Stage 070 correction's explicit boundaries."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SECRETS = [('rhdh', 'rhdh-gitlab'), ('openshift-gitops', 'rhdh-argocd-reader'),
           ('gitlab-system', 'gitlab-oidc'), ('openshift-mta', 'kai-api-keys'),
           ('app-platform-build', 'sonarqube-credentials'),
           ('openshift-devspaces', 'gitlab-oauth-config'), ('gitlab-system', 'stage070-scm-provisioner')]
CLIENTS = [('rhdh', 'stage070-rhdh-provisioner', 'rhdh'),
           ('openshift-mta', 'stage070-mta-provisioner', 'mta-hub'),
           ('trusted-artifact-signer', 'stage070-signing-provisioner', 'trusted-artifact-signer'),
           ('gitlab-system', 'stage070-scm-provisioner', 'gitlab')]
LAST_APPLIED = 'kubectl.kubernetes.io/last-applied-configuration'


def command(*args):
    return subprocess.check_output(args, universal_newlines=True, stderr=subprocess.PIPE, timeout=30).strip()


def oc(*args):
    return json.loads(command('oc', '--request-timeout=15s', *args, '-o', 'json'))


def denied(verb, resource, namespace, principal):
    result = subprocess.run(['oc', '--request-timeout=15s', 'auth', 'can-i', verb, resource,
                            '-n', namespace, '--as=' + principal], universal_newlines=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.stdout.strip() not in ('yes', 'no'):
        raise RuntimeError('Authorization result unavailable')
    return result.stdout.strip() == 'no'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-stopped', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    expected = os.environ.get('RHOAI_EXPECTED_API_SERVER')
    if not expected or expected not in command('oc', 'whoami', '--show-server'):
        raise ValueError('Project API-server guard is required')
    checks = {}
    for ns, name in SECRETS:
        value = oc('get', 'secret', name, '-n', ns)
        checks['no_credential_annotation:' + ns + '/' + name] = LAST_APPLIED not in value['metadata'].get('annotations', {})
    # The original seven-name review was a sample. Inspect the bounded developer
    # platform estate too, but never log or persist Secret values/annotations.
    namespaces = {'gitlab-system', 'rhdh', 'openshift-mta', 'openshift-devspaces', 'openshift-gitops',
                  'app-platform-build', 'sonarqube', 'trusted-artifact-signer', 'wksp-ai-developer', 'wksp-ai-admin', 'coolstore-dev'}
    namespaces.update(x['metadata']['name'] for x in oc('get', 'namespaces', '-l', 'rhoai3.redhat.com/pipeline-project=true')['items'])
    for ns in sorted(namespaces):
        values = oc('get', 'secrets', '-n', ns)['items']
        checks['no_retained_secret_annotation:' + ns] = all(LAST_APPLIED not in x['metadata'].get('annotations', {}) for x in values)
    apps = oc('get', 'applications', '-n', 'openshift-gitops')['items']
    # Generated project-*/runtime-* Applications carry the stage label too; components are the rhoai-demo ones.
    components = [a for a in apps if a['metadata'].get('labels', {}).get('demo.rhoai.io/stage') == '070'
                  and a['spec'].get('project') == 'rhoai-demo']
    selected = components + [a for a in apps if a['spec'].get('project') in ('platform-projects', 'runtime-projects')]
    checks['diff_strategy_on_stage_and_generated_apps'] = bool(selected) and all(
        'ServerSideDiff=true' in a['metadata'].get('annotations', {}).get('argocd.argoproj.io/compare-options', '').split(',') for a in selected)
    checks['no_client_apply_migration_for_declarative_secrets'] = bool(components) and all(
        'ClientSideApplyMigration=false' in a['spec'].get('syncPolicy', {}).get('syncOptions', []) for a in components)
    claims = [x for a in components for x in a['spec'].get('ignoreDifferences', []) if x.get('kind') == 'PersistentVolumeClaim']
    checks['only_named_controller_pvc_fields_ignored'] = bool(claims) and all(
        x.get('name') and x.get('namespace') and x.get('jsonPointers') == ['/spec/volumeName'] for x in claims)
    bootstrap = 'system:serviceaccount:gitlab-system:gitlab-integrations-bootstrap'
    checks['idle_bootstrap_cannot_exec'] = denied('create', 'pods/exec', 'gitlab-system', bootstrap)
    checks['idle_bootstrap_cannot_write_credentials'] = all(denied('create', 'secrets', ns, bootstrap)
        for ns in ('gitlab-system', 'rhdh', 'app-platform-build', 'openshift-devspaces'))
    for ns, sa in [('rhdh', 'job-configure-rhdh'), ('openshift-mta', 'job-configure-mta-sso'),
                   ('trusted-artifact-signer', 'configure-signing')]:
        checks['no_master_secret:' + ns + '/' + sa] = denied('get', 'secret/keycloak-initial-admin', 'keycloak', 'system:serviceaccount:' + ns + ':' + sa)
    host = oc('get', 'route', 'keycloak', '-n', 'keycloak')['spec']['host']
    base = 'https://' + host
    for ns, secret, target in CLIENTS:
        raw = oc('get', 'secret', secret, '-n', ns)['data']
        credentials = {k: base64.b64decode(raw[k]).decode() for k in ('client_id', 'client_secret')}
        req = urllib.request.Request(base + '/realms/platform/protocol/openid-connect/token',
            urllib.parse.urlencode(dict(grant_type='client_credentials', **credentials)).encode())
        with urllib.request.urlopen(req, timeout=30) as response:
            token = json.load(response)['access_token']
        req = urllib.request.Request(base + '/admin/realms/platform/clients?clientId=' + target,
                                     headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(req, timeout=30) as response:
            rows = json.load(response)
        checks['scoped_client_can_read_its_platform_configuration:' + secret] = len(rows) == 1 and rows[0]['clientId'] == target
        for realm in ('sso', 'master'):
            refused = False
            try:
                urllib.request.urlopen(urllib.request.Request(base + '/admin/realms/' + realm,
                    headers={'Authorization': 'Bearer ' + token}), timeout=30)
            except urllib.error.HTTPError as error:
                if error.code not in (401, 403):
                    raise
                refused = True
            checks['scoped_client_cannot_administer:' + secret + '/' + realm] = refused
    for ns in ('gitlab-system', 'sonarqube', 'rhdh', 'app-platform-build', 'trusted-artifact-signer'):
        policies = oc('get', 'networkpolicy', 'platform-ingress', '-n', ns)
        checks['ingress_policy_installed:' + ns] = policies['spec'].get('policyTypes') == ['Ingress']
    if args.models_stopped:
        model = oc('get', 'llminferenceservice', 'qwen3-8-27b', '-n', 'internal-models')
        int4 = oc('get', 'inferenceservice', 'qwen3-8-27b-int4', '-n', 'evaluated-models')
        checks['both_models_stopped'] = model['spec'].get('replicas') == 0 and int4['metadata'].get('annotations', {}).get('serving.kserve.io/stop') == 'true'
        gpu = [x for x in oc('get', 'machinesets', '-n', 'openshift-machine-api')['items'] if 'gpu' in x['metadata']['name']]
        checks['gpu_machinesets_stopped'] = bool(gpu) and all(x['spec'].get('replicas') == 0 for x in gpu)
    result = {'checks': checks, 'passed': all(checks.values()), 'inference_performed': False}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    for key, value in checks.items():
        print(('PASS: ' if value else 'FAIL: ') + key)
    if not result['passed']:
        raise ValueError('Stage 070 security boundaries are not all qualified')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit('Security validation stopped: ' + type(error).__name__ + '; credential values redacted')
