"""Resolve the existing realm's issuer; never replace signing keys or roots."""
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode


def oc(*args):
    return json.loads(subprocess.check_output(['oc', *args], universal_newlines=True))


def issuer_configuration(host):
    if not host or '/' in host or '\n' in host:
        raise ValueError('Invalid platform identity Route host')
    issuer = 'https://' + host + '/realms/platform'
    return [{'clientID': 'trusted-artifact-signer', 'issuer': issuer,
             'issuerURL': issuer, 'type': 'email'}]


def client_configuration():
    # Keycloak normalizes native HTTP loopback ports to 80 for comparison.
    # A wildcard inside the port is not a supported redirect pattern.
    return {'clientId': 'trusted-artifact-signer', 'enabled': True, 'protocol': 'openid-connect',
        'publicClient': True, 'standardFlowEnabled': True, 'directAccessGrantsEnabled': False,
        'serviceAccountsEnabled': False,
        'redirectUris': ['http://localhost/auth/callback', 'http://localhost:80/auth/callback'],
        'attributes': {'pkce.code.challenge.method': 'S256'}}


def main():
    host = oc('get', 'route', 'keycloak', '-n', 'keycloak', '-o', 'json')['spec']['host']
    base = 'https://' + host
    admin = oc('get', 'secret', 'keycloak-initial-admin', '-n', 'keycloak', '-o', 'json')['data']
    credentials = {key: base64.b64decode(admin[key]).decode() for key in ('username', 'password')}
    request = urllib.request.Request(base + '/realms/master/protocol/openid-connect/token',
        urlencode({'grant_type': 'password', 'client_id': 'admin-cli', **credentials}).encode(),
        {'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response: token = json.load(response)['access_token']

    def api(method, path, payload=None):
        request = urllib.request.Request(base + '/admin/realms/platform/' + path,
            None if payload is None else json.dumps(payload).encode(),
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(); return json.loads(body) if body else None

    clients = api('GET', 'clients?clientId=trusted-artifact-signer')
    if len(clients) > 1: raise RuntimeError('Duplicate signing client')
    desired = client_configuration()
    if clients: api('PUT', 'clients/' + clients[0]['id'], {**clients[0], **desired})
    else: api('POST', 'clients', desired)
    # The native CR and this hook share a wave. Wait only for CR creation;
    # waiting for its Ready condition would depend on the issuer we are setting.
    for _ in range(30):
        try:
            oc('get', 'securesign', 'platform', '-n', 'trusted-artifact-signer', '-o', 'json')
            break
        except subprocess.CalledProcessError: time.sleep(2)
    else: raise RuntimeError('Native signing resource was not created')
    patch = {'spec': {'fulcio': {'config': {'oidcIssuers': issuer_configuration(host)}}}}
    oc('patch', 'securesign', 'platform', '-n', 'trusted-artifact-signer', '--type=merge',
       '-p', json.dumps(patch), '-o', 'json')
    print('Signing issuer configured; root material retained. Signature verification still required.')


if __name__ == '__main__': main()
