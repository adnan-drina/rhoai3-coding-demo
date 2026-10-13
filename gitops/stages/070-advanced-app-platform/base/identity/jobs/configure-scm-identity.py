"""Bootstrap a realm-scoped SCM client; downstream Jobs never receive master credentials."""
import base64
import json
import os
import subprocess
import urllib.request


def main():
    base = os.environ['SCM_IDENTITY_URL'].rstrip('/')
    token = os.environ['SCM_ADMIN_TOKEN']
    def api(method, path, data=None):
        req = urllib.request.Request(base + '/admin/realms/platform/' + path,
            None if data is None else json.dumps(data).encode(),
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read(); return json.loads(body) if body else None
    rows = api('GET', 'clients?clientId=stage070-scm-provisioner')
    if len(rows) > 1: raise ValueError('Duplicate SCM identity client')
    if rows and rows[0].get('attributes', {}).get('rhoai3.owner') != 'stage070':
        raise ValueError('Foreign SCM identity client')
    if not rows:
        api('POST', 'clients', {'clientId':'stage070-scm-provisioner','enabled':True,
            'protocol':'openid-connect','publicClient':False,'serviceAccountsEnabled':True,
            'standardFlowEnabled':False,'directAccessGrantsEnabled':False,
            'attributes':{'rhoai3.owner':'stage070'}})
        rows = api('GET', 'clients?clientId=stage070-scm-provisioner')
    client = rows[0]['id']
    user = api('GET', 'clients/' + client + '/service-account-user')['id']
    management = api('GET', 'clients?clientId=realm-management')[0]['id']
    desired = [api('GET', 'clients/' + management + '/roles/' + role)
               for role in ('manage-clients','view-users')]
    existing = api('GET', 'users/' + user + '/role-mappings/clients/' + management)
    if any(role['name'] not in ('manage-clients','view-users') for role in existing):
        raise ValueError('SCM identity has unexpected realm-management authority')
    api('POST', 'users/' + user + '/role-mappings/clients/' + management, desired)
    secret = api('GET', 'clients/' + client + '/client-secret')['value']
    document = {'apiVersion':'v1','kind':'Secret','metadata':{
        'name':'stage070-scm-provisioner','namespace':'gitlab-system'},'type':'Opaque',
        'stringData':{'client_id':'stage070-scm-provisioner','client_secret':secret}}
    subprocess.run(['oc','apply','-f','-'], input=json.dumps(document), universal_newlines=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print('SCM realm client configured with manage-clients/view-users; no master credential distributed')


if __name__ == '__main__': main()
