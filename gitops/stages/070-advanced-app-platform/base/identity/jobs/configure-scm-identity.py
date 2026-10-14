"""Provision realm-scoped service identities; only this bootstrap receives master authority."""
import json
import os
import urllib.request
from secret_writer import write_secret

# Client roles remain restricted to platform, never the master or base sso realm.
CLIENTS = (
    ('stage070-scm-provisioner', 'gitlab-system', ('manage-clients', 'view-users')),
    ('stage070-rhdh-provisioner', 'rhdh', ('manage-clients',)),
    # The retained MTA setup assigns application roles to the two existing
    # personas, as well as configuring its client and realm client scopes.
    ('stage070-mta-provisioner', 'openshift-mta', ('manage-clients', 'manage-realm', 'view-realm', 'manage-users')),
    ('stage070-signing-provisioner', 'trusted-artifact-signer', ('manage-clients',)),
)


def configure(api, client_name, namespace, role_names, writer=write_secret):
    rows = api('GET', 'clients?clientId=' + client_name)
    if len(rows) > 1:
        raise ValueError('Duplicate platform service client')
    if rows and rows[0].get('attributes', {}).get('rhoai3.owner') != 'stage070':
        raise ValueError('Foreign platform service client')
    desired = {'clientId': client_name, 'enabled': True, 'protocol': 'openid-connect',
               'publicClient': False, 'serviceAccountsEnabled': True,
               'standardFlowEnabled': False, 'directAccessGrantsEnabled': False,
               'fullScopeAllowed': False, 'attributes': {'rhoai3.owner': 'stage070'}}
    if rows:
        api('PUT', 'clients/' + rows[0]['id'], {**rows[0], **desired})
    else:
        api('POST', 'clients', desired)
        rows = api('GET', 'clients?clientId=' + client_name)
    client = rows[0]['id']
    user = api('GET', 'clients/' + client + '/service-account-user')['id']
    management = api('GET', 'clients?clientId=realm-management')[0]['id']
    roles = [api('GET', 'clients/' + management + '/roles/' + name) for name in role_names]
    existing = api('GET', 'users/' + user + '/role-mappings/clients/' + management)
    if any(role['name'] not in role_names for role in existing):
        raise ValueError('Platform service has unexpected realm-management authority')
    api('POST', 'users/' + user + '/role-mappings/clients/' + management, roles)
    # Service-account roles and client scope intersect in the issued access token.
    api('POST', 'clients/' + client + '/scope-mappings/clients/' + management, roles)
    secret = api('GET', 'clients/' + client + '/client-secret')['value']
    writer({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {
        'name': client_name, 'namespace': namespace}, 'type': 'Opaque',
        'stringData': {'client_id': client_name, 'client_secret': secret}})


def main():
    base = os.environ['SCM_IDENTITY_URL'].rstrip('/')
    token = os.environ['SCM_ADMIN_TOKEN']
    def api(method, path, data=None):
        req = urllib.request.Request(base + '/admin/realms/platform/' + path,
            None if data is None else json.dumps(data).encode(),
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None
    for args in CLIENTS:
        configure(api, *args)
    print('Platform service clients configured; no master credential distributed')


if __name__ == '__main__':
    main()
