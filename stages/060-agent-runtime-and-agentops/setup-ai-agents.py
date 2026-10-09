#!/usr/bin/env python3
"""Create/check only the ai-agents native workspace and verified ai-admin membership.

Kubernetes operands are GitOps-owned. No sandbox, provider, model or identity edits.
Bootstrap tokens exist only in a private temporary native CLI profile, removed on exit.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from native_api import guarded, oc, need

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = 'ai-agents'
LABELS = {'app.kubernetes.io/managed-by': 'openshell-runtime', 'app.kubernetes.io/part-of': 'rhoai3-coding-demo'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision', required=True)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    env = guarded(os.environ.get('KUBECONFIG', str(Path.home() / '.kube/config')))
    path = str(Path(__file__).relative_to(ROOT))
    need(subprocess.check_output(['git', '-C', str(ROOT), 'show', args.revision + ':' + path]) == Path(__file__).read_bytes(), 'Helper differs from selected published source')
    cli = Path(os.environ.get('RHOAI_STAGE060_OPENSHELL_CLI', ''))
    pins = json.loads((ROOT / 'gitops/stages/060-agent-runtime-and-agentops/runtime-candidate/source-pins.json').read_text())
    need(cli.is_file() and hashlib.sha256(cli.read_bytes()).hexdigest() == pins['cliBinarySha256'], 'Set RHOAI_STAGE060_OPENSHELL_CLI to the pinned native CLI')
    def get(kind, name, ns=None):
        return json.loads(oc(env, 'get', kind, name, *(['-n', ns] if ns else []), '-o', 'json'))
    app = get('application', 'openshell-runtime', 'openshift-gitops')
    need(app['spec']['source']['targetRevision'] == args.revision and app['status']['sync']['revision'] == args.revision and app['status']['sync']['status'] == 'Synced' and app['status']['health']['status'] == 'Healthy' and not app.get('operation'), 'Exact runtime GitOps revision is not ready')
    ns = get('namespace', WORKSPACE)
    need(ns['metadata']['labels'].get('rhoai3.redhat.com/openshell-workspace') == 'true' and ns['metadata']['labels'].get('opendatahub.io/dashboard') == 'true' and not ns['metadata'].get('deletionTimestamp'), 'GitOps workspace namespace is not admitted')
    binding = get('rolebinding', 'openshell-sandbox', WORKSPACE)
    need(binding['roleRef'] == {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'openshell-sandbox'} and binding['subjects'] == [{'kind': 'ServiceAccount', 'name': 'openshell', 'namespace': 'openshell'}], 'Native gateway workspace binding differs')
    issuer = get('configmap', 'openshell-identity', 'openshell')['data']['issuer']
    need(issuer.startswith('https://') and issuer.endswith('/realms/openshell'), 'Unexpected native issuer')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    http = urllib.request.build_opener(NoRedirect())
    def request(url, form=None, token=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        try:
            with http.open(urllib.request.Request(url, data=data, headers=headers), timeout=15) as response:
                return json.load(response)
        except Exception:
            raise RuntimeError('Bounded native identity API request failed') from None
    admin = get('secret', 'keycloak-initial-admin', 'keycloak')
    kc = get('keycloak', 'keycloak', 'keycloak')
    need(any(o.get('uid') == kc['metadata']['uid'] and o.get('kind') == 'Keycloak' for o in admin['metadata'].get('ownerReferences', [])), 'Foreign identity bootstrap owner')
    base = issuer.rsplit('/realms/', 1)[0]
    master = request(base + '/realms/master/protocol/openid-connect/token', {'grant_type': 'password', 'client_id': 'admin-cli', 'username': base64.b64decode(admin['data']['username']).decode(), 'password': base64.b64decode(admin['data']['password']).decode()})['access_token']
    users = request(base + '/admin/realms/openshell/users?username=ai-admin&exact=true', token=master)
    need(len(users) == 1 and users[0].get('enabled'), 'Managed ai-admin identity is absent or ambiguous')
    user = users[0]
    uid = get('user', 'ai-admin')['metadata']['uid']
    need(user.get('attributes', {}).get('openshell-managed') == ['rhoai3-coding-demo'] and user['attributes'].get('openshift-uid') == [uid], 'Managed immutable identity mapping differs')
    links = request(base + '/admin/realms/openshell/users/' + user['id'] + '/federated-identity', token=master)
    need(links == [{'identityProvider': 'openshift-v4', 'userId': uid, 'userName': 'ai-admin'}], 'Native broker identity mapping differs')
    secret = get('secret', 'openshell-auth', 'keycloak')
    token = request(issuer + '/protocol/openid-connect/token', {'grant_type': 'client_credentials', 'client_id': 'openshell-bootstrap', 'client_secret': base64.b64decode(secret['data']['bootstrap-client-secret']).decode()})['access_token']
    claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=' * (-len(token.split('.')[1]) % 4)))
    need(claims.get('iss') == issuer and 'openshell-platform-admin' in claims.get('realm_access', {}).get('roles', []), 'Native bootstrap is not platform administrator')
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0)); port = reserved.getsockname()[1]
    forward = subprocess.Popen(['oc', '--request-timeout=10s', 'port-forward', 'svc/openshell', f'{port}:8080', '-n', 'openshell', '--address=127.0.0.1'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 15
        while True:
            need(forward.poll() is None and time.monotonic() < end, 'Native gateway tunnel unavailable')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2): break
            except OSError: time.sleep(.2)
        with tempfile.TemporaryDirectory(prefix='ai-agents-native-') as home:
            directory = Path(home) / 'openshell/gateways/openshell'
            (directory / 'mtls').mkdir(parents=True)
            (Path(home) / 'openshell/active_gateway').write_text('openshell')
            metadata = {'name': 'openshell', 'gateway_endpoint': f'https://127.0.0.1:{port}', 'is_remote': True, 'gateway_port': port, 'auth_mode': 'oidc', 'oidc_issuer': issuer, 'oidc_client_id': 'openshell-bootstrap', 'oidc_audience': 'openshell-gateway'}
            (directory / 'metadata.json').write_text(json.dumps(metadata))
            (directory / 'mtls/ca.crt').write_bytes(base64.b64decode(oc(env, 'get', 'secret', 'openshell-server-tls', '-n', 'openshell', '-o', r'jsonpath={.data.ca\.crt}')))
            credential = directory / 'oidc_token.json'
            descriptor = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream: json.dump({'access_token': token, 'expires_at': claims['exp'], 'issuer': issuer, 'client_id': 'openshell-bootstrap'}, stream)
            def run(arguments, structured=True):
                result = subprocess.run([str(cli), '--gateway', 'openshell', *arguments], env=dict(env, XDG_CONFIG_HOME=home), capture_output=True, text=True, timeout=20)
                need(result.returncode == 0, 'Bounded native workspace operation failed; credentials and raw errors are suppressed')
                return json.loads(result.stdout) if structured else None
            def listed(arguments, key):
                result = run(arguments + ['-o', 'json'])
                need(not result.get('next_page_token'), 'Native workspace inventory exceeds one page; no partial reconciliation')
                return result[key]
            workspaces = listed(['workspace', 'list'], 'workspaces')
            existing = [w for w in workspaces if w['name'] == WORKSPACE]
            need(len(existing) <= 1, 'Ambiguous native workspace')
            changed = []
            if not existing:
                need(not args.check, 'Native ai-agents workspace is absent')
                run(['workspace', 'create', '--name', WORKSPACE, *[item for k, v in LABELS.items() for item in ('--label', k + '=' + v)]], False)
                changed.append('workspace-created')
            else:
                need(existing[0].get('labels') == LABELS and existing[0].get('status') == 'Active', 'Foreign or inactive ai-agents workspace; takeover refused')
            members = listed(['workspace', 'member', 'list', '--workspace', WORKSPACE], 'members')
            need(all(m.get('subject') == user['id'] and m.get('role') == 'admin' for m in members) and len(members) <= 1, 'Unexpected native membership; rewriting refused')
            if not members:
                need(not args.check, 'Native ai-admin workspace membership is absent')
                run(['workspace', 'member', 'add', '--workspace', WORKSPACE, '--subject', user['id'], '--role', 'admin'], False)
                changed.append('admin-member-added')
            final = listed(['workspace', 'member', 'list', '--workspace', WORKSPACE], 'members')
            need(len(final) == 1 and final[0].get('subject') == user['id'] and final[0].get('role') == 'admin', 'Native membership readback differs')
            print(json.dumps({'workspace': WORKSPACE, 'namespace': WORKSPACE, 'administrator': 'ai-admin', 'native_role': 'admin', 'changes': changed, 'scope': 'configuration only; no agent deployment or inference'}))
    finally:
        forward.terminate()
        try: forward.wait(timeout=5)
        except subprocess.TimeoutExpired: forward.kill(); forward.wait(timeout=5)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        # Never include subprocess stderr, token-bearing request content or raw API objects.
        print('[FAIL] ' + (str(error) if isinstance(error, RuntimeError) else 'Bounded native setup did not complete'))
        raise SystemExit(1)
