"""Configure GitLab's OIDC client in the existing Stage 070 platform realm."""
import base64
import json
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlencode, quote


def oc(*args, document=None):
    result = subprocess.run(['oc', *args], input=None if document is None else json.dumps(document),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
    return json.loads(result.stdout)


def provider(issuer, host, client_secret):
    if not issuer.startswith('https://') or not host or '/' in host:
        raise ValueError('GitLab OIDC requires reviewed HTTPS issuer and Route host')
    return {'name': 'openid_connect', 'label': 'OpenShift', 'args': {
        'name': 'openid_connect', 'scope': ['openid', 'profile', 'email'],
        'response_type': 'code', 'issuer': issuer, 'discovery': True,
        'client_auth_method': 'query', 'uid_field': 'sub',
        'client_options': {'identifier': 'gitlab', 'secret': client_secret,
                           'redirect_uri': 'https://' + host + '/users/auth/openid_connect/callback'}}}


def main():
    sso_host = oc('get', 'route', 'keycloak', '-n', 'keycloak', '-o', 'json')['spec']['host']
    gitlab_host = oc('get', 'route', 'gitlab', '-n', 'gitlab-system', '-o', 'json')['spec']['host']
    admin = oc('get', 'secret', 'stage070-scm-provisioner', '-n', 'gitlab-system', '-o', 'json')['data']
    credentials = {key: base64.b64decode(admin[key]).decode() for key in ('client_id', 'client_secret')}
    base = 'https://' + sso_host
    req = urllib.request.Request(base + '/realms/platform/protocol/openid-connect/token',
        urlencode({'grant_type': 'client_credentials', **credentials}).encode(),
        {'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as response: token = json.load(response)['access_token']

    def request(method, path, payload=None):
        req = urllib.request.Request(base + '/admin/realms/platform/' + path,
            None if payload is None else json.dumps(payload).encode(),
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read(); return json.loads(body) if body else None

    clients = request('GET', 'clients?clientId=gitlab')
    if len(clients) > 1: raise RuntimeError('Duplicate GitLab OIDC client')
    desired = {'clientId': 'gitlab', 'enabled': True, 'protocol': 'openid-connect',
               'publicClient': False, 'standardFlowEnabled': True,
               'directAccessGrantsEnabled': False, 'serviceAccountsEnabled': False,
               'redirectUris': ['https://' + gitlab_host + '/users/auth/openid_connect/callback'],
               'webOrigins': ['https://' + gitlab_host]}
    if clients:
        client_id = clients[0]['id']; request('PUT', 'clients/' + client_id, {**clients[0], **desired})
    else:
        request('POST', 'clients', desired)
        client_id = request('GET', 'clients?clientId=gitlab')[0]['id']
    client_secret = request('GET', 'clients/' + client_id + '/client-secret')['value']
    document = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': 'gitlab-oidc', 'namespace': 'gitlab-system'}, 'type': 'Opaque',
        'stringData': {'provider': json.dumps(provider(base + '/realms/platform', gitlab_host, client_secret))}}
    oc('apply', '-f', '-', '-o', 'json', document=document)
    print('GitLab OIDC client and scoped provider Secret configured')


if __name__ == '__main__': main()
