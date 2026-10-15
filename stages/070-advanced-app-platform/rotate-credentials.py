"""Explicit operator rotation; never called by routine reconciliation or a worker."""
import argparse
import base64
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROVISIONER = 'platform-provisioner'
SONAR_KEY, SONAR_TYPE, SONAR_NAME = 'rhoai3.io/sonar-project-key', 'rhoai3.io/sonar-token-type', 'rhoai3.io/sonar-token-name'
BASE = ROOT / 'gitops/stages/070-advanced-app-platform'
sys.path.insert(0, str(BASE / '070-pipelines/gitlab'))
from secret_writer import write_secret
sys.path.insert(0, str(ROOT / 'scripts/shared'))
import stage_apps


def command(*args):
    return subprocess.check_output(args, universal_newlines=True, stderr=subprocess.PIPE, timeout=600).strip()


def oc(*args):
    return json.loads(command('oc', '--request-timeout=30s', *args, '-o', 'json'))


def data(namespace, name):
    value = oc('get', 'secret', name, '-n', namespace)
    return value, {k: base64.b64decode(v).decode() for k, v in value.get('data', {}).items()}


def update(namespace, name, values):
    # Only named keys change; unrelated values and identity metadata survive.
    write_secret({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': name, 'namespace': namespace}, 'stringData': values})


def request(base, method, path, payload=None, headers=None, form=False):
    body = None if payload is None else (urllib.parse.urlencode(payload).encode() if form else json.dumps(payload).encode())
    headers = dict(headers or {})
    headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    req = urllib.request.Request(base + path, body, headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def rejected(action, statuses=(400, 401, 403)):
    try:
        action()
    except urllib.error.HTTPError as error:
        if error.code in statuses:
            return True
        raise
    return False


def token_claims(token):
    payload = token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))


def remove_annotation(identifier):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9.-]*', identifier or ''):
        raise ValueError('Annotation cleanup requires one exact namespace/Secret name')
    namespace, name = identifier.split('/')
    before = oc('get', 'secret', name, '-n', namespace)
    # A metadata-only merge removes the extra copy without touching any value,
    # including encryption material that must not be rotated by a generic tool.
    write_secret({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': name, 'namespace': namespace}})
    after = oc('get', 'secret', name, '-n', namespace)
    return {'secret_identity_preserved': before['metadata']['uid'] == after['metadata']['uid'],
            'data_and_type_preserved': before.get('data') == after.get('data') and before.get('type') == after.get('type'),
            'annotation_removed': 'kubectl.kubernetes.io/last-applied-configuration' not in after['metadata'].get('annotations', {})}


class Rotation:
    def __init__(self):
        self.sso = 'https://' + oc('get', 'route', 'keycloak', '-n', 'keycloak')['spec']['host']
        self.gitlab = 'https://' + oc('get', 'route', 'gitlab', '-n', 'gitlab-system')['spec']['host']
        _, admin = data('keycloak', 'keycloak-initial-admin')
        self.master = request(self.sso, 'POST', '/realms/master/protocol/openid-connect/token',
            dict(grant_type='password', client_id='admin-cli', **admin), form=True)['access_token']
        self.gitlab_token = None

    def keycloak(self, method, path, payload=None):
        return request(self.sso, method, '/admin/realms/platform/' + path, payload,
                       {'Authorization': 'Bearer ' + self.master})

    def root_api(self, method, path, payload=None):
        if self.gitlab_token is None:
            pods = oc('get', 'pods', '-n', 'gitlab-system', '-l', 'app=toolbox,release=gitlab')['items']
            ready = [p for p in pods if any(c.get('type') == 'Ready' and c.get('status') == 'True'
                     for c in p.get('status', {}).get('conditions', []))]
            if len(ready) != 1:
                raise ValueError('Expected one Ready trusted GitLab toolbox')
            ruby = "u=User.find_by_username!('root'); t=u.personal_access_tokens.create!(name:'stage070-reviewed-rotation',scopes:['api'],expires_at:1.day.from_now); puts t.token"
            self.gitlab_token = command('oc', 'exec', '-n', 'gitlab-system', ready[0]['metadata']['name'],
                                       '-c', 'toolbox', '--', 'gitlab-rails', 'runner', ruby).splitlines()[-1]
            if not self.gitlab_token.startswith('glpat-'):
                raise ValueError('GitLab did not produce its temporary operator token')
        return request(self.gitlab, method, '/api/v4/' + path, payload, {'PRIVATE-TOKEN': self.gitlab_token})

    def close(self):
        if self.gitlab_token:
            self.root_api('DELETE', 'personal_access_tokens/self')
            self.gitlab_token = None

    def client(self, client_name):
        rows = self.keycloak('GET', 'clients?clientId=' + client_name)
        if len(rows) != 1 or rows[0].get('clientId') != client_name:
            raise ValueError('Keycloak client identity is ambiguous')
        return rows[0]['id']

    def rotate_client(self, client_name, persist):
        client = self.client(client_name)
        old = self.keycloak('GET', 'clients/' + client + '/client-secret')['value']
        new = self.keycloak('POST', 'clients/' + client + '/client-secret')['value']
        if new == old:
            raise ValueError('Keycloak did not replace the credential')
        persist(new)
        try:
            self.keycloak('DELETE', 'clients/' + client + '/client-secret/rotated')
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        denied = rejected(lambda: request(self.sso, 'POST', '/realms/platform/protocol/openid-connect/token',
            {'grant_type': 'client_credentials', 'client_id': client_name, 'client_secret': old}, form=True))
        # Browser-only clients reject this grant even with a good secret. Their
        # old credential proof is the server's current/rotated-secret read-back.
        current = self.keycloak('GET', 'clients/' + client + '/client-secret')['value']
        return {'client_id_preserved': self.client(client_name) == client,
                'new_current_secret_matches': current == new, 'old_secret_not_current': current != old,
                'old_client_credentials_grant_refused': denied}

    def gitlab_oidc(self):
        _, stored = data('gitlab-system', 'gitlab-oidc')
        provider = json.loads(stored['provider'])
        if provider['args']['client_options']['identifier'] != 'gitlab' or provider['args']['issuer'] != self.sso + '/realms/platform':
            raise ValueError('GitLab provider is not bound to the retained platform issuer')
        def persist(secret):
            provider['args']['client_options']['secret'] = secret
            update('gitlab-system', 'gitlab-oidc', {'provider': json.dumps(provider)})
        proof = self.rotate_client('gitlab', persist)
        command('oc', 'rollout', 'restart', 'deployment/gitlab-webservice-default', '-n', 'gitlab-system')
        command('oc', 'rollout', 'status', 'deployment/gitlab-webservice-default', '-n', 'gitlab-system', '--timeout=300s')
        return proof

    def scm_client(self):
        return self.rotate_client('stage070-scm-provisioner', lambda secret:
            update('gitlab-system', 'stage070-scm-provisioner', {'client_secret': secret}))

    def publisher(self):
        _, stored = data('rhdh', 'gitlab-publisher'); old = stored['token']
        old_headers = {'PRIVATE-TOKEN': old}
        previous = request(self.gitlab, 'GET', '/api/v4/personal_access_tokens/self', headers=old_headers)
        user = self.root_api('GET', 'users/' + str(previous['user_id']))
        if user['username'] != 'rhdh-publisher':
            raise ValueError('Publisher token belongs to another account')
        # Create and persist a replacement before revoking the predecessor.
        new = self.root_api('POST', 'users/%s/personal_access_tokens' % user['id'], {
            'name': 'stage070-publisher-rotation-' + uuid.uuid4().hex[:12],
            'scopes': previous['scopes'], 'expires_at': previous['expires_at']})
        if (set(new['scopes']) != set(previous['scopes']) or new['user_id'] != previous['user_id']
                or new['expires_at'] != previous['expires_at']):
            raise ValueError('Publisher replacement changed authority')
        update('rhdh', 'gitlab-publisher', {'token': new['token']})
        update('rhdh', 'rhdh-gitlab', {'GITLAB_PUBLISHER_TOKEN': new['token']})
        request(self.gitlab, 'GET', '/api/v4/personal_access_tokens/self', headers={'PRIVATE-TOKEN': new['token']})
        self.root_api('DELETE', 'personal_access_tokens/' + str(previous['id']))
        return {'identity_scopes_expiry_preserved': new['expires_at'] == previous['expires_at'],
                'old_token_refused': rejected(lambda: request(self.gitlab, 'GET', '/api/v4/personal_access_tokens/self', headers=old_headers))}

    def devspaces_oauth(self):
        _, old = data('openshift-devspaces', 'gitlab-oauth-config')
        rows = [a for a in self.root_api('GET', 'applications') if a['application_id'] == old['id']]
        if len(rows) != 1 or rows[0]['application_name'] != 'Dev Spaces':
            raise ValueError('Dev Spaces OAuth application identity mismatch')
        previous = rows[0]
        new = self.root_api('POST', 'applications/%s/renew-secret' % rows[0]['id'])
        # GitLab returns application_name/callback_url, unlike request fields.
        # https://docs.gitlab.com/api/applications/#renew-an-application-secret
        identity = ('id', 'application_id', 'application_name', 'callback_url', 'confidential')
        if (any(new[k] != previous[k] for k in identity)
                or set(new['scopes']) != set(previous['scopes'])
                or not new.get('secret') or new['secret'] == old['secret']):
            raise ValueError('OAuth renewal changed authority or retained the old secret')
        update('openshift-devspaces', 'gitlab-oauth-config', {'secret': new['secret']})
        # invalid_grant proves client authentication; invalid_client rejects it.
        def auth(secret):
            try:
                request(self.gitlab, 'POST', '/oauth/token', {'grant_type': 'authorization_code',
                    'client_id': old['id'], 'client_secret': secret, 'code': 'stage070-invalid-code',
                    'redirect_uri': previous['callback_url']}, form=True)
            except urllib.error.HTTPError as error:
                return json.loads(error.read()).get('error')
            raise ValueError('An intentionally invalid authorization code was accepted')
        return {'application_authority_preserved': True, 'old_secret_refused': auth(old['secret']) == 'invalid_client',
                'new_secret_authenticates': auth(new['secret']) == 'invalid_grant'}

    def sonar(self):
        _, admin = data('sonarqube', 'sonarqube-admin')
        _, old = data('app-platform-build', 'sonarqube-credentials')
        # Pipeline host stays cluster-local; this operator tool runs externally.
        host = 'https://' + oc('get', 'route', 'sonarqube', '-n', 'sonarqube')['spec']['host']
        password = admin.get('password') or admin.get('admin-password')
        if not password:
            raise ValueError('Sonar administrator secret schema mismatch')
        auth = {'Authorization': 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()}
        old_secret = oc('get', 'secret', 'sonarqube-credentials', '-n', 'app-platform-build')
        annotations = old_secret['metadata'].get('annotations', {})
        previous_name = annotations.get('rhoai3.io/control-token-name', 'platform-pipeline')
        previous_owner = annotations.get('rhoai3.io/control-token-owner', 'admin')
        # The control credential belongs to the technical user the configure-sonarqube hook creates.
        name = 'platform-pipeline-rotation-' + uuid.uuid4().hex[:12]
        new = request(host, 'POST', '/api/user_tokens/generate',
                      {'login': PROVISIONER, 'name': name, 'type': 'USER_TOKEN'}, auth, form=True)
        update('app-platform-build', 'sonarqube-credentials', {'token': new['token']})
        patch = {'metadata': {'annotations': {'rhoai3.io/control-token-name': name,
                                              'rhoai3.io/control-token-owner': PROVISIONER}}}
        subprocess.run(['oc', 'patch', 'secret', 'sonarqube-credentials', '-n', 'app-platform-build',
            '--type=merge', '--patch-file=/dev/stdin'], input=json.dumps(patch), universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        request(host, 'POST', '/api/user_tokens/revoke', {'login': previous_owner, 'name': previous_name}, auth, form=True)
        def valid(token):
            headers = {'Authorization': 'Basic ' + base64.b64encode((token + ':').encode()).decode()}
            return request(host, 'GET', '/api/authentication/validate', headers=headers).get('valid')
        return {'old_token_refused': not valid(old['token']), 'new_token_valid': valid(new['token'])}

    def sonar_projects(self):
        """Re-mint each enrolled project's analysis token under the provisioner user, update its Secret and the
        workspace mirrors, then revoke the administrator's token of the same name."""
        _, admin = data('sonarqube', 'sonarqube-admin')
        host = 'https://' + oc('get', 'route', 'sonarqube', '-n', 'sonarqube')['spec']['host']
        auth = {'Authorization': 'Basic ' + base64.b64encode(('admin:' + admin['password']).encode()).decode()}
        # SonarQube mints a project analysis token only for the calling user: authenticate as the provisioner.
        _, control = data('app-platform-build', 'sonarqube-credentials')
        provisioner = {'Authorization': 'Basic ' + base64.b64encode((control['token'] + ':').encode()).decode()}
        def tokens(login):
            return {t['name']: t for t in request(host, 'GET', '/api/user_tokens/search?' + urllib.parse.urlencode({'login': login}),
                                                  headers=auth)['userTokens']}
        def valid(token):
            headers = {'Authorization': 'Basic ' + base64.b64encode((token + ':').encode()).decode()}
            return request(host, 'GET', '/api/authentication/validate', headers=headers).get('valid')
        admin_tokens, checks = tokens('admin'), {}
        stored = [s for s in oc('get', 'secret', '-A', '--field-selector', 'metadata.name=sonarqube-credentials')['items']
                  if s['metadata'].get('annotations', {}).get(SONAR_TYPE) == 'PROJECT_ANALYSIS_TOKEN']
        mirrors = [s for ns in ('wksp-ai-developer', 'wksp-ai-admin') for s in oc('get', 'secret', '-n', ns)['items']
                   if s['metadata']['name'].endswith('-sonar-credentials')]
        for secret in stored:
            meta = secret['metadata']; key, name = meta['annotations'][SONAR_KEY], meta['annotations'][SONAR_NAME]
            old = base64.b64decode(secret['data']['token']).decode()
            if name not in admin_tokens:
                checks[meta['namespace'] + '_already_migrated'] = name in tokens(PROVISIONER) and bool(valid(old))
                continue
            new = request(host, 'POST', '/api/user_tokens/generate', {'name': name,
                          'type': 'PROJECT_ANALYSIS_TOKEN', 'projectKey': key}, provisioner, form=True)
            if new.get('type') != 'PROJECT_ANALYSIS_TOKEN' or not new.get('token'):
                raise ValueError('SonarQube did not emit a project analysis token')
            update(meta['namespace'], 'sonarqube-credentials', {'token': new['token']})
            for mirror in mirrors:
                if mirror['metadata'].get('annotations', {}).get(SONAR_KEY) == key:
                    update(mirror['metadata']['namespace'], mirror['metadata']['name'], {'SONAR_TOKEN': new['token']})
            request(host, 'POST', '/api/user_tokens/revoke', {'login': 'admin', 'name': name}, auth, form=True)
            checks[meta['namespace'] + '_new_valid'] = bool(valid(new['token']))
            checks[meta['namespace'] + '_old_refused'] = not valid(old)
        checks['no_admin_project_tokens_left'] = not [t for t in tokens('admin').values() if t.get('type') == 'PROJECT_ANALYSIS_TOKEN']
        return checks

    def argo(self):
        """The OpenShift GitOps operator owns the rhdh local user's token (Secret rhdh-local-user, key apiToken);
        deleting the Secret makes it issue a new one. Developer Hub's copy then follows."""
        base = 'https://' + oc('get', 'route', 'openshift-gitops-server', '-n', 'openshift-gitops')['spec']['host']
        before, old = data('openshift-gitops', 'rhdh-local-user')
        claims = token_claims(old['apiToken'])
        if claims.get('sub') != 'rhdh:apiKey' or claims.get('iss') != 'argocd':
            raise ValueError('Argo credential is not the expected reader account')
        command('oc', 'delete', 'secret', 'rhdh-local-user', '-n', 'openshift-gitops', '--wait=true')
        for _ in range(60):
            try:
                after, new = data('openshift-gitops', 'rhdh-local-user')
                if after['metadata']['uid'] != before['metadata']['uid'] and new.get('apiToken'):
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(5)
        else:
            raise ValueError('The GitOps operator did not issue a new reader token')
        replacement = token_claims(new['apiToken'])
        if replacement.get('sub') != claims['sub'] or replacement.get('jti') == claims.get('jti'):
            raise ValueError('Argo replacement changed reader identity or kept the old token')
        def works(token):
            return isinstance(request(base, 'GET', '/api/v1/applications', headers={'Authorization': 'Bearer ' + token}), dict)
        valid = works(new['apiToken'])
        update('rhdh', 'rhdh-secrets', {'RHDH_ARGOCD_TOKEN': new['apiToken']})
        return {'reader_identity_preserved': True, 'new_reader_valid': valid,
                'old_reader_refused': rejected(lambda: works(old['apiToken']))}

    def delivery_writers(self):
        """Renew every project's gitlab-delivery-writer token with GitLab's self-rotation (the token rotates itself;
        no administrator token). The bot user of a project access token is a member of exactly its own project."""
        checks = {}
        for secret in oc('get', 'secret', '-A', '--field-selector', 'metadata.name=gitlab-delivery-writer')['items']:
            ns = secret['metadata']['namespace']
            old = base64.b64decode(secret['data']['token']).decode()
            headers = {'PRIVATE-TOKEN': old}
            projects = request(self.gitlab, 'GET', '/api/v4/projects?membership=true&simple=true', headers=headers)
            if len(projects) != 1:
                raise ValueError('Delivery writer token is not bound to exactly one project')
            expiry = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
            new = request(self.gitlab, 'POST', '/api/v4/projects/%s/access_tokens/self/rotate' % projects[0]['id'],
                          {'expires_at': expiry}, headers)
            if not new.get('token') or new.get('expires_at') != expiry:
                raise ValueError('GitLab did not rotate the delivery writer token')
            update(ns, 'gitlab-delivery-writer', {'token': new['token'], 'expires_at': expiry})
            def works(token):
                return isinstance(request(self.gitlab, 'GET', '/api/v4/personal_access_tokens/self',
                                          headers={'PRIVATE-TOKEN': token}), dict)
            checks[ns + '_new_valid'] = works(new['token'])
            checks[ns + '_old_refused'] = rejected(lambda: works(old))
        return checks

    def mta(self):
        gateway = oc('get', 'gateway.gateway.networking.k8s.io', 'maas-default-gateway', '-n', 'openshift-ingress')
        hosts = [x['hostname'] for x in gateway['spec']['listeners'] if x.get('hostname', '').startswith('maas.')]
        if len(hosts) != 1:
            raise ValueError('Expected one MaaS API listener')
        base = 'https://' + hosts[0]
        bearer = command('oc', 'create', 'token', 'mta-maas-provisioner', '-n', 'openshift-mta', '--duration=10m')
        headers = {'Authorization': 'Bearer ' + bearer}
        _, old = data('openshift-mta', 'kai-api-keys')
        prefix = '/maas-api/v1/api-keys'
        previous = request(base, 'GET', prefix + '/' + old['MAAS_KEY_ID'], headers=headers)
        principal = 'system:serviceaccount:openshift-mta:mta-maas-provisioner'
        if previous.get('username') != principal or previous.get('subscription') != 'mta-migration-ai':
            raise ValueError('Foreign MaaS predecessor')
        new = request(base, 'POST', prefix, {'name': 'mta-reviewed-rotation', 'subscription': previous['subscription']}, headers)
        update('openshift-mta', 'kai-api-keys', {'OPENAI_API_KEY': new['key'], 'MAAS_KEY_ID': new['id']})
        request(base, 'DELETE', prefix + '/' + old['MAAS_KEY_ID'], headers=headers)
        try:
            revoked = request(base, 'GET', prefix + '/' + old['MAAS_KEY_ID'], headers=headers)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            revoked = {'status': 'revoked'}
        current = request(base, 'GET', prefix + '/' + new['id'], headers=headers)
        return {'owner_and_subscription_preserved': current.get('username') == principal and current.get('subscription') == previous['subscription'],
                'old_key_revoked': revoked.get('status') == 'revoked', 'new_key_active': current.get('status') == 'active', 'inference_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['gitlab_oidc', 'scm_client', 'publisher', 'devspaces_oauth', 'sonar', 'sonar_projects', 'delivery_writers', 'argo', 'mta', 'annotation_copy'], required=True)
    parser.add_argument('--secret', help='One exact namespace/name, only for annotation_copy')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--repo-url', required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if bool(args.secret) != (args.component == 'annotation_copy'):
        parser.error('--secret is required only for annotation_copy')
    expected = os.environ.get('RHOAI_EXPECTED_API_SERVER')
    if not expected or expected not in command('oc', 'whoami', '--show-server'):
        raise ValueError('Load the project environment and verify its API server before rotation')
    # Refuse a locally modified maintenance implementation or a different
    # publication, just as deployment refuses unpublished/dirty stage content.
    if stage_apps.select_revision('070', args.revision, args.repo_url) != args.revision:
        raise ValueError('Use the reviewed published correction revision')
    if stage_apps.stage_problems('070', args.revision, args.repo_url):
        raise ValueError('Deploy and qualify the corrected pinned stage before rotation')
    if not args.execute:
        raise ValueError('Rotation requires the explicit --execute flag')
    if args.report.exists():
        raise ValueError('Preserve the existing rotation report; do not silently rotate twice')
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'component': args.component,
              'revision': args.revision, 'passed': False, 'phase': 'starting'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    rotation = None
    try:
        if args.component == 'annotation_copy':
            result['checks'] = remove_annotation(args.secret)
        else:
            rotation = Rotation()
            result['checks'] = getattr(rotation, args.component)()
        result['passed'] = all(v for k, v in result['checks'].items() if k != 'inference_performed')
        result['phase'] = 'verified' if result['passed'] else 'verification_failed'
    finally:
        try:
            if rotation:
                rotation.close()
        finally:
            args.report.write_text(json.dumps(result, indent=2) + '\n')
            args.report.chmod(0o600)
    if not result['passed']:
        raise ValueError('Credential rotation is not verified; preserve the report and investigate')
    print('PASS: ' + args.component + ' replacement and predecessor checks; no inference')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # API responses, process arguments and credentials must not reach logs.
        sys.exit('Rotation stopped: ' + type(error).__name__ + '; credential payloads redacted')
