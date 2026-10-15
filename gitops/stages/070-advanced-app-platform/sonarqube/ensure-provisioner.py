"""Give the platform its own SonarQube technical user instead of the administrator's token.

The pipeline reconciler creates projects and mints per-project analysis tokens with the control credential in
app-platform-build/sonarqube-credentials. That credential belongs to the local user platform-provisioner, which holds
only the global "Create Projects" and "Execute Analysis" permissions (SonarQube's least-privilege guidance for CI
integrations). An existing valid token of that user is reused; otherwise a new one is minted, stored, and the previous
control token is revoked. Never prints a credential.

  python3 ensure-provisioner.py ADMIN_PASSWORD_ENV
"""
import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import secret_writer  # noqa: E402

BASE = 'http://sonarqube.sonarqube.svc:9000'
LOGIN = 'platform-provisioner'
PERMISSIONS = ('provisioning', 'scan')
NAMESPACE, SECRET = 'app-platform-build', 'sonarqube-credentials'
OWNER = 'rhoai3.io/control-token-owner'
NAME = 'rhoai3.io/control-token-name'


def call(path, user, data=None, method=None, body_json=None):
    auth = base64.b64encode((user + ':').encode() if ':' not in user else user.encode()).decode()
    headers = {'Authorization': 'Basic ' + auth}
    payload = None
    if body_json is not None:
        payload, headers['Content-Type'] = json.dumps(body_json).encode(), 'application/json'
    elif data is not None:
        payload = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, payload, headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        return error.code, None


def ensure_user(admin):
    code, found = call('/api/v2/users-management/users?' + urllib.parse.urlencode({'q': LOGIN}), admin)
    if code != 200:
        raise RuntimeError('SonarQube user search HTTP %s' % code)
    if not any(u['login'] == LOGIN for u in found['users']):
        # A local account nobody signs in to: the password is random and discarded; access is by token only.
        password = 'Aa1!' + secrets.token_urlsafe(24)
        code, _ = call('/api/v2/users-management/users', admin, body_json={
            'login': LOGIN, 'name': 'Platform provisioner (pipelines)', 'password': password, 'local': True})
        if code not in (200, 201):
            raise RuntimeError('SonarQube user creation HTTP %s' % code)
        print('Created technical user ' + LOGIN)
    for permission in PERMISSIONS:
        code, _ = call('/api/permissions/add_user', admin, {'login': LOGIN, 'permission': permission})
        if code not in (200, 204):
            raise RuntimeError('SonarQube permission %s HTTP %s' % (permission, code))


def token_names(admin, login):
    code, found = call('/api/user_tokens/search?' + urllib.parse.urlencode({'login': login}), admin)
    if code != 200:
        raise RuntimeError('SonarQube token search HTTP %s' % code)
    return {t['name'] for t in found['userTokens']}


def stored():
    try:
        secret = secret_writer.oc('get', 'secret', SECRET, '-n', NAMESPACE, '-o', 'json')
    except Exception:
        return {}, {}
    data = {k: base64.b64decode(v).decode() for k, v in secret.get('data', {}).items()}
    return data, secret['metadata'].get('annotations', {})


def main():
    admin = 'admin:' + os.environ[sys.argv[1]]
    ensure_user(admin)
    data, annotations = stored()
    current = annotations.get(NAME, 'platform-pipeline')
    owner = annotations.get(OWNER, 'admin')
    if (owner == LOGIN and data.get('token') and current in token_names(admin, LOGIN)
            and (call('/api/authentication/validate', data['token'])[1] or {}).get('valid')):
        print('Reusing the valid ' + LOGIN + ' control token')
        return
    name = 'platform-pipeline-' + secrets.token_hex(6)
    code, token = call('/api/user_tokens/generate', admin, {'login': LOGIN, 'name': name, 'type': 'USER_TOKEN'})
    if code != 200 or not (token or {}).get('token'):
        raise RuntimeError('SonarQube token generation HTTP %s' % code)
    secret_writer.write_secret({'apiVersion': 'v1', 'kind': 'Secret', 'type': 'Opaque',
        'metadata': {'name': SECRET, 'namespace': NAMESPACE, 'annotations': {OWNER: LOGIN, NAME: name}},
        'stringData': {'host': BASE, 'token': token['token']}})
    # The previous control token (the administrator's before this change) stops working once replaced.
    if current in token_names(admin, owner):
        call('/api/user_tokens/revoke', admin, {'login': owner, 'name': current})
    print('Control token of ' + LOGIN + ' stored in ' + NAMESPACE + '/' + SECRET + '; previous token revoked')


if __name__ == '__main__':
    main()
